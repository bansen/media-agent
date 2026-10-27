# 内容创作助手（Content Agent）

根据关键词或原始来源链接，完成热点候选整理、渠道内容生成、封面制作、公众号排版与草稿提交。基本流程：

```text
关键词或原链接 → 候选内容与热度评分 → 渠道文稿 → 封面 → 公众号草稿 / 小红书素材包
```

## 支持渠道

- **微信公众号**：生成文章、排版和封面，并可提交到已绑定公众号的草稿箱。
- **百家号**：当前暂停；本版既不生成百家号内容，也没有发布接口。
- **小红书**：生成供人工发布的图文素材包，暂不自动发布。

## 快速开始

复制配置模板并填写所需的服务凭据，然后运行测试或命令行工具：

```bash
cp .env.example .env
python3 -m unittest discover -s tests -v
python3 -m content_agent.cli --keyword "AI副业"
```

用百度千帆搜索收集关键词结果：

```bash
python3 -m content_agent.cli --keyword "AI副业" --channel wechat
```

启动本地网页工作台：

```bash
python3 -m content_agent.web --host 127.0.0.1 --port 8000
```

使用已配置的大模型生成文稿：

```bash
python3 -m content_agent.cli --keyword "AI副业" --channel wechat --use-llm
```

使用内置 `gzh-design` 技能排版公众号文章：

```bash
python3 -m content_agent.cli --keyword "AI副业" --channel wechat --format-gzh
```

生成封面并将排版后的文章提交到公众号草稿箱：

```bash
python3 -m content_agent.cli \
  --keyword "AI副业" \
  --channel wechat \
  --use-llm \
  --generate-cover \
  --submit-wechat-draft
```

确有需要时，可用本地图片替代生成封面：

```bash
python3 -m content_agent.cli \
  --keyword "AI副业" \
  --channel wechat \
  --use-llm \
  --submit-wechat-draft \
  --wechat-cover-image /absolute/path/to/cover.jpg
```

如果文稿和封面已经生成，但公众号因 IP 白名单拒绝提交，先修复白名单，再复用现有文件，避免再次调用付费生成服务：

```bash
python3 -m content_agent.cli \
  --keyword "AI副业" \
  --channel wechat \
  --submit-wechat-draft \
  --wechat-content-html "output/AI副业_排版_摸鱼绿(moyu-green).html" \
  --wechat-cover-image "output/AI副业_cover.jpg"
```

提交命令会调用真实的微信接口。使用 `--generate-cover` 时，程序先生成封面，再获取访问令牌（如未配置 `WECHAT_ACCESS_TOKEN`）、上传永久封面素材、取得 `media_id`，最后提交草稿。

排版输出包括：

- `output/<keyword>_排版_摸鱼绿(moyu-green).html`：可用于公众号的正文片段。
- `output/<keyword>_排版_摸鱼绿(moyu-green)_预览.html`：带复制按钮的浏览器预览页。

## 选题与来源

手动输入普通关键词时，使用 `baidu_search`（百度千帆网页搜索）。程序过滤明显广告和推广结果，转换为 `CandidateContent` 后，继续执行评分、写作、排版、封面和草稿流程。

简报选题或提供原始来源 URL 时，网页工作台、API 和命令行会直接请求 `http(s)` 页面并提取正文，跳过百度搜索。此路径不使用 Tavily。

普通关键词模式需要配置：

```env
BAIDU_SEARCH_API_KEY=your_baidu_qianfan_key
```

来源链接可通过以下方式传入：

- 在工作台的「原链接（每行一个）」文本框填写，或直接粘贴进创作提示词。
- 在 API 的 `source_urls` 字段填写数组或按行分隔的字符串。
- 在命令行重复使用 `--source-url`。简报模式还可使用 `--use-prompt-as-title`，但必须提供至少一个 URL。

如果勾选「简报选题」却没有可解析的 URL，任务会明确报错，不会改用百度搜索。示例：

```bash
python3 -m content_agent.cli \
  --keyword "AI副业" \
  --channel wechat

# 简报 / 原链接模式
python3 -m content_agent.cli \
  --keyword "某条简报选题标题" \
  --use-prompt-as-title \
  --source-url "https://example.com/original-article" \
  --channel wechat
```

