from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[2] / ".agents" / "skills" / "gzh-design"


@dataclass(frozen=True)
class GzhOutputPaths:
    clean_html: Path
    preview_html: Path


THEME_LABELS = {
    "moyu-green": "摸鱼绿(moyu-green)",
    "tech-blue": "科技蓝(tech-blue)",
    "minimal-mono": "极简黑白(minimal-mono)",
    "warm-card": "暖色知识卡(warm-card)",
}

THEME_PALETTES = {
    "moyu-green": {},
    "tech-blue": {
        "#059669": "#2563EB",
        "#10B981": "#38BDF8",
        "#34D399": "#60A5FA",
        "#BBF7D0": "#BFDBFE",
        "#F0FDF4": "#EFF6FF",
        "#A7F3D0": "#93C5FD",
        "#FDE68A": "#DBEAFE",
    },
    "minimal-mono": {
        "#059669": "#111827",
        "#10B981": "#4B5563",
        "#34D399": "#6B7280",
        "#BBF7D0": "#D1D5DB",
        "#F0FDF4": "#F9FAFB",
        "#A7F3D0": "#9CA3AF",
        "#FDE68A": "#E5E7EB",
    },
    "warm-card": {
        "#059669": "#B45309",
        "#10B981": "#F59E0B",
        "#34D399": "#FBBF24",
        "#BBF7D0": "#FED7AA",
        "#F0FDF4": "#FFF7ED",
        "#A7F3D0": "#FDBA74",
        "#FDE68A": "#FEF3C7",
    },
}


def format_wechat_markdown(markdown: str, theme: str = "moyu-green") -> str:
    theme = normalize_theme(theme)
    document = _parse_markdown(_sanitize_publish_markdown(markdown))
    title = document["title"] or "公众号文章"
    sections = document["sections"] or [{"title": "正文", "blocks": document["intro_blocks"]}]
    intro_blocks = document["intro_blocks"] if document["sections"] else []

    parts = [_container_start()]
    parts.append(_cover(title, sections))
    if intro_blocks:
        parts.extend(_render_block(block, index=0) for block in intro_blocks)
    if len(sections) >= 2:
        parts.append(_toc(sections))
    for index, section in enumerate(sections, start=1):
        is_last = index == len(sections) and _is_conclusion(section["title"])
        parts.append(_chapter_title(section["title"], index, is_last=is_last))
        for block in section["blocks"]:
            parts.append(_render_block(block, index=index))
    parts.append(_signature())
    parts.append(_footer_cta())
    parts.append("</section>")
    return _apply_theme("\n".join(part for part in parts if part), theme)


def normalize_theme(theme: str) -> str:
    normalized = (theme or "moyu-green").strip()
    if normalized not in THEME_LABELS:
        raise ValueError(f"unsupported gzh theme: {theme}")
    return normalized


def theme_label(theme: str) -> str:
    return THEME_LABELS[normalize_theme(theme)]


def _apply_theme(html: str, theme: str) -> str:
    for source, target in THEME_PALETTES[theme].items():
        html = html.replace(source, target)
    return html


def _sanitize_publish_markdown(markdown: str) -> str:
    replacements = {
        "关注我，每天分享一个 AI 副业避坑指南": "关注我，一起拆解 AI 工具、副业实践和普通人的学习路径",
        "关注我，每天分享一个AI副业避坑指南": "关注我，一起拆解 AI 工具、副业实践和普通人的学习路径",
    }
    sanitized = markdown
    for source, target in replacements.items():
        sanitized = sanitized.replace(source, target)
    return sanitized


def write_gzh_outputs(html: str, output_dir: Path, basename: str, theme: str = "moyu-green") -> GzhOutputPaths:
    output_dir.mkdir(parents=True, exist_ok=True)
    label = theme_label(theme)
    clean_html = output_dir / f"{basename}_排版_{label}.html"
    preview_html = output_dir / f"{basename}_排版_{label}_预览.html"
    clean_html.write_text(html, encoding="utf-8")
    subprocess.run(
        ["python3", str(SKILL_ROOT / "scripts" / "wrap_preview.py"), str(clean_html), str(preview_html)],
        check=True,
        text=True,
        capture_output=True,
    )
    return GzhOutputPaths(clean_html=clean_html, preview_html=preview_html)


