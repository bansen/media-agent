# Content Agent

MVP for a keyword-driven content agent:

```text
keyword -> viral topic scoring -> channel drafts -> cover prompt -> WeChat draft payload -> Xiaohongshu package
```

## Channels

- WeChat official account: full automation to draft payload first, real draft submission after credentials and IP allowlist are configured.
- Baijiahao: paused. No API integration and no content generation in the current MVP.
- Xiaohongshu: semi-automatic publishing package. The first version does not auto-post.

## Setup

```bash
cp .env.example .env
python3 -m unittest discover -s tests -v
python3 -m content_agent.cli --keyword "AI副业"
```

Use Baidu Qianfan search to collect the top keyword results:

```bash
python3 -m content_agent.cli --keyword "AI副业" --channel wechat
```

Start the local web workbench:

```bash
python3 -m content_agent.web --host 127.0.0.1 --port 8000
```

Use the configured LLM to generate real channel drafts:

```bash
python3 -m content_agent.cli --keyword "AI副业" --channel wechat --use-llm
```

Format the WeChat draft with the installed `gzh-design` skill assets:

```bash
python3 -m content_agent.cli --keyword "AI副业" --channel wechat --format-gzh
```

Submit the formatted article to the WeChat draft box:

```bash
python3 -m content_agent.cli \
  --keyword "AI副业" \
  --channel wechat \
  --use-llm \
  --generate-cover \
  --submit-wechat-draft
```

Override the generated cover with a local image only when needed:

```bash
python3 -m content_agent.cli \
  --keyword "AI副业" \
  --channel wechat \
  --use-llm \
  --submit-wechat-draft \
  --wechat-cover-image /absolute/path/to/cover.jpg
```

If WeChat rejects the submission after content and cover are already generated, fix the WeChat IP allowlist first, then reuse the existing files without spending another LLM or Replicate call:

```bash
python3 -m content_agent.cli \
  --keyword "AI副业" \
  --channel wechat \
  --submit-wechat-draft \
  --wechat-content-html "output/AI副业_排版_摸鱼绿(moyu-green).html" \
  --wechat-cover-image "output/AI副业_cover.jpg"
```

This command performs real WeChat API calls:

```text
generate cover with Replicate if --generate-cover is used
fetch access_token if WECHAT_ACCESS_TOKEN is empty
upload cover image as permanent thumb material
receive new thumb media_id
submit formatted article to draft box
```

This writes:

- `output/<keyword>_排版_摸鱼绿(moyu-green).html` - clean WeChat body fragment.
- `output/<keyword>_排版_摸鱼绿(moyu-green)_预览.html` - browser preview with a copy button.

## Topic Sources

Manual keywords still use `baidu_search` (Baidu Qianfan web search): it filters obvious ads/promoted results, maps hits into `CandidateContent`, then reuses scoring, drafting, formatting, cover, and WeChat draft submission.

Briefing topics and any run that supplies source URLs skip Baidu entirely. The workbench / API / CLI fetch each `http(s)` page directly (plain HTTP + HTML/text extraction) and build candidates from that content. Do **not** use Tavily for this path.

Configure Baidu for ordinary keyword runs:

```env
BAIDU_SEARCH_API_KEY=your_baidu_qianfan_key
```

Pass source URLs via:

- Workbench textarea「原链接（每行一个）」, or paste links inside the creative prompt
- API / options JSON field `source_urls` (array or newline-separated string)
- CLI `--source-url` (repeatable). Briefing mode: `--use-prompt-as-title` (requires at least one URL)

If「简报选题」is checked but no URL can be resolved, the run fails with `简报选题已勾选但未提供原链接，请粘贴来源 URL` instead of falling back to Baidu.

Run with:

```bash
python3 -m content_agent.cli \
  --keyword "AI副业" \
  --channel wechat

# Briefing / source-link mode
python3 -m content_agent.cli \
  --keyword "某条简报选题标题" \
  --use-prompt-as-title \
  --source-url "https://example.com/original-article" \
  --channel wechat
```

If Baidu returns no usable result for a niche keyword (manual mode only), the workflow falls back to keyword-seed topics so the user can still generate a preview instead of hitting an empty-candidate error.