仅在手动关键词模式下，如果百度没有返回可用结果，程序会用关键词种子生成候选，供预览流程继续运行。

## 网页工作台

启动服务后打开 `http://127.0.0.1:8000`。根页面是产品介绍页；试用入口跳转到 `/trial` 选择渠道。当前开放微信公众号；百家号和小红书显示为即将开放。公众号用户登录后，可通过微信开放平台授权公众号，也可手动填写公众号平台提供的 AppID、AppSecret 或访问令牌。

工作台将每次生成保存为内容记录：

- 启动后台任务，并通过 `/api/jobs/<job_id>` 查询进度。
- 在数据库中保存任务状态、进度事件、结果 JSON、预览与封面路径，以及公众号提交尝试。
- 在 `/api/jobs` 展示当前登录用户的历史记录；重新打开记录可恢复预览并稍后提交草稿。
- 复用命令行的采集、模型生成、`gzh-design` 排版、封面生成和草稿提交功能。
- 从 `output/` 提供预览 HTML 和封面，供本地检查。

一键任务会分别保存素材选择、内容策划、文章、排版、封面及小红书布局阶段。如果后续阶段失败，可打开失败记录并从相应步骤继续，无须重新生成文章；成功重试会清除之前的错误。

重新生成正文会使旧排版、封面、布局和当前草稿提交标记失效。重新排版或替换封面可提交修订版，同时保留历史提交尝试。从导入的 HTML 切换到生成正文也会使旧封面失效；仅切换排版主题则保留封面。

公众号文章不设最低字数。已读取的原始来源优先于内容策划。独立的大模型调用会检查最终标题和正文，返回待核查表述、来源证据和失败原因；最多进行一次针对性修订。再次失败或审查服务不可用、格式无效时，流程停止并保留稿件。生成封面需要有效的当前审查结果；提交前还会检查实际 HTML 与提交标题，包括导入 HTML 和历史任务。审查结果与来源、文章指纹绑定，内容变更后须重新检查。这些检查用于减少缺乏依据的表述，不代表原始来源本身已经证实。

未设置 `DATABASE_URL` 时，本地开发默认使用 `sqlite:///output/content_agent.db`。生产环境的 Docker Compose 使用 PostgreSQL，并向应用注入数据库连接，例如：

```env
DATABASE_URL=postgresql+psycopg://media_agent:media_agent_change_me@db:5432/media_agent
```

生产环境须在 `.env.production` 中一起修改 `POSTGRES_PASSWORD` 和 `DATABASE_URL`。

### 单管理员登录（不使用微信开放平台）

如果个人部署已经在 `.env.production` 保存了一个公众号，可使用独立管理员密码进入工作台。公众号 AppID 和 AppSecret 保留在服务器端，登录后才导入账号绑定信息，不会展示在登录页。

```env
OWNER_LOGIN_PASSWORD=use-a-long-random-password
OWNER_DISPLAY_NAME=server-owner
WECHAT_APP_ID=
WECHAT_APP_SECRET=
WECHAT_ACCESS_TOKEN=
```

可用 `openssl rand -hex 24` 生成密码，重建应用容器后访问 `/auth/owner`。这一方式面向单一管理员；多人使用时应配置网站 OAuth 或其他用户身份系统。

### 微信网站登录与公众号授权

这两个流程用途不同：

- **网站登录**：识别内容工作台用户，并创建本地会话。
- **微信开放平台公众号授权**：取得向用户公众号提交草稿的权限，无须向该用户索取 AppSecret。

网站登录配置：

```env
WECHAT_LOGIN_APP_ID=
WECHAT_LOGIN_APP_SECRET=
WECHAT_LOGIN_REDIRECT_URI=https://media-agent.createbeauty.top/auth/wechat/callback
WECHAT_LOGIN_SCOPE=snsapi_login
```

公众号授权配置：

```env
WECHAT_COMPONENT_APP_ID=
WECHAT_COMPONENT_APP_SECRET=
WECHAT_COMPONENT_TOKEN=
WECHAT_COMPONENT_AES_KEY=
WECHAT_COMPONENT_AUTH_REDIRECT_URI=https://media-agent.createbeauty.top/auth/wechat-official/callback
WECHAT_COMPONENT_VERIFY_TICKET=
WECHAT_COMPONENT_ACCESS_TOKEN=
```

