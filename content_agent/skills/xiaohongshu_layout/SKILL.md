---
name: xiaohongshu_layout
description: Use when a Xiaohongshu note needs visual pagination, a 3:4 cover, content cards, a final card, preview assets, or a downloadable manual-publishing package.
---

# Xiaohongshu Layout Skill

Turn a finished Xiaohongshu note into a readable image sequence. Keep content decisions in the note and visual decisions in the layout package.

## Core Rules

- Use 3:4 portrait images at 1080 x 1440.
- Generate one cover, one card per main numbered point, and one final card.
- Keep the sequence between 4 and 7 cards. Use at most five point cards.
- Let Replicate provide a topic-specific background image, but render all Chinese text deterministically.
- Keep every card understandable on its own while preserving a clear reading sequence.
- Exclude layout instructions and the `封面图组` section from publishable copy.

## Card Roles

### Cover

- Use the final title as the main hook.
- Keep the title to four lines or fewer.
- Preserve the meaningful subject of the background image and add contrast behind text.
- Do not show URLs, source titles, or instructions from the user's prompt.

### Point Cards

- Match one card to one numbered body point.
- Use the point heading as the visual headline and its explanation as supporting copy.
- Prefer one useful idea per card; do not repeat the same advice with different wording.
- Truncate overflow instead of shrinking text until it becomes unreadable.

### Final Card

- Summarize the note's practical value.
- Use a gentle save or action cue, not an engagement demand.
- Do not add medical promises, income guarantees, or artificial urgency.

## Theme Selection

- `fresh-green`: health, routines, workplace wellness, calm daily life.
- `warm-coral`: women, moms, home life, emotional resonance.
- `editorial-blue`: tools, projects, knowledge sharing, professional topics.

Use the selected UI style when provided. Otherwise infer the closest theme from the title and note body.

## Publishing Package

Return assets in reading order and include clean publishable text separately. The package must contain:

- `01-cover.jpg`
- sequential point cards
- one final card
- `发布文案.txt`
- a ZIP archive containing all files

