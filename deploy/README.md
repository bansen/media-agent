# Media Agent 部署说明

当前仓库为公开仓库 [bansen/media-agent](https://github.com/bansen/media-agent)。部署流程：

```text
推送 main → GitHub Actions 运行测试 → 构建并推送 GHCR 镜像 → 服务器 Docker Compose 更新 → Nginx 反向代理 → Cloudflare 域名解析
```

## 1. 推送代码

不要提交 .env 或 `.env.production`；真实密钥只保留在本机、GitHub Actions Secrets 和服务器。仓库已配置 Git 远端时，正常提交并推送即可：

```bash
git add <已检查的文件>
git commit -m "说明本次修改"
git push origin main
```

推送 `main` 会触发 `.github/workflows/deploy.yml`。它先运行测试；测试通过后构建镜像并部署。仓库公开不代表部署密钥公开，密钥仍需在 GitHub Actions Secrets 中单独配置。

`scripts/publish_private_repo.sh` 是最初创建**私有**仓库时的辅助脚本；当前仓库已公开，日常更新无需运行它。

## 2. 配置 GitHub Actions Secrets

在仓库的 `Settings → Secrets and variables → Actions` 中配置：

- `ALIYUN_HOST`：ECS 公网 IP 或域名。
- `ALIYUN_USER`：SSH 用户，例如 `root`。
- `ALIYUN_SSH_KEY`：SSH 私钥内容。
- `ALIYUN_SSH_PASSPHRASE`：私钥的密码短语；没有则留空。
- `ALIYUN_SSH_PORT`：SSH 端口，默认 `22`。

工作流会使用 GitHub 提供的 `GITHUB_TOKEN` 登录 GHCR。推送 `main` 后，Actions 构建镜像，并将部署文件同步到服务器 `/opt/media-agent`。

## 3. 服务器运行

推荐使用 Docker Compose，应用端口仅绑定服务器本机 `127.0.0.1:8000`：

```bash
mkdir -p /opt/media-agent
cd /opt/media-agent
sh scripts/deploy.sh
```

首次部署时，如果服务器没有 `.env.production`，部署脚本会从 `.env.example` 创建配置文件：

```bash
cp .env.example .env.production
```

随后在服务器上填写模型、图片和微信公众号等实际凭据。后续部署不会覆盖已有的 `.env.production`。

如启用 WebSearch MCP 读取 GitHub、官网或文档链接，需在服务器 `.env.production` 中补充：

```env
WEBSEARCH_MCP_ENABLED=true
WEBSEARCH_MCP_COMMAND=npx
WEBSEARCH_MCP_ARGS=-y,tavily-mcp@0.1.3
WEBSEARCH_MCP_TIMEOUT=60
TAVILY_API_KEY=your_tavily_key
```

## 4. Nginx 与二级域名

GitHub Actions 将 `deploy/nginx.media-agent.conf` 同步到服务器。服务器已安装 Nginx 时，工作流会将它写入：

```text
/etc/nginx/conf.d/media-agent.conf
```

示例域名（部署时替换为自己的域名）：

```text
xxx.example.com
```

Cloudflare DNS 记录可配置为：

- 类型：`A`
- 名称：`xxx`
- 内容：服务器公网 IP
- 代理状态：先选 `DNS only`，确认服务正常后再按需开启代理

## 5. 部署脚本与镜像清理

`scripts/deploy.sh` 在服务器 `/opt/media-agent` 下启动最新镜像。GitHub Actions 会同步 `docker-compose.prod.yml`、`scripts/deploy.sh`、`.env.example` 和 Nginx 配置；通常无须在本地手动运行部署脚本。

每次拉取镜像后，脚本最多等待 120 秒，确认 Compose 服务正常运行（有健康检查的服务还须处于健康状态），然后执行 `docker image prune --all --force`。这会清理该服务器上**所有**未被容器引用的镜像，包括其他项目闲置镜像和带标签旧镜像。运行中或已停止的容器所引用的镜像会保留；容器、数据卷、数据库、文章和图片不会清理。需要回滚时，可从 GHCR 重新拉取旧版本镜像。

拉取或启动失败时不执行清理；清理失败会让部署报错，释放空间的结果会记录在部署日志中。本地手动部署入口也调用同一脚本。

如需从本地手动触发服务器部署：

```bash
export DEPLOY_HOST=<server-ip>
export DEPLOY_USER=<ssh-user>
export REPO_URL=https://github.com/bansen/media-agent.git
./deploy/deploy_server.sh
```

如果服务器未安装 Nginx，工作流会跳过反向代理配置，并在 Actions 日志中说明。
