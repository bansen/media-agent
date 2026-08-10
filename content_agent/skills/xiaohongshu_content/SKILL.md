---
name: xiaohongshu_content
description: Generate high-quality Xiaohongshu notes for health, lifestyle, women, moms, workplace, tools, and content-sharing topics. Use this skill whenever the product generates Xiaohongshu titles, note copy, cover-card plans, hashtags, or summarizes viral note patterns for reuse.
---

# Xiaohongshu Content Skill

Use this skill to turn a user prompt plus search/material notes into a Xiaohongshu publishing package. The goal is not to copy viral posts, but to extract reusable hooks, reader pain points, structure, and visual logic.

## Operating Principle

Write like a useful creator with real experience. Avoid stiff article tone, exaggerated marketing, and generic advice. Every note should make the reader feel: "This is about my daily life, I can try one thing today, and it is worth saving."

## Input Interpretation

Treat the user input as a creative brief, not a keyword. Extract:

- Topic: what the note is really about.
- Audience: who should feel seen.
- Scenario: where the problem appears in daily life.
- Promise: what the reader can get after reading.
- Boundary: what cannot be claimed, especially for health content.

If source materials are provided, summarize them into:

- Viral hooks: title patterns, first-line hooks, conflict, contrast, or curiosity.
- Reader pains: anxiety, inconvenience, decision difficulty, or hidden misunderstanding.
- Useful details: concrete steps, examples, habits, products, or checks.
- Reusable angle: what can be transformed into an original note.

Do not copy source wording. Rewrite into the account's own angle.

## Title Rules

Generate titles before writing the body. A good title should be short, specific, and save-worthy.

Use 6-8 candidates internally and choose the best one. Prefer these hook types:

- Scenario hook: "上班久坐的人，先把这 4 件小事做起来"
- Benefit hook: "每天 10 分钟，把睡前状态慢慢调回来"
- Mistake hook: "别把养生复杂化，这 3 件事更适合新手"
- Identity hook: "宝妈也能坚持的低成本放松清单"
- Checklist hook: "职场女性可收藏的低成本习惯清单"

Avoid:

- Medical promises such as cure, treatment, diagnosis, symptom elimination.
- Income guarantees or miracle claims.
- Raw links, source titles, or user instruction fragments.
- Over-fixed templates such as always using "3 个关键问题".

## Note Structure

Use this structure for health/lifestyle notes:

1. First line: one daily-life scene or emotional hook.
2. Why it matters: explain the hidden pain in 1-2 short paragraphs.
3. Useful list: give 3-5 concrete actions, each with when to use it.
4. Boundary: clarify who should be careful and what the note cannot replace.
5. Save/comment ending: invite readers to save, comment their scenario, or pick one habit to start.

For tool/project sharing notes:

1. First line: the problem the tool solves, not the link.
2. What it is: one-sentence positioning.
3. Why it is useful: 3 concrete use cases.
4. Who should try it: suitable and unsuitable users.
5. Link or project name: place only at the end if needed.

## Writing Style

- Use short paragraphs.
- Use "你" sparingly and naturally.
- Prefer concrete scenes over abstract claims.
- Keep each bullet distinct; no repeated advice in different wording.
- Make the note feel handwritten but not messy.
- Use light emotional resonance, not anxiety.

## Cover Card Plan

Always produce a cover plan for manual design or image generation:

- First image: title hook, visual subject, style direction.
- Card 2-5: match the number of body points. If there are 4 methods, plan 4 method cards.
- Final card: summary, save reminder, or gentle comment prompt.

Cover style should match the topic:

- Health/lifestyle: bright real-life scene, warm daylight, clean home or workplace corner.
- Workplace women: tidy desk, water bottle, stretching break, soft color contrast.
- Moms: lived-in home corner, calm bedtime or morning routine, no staged perfection.
- Tool/project: product workflow, task board, app interface abstraction, no raw URL.

Avoid blank white rectangles, poster boards, tiny unreadable text, medical icons, exaggerated before-after effects, and generic office photos when the topic has a more specific scene.

## Output Format

Return only the Xiaohongshu package in Markdown:

```markdown
标题：...

正文：
...

封面图组：
1. 首图：...
2. ...

标签：
#标签1 #标签2 #标签3
```

## Compliance

For health content, never diagnose, prescribe, promise treatment, claim cure, or imply guaranteed physical results. Use "日常习惯", "可以试试", "不适及时咨询专业人士" when needed.
