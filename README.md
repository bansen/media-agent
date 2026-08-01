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

Use keyword-searchable free sources without paid API keys:

```bash
python3 -m content_agent.cli --keyword "AI副业" --channel wechat --collector free_hot
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

## Mock Data

The current MVP uses `content_agent/mock_data.py` instead of live platform collection. It includes mock candidates for:

- WeChat: side hustles, AI earning, AI learning.
- Xiaohongshu: workplace women, moms, health habits.

Replace `get_mock_candidates()` with a real collector later without changing the workflow contract.

## Free Hot Data

`free_hot` collects topic candidates from free public sources that support keyword search. Paid/keyed APIs and fixed hot-list feeds are intentionally not exposed in the product workflow.

Default sources:

```env
FREE_HOT_SOURCES=google_news_rss,hn,github
```

Supported sources:

- `google_news_rss` - Google News RSS keyword search, no key.
- `hn` - Hacker News Algolia search, no key.
- `github` - GitHub repository search, no key for low-volume public requests.

Run with:

```bash
python3 -m content_agent.cli \
  --keyword "AI副业" \
  --channel wechat \
  --collector free_hot
```

The collector maps all sources into `CandidateContent`, then reuses the existing scoring, drafting, formatting, cover, and WeChat draft submission workflow.

## Web Workbench

Run a local browser UI instead of typing CLI flags:

```bash
python3 -m content_agent.web --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

The first version is intentionally local and lightweight:

- No login, no database, no multi-user queue.
- Starts a background job for each run and polls `/api/jobs/<job_id>` for progress.
- Reuses the same collectors, LLM generation, gzh-design formatting, Replicate cover generation, and WeChat draft submission functions as the CLI.
- Serves generated preview HTML and cover files from `output/` for local inspection.

## Model Strategy

The LLM provider is OpenAI-compatible, so DeepSeek or other domestic models can be used by changing environment variables:

```env
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
LLM_API_KEY=your_key
```

## Image Strategy

Replicate is used as an image provider boundary. The recommended production approach is:

```text
Replicate generates the background image -> local renderer overlays Chinese title text
```

This avoids unstable Chinese text rendering inside image-generation models.

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
