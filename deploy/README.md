# Media Agent 部署说明

目标流程：

```text
本地提交到私有 Git 仓库 -> GitHub Actions 构建 GHCR 镜像 -> 服务器 Docker Compose 更新 -> Nginx 反向代理 -> Cloudflare 二级域名解析
```

## 1. 发布到私有 Git 仓库

不要提交 .env，真实密钥只放在本机和服务器。

如果已经有私有仓库：

```bash
GIT_REMOTE_URL=git@github.com:bansen/media-agent.git \
COMMIT_MESSAGE="Deploy media agent" \
./scripts/publish_private_repo.sh
```

如果没有仓库，并且本机已登录 GitHub CLI：

```bash
gh auth login
REPO_NAME=media-agent ./scripts/publish_private_repo.sh
```

当前机器暂未检测到 `gh`，所以更稳的第一步是：你先安装并登录 GitHub CLI，或手动创建 private repo 后把 SSH 地址给脚本。

## 2. GitHub Actions Secrets

参考菩提阁项目，在 GitHub 仓库 `Settings -> Secrets and variables -> Actions` 配置：

- `ALIYUN_HOST`: ECS 公网 IP 或域名
- `ALIYUN_USER`: SSH 用户，例如 `root`
- `ALIYUN_SSH_KEY`: 私钥内容
- `ALIYUN_SSH_PASSPHRASE`: 如果私钥创建时设置了密码短语，就填这个；无密码私钥可不填
- `ALIYUN_SSH_PORT`: SSH 端口，默认 `22`

推送到 `main` 后，Actions 会运行测试、构建 Docker 镜像并部署到服务器 `/opt/media-agent`。

## 3. 服务器运行方式

推荐用 Docker Compose 跑服务，只对服务器本机暴露 `127.0.0.1:8000`：

```bash
mkdir -p /opt/media-agent
cd /opt/media-agent
docker compose --env-file .env.production -f docker-compose.prod.yml up -d app
```

首次部署时，如果服务器上没有 `.env.production`，部署脚本会先从 `.env.example` 创建一个默认文件：

```bash
cp .env.example .env.production
```

然后你需要登录服务器填写 DeepSeek、Replicate、微信公众号等真实密钥；已有 `.env.production` 时部署不会覆盖。

如果启用 WebSearch MCP 读取 GitHub、官网或文档链接，已有 `.env.production` 还需要补充：

```env
WEBSEARCH_MCP_ENABLED=true
WEBSEARCH_MCP_COMMAND=npx
WEBSEARCH_MCP_ARGS=-y,tavily-mcp@0.1.3
WEBSEARCH_MCP_TIMEOUT=60
TAVILY_API_KEY=your_tavily_key
```

## 4. Nginx 二级域名

GitHub Actions 会把 `deploy/nginx.media-agent.conf` 同步到服务器，并在服务器安装了 Nginx 时自动写入：

```text
/etc/nginx/conf.d/media-agent.conf
```

域名使用：

```text
media-agent.createbeauty.top
```

Cloudflare 里手动配置：

- 类型：`A`
- 名称：`media-agent`
- 内容：服务器公网 IP
- 代理状态：先用 DNS only，确认正常后再按需开启代理

## 5. 手动部署脚本

`scripts/deploy.sh` 会在服务器 `/opt/media-agent` 下启动最新镜像。GitHub Actions 会自动同步 `docker-compose.prod.yml`、`scripts/deploy.sh`、`.env.example` 和 Nginx 配置，一般不需要本地手动运行。

如需从本地手动触发服务器部署，可使用：

```bash
export DEPLOY_HOST=<server-ip>
export DEPLOY_USER=<ssh-user>
export REPO_URL=https://github.com/bansen/media-agent.git
./deploy/deploy_server.sh
```

Nginx 配置可由 Actions 自动启用；如果服务器没有安装 Nginx，脚本会跳过并在 Actions 日志中提示。