def _parse_markdown(markdown: str) -> dict:
    lines = [line.rstrip() for line in markdown.strip().splitlines()]
    title = ""
    intro_blocks: list[dict] = []
    sections: list[dict] = []
    current = None
    paragraph: list[str] = []
    ordered_items: list[str] = []

    def flush_paragraph():
        nonlocal paragraph
        if paragraph:
            _append_block({"type": "paragraph", "text": " ".join(paragraph).strip()})
            paragraph = []

    def flush_ordered():
        nonlocal ordered_items
        if ordered_items:
            _append_block({"type": "ordered_list", "items": ordered_items})
            ordered_items = []

    def _append_block(block: dict):
        if current is None:
            intro_blocks.append(block)
        else:
            current["blocks"].append(block)

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            flush_ordered()
            continue
        if stripped.startswith("# "):
            flush_paragraph()
            flush_ordered()
            title = stripped[2:].strip()
            continue
        if stripped.startswith("## "):
            flush_paragraph()
            flush_ordered()
            current = {"title": stripped[3:].strip(), "blocks": []}
            sections.append(current)
            continue
        if stripped.startswith("### "):
            flush_paragraph()
            flush_ordered()
            _append_block({"type": "subtitle", "text": stripped[4:].strip()})
            continue
        if stripped.startswith("> "):
            flush_paragraph()
            flush_ordered()
            _append_block({"type": "quote", "text": stripped[2:].strip()})
            continue
        ordered_match = re.match(r"^\d+\.\s+(.+)$", stripped)
        if ordered_match:
            flush_paragraph()
            ordered_items.append(ordered_match.group(1).strip())
            continue
        flush_ordered()
        paragraph.append(stripped)

    flush_paragraph()
    flush_ordered()
    return {"title": title, "intro_blocks": intro_blocks, "sections": sections}


def _container_start() -> str:
    return (
        '<section style="max-width:677px;margin:0 auto;background:#ffffff;'
        "font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;"
        'color:#374151;line-height:1.75;letter-spacing:0.5px;overflow-x:hidden;">'
    )


def _cover(title: str, sections: list[dict]) -> str:
    first, second = _split_title(title)
    cover_label = _cover_label(title)
    subtitle = _cover_subtitle(sections)
    subtitle_html = (
        f'''<p style="font-size:13px;color:#9CA3AF;margin:0;line-height:1.7;letter-spacing:0.5px;">
        <span leaf="">{_text(subtitle)}</span>
      </p>'''
        if subtitle
        else ""
    )
    return f"""
<section style="margin:0 0 32px;background:#fff;border:1.5px solid rgba(5,150,105,0.15);border-radius:20px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.06);width:100%;">
  <section style="padding:32px 28px 28px;">
    <section style="display:flex;align-items:center;gap:8px;margin-bottom:28px;">
      <span style="width:6px;height:6px;background:#059669;border-radius:50%;"><span leaf=""><br></span></span>
      <span style="font-size:11px;font-weight:700;letter-spacing:3px;color:#059669;"><span leaf="">TUTORIAL</span></span>
      <section style="flex:1;height:1px;overflow:hidden;background:linear-gradient(to right,rgba(5,150,105,0.12),transparent);"><span leaf=""><br></span></section>
      <span style="font-size:10px;color:#D1D5DB;font-weight:600;"><span leaf="">{datetime.now().strftime('%Y.%m')}</span></span>
    </section>
    <section>
      <p style="font-size:24px;font-weight:900;color:#111827;margin:0;line-height:1.16;letter-spacing:0;">
        <span leaf="">{_text(first)}</span>
      </p>
      <p style="font-size:24px;font-weight:900;color:#059669;margin:0 0 16px;line-height:1.16;letter-spacing:0;">
        <span leaf="">{_text(second)}</span>
      </p>
      <section style="width:48px;height:3px;background:linear-gradient(to right,#059669,#34D399);border-radius:2px;margin-bottom:12px;">
        <span leaf=""><br></span>
      </section>
      {subtitle_html}
    </section>
  </section>
  <section style="background:linear-gradient(135deg,#059669,#10B981);padding:12px 28px;display:flex;align-items:center;justify-content:space-between;">
    <p style="font-size:12px;color:rgba(255,255,255,0.9);margin:0;font-weight:600;letter-spacing:0.5px;">
      <span leaf="">{_text(cover_label)}</span>
    </p>
    <section style="display:flex;gap:4px;">
      <span style="background:rgba(255,255,255,0.2);padding:1px 6px;border-radius:3px;font-size:8px;color:#fff;font-weight:600;"><span leaf="">AI</span></span>
      <span style="background:rgba(255,255,255,0.2);padding:1px 6px;border-radius:3px;font-size:8px;color:#fff;font-weight:600;"><span leaf="">SIDE</span></span>
    </section>
  </section>
</section>""".strip()


