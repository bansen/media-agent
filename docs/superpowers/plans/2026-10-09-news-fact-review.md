# News fact review implementation plan

Approved by the user in this conversation: preserve URL-only input, remove minimum length, ground all claims in retrieved sources, independently review final title/body, allow one targeted repair, then stop on failure before images or publishing.

**Architecture:** A small independent reviewer consumes source title/URL/body and the final article, never the editorial plan. Strict JSON findings quote the article and supporting source; malformed responses and provider failures block advancement. Deterministic score checks supplement semantic review. Versioned hashes bind a review to source and article. Submission independently reviews the actual rendered/imported HTML text, links and published title; legacy or changed HTML must be checked before publication. Failures retain draft and findings. Existing WeChat credentials and model stay unchanged.

**Scope:** WeChat generation, web steps and CLI publishing, source extraction, regression tests. No editor, model migration, or new user-facing input. No new public publication. Existing successful drafts are untouched.

## Tasks

- [x] Add regression tests for score arithmetic, altered scope, invented causality, malformed/unsupported review evidence, valid concise articles, and one-repair maximum. Run the new tests and confirm failures before implementation.
- [x] Implement `content_agent/fact_review.py` and conservative arithmetic rules in `factual_guard.py`; integrate final-title review and targeted repair into `generation.py`. Retain rejected drafts and review reports.
- [x] Remove minimum-length and sensationalism instructions from the bundled WeChat skill/prompt; make original source override the editorial plan.
- [x] Prefer article body in `collectors/source_urls.py`, remove recommendation/advertising blocks, and preserve paragraph breaks. Test valid body text, inline words, fallback extraction and malformed markup.
- [x] Gate web/CLI cover and submission flows on a current review. Include external HTML and resumed legacy tasks; reject tampered/missing evidence. Persist failures without keeping stale previews as publishable.
- [x] Update existing fake providers to explicitly answer independent review prompts. Add workflow tests proving rejected drafts never invoke image/publish services and that changed source/body invalidates review.
- [ ] Run `python3 -m unittest discover -s tests -v`. Run read-only live review against the three captured failures and valid source-grounded short drafts; do not publish during verification. Review diff, commit and deploy using existing authorized CI/CD flow, then verify deployment and read-only behavior.

## Acceptance

`5-11,12-10,9-11,11-9,11-7` cannot support “11-7 is the largest margin”. “No reports among institute staff” cannot become “no cases among all contacts”. Daily market moves cannot establish capital flows. Missing review, invalid JSON, unrelated evidence, provider failures and modified HTML cannot silently count as passed. A corrected draft gets one final audit; a second failure stops before image generation and records a reason.

## Verification record

- Local suite: 266 tests passed; whitespace check passed.
- Independent code review identified omitted HTML head-end handling and incomplete cached-evidence validation; both fixed with regressions.
- Live historical-draft model review awaits explicit transmission approval after automatic approval review rejected the initial request. No historical draft was sent by that rejected command.
- Deployment pending final commit and CI/CD.
