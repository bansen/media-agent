# Content Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an MVP content production agent that turns a keyword into ranked topic options, channel-specific drafts, a Replicate-ready cover image prompt, a WeChat draft payload, and a Xiaohongshu publishing package.

**Architecture:** The first version is a deterministic Python workflow with replaceable provider interfaces for LLMs, image generation, and publishers. LangGraph will be added as the orchestration layer after the core data contracts and scoring logic are stable.

**Tech Stack:** Python 3.13, standard-library tests, OpenAI-compatible LLM provider design for DeepSeek/domestic models, Replicate image provider boundary, WeChat draft publisher boundary, Markdown/JSON exports.

---

## Scope

### In Version 0.1

- Input a keyword and channel profile.
- Expand related keywords.
- Score candidate viral topics with an explainable formula.
- Generate reusable content briefs for WeChat/Baijiahao and Xiaohongshu.
- Generate a Replicate-ready cover prompt.
- Export a Xiaohongshu package for manual posting.
- Build a WeChat draft payload boundary without storing credentials in code.

### Not In Version 0.1

- Fully automatic Xiaohongshu posting.
- Unapproved scraping of protected platform pages.
- Automatic Baijiahao publishing until account API access is confirmed.
- Medical, income, or investment claims without human review.
- Real LangGraph runtime dependency before the MVP logic is tested.

## File Structure

- `content-agent/PLAN.md` - implementation plan and product scope.
- `content-agent/README.md` - setup, environment variables, and usage.
- `content-agent/.env.example` - non-secret configuration template.
- `content-agent/content_agent/models.py` - shared dataclasses and channel constants.
- `content-agent/content_agent/keyword_expander.py` - deterministic keyword expansion.
- `content-agent/content_agent/mock_data.py` - mock candidate data before live collection is connected.
- `content-agent/content_agent/scoring.py` - explainable viral-topic scoring.
- `content-agent/content_agent/prompts.py` - prompt builders for domestic LLMs and Replicate.
- `content-agent/content_agent/workflow.py` - MVP orchestration without external side effects.
- `content-agent/content_agent/exporters.py` - Xiaohongshu package and WeChat payload export helpers.
- `content-agent/content_agent/formatters/wechat_gzh.py` - gzh-design-based WeChat Markdown to styled HTML adapter.
- `content-agent/content_agent/providers/llm.py` - LLM provider interfaces and OpenAI-compatible stub.
- `content-agent/content_agent/providers/image.py` - Replicate provider boundary.
- `content-agent/content_agent/providers/wechat.py` - WeChat draft publisher boundary.
- `content-agent/content_agent/cli.py` - command-line entry point.
- `content-agent/tests/test_keyword_expander.py` - keyword expansion tests.
- `content-agent/tests/test_scoring.py` - scoring tests.
- `content-agent/tests/test_workflow_exports.py` - workflow and export tests.

## Task 1: Plan And Test Skeleton

**Files:**
- Create: `content-agent/PLAN.md`
- Create: `content-agent/tests/test_keyword_expander.py`
- Create: `content-agent/tests/test_scoring.py`
- Create: `content-agent/tests/test_workflow_exports.py`

- [x] **Step 1: Write the implementation plan**

Write this document with scope, architecture, files, and task steps.

- [x] **Step 2: Write failing tests**

Tests must assert:

```python
from content_agent.keyword_expander import expand_keywords
from content_agent.scoring import score_candidate
from content_agent.workflow import run_keyword_workflow
```

- [x] **Step 3: Run tests to verify RED**

Run:

```bash
cd content-agent
python3 -m unittest discover -s tests -v
```

Observed: FAIL because `content_agent` did not exist yet.

## Task 2: Core Data Models And Scoring

**Files:**
- Create: `content-agent/content_agent/__init__.py`
- Create: `content-agent/content_agent/models.py`
- Create: `content-agent/content_agent/keyword_expander.py`
- Create: `content-agent/content_agent/scoring.py`
- Test: `content-agent/tests/test_keyword_expander.py`
- Test: `content-agent/tests/test_scoring.py`

- [x] **Step 1: Implement dataclasses**

Create `ContentChannel`, `CandidateContent`, `TopicScore`, `TopicBrief`, and `WorkflowResult`.

