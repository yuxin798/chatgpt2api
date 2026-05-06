import importlib.util
import sys
import types
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def _load_git_storage_backend():
    module_names = ["git", "git.exc", "services.storage", "services.storage.base"]
    old_modules = {name: sys.modules.get(name) for name in module_names}

    git_module = types.ModuleType("git")
    git_exc_module = types.ModuleType("git.exc")
    storage_package = types.ModuleType("services.storage")
    storage_base_module = types.ModuleType("services.storage.base")

    class DummyRepo:
        pass

    class DummyGitCommandError(Exception):
        pass

    class DummyStorageBackend:
        pass

    git_module.Repo = DummyRepo
    git_exc_module.GitCommandError = DummyGitCommandError
    storage_package.__path__ = []
    storage_base_module.StorageBackend = DummyStorageBackend

    sys.modules["git"] = git_module
    sys.modules["git.exc"] = git_exc_module
    sys.modules["services.storage"] = storage_package
    sys.modules["services.storage.base"] = storage_base_module

    try:
        spec = importlib.util.spec_from_file_location(
            "_git_storage_under_test",
            ROOT_DIR / "services" / "storage" / "git_storage.py",
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module.GitStorageBackend
    finally:
        for name, value in old_modules.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


class GitStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.backend = _load_git_storage_backend()

    def test_build_auth_url_uses_github_token_username(self) -> None:
        value = self.backend._build_auth_url(
            "https://github.com/example/data.git",
            "ghp_test/token",
        )

        self.assertEqual(value, "https://x-access-token:ghp_test%2Ftoken@github.com/example/data.git")

    def test_build_auth_url_converts_ssh_url(self) -> None:
        value = self.backend._build_auth_url(
            "git@github.com:example/data.git",
            "ghp_test",
        )

        self.assertEqual(value, "https://x-access-token:ghp_test@github.com/example/data.git")

    def test_missing_branch_errors_are_detected(self) -> None:
        self.assertTrue(self.backend._is_missing_branch_error(Exception("fatal: Remote branch main not found in upstream origin")))
        self.assertTrue(self.backend._is_missing_branch_error(Exception("fatal: couldn't find remote ref main")))


if __name__ == "__main__":
    unittest.main()