## Web Workbench

Run a local browser UI instead of typing CLI flags:

```bash
python3 -m content_agent.web --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

The root page is a public product intro page with platform-neutral trial CTAs. It can mention supported platform categories, but clickable trial text should route to `/trial`, where users choose an available platform:

- WeChat official account is currently open.
- Baijiahao and Xiaohongshu are shown as coming soon.
- For WeChat, users first log in to the workbench, then either authorize their official account through WeChat Open Platform or manually fill AppID/AppSecret/access token from WeChat Official Account Platform.

The web workbench persists each generated run as a content record:

- Starts a background job for each run and polls `/api/jobs/<job_id>` for progress.
- Saves job status, progress events, generated result JSON, preview paths, cover paths, and WeChat publish attempts in the database.
- Lists historical records from `/api/jobs`; selecting a record restores its preview and allows submitting it to the WeChat draft box later.
- Filters historical records by the current logged-in user.
- Reuses the same collectors, LLM generation, gzh-design formatting, Replicate cover generation, and WeChat draft submission functions as the CLI.
- Serves generated preview HTML and cover files from `output/` for local inspection.

One-click jobs save completed material selection, content planning, article, formatting, cover, and Xiaohongshu layout stages in the database. If a later stage fails, select the failed record and continue with the individual step buttons; the article does not need to be generated again. A successful retry clears the previous error.

Regenerating content invalidates the previous formatting, cover, layout and current draft-submission marker. Reformatting or replacing a cover allows submitting the revised version while preserving historical submission attempts. Switching from an imported HTML article to the generated article also invalidates its cover; changing only the formatting theme preserves it.

WeChat drafts have no minimum length. The retrieved source, rather than the editorial plan, is the factual authority. An independent call to the configured LLM checks the final title and article, returning quoted claims, source evidence and failure reasons. One targeted repair is allowed; a second rejection or unavailable/invalid review stops the workflow and preserves the rejected draft. Cover generation requires a current review. Submission separately checks the actual HTML and published title, including imported HTML and legacy records. Reports are bound to source and article hashes; changed content must be checked again. These checks reduce unsupported claims but do not establish that the original source itself is true.

Local development defaults to `sqlite:///output/content_agent.db` if `DATABASE_URL` is not set. Production Docker Compose runs PostgreSQL and injects:

```env
DATABASE_URL=postgresql+psycopg://media_agent:media_agent_change_me@db:5432/media_agent
```

Change `POSTGRES_PASSWORD` and `DATABASE_URL` together in `.env.production`.

### Single-owner login without WeChat Open Platform

For a personal deployment that already stores one official account in `.env.production`, use a separate administrator password to enter the workbench. The official-account AppID and AppSecret stay on the server and are imported after login; they are never rendered into the login page.

```env
OWNER_LOGIN_PASSWORD=use-a-long-random-password
OWNER_DISPLAY_NAME=server-owner
WECHAT_APP_ID=
WECHAT_APP_SECRET=
WECHAT_ACCESS_TOKEN=
```

Generate a password with `openssl rand -hex 24`, recreate the app container, then open `/auth/owner`. This mode is intended for one owner. Keep website OAuth or another user identity system for future multi-user access.

### WeChat Login vs Official Account Authorization

There are two separate WeChat flows:

- WeChat website login identifies the Media Agent user and creates a local session.
- WeChat Open Platform official-account authorization gives Media Agent permission to submit drafts to the user's own official account without asking that user for AppSecret.

Website login config:

```env
WECHAT_LOGIN_APP_ID=
WECHAT_LOGIN_APP_SECRET=
WECHAT_LOGIN_REDIRECT_URI=https://media-agent.createbeauty.top/auth/wechat/callback
WECHAT_LOGIN_SCOPE=snsapi_login
```

Official-account authorization config:

```env
WECHAT_COMPONENT_APP_ID=
WECHAT_COMPONENT_APP_SECRET=
WECHAT_COMPONENT_TOKEN=
WECHAT_COMPONENT_AES_KEY=
WECHAT_COMPONENT_AUTH_REDIRECT_URI=https://media-agent.createbeauty.top/auth/wechat-official/callback
WECHAT_COMPONENT_VERIFY_TICKET=
WECHAT_COMPONENT_ACCESS_TOKEN=
```