- [x] **Step 2: Implement keyword expansion**

Make `expand_keywords("AI副业", "wechat")` include the original keyword plus practical related phrases.

- [x] **Step 3: Implement explainable scoring**

Use this formula:

```text
hot_score = heat * 0.30 + interaction * 0.20 + hook * 0.15 + pain * 0.15 + reuse * 0.10 + material * 0.10
```

- [x] **Step 4: Run tests**

Run:

```bash
cd content-agent
python3 -m unittest tests.test_keyword_expander tests.test_scoring -v
```

Observed: PASS.

## Task 2.5: Mock Data Source

**Files:**
- Create: `content-agent/content_agent/mock_data.py`
- Create: `content-agent/tests/test_mock_data.py`
- Modify: `content-agent/content_agent/cli.py`
- Modify: `content-agent/README.md`

- [x] **Step 1: Write failing tests for mock candidates**

Tests assert that WeChat/Baijiahao keywords return AI side-hustle mock content and Xiaohongshu health keywords return workplace-women and mom-health mock content.

- [x] **Step 2: Implement `get_mock_candidates()`**

The function returns deterministic `CandidateContent` records with `source="mock"` and realistic scoring metrics.

- [x] **Step 3: Update CLI to use mock data**

The CLI now calls `get_mock_candidates(args.keyword, channel=args.channel)` instead of using an internal sample function.

- [x] **Step 4: Verify**

Run:

```bash
cd content-agent
python3 -m unittest tests.test_mock_data -v
python3 -m unittest discover -s tests -v
```

Observed: PASS.

## Task 3: Workflow And Exporters

**Files:**
- Create: `content-agent/content_agent/prompts.py`
- Create: `content-agent/content_agent/workflow.py`
- Create: `content-agent/content_agent/exporters.py`
- Test: `content-agent/tests/test_workflow_exports.py`

- [x] **Step 1: Implement prompt builders**

Generate platform-specific prompts for WeChat/Baijiahao side-hustle/AI-learning content and Xiaohongshu health content.

- [x] **Step 2: Implement deterministic MVP workflow**

Given a keyword and candidates, return ranked topic briefs, a WeChat article outline, a Xiaohongshu publishing package, and cover prompt metadata.

- [x] **Step 3: Implement export helpers**

Produce a WeChat draft payload shape and a Xiaohongshu Markdown package.

- [x] **Step 4: Run workflow tests**

Run:

```bash
cd content-agent
python3 -m unittest tests.test_workflow_exports -v
```

Observed: PASS.

## Task 4: Provider Boundaries And CLI

**Files:**
- Create: `content-agent/content_agent/providers/__init__.py`
- Create: `content-agent/content_agent/providers/llm.py`
- Create: `content-agent/content_agent/providers/image.py`
- Create: `content-agent/content_agent/providers/wechat.py`
- Create: `content-agent/content_agent/cli.py`
- Create: `content-agent/.env.example`
- Create: `content-agent/README.md`

- [x] **Step 1: Add provider interfaces**

Create interfaces for OpenAI-compatible LLM calls, Replicate image predictions, and WeChat draft submission.

- [x] **Step 2: Add CLI**

Support:

```bash
python3 -m content_agent.cli --keyword "AI副业"
```

- [x] **Step 3: Add docs and config template**

Document DeepSeek, Replicate, WeChat, Baijiahao, and Xiaohongshu boundaries.

- [x] **Step 4: Run full verification**

Run:

```bash
cd content-agent
python3 -m unittest discover -s tests -v
python3 -m content_agent.cli --keyword "AI副业"
```

Observed: tests pass and CLI prints a JSON result.

## Task 5: WeChat gzh-design Formatting

**Files:**
- Create: `content-agent/content_agent/formatters/__init__.py`
- Create: `content-agent/content_agent/formatters/wechat_gzh.py`
- Create: `content-agent/tests/test_wechat_formatting.py`
- Modify: `content-agent/content_agent/exporters.py`
- Modify: `content-agent/content_agent/cli.py`
- Modify: `content-agent/README.md`

- [x] **Step 1: Read installed gzh-design skill**