def _cover_subtitle(sections: list[dict]) -> str:
    """Use an article-specific section as the cover context, when available."""
    generic_titles = {"正文", "写在最后", "结语", "总结", "总结与行动"}
    for section in sections:
        title = str(section.get("title", "")).strip()
        if title and title not in generic_titles:
            return f"本文拆解：{title}"
    return ""


def _toc(sections: list[dict]) -> str:
    cards = []
    for index, section in enumerate(sections, start=1):
        part_label = f"PART {index:02d}"
        if index == 1:
            cards.append(
                f"""
    <section style="display:inline-block;white-space:normal;vertical-align:top;width:110px;background:linear-gradient(135deg,#059669,#10B981);border-radius:12px;padding:12px;margin-right:8px;">
      <p style="font-size:9px;font-weight:700;color:rgba(255,255,255,0.7);letter-spacing:1px;margin:0 0 5px;"><span leaf="">{part_label}</span></p>
      <p style="font-size:13px;font-weight:800;color:#fff;margin:0 0 3px;"><span leaf="">{_text(section["title"])}</span></p>
      <p style="font-size:10px;color:rgba(255,255,255,0.7);margin:0;"><span leaf="">KEY POINT</span></p>
    </section>""".strip()
            )
        else:
            cards.append(
                f"""
    <section style="display:inline-block;white-space:normal;vertical-align:top;width:110px;background:#fff;border:1px solid #E5E7EB;border-radius:12px;padding:12px;margin-right:8px;box-shadow:0 2px 6px rgba(0,0,0,0.04);">
      <p style="font-size:9px;font-weight:700;color:#9CA3AF;letter-spacing:1px;margin:0 0 5px;"><span leaf="">{part_label}</span></p>
      <p style="font-size:13px;font-weight:800;color:#111827;margin:0 0 3px;"><span leaf="">{_text(section["title"])}</span></p>
      <p style="font-size:10px;color:#9CA3AF;margin:0;"><span leaf="">KEY POINT</span></p>
    </section>""".strip()
            )
    return f"""
<section style="margin:0 20px 32px;">
  <section style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
    <p style="font-size:10px;color:#9CA3AF;margin:0;text-transform:uppercase;letter-spacing:2px;font-weight:600;"><span leaf="">📦 {len(sections)} Parts</span></p>
    <p style="font-size:10px;color:#9CA3AF;margin:0;"><span leaf="">👉 滑动</span></p>
  </section>
  <section style="overflow-x:scroll;-webkit-overflow-scrolling:touch;white-space:nowrap;padding-bottom:8px;">
{chr(10).join(cards)}
  </section>
</section>""".strip()


