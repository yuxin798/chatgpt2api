# Render GitHub 部署

本仓库提供 `render.yaml`，用于 Render 从 GitHub 直接构建和部署，不走 Docker 镜像。

## 创建服务

1. 将应用仓库推送到 GitHub。
2. 在 Render Dashboard 选择 `New` -> `Blueprint`，连接该 GitHub 仓库。
3. Render 会读取仓库根目录的 `render.yaml`，创建 `chatgpt2api` Web Service。
4. 按提示填写环境变量。

## 必填环境变量

| 变量 | 说明 |
| --- | --- |
| `CHATGPT2API_AUTH_KEY` | 后台登录和 API 鉴权密钥 |
| `MOEMAIL_API_KEY` | MoeMail OpenAPI Key |
| `MOEMAIL_DOMAIN` | MoeMail 可用域名，多个域名用英文逗号分隔 |
| `GIT_REPO_URL` | 单独的数据仓库地址，例如 `https://github.com/your-name/chatgpt2api-data.git` |
| `GIT_TOKEN` | 对数据仓库有读写权限的 GitHub token |

## Git 数据仓库

`render.yaml` 已默认设置：

- `STORAGE_BACKEND=git`
- `GIT_BRANCH=main`
- `GIT_FILE_PATH=accounts.json`
- `GIT_AUTH_KEYS_FILE_PATH=auth_keys.json`
- `GIT_AUTH_USERNAME=x-access-token`

建议新建一个单独的私有数据仓库，不要把 `GIT_REPO_URL` 指向当前部署仓库。否则每次账号池或鉴权 key 更新都会向部署仓库提交，容易触发 Render 重复部署。

数据仓库可以先放两个文件：

```json
[]
```

文件名为 `accounts.json`。

```json
{
  "items": []
}
```

文件名为 `auth_keys.json`。

GitHub token 需要对这个数据仓库有读写权限。Fine-grained token 至少授予目标仓库 `Contents: Read and write`。

## 构建和启动

Render 使用 Python native runtime：

- Build Command: `bash scripts/render_build.sh`
- Start Command: `uv run --no-sync uvicorn main:app --host 0.0.0.0 --port $PORT --access-log`
- Python 版本由仓库根目录 `.python-version` 指定为 `3.13`
- Health Check Path: `/healthz`

构建脚本会执行：

1. `uv sync --frozen --no-dev --no-install-project`
2. `npm --prefix web install`
3. `npm --prefix web run build`
4. 将 `web/out` 复制到后端读取的 `web_dist`

如果访问域名显示 `Not Found`，通常是前端静态文件没有复制到 `web_dist/index.html`。当前构建脚本会在构建后检查 `web/out/index.html` 和 `web_dist/index.html`，缺失时直接让 Render 构建失败。

## MoeMail 环境变量

注册机启动时会优先读取以下环境变量生成 MoeMail provider：

| 变量 | 说明 |
| --- | --- |
| `REGISTER_MAIL_PROVIDER` | 设置为 `moemail` |
| `MOEMAIL_API_BASE` | MoeMail 地址，默认 `https://moemail.app` |
| `MOEMAIL_API_KEY` | MoeMail OpenAPI Key |
| `MOEMAIL_DOMAIN` / `MOEMAIL_DOMAINS` | 邮箱域名，多个用逗号分隔 |
| `MOEMAIL_EXPIRY_TIME` | 邮箱有效期毫秒，默认 `0` |
| `REGISTER_MAIL_WAIT_TIMEOUT` | 等待验证码超时时间秒，默认 `30` |
| `REGISTER_MAIL_WAIT_INTERVAL` | 轮询间隔秒，默认 `2` |

## 注意

当前 Git 存储覆盖账号池数据和专用鉴权 key。Web UI 保存的注册机配置仍可能写入实例本地的 `data/register.json`，Render 重新部署后可能丢失；MoeMail 相关配置建议继续放在环境变量里。