Read `.agents/skills/gzh-design/SKILL.md`, `references/theme-index.md`, `references/theme-moyu-green.md`, and `references/common-components.md`.

- [x] **Step 2: Write failing formatter tests**

Tests assert that Markdown becomes a pure `<section>` fragment, includes `span leaf`, passes the skill validator, can be used in WeChat draft payload, and can write clean/preview HTML files.

- [x] **Step 3: Implement the MVP formatter**

Implemented `format_wechat_markdown()` with the `摸鱼绿(moyu-green)` theme and `write_gzh_outputs()` using the skill's `wrap_preview.py`.

- [x] **Step 4: Add CLI flag**

Added:

```bash
python3 -m content_agent.cli --keyword "AI副业" --channel wechat --format-gzh
```

- [x] **Step 5: Verify**

Run:

```bash
cd content-agent
python3 -m unittest discover -s tests -v
python3 .agents/skills/gzh-design/scripts/validate_gzh_html.py 'output/AI副业_排版_摸鱼绿(moyu-green).html'
```

Observed: 27 tests pass, generated HTML passes with `✅ 完全合规，可直接粘贴到公众号编辑器`.

## Task 6: WeChat Draft Submission

**Files:**
- Create: `content-agent/content_agent/wechat_publish.py`
- Create: `content-agent/tests/test_wechat_draft_publish.py`
- Modify: `content-agent/content_agent/providers/wechat.py`
- Modify: `content-agent/content_agent/cli.py`
- Modify: `content-agent/README.md`

- [x] **Step 1: Write failing tests**

Tests assert that publishing uploads the cover image, uses the returned `thumb_media_id`, builds a WeChat draft payload with formatted HTML, submits it, and rejects missing cover images.

- [x] **Step 2: Implement access-token and draft publishing service**

`WeChatDraftPublisher.fetch_access_token()` fetches an access token when `.env` does not provide one. `publish_wechat_draft()` uploads the cover, builds payload, and submits the draft.

- [x] **Step 3: Add CLI flags**

Added:

```bash
--submit-wechat-draft
--wechat-cover-image /path/to/cover.jpg
```

The command refuses to submit without a cover image path.

- [x] **Step 4: Verify**

Run:

```bash
cd content-agent
python3 -m unittest discover -s tests -v
```

Observed: 30 tests pass.

## Task 7: Replicate Cover Generation Before WeChat Upload

**Files:**
- Create: `content-agent/content_agent/cover_generation.py`
- Create: `content-agent/tests/test_cover_generation.py`
- Modify: `content-agent/content_agent/cli.py`
- Modify: `content-agent/content_agent/config.py`
- Modify: `content-agent/.env.example`
- Modify: `content-agent/README.md`

- [x] **Step 1: Write failing tests**

Tests assert that Replicate cover generation writes an image to disk, preserves output URL metadata, sets `REPLICATE_API_TOKEN` for the SDK, and allows draft submission with `--generate-cover` instead of `--wechat-cover-image`.

- [x] **Step 2: Implement Replicate cover generation**

`generate_cover_image()` supports SDK-style `replicate.run(model, input={...})` and an HTTP fallback if the SDK is not installed.

- [x] **Step 3: Wire CLI**

Added:

```bash
--generate-cover
```

When used with `--submit-wechat-draft`, the generated image path is passed directly to the WeChat thumb upload step.

- [x] **Step 4: Verify**

Run:

```bash
cd content-agent
python3 -m unittest discover -s tests -v
```

Observed: 34 tests pass.

## Git Note

The parent directory `/Users/bansen/www/bansen` is not a Git repository, so commit steps were not executed. Initialize Git or move this folder into an existing repository before using commit-based checkpoints.

## Self-Review

- Spec coverage: The plan covers keyword input, viral scoring, platform-specific content generation boundaries, Replicate image generation boundary, WeChat draft payload, Xiaohongshu publishing package, and Baijiahao reservation.
- Placeholder scan: No implementation step depends on unspecified secrets or hidden platform access.
- Type consistency: Tests and implementation use `CandidateContent`, `TopicScore`, `TopicBrief`, `WorkflowResult`, `expand_keywords`, `score_candidate`, and `run_keyword_workflow`.