def _chapter_title(title: str, index: int, is_last: bool = False) -> str:
    number = "///" if is_last else f"{index:02d}"
    label = "LAST" if is_last else "PART"
    margin_top = "16px" if index == 1 else "48px"
    english = _english_label(title)
    return f"""
<section style="margin-top:{margin_top};margin-bottom:32px;padding:0 20px;">
  <section style="display:flex;align-items:center;gap:16px;margin-bottom:24px;">
    <section style="text-align:center;flex-shrink:0;">
      <p style="margin:0;font-size:28px;font-weight:900;color:#059669;line-height:1;letter-spacing:0;">
        <span leaf="">{number}</span>
      </p>
      <p style="margin:0;font-size:8px;font-weight:700;color:#D1D5DB;letter-spacing:2px;">
        <span leaf="">{label}</span>
      </p>
    </section>
    <span style="width:1px;height:36px;background:#E5E7EB;flex-shrink:0;"><span leaf=""><br></span></span>
    <section>
      <p style="margin:0 0 1px;font-size:17px;font-weight:900;color:#111827;letter-spacing:0.3px;">
        <span leaf="">{_text(title)}</span>
      </p>
      <p style="margin:0;font-size:11px;font-weight:600;color:#9CA3AF;letter-spacing:1.5px;">
        <span leaf="">{english}</span>
      </p>
    </section>
  </section>
</section>""".strip()


def _render_block(block: dict, index: int) -> str:
    kind = block["type"]
    if kind == "paragraph":
        return _paragraph(block["text"])
    if kind == "subtitle":
        return _subtitle(block["text"])
    if kind == "quote":
        return _quote(block["text"])
    if kind == "ordered_list":
        return _ordered_list(block["items"])
    raise ValueError(f"Unknown block type: {kind}")


def _paragraph(text: str) -> str:
    return (
        '<p style="margin:0 20px 16px;font-size:14px;line-height:1.9;text-align:justify;">'
        f"{_inline(text)}"
        "</p>"
    )


def _subtitle(text: str) -> str:
    return (
        '<p style="font-size:15px;font-weight:900;color:#111827;margin:0 20px 16px;">'
        f'<span style="background:linear-gradient(180deg,transparent 65%,#FDE68A 65%);padding:0 4px;"><span leaf="">{_text(text)}</span></span>'
        "</p>"
    )


def _quote(text: str) -> str:
    return (
        '<section style="background:#FFF;border:1px dashed #BBF7D0;border-radius:8px;padding:14px 16px;margin:0 20px 24px;text-align:center;">'
        '<p style="margin:0;line-height:1.6;">'
        f'<span style="font-size:15px;color:#059669;font-weight:bold;border-bottom:3px solid #FDE68A;padding-bottom:2px;"><span leaf="">{_text(text)}</span></span>'
        "</p></section>"
    )


def _ordered_list(items: list[str]) -> str:
    rendered = []
    for index, item in enumerate(items, start=1):
        rendered.append(
            f"""
  <section style="display:flex;align-items:flex-start;gap:10px;margin-bottom:12px;">
    <span style="display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;background:#059669;color:#fff;font-size:11px;font-weight:700;border-radius:50%;flex-shrink:0;margin-top:2px;"><span leaf="">{index}</span></span>
    <p style="font-size:14px;color:#374151;margin:0;line-height:1.9;flex:1;">
      {_inline(item)}
    </p>
  </section>""".strip()
        )
    return '<section style="margin:0 20px 24px;">\n' + "\n".join(rendered) + "\n</section>"


def _signature() -> str:
    return (
        '<p style="margin:0 20px 16px;font-size:14px;line-height:1.9;text-align:justify;">'
        '<span leaf="">这里持续分享 AI 工具、副业实践和学习方法，陪你把想法落到可执行的小步骤。</span>'
        "</p>"
    )


def _footer_cta() -> str:
    return """
<section style="background:#F0FDF4;padding:16px 20px;border-radius:12px;border:1px solid #BBF7D0;margin:0 20px 24px;text-align:center;">
  <p style="font-size:13px;color:#374151;margin:0;line-height:1.8;">
    <span leaf="">如果你觉得今天这篇有收获，欢迎点赞、在看、转发三连，我们下篇见</span>
  </p>
</section>""".strip()