`WECHAT_COMPONENT_VERIFY_TICKET` is normally pushed by WeChat to the third-party platform event endpoint. For the first production run, you can also configure a valid `WECHAT_COMPONENT_ACCESS_TOKEN` to validate the authorization flow, then replace that with automated encrypted event handling.

Configure the WeChat Open Platform authorization event URL as:

```text
https://media-agent.createbeauty.top/wechat/component/notify
```

## Model Strategy

The LLM provider is OpenAI-compatible, so DeepSeek or other domestic models can be used by changing environment variables:

```env
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
LLM_API_KEY=your_key
```

## Image Strategy

Set `IMAGE_PROVIDER=seedream` to generate covers through the official Volcengine Ark API:

```env
IMAGE_PROVIDER=seedream
ARK_API_KEY=your_ark_key
SEEDREAM_MODEL=your_enabled_model_id
```

Copy the complete model ID (or endpoint ID) from the Ark console's API example. Enable that model in the same account as the API key. Seedream is billed separately from Jimeng consumer subscriptions. Never commit real API keys.

Local configuration belongs in `.env`; production configuration belongs in `/opt/media-agent/.env.production`. After updating production configuration, recreate the app container with `docker compose --env-file .env.production -f docker-compose.prod.yml up -d app`.

Both one-click generation and individual cover regeneration use this setting. Seedream requests one image at 2560x1440 for WeChat or 1728x2304 for Xiaohongshu, then saves the existing delivery sizes (1600x900 / 1080x1440) locally. Choose a model supporting these sizes; API failures stop generation without silently switching to another paid provider. Visible AI watermarks are enabled.

Cover generation now requires the final article for the selected channel. The configured LLM extracts a short Chinese headline (up to 24 characters), a visual scene, and an exact supporting quote from that article. The saved `cover_copy` records these fields and the article fingerprint; `cover_image.prompt` records the actual image request. Old planning prompts are not reused when regenerating a cover.

All image-generation prompts request a text-free background: no headline, letters, numbers, slogans, pseudo-text, or added watermark. The extracted headline remains in `cover_copy` and the workbench as an unused suggestion for a future local text-overlay step. Image dimensions are set through API parameters, not written into the prompt. Xiaohongshu continues to add its note title in the existing local layout renderer; WeChat currently ships the text-free image as generated. CLI cover generation requires `--use-llm` or an existing `--wechat-content-html` article. When an existing HTML article is selected, its extracted text is the cover source; scripts, styles and markup are excluded. Cover validation also rejects known factual reversals using the same fact checks as article generation.

Existing installations default to Replicate. Set `IMAGE_PROVIDER=replicate` to switch back.

Configure Replicate like this:

```env
REPLICATE_API_TOKEN=your_key
REPLICATE_COVER_MODEL=black-forest-labs/flux-1.1-pro
```

If the Python `replicate` package is installed, the project uses `replicate.run(...)`. If it is not installed, it falls back to Replicate's HTTP API with the same token.

## WeChat Cover Strategy

Do not hardcode `thumb_media_id` in `.env`. Each article cover should use this flow:

```text
generate cover -> upload as WeChat permanent thumb material -> receive media_id -> set articles[0].thumb_media_id -> submit draft
```

The provider boundary for this is `WeChatDraftPublisher.upload_thumb_material()`.

## WeChat Formatting Strategy

The project uses the installed skill at `.agents/skills/gzh-design` for formatting rules, validation, and preview wrapping.

Current MVP adapter:

- Theme: `摸鱼绿(moyu-green)`.
- Input: Markdown or generated WeChat outline converted to Markdown.
- Output: WeChat-safe `<section>...</section>` fragment.
- Validation: `.agents/skills/gzh-design/scripts/validate_gzh_html.py`.
- Preview: `.agents/skills/gzh-design/scripts/wrap_preview.py`.

## Safety Rules

- Do not promise income results.
- Do not publish health diagnosis or treatment claims.
- Keep human confirmation before final publishing.
- Keep API keys in `.env`; never commit real secrets.
