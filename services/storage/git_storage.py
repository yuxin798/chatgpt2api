from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path
from threading import RLock
from typing import Any
from urllib.parse import quote

from git import Repo
from git.exc import GitCommandError

from services.storage.base import StorageBackend


class GitStorageBackend(StorageBackend):
    """Git 私有仓库存储后端"""

    def __init__(
        self,
        repo_url: str,
        token: str,
        branch: str = "main",
        file_path: str = "accounts.json",
        auth_keys_file_path: str = "auth_keys.json",
        local_cache_dir: Path | None = None,
        auth_username: str = "x-access-token",
        commit_user_name: str = "chatgpt2api",
        commit_user_email: str = "chatgpt2api@users.noreply.github.com",
    ):
        self.repo_url = repo_url
        self.token = token
        self.branch = branch
        self.file_path = file_path
        self.auth_keys_file_path = auth_keys_file_path
        self.auth_username = auth_username.strip() or "x-access-token"
        self.commit_user_name = commit_user_name.strip() or "chatgpt2api"
        self.commit_user_email = commit_user_email.strip() or "chatgpt2api@users.noreply.github.com"
        self._lock = RLock()
        
        # 本地缓存目录
        if local_cache_dir is None:
            local_cache_dir = Path(tempfile.gettempdir()) / "chatgpt2api_git_cache"
        self.local_cache_dir = local_cache_dir
        self.local_cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 构建带认证的 Git URL
        self.auth_repo_url = self._build_auth_url(repo_url, token, self.auth_username)

    @staticmethod
    def _build_auth_url(repo_url: str, token: str, username: str = "x-access-token") -> str:
        """构建带认证的 Git URL"""
        if not token:
            return repo_url
        safe_token = quote(token, safe="")
        safe_username = quote(username or "x-access-token", safe="")
        
        # 支持 HTTPS 格式：https://github.com/user/repo.git
        if repo_url.startswith("https://"):
            netloc = repo_url.split("://", 1)[1].split("/", 1)[0]
            if "@" in netloc:
                return repo_url
            return repo_url.replace("https://", f"https://{safe_username}:{safe_token}@")
        
        # 支持 git@ 格式：git@github.com:user/repo.git
        # 转换为 HTTPS 格式
        if repo_url.startswith("git@"):
            repo_url = repo_url.replace("git@", "https://")
            repo_url = repo_url.replace(".com:", ".com/")
            return repo_url.replace("https://", f"https://{safe_username}:{safe_token}@")
        
        return repo_url

    def _configure_repo(self, repo: Repo) -> Repo:
        repo.git.config("user.name", self.commit_user_name)
        repo.git.config("user.email", self.commit_user_email)
        try:
            repo.remote("origin").set_url(self.auth_repo_url)
        except Exception:
            pass
        return repo

    def _drop_cache(self) -> None:
        repo_path = self.local_cache_dir / "repo"
        if repo_path.exists():
            shutil.rmtree(repo_path)

    @staticmethod
    def _is_missing_branch_error(error: GitCommandError) -> bool:
        text = str(error).lower()
        return (
            ("remote branch" in text and "not found" in text)
            or "couldn't find remote ref" in text
            or "could not find remote ref" in text
        )

    @staticmethod
    def _last_commit(repo: Repo) -> str | None:
        try:
            return repo.head.commit.hexsha[:8]
        except Exception:
            return None

    def _checkout_configured_branch(self, repo: Repo) -> Repo:
        repo = self._configure_repo(repo)
        try:
            repo.git.checkout(self.branch)
            return repo
        except GitCommandError:
            pass
        try:
            repo.git.checkout("-B", self.branch)
        except GitCommandError:
            repo.git.checkout("--orphan", self.branch)
        return repo

    def _clone_missing_branch_repo(self, repo_path: Path) -> Repo:
        repo = Repo.clone_from(self.auth_repo_url, repo_path)
        return self._checkout_configured_branch(repo)

    def _clone_or_pull(self) -> Repo:
        """克隆或拉取仓库"""
        repo_path = self.local_cache_dir / "repo"
        
        if repo_path.exists() and (repo_path / ".git").exists():
            # 仓库已存在，拉取最新代码
            try:
                repo = self._configure_repo(Repo(repo_path))
                repo.git.pull("--rebase", "origin", self.branch)
                return self._checkout_configured_branch(repo)
            except GitCommandError as exc:
                if self._is_missing_branch_error(exc):
                    return self._checkout_configured_branch(repo)
                # 拉取失败，删除重新克隆
                self._drop_cache()
        
        # 克隆仓库
        try:
            repo = Repo.clone_from(
                self.auth_repo_url,
                repo_path,
                branch=self.branch,
            )
            return self._configure_repo(repo)
        except GitCommandError as exc:
            if not self._is_missing_branch_error(exc):
                raise
            self._drop_cache()
            return self._clone_missing_branch_repo(repo_path)

    def load_accounts(self) -> list[dict[str, Any]]:
        """从 Git 仓库加载账号数据"""
        try:
            return self._load_json_file(self.file_path)
        except Exception as e:
            message = self._mask_error(e)
            print(f"[git-storage] load failed: {message}")
            raise RuntimeError(message) from e

    def save_accounts(self, accounts: list[dict[str, Any]]) -> None:
        """保存账号数据到 Git 仓库"""
        try:
            self._save_json_file(self.file_path, accounts, "Update accounts data")
        except Exception as e:
            message = self._mask_error(e)
            print(f"[git-storage] save failed: {message}")
            raise RuntimeError(message) from e

    def load_auth_keys(self) -> list[dict[str, Any]]:
        """从 Git 仓库加载鉴权密钥数据"""
        try:
            data = self._load_json_value(self.auth_keys_file_path)
            if isinstance(data, dict):
                data = data.get("items")
            return data if isinstance(data, list) else []
        except Exception as e:
            message = self._mask_error(e)
            print(f"[git-storage] load failed: {message}")
            raise RuntimeError(message) from e

    def save_auth_keys(self, auth_keys: list[dict[str, Any]]) -> None:
        """保存鉴权密钥数据到 Git 仓库"""
        try:
            self._save_json_file(self.auth_keys_file_path, {"items": auth_keys}, "Update auth keys data")
        except Exception as e:
            message = self._mask_error(e)
            print(f"[git-storage] save failed: {message}")
            raise RuntimeError(message) from e

    def _load_json_file(self, file_path: str) -> list[dict[str, Any]]:
        data = self._load_json_value(file_path)
        return data if isinstance(data, list) else []

    def _load_json_value(self, file_path: str) -> Any:
        with self._lock:
            repo = self._clone_or_pull()
            file_full_path = Path(repo.working_dir) / file_path
            if not file_full_path.exists():
                return None
            return json.loads(file_full_path.read_text(encoding="utf-8"))

    def _save_json_file(self, file_path: str, items: Any, message: str) -> None:
        with self._lock:
            last_error: Exception | None = None
            for attempt in range(3):
                try:
                    repo = self._clone_or_pull()
                    file_full_path = Path(repo.working_dir) / file_path
                    file_full_path.parent.mkdir(parents=True, exist_ok=True)
                    file_full_path.write_text(
                        json.dumps(items, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    repo.index.add([file_path])
                    if repo.is_dirty(index=True, working_tree=True, untracked_files=True):
                        repo.index.commit(message)
                        repo.remote("origin").push(self.branch)
                    return
                except GitCommandError as exc:
                    last_error = exc
                    self._drop_cache()
                    time.sleep(0.5 * (attempt + 1))
            if last_error is not None:
                raise last_error

    def health_check(self) -> dict[str, Any]:
        """健康检查"""
        try:
            with self._lock:
                repo = self._clone_or_pull()
            return {
                "status": "healthy",
                "backend": "git",
                "repo_url": self._mask_token(self.repo_url),
                "branch": self.branch,
                "file_path": self.file_path,
                "auth_keys_file_path": self.auth_keys_file_path,
                "last_commit": self._last_commit(repo),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "backend": "git",
                "error": self._mask_error(e),
            }

    def get_backend_info(self) -> dict[str, Any]:
        """获取存储后端信息"""
        return {
            "type": "git",
            "description": "Git 私有仓库存储",
            "repo_url": self._mask_token(self.repo_url),
            "branch": self.branch,
            "file_path": self.file_path,
            "auth_keys_file_path": self.auth_keys_file_path,
        }

    @staticmethod
    def _mask_token(url: str) -> str:
        """隐藏 URL 中的 token"""
        if "@" in url and "://" in url:
            protocol, rest = url.split("://", 1)
            if "@" in rest:
                _, host = rest.split("@", 1)
                return f"{protocol}://****@{host}"
        return url

    def _mask_error(self, error: Exception) -> str:
        text = str(error)
        if self.auth_repo_url:
            text = text.replace(self.auth_repo_url, self._mask_token(self.auth_repo_url))
        if self.token:
            text = text.replace(self.token, "****")
        return text
