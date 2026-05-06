# Render GitHub 部署

本仓库已提供 `render.yaml`，用于 Render 从 GitHub 直接构建和部署，不走 Docker 镜像。

## 创建服务

1. 将仓库推送到 GitHub。
2. 在 Render Dashboard 选择 `New` -> `Blueprint`，连接该 GitHub 仓库。
3. Render 会读取仓库根目录的 `render.yaml`，创建 `chatgpt2api` Web Service。
4. 按提示填写环境变量：
   - `CHATGPT2API_AUTH_KEY`: 后台登录和 API 鉴权密钥。
   - `MOEMAIL_API_KEY`: MoeMail OpenAPI Key。
   - `MOEMAIL_DOMAIN`: MoeMail 可用域名，例如 `moemail.app`。多个域名用英文逗号分隔。

## 构建和启动

Render 使用 Python native runtime：

- Build Command: `bash scripts/render_build.sh`
- Start Command: `uv run --no-sync uvicorn main:app --host 0.0.0.0 --port $PORT --access-log`
- Python 版本由仓库根目录 `.python-version` 指定为 `3.13`

构建脚本会执行：

1. `uv sync --frozen --no-dev --no-install-project`
2. `npm --prefix web install`
3. `npm --prefix web run build`
4. 将 `web/out` 复制到后端会读取的 `web_dist`

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

## 数据持久化

默认 `STORAGE_BACKEND=json` 适合先跑通部署，但 Render 的免费实例文件系统不适合作为长期数据存储。长期使用建议改为：

- `STORAGE_BACKEND=postgres` 并配置 `DATABASE_URL`
- 或 `STORAGE_BACKEND=git` 并配置 `GIT_REPO_URL`、`GIT_TOKEN`

如果使用 Web UI 保存注册机配置，Render 重新部署后本地 `data/register.json` 可能丢失；MoeMail 相关配置建议放在环境变量里。
