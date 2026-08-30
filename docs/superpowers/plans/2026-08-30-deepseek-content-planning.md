# DeepSeek Content Planning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development to implement this plan task-by-task.

**Goal:** Use DeepSeek to derive Chinese titles and a shared content plan from source material before generating channel content.

**Architecture:** Add a focused LLM planning module that validates structured JSON, then apply its selected title and plan to the immutable workflow result. Web and CLI orchestration call planning before draft generation; draft prompts consume the persisted plan and existing channel Skills.

**Tech Stack:** Python 3.13, DeepSeek OpenAI-compatible API, dataclasses, unittest, existing WebSearch and content Skills.

---

### Task 1: Define and validate the LLM content plan

**Files:**
- Create: `content_agent/llm_content_planner.py`
- Create: `tests/test_llm_content_planner.py`

- [ ] Write failing tests for prompt grounding, JSON code-block parsing, required fields, Chinese titles, forbidden template phrases and title limits.
- [ ] Run the focused tests and confirm they fail because the planning module is missing.
- [ ] Implement the immutable plan model, prompt builder, parser and validation.
- [ ] Run focused tests until they pass.

### Task 2: Apply the plan to all generated assets

**Files:**
- Modify: `content_agent/models.py`
- Modify: `content_agent/workflow.py`
- Modify: `content_agent/prompts.py`
- Test: `tests/test_llm_content_planner.py`

- [ ] Write a failing test showing the selected LLM title replaces the rule title and rebuilds outline, title candidates and cover prompt.
- [ ] Add `content_plan` to `WorkflowResult` and implement a pure apply function.
- [ ] Rebuild channel outputs from the updated topic and plan.
- [ ] Run focused tests until they pass.

### Task 3: Generate content from the shared plan

**Files:**
- Modify: `content_agent/generation.py`
- Modify: `tests/test_generation.py`

- [ ] Write failing tests requiring the content prompt to contain the persisted plan and `wechat-write` Skill.
- [ ] Require a plan for LLM draft generation and include its facts and structure in the prompt.
- [ ] Keep final heading enforcement tied to the LLM-selected title.
- [ ] Run generation tests until they pass.

### Task 4: Integrate Web and CLI orchestration

**Files:**
- Modify: `content_agent/web.py`
- Modify: `content_agent/cli.py`
- Modify: `tests/test_web.py`
- Modify: `tests/test_providers_cli.py`

- [ ] Write failing tests for two LLM calls in one-click generation and one planning call in the materials step.
- [ ] Call DeepSeek planning after deterministic material selection and before draft generation.
- [ ] Persist and restore `content_plan`; make the UI materials request enable LLM.
- [ ] Apply the same two-stage behavior to CLI `--use-llm`.
- [ ] Run Web and CLI tests until they pass.

### Task 5: Verify and deploy

**Files:**
- No production file changes expected.

- [ ] Run `python3 -m unittest discover -s tests -v`.
- [ ] Run `git diff --check` and inspect the final diff.
- [ ] Commit and push `main`.
- [ ] Confirm GitHub Actions succeeds and production returns HTTP 200.