def _inline(text: str) -> str:
    normalized = _normalize_punctuation(text)
    tokens = re.split(r"(\*\*.+?\*\*|==.+?==|`.+?`|<u>.+?</u>|\+\+.+?\+\+)", normalized)
    parts = []
    underlined = False
    for token in tokens:
        if not token:
            continue
        if token.startswith("**") and token.endswith("**"):
            parts.append(f'<strong style="color:#059669;"><span leaf="">{_text(token[2:-2])}</span></strong>')
        elif token.startswith("==") and token.endswith("=="):
            parts.append(
                '<span style="background:linear-gradient(120deg,#FDE68A 0%,rgba(255,255,255,0) 100%);padding:0 4px;border-radius:2px;font-weight:600;color:#111827;">'
                f'<span leaf="">{_text(token[2:-2])}</span></span>'
            )
        elif token.startswith("`") and token.endswith("`"):
            parts.append(
                '<span style="background:#F3F4F6;color:#1F2937;padding:2px 6px;border-radius:4px;font-size:13px;font-weight:600;">'
                f'<span leaf="">{escape(token[1:-1])}</span></span>'
            )
        elif token.startswith("<u>") and token.endswith("</u>"):
            parts.append(_underline(token[3:-4]))
            underlined = True
        elif token.startswith("++") and token.endswith("++"):
            parts.append(_underline(token[2:-2]))
            underlined = True
        else:
            if not underlined:
                marked = _auto_underline_first_phrase(token)
                parts.append(marked)
                underlined = marked != _leaf(token)
            else:
                parts.append(_leaf(token))
    return "".join(parts)


def _auto_underline_first_phrase(text: str) -> str:
    phrases = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{4,15}", text)
    if not phrases:
        return _leaf(text)
    phrase = phrases[0]
    before, _, after = text.partition(phrase)
    return _leaf(before) + _underline(phrase) + _leaf(after)


def _underline(text: str) -> str:
    return f'<span style="border-bottom:2px solid #A7F3D0;font-weight:600;"><span leaf="">{_text(text)}</span></span>'


def _leaf(text: str) -> str:
    if not text:
        return ""
    return f'<span leaf="">{_text(text)}</span>'


def _text(text: str) -> str:
    return escape(_normalize_punctuation(text), quote=False)


def _normalize_punctuation(text: str) -> str:
    return (
        text.replace(",", "，")
        .replace(";", "；")
        .replace("!", "！")
        .replace("?", "？")
        .replace(":", "：")
        .replace('"', "”")
        .replace("'", "’")
    )


def _split_title(title: str) -> tuple[str, str]:
    clean = title.strip()
    if len(clean) <= 12:
        return clean, "方法拆解"
    return clean[:12], clean[12:] or "方法拆解"


def _cover_label(title: str) -> str:
    if _contains_any(title, ["MiniMax", "DeepSeek", "GPT", "Claude", "H3", "大模型", "模型"]):
        return "AI 模型观察"
    if _contains_any(title, ["工具", "提示词", "教程", "场景"]):
        return "AI 工具实战"
    if _contains_any(title, ["副业", "接单", "变现", "赚钱"]):
        return "AI 副业实践"
    if _contains_any(title, ["养生", "健康", "久坐", "睡前"]):
        return "健康生活清单"
    return "AI 实用观察"


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _english_label(title: str) -> str:
    if "总结" in title or "最后" in title:
        return "SUMMARY"
    if "工具" in title:
        return "TOOLS"
    if "案例" in title:
        return "CASE STUDY"
    if "步骤" in title or "方法" in title:
        return "METHOD"
    return "KEY POINT"


def _is_conclusion(title: str) -> bool:
    return any(word in title for word in ["结语", "总结", "最后", "写在最后"])