`WECHAT_COMPONENT_VERIFY_TICKET` 通常由微信推送至第三方平台事件接收接口。首次部署时，也可以先配置有效的 `WECHAT_COMPONENT_ACCESS_TOKEN` 验证授权流程，之后再改为自动处理加密事件。微信开放平台的授权事件 URL：

```text
https://media-agent.createbeauty.top/wechat/component/notify
```

## 模型配置

大模型接口兼容 OpenAI 格式；修改环境变量即可使用 DeepSeek 等模型：

```env
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
LLM_API_KEY=your_key
```

## 图片与封面

设置 `IMAGE_PROVIDER=seedream`，可通过火山引擎方舟接口生成封面：

```env
IMAGE_PROVIDER=seedream
ARK_API_KEY=your_ark_key
SEEDREAM_MODEL=your_enabled_model_id
```

模型 ID（或接入点 ID）应按方舟控制台的 API 示例填写，并在同一账号启用。即梦消费者订阅与 Seedream API 分开计费。真实 API Key 不得提交到 Git。

本地配置放在 `.env`；生产配置放在 `/opt/media-agent/.env.production`。修改生产配置后，运行 `docker compose --env-file .env.production -f docker-compose.prod.yml up -d app` 重建应用容器。

一键生成和单独重做封面都会读取图片提供方设置。Seedream 为公众号请求 2560×1440 图片，为小红书请求 1728×2304 图片，然后在本地保存既有交付尺寸（1600×900 / 1080×1440）。所选模型须支持这些尺寸；接口失败时会停止，不会悄悄切换到其他付费提供方。图片请求关闭可见水印，并要求画面不含文字；仍应人工检查实际结果。

封面生成基于所选渠道的最终文章。大模型从文章中提取不超过 24 字的中文标题建议、视觉场景，以及逐字引用的支撑句。保存的 `cover_copy` 记录这些字段和文章指纹；`cover_image.prompt` 记录实际图片请求。重做封面时不再使用旧策划提示词。

图片提示词要求无字背景：不生成标题、字母、数字、标语、伪文字或额外水印。标题建议保留在 `cover_copy` 和工作台中，供以后需要本地叠字时使用；当前公众号交付的是无字封面。尺寸通过 API 参数指定，不写进图片提示词。小红书仍由现有本地布局器添加笔记标题。命令行生成封面需要 `--use-llm`，或已有的 `--wechat-content-html` 文章；选择现有 HTML 时，只提取正文文字，排除脚本、样式和标记。封面核查也会复用正文事实检查，拦截已知事实反转。

已有安装默认使用 Replicate；设置 `IMAGE_PROVIDER=replicate` 可显式切换。配置示例：

```env
REPLICATE_API_TOKEN=your_key
REPLICATE_COVER_MODEL=black-forest-labs/flux-1.1-pro
```

已安装 Python `replicate` 包时调用 `replicate.run(...)`；否则使用同一令牌通过 Replicate HTTP API 请求。

### 公众号封面上传

不要在 `.env` 中写死 `thumb_media_id`。每篇文章按以下顺序处理：

```text
生成封面 → 上传为微信永久缩略图素材 → 获取 media_id → 设置 articles[0].thumb_media_id → 提交草稿
```

相关接口封装在 `WeChatDraftPublisher.upload_thumb_material()`。

### 公众号排版

项目使用 `.agents/skills/gzh-design` 中的规则、校验器和预览工具。当前适配器将 Markdown 或生成的公众号大纲转换为 Markdown，再输出适合微信的 `<section>...</section>` 片段，默认主题为「摸鱼绿（moyu-green）」：

- 校验脚本：`.agents/skills/gzh-design/scripts/validate_gzh_html.py`
- 预览脚本：`.agents/skills/gzh-design/scripts/wrap_preview.py`

## 内容安全

- 不承诺赚钱收益。
- 不发布未经核实的医疗诊断或治疗结论。
- 最终公开发布前保留人工确认。
- API Key 存放在 `.env`，不要提交真实密钥。

## 许可证

本仓库的原创代码采用 [MIT 许可证](LICENSE)。内置的第三方 `gzh-design` 技能位于 `.agents/skills/gzh-design`，单独采用其 [AGPL-3.0 许可证](.agents/skills/gzh-design/LICENSE)；其原作者版权和许可条款继续有效。
