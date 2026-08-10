from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import zipfile

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps


CARD_SIZE = (1080, 1440)
MAX_POINT_CARDS = 5


@dataclass(frozen=True)
class XhsPoint:
    title: str
    detail: str


@dataclass(frozen=True)
class ParsedXhsNote:
    title: str
    intro: str
    body: str
    points: list[XhsPoint]
    tags: list[str]
    publish_text: str


@dataclass(frozen=True)
class XhsCard:
    index: int
    kind: str
    path: Path
    title: str

    def to_dict(self) -> dict:
        return {"index": self.index, "kind": self.kind, "path": str(self.path), "title": self.title}


@dataclass(frozen=True)
class XhsLayoutPackage:
    theme: str
    title: str
    body: str
    tags: list[str]
    publish_text: str
    cards: list[XhsCard]
    zip_path: Path

    def to_dict(self) -> dict:
        return {
            "theme": self.theme,
            "title": self.title,
            "body": self.body,
            "tags": list(self.tags),
            "publish_text": self.publish_text,
            "cards": [card.to_dict() for card in self.cards],
            "zip_path": str(self.zip_path),
        }


THEMES = {
    "fresh-green": {
        "background": "#EEF5EA",
        "surface": "#FFFFFF",
        "ink": "#18352C",
        "muted": "#587067",
        "accent": "#13966B",
        "soft": "#D7EBDD",
    },
    "warm-coral": {
        "background": "#FFF2EC",
        "surface": "#FFFDFC",
        "ink": "#442925",
        "muted": "#7E615B",
        "accent": "#D95E4F",
        "soft": "#F7D8CF",
    },
    "editorial-blue": {
        "background": "#EDF3F8",
        "surface": "#FFFFFF",
        "ink": "#162D3D",
        "muted": "#536B7A",
        "accent": "#267AA5",
        "soft": "#D4E6EF",
    },
}


def parse_xhs_note(markdown: str) -> ParsedXhsNote:
    text = _clean_markdown(markdown)
    title = _extract_title(text)
    body = _extract_section(text, "正文", ("封面图组", "标签"))
    if not body:
        body = _fallback_body(text)
    body = body.strip()
    points, intro = _extract_points(body)
    if not points:
        points = _paragraph_points(body)
        intro = ""
    tags = list(dict.fromkeys(re.findall(r"#[^#\s]+", text)))
    publish_parts = [title, body]
    if tags:
        publish_parts.append(" ".join(tags))
    publish_text = "\n\n".join(part.strip() for part in publish_parts if part.strip())
    return ParsedXhsNote(
        title=title,
        intro=intro,
        body=body,
        points=points[:MAX_POINT_CARDS],
        tags=tags,
        publish_text=publish_text,
    )


def render_xhs_package(
    markdown: str,
    output_dir: Path,
    basename: str,
    background_path: str | Path | None = None,
    theme: str = "fresh-green",
    package_id: str | None = None,
) -> XhsLayoutPackage:
    note = parse_xhs_note(markdown)
    selected_theme = _select_theme(theme, note)
    palette = THEMES[selected_theme]
    package_root = output_dir / _safe_basename(package_id) if package_id else output_dir
    package_dir = package_root / f"{_safe_basename(basename)}_xiaohongshu"
    package_dir.mkdir(parents=True, exist_ok=True)
    fonts = _load_fonts()
    cards: list[XhsCard] = []

    cover_path = package_dir / "01-cover.jpg"
    _render_cover(cover_path, note, palette, fonts, Path(background_path) if background_path else None)
    cards.append(XhsCard(index=1, kind="cover", path=cover_path, title=note.title))

    for offset, point in enumerate(note.points, start=2):
        point_path = package_dir / f"{offset:02d}-point.jpg"
        _render_point(point_path, note, point, offset - 1, len(note.points), palette, fonts)
        cards.append(XhsCard(index=offset, kind="point", path=point_path, title=point.title))

    tail_index = len(cards) + 1
    tail_path = package_dir / f"{tail_index:02d}-tail.jpg"
    _render_tail(tail_path, note, palette, fonts)
    cards.append(XhsCard(index=tail_index, kind="tail", path=tail_path, title="从一件小事开始"))

    copy_path = package_dir / "发布文案.txt"
    copy_path.write_text(note.publish_text, encoding="utf-8")
    zip_path = package_dir / "xiaohongshu-package.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for card in cards:
            archive.write(card.path, arcname=card.path.name)
        archive.write(copy_path, arcname=copy_path.name)

    return XhsLayoutPackage(
        theme=selected_theme,
        title=note.title,
        body=note.body,
        tags=note.tags,
        publish_text=note.publish_text,
        cards=cards,
        zip_path=zip_path,
    )


def _clean_markdown(markdown: str) -> str:
    text = markdown.strip()
    text = re.sub(r"^```(?:markdown)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text


def _extract_title(text: str) -> str:
    match = re.search(r"(?m)^\s*(?:#+\s*)?标题[：:]\s*(.+?)\s*$", text)
    if not match:
        match = re.search(r"(?m)^#\s+(.+?)\s*$", text)
    if not match:
        raise ValueError("小红书内容缺少标题")
    return _plain_text(match.group(1))


def _extract_section(text: str, heading: str, stops: tuple[str, ...]) -> str:
    start = re.search(rf"(?m)^\s*(?:#+\s*)?{re.escape(heading)}(?:[：:]\s*(.*?))?\s*$", text)
    if not start:
        return ""
    inline_content = (start.group(1) or "").strip()
    remainder = text[start.end():].lstrip("\r\n")
    if inline_content:
        remainder = f"{inline_content}\n{remainder}" if remainder else inline_content
    stop_pattern = "|".join(re.escape(item) for item in stops)
    stop = re.search(rf"(?m)^\s*(?:#+\s*)?(?:{stop_pattern})(?:[：:].*)?\s*$", remainder)
    return remainder[:stop.start()] if stop else remainder


def _fallback_body(text: str) -> str:
    text = re.sub(r"(?m)^\s*(?:#+\s*)?标题[：:].*$", "", text, count=1)
    text = re.split(r"(?m)^\s*(?:#+\s*)?(?:封面图组|标签)(?:[：:].*)?\s*$", text, maxsplit=1)[0]
    return text.strip()


def _extract_points(body: str) -> tuple[list[XhsPoint], str]:
    matches = list(re.finditer(r"(?m)^\s*(\d+)[.、]\s*(.+?)\s*$", body))
    if not matches:
        return [], body.strip()
    intro = body[:matches[0].start()].strip()
    points: list[XhsPoint] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        detail = body[match.end():end].strip()
        points.append(XhsPoint(title=_plain_text(match.group(2)), detail=_plain_text(detail)))
    return points, _plain_text(intro)


def _paragraph_points(body: str) -> list[XhsPoint]:
    paragraphs = [_plain_text(part) for part in re.split(r"\n\s*\n", body) if _plain_text(part)]
    points = []
    for paragraph in paragraphs[:3]:
        sentences = re.split(r"(?<=[。！？!?])", paragraph, maxsplit=1)
        points.append(XhsPoint(title=sentences[0][:24], detail="".join(sentences[1:]).strip()))
    return points


def _plain_text(text: str) -> str:
    clean = re.sub(r"[*_`>#]", "", text)
    return re.sub(r"\s+", " ", clean).strip()


def _select_theme(theme: str, note: ParsedXhsNote) -> str:
    if theme in THEMES:
        return theme
    content = f"{note.title} {note.body}"
    if any(word in content for word in ("宝妈", "妈妈", "女性", "情绪", "家庭")):
        return "warm-coral"
    if any(word in content for word in ("AI", "工具", "项目", "GitHub", "职场", "效率")):
        return "editorial-blue"
    return "fresh-green"


def _load_fonts() -> dict[str, ImageFont.FreeTypeFont]:
    font_path = _find_font_path()
    return {
        "display": ImageFont.truetype(font_path, 82),
        "title": ImageFont.truetype(font_path, 58),
        "body": ImageFont.truetype(font_path, 38),
        "small": ImageFont.truetype(font_path, 28),
        "number": ImageFont.truetype(font_path, 94),
    }


def _find_font_path() -> str:
    candidates = [
        os.environ.get("XHS_FONT_PATH", ""),
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    raise RuntimeError("未找到可用于小红书排版的字体，请安装 fonts-noto-cjk 或配置 XHS_FONT_PATH")


def _render_cover(path: Path, note: ParsedXhsNote, palette: dict, fonts: dict, background_path: Path | None) -> None:
    if background_path and background_path.exists():
        with Image.open(background_path) as source:
            image = ImageOps.fit(source.convert("RGB"), CARD_SIZE, method=Image.Resampling.LANCZOS)
        image = ImageEnhance.Color(image).enhance(0.88)
    else:
        image = Image.new("RGB", CARD_SIZE, palette["background"])
    overlay = Image.new("RGBA", CARD_SIZE, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rounded_rectangle((62, 710, 1018, 1358), radius=42, fill=(16, 28, 24, 205))
    image = Image.alpha_composite(image.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(image)
    draw.text((108, 770), "值得收藏的生活提案", font=fonts["small"], fill="#D8F2E6")
    _draw_wrapped(draw, note.title, (108, 842), 820, fonts["display"], "#FFFFFF", line_gap=22, max_lines=4)
    draw.rounded_rectangle((108, 1260, 290, 1272), radius=6, fill=palette["accent"])
    image.convert("RGB").save(path, format="JPEG", quality=95, optimize=True)


def _render_point(path: Path, note: ParsedXhsNote, point: XhsPoint, number: int, total: int, palette: dict, fonts: dict) -> None:
    image = Image.new("RGB", CARD_SIZE, palette["background"])
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((64, 64, 1016, 1376), radius=40, fill=palette["surface"])
    draw.text((112, 116), _short_topic(note.title), font=fonts["small"], fill=palette["muted"])
    draw.text((112, 238), f"{number:02d}", font=fonts["number"], fill=palette["accent"])
    draw.text((860, 146), f"{number} / {total}", font=fonts["small"], fill=palette["muted"])
    title_end = _draw_wrapped(draw, point.title, (112, 390), 840, fonts["title"], palette["ink"], line_gap=18, max_lines=3)
    draw.rounded_rectangle((112, title_end + 38, 230, title_end + 48), radius=5, fill=palette["accent"])
    _draw_wrapped(draw, point.detail or "把这件小事放进日常节奏里，慢慢坚持就好。", (112, title_end + 102), 836, fonts["body"], palette["muted"], line_gap=20, max_lines=8)
    draw.rounded_rectangle((112, 1278, 968, 1282), radius=2, fill=palette["soft"])
    draw.text((112, 1310), "日常习惯 · 从舒服和可持续开始", font=fonts["small"], fill=palette["muted"])
    image.save(path, format="JPEG", quality=95, optimize=True)


def _render_tail(path: Path, note: ParsedXhsNote, palette: dict, fonts: dict) -> None:
    image = Image.new("RGB", CARD_SIZE, palette["accent"])
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((72, 72, 1008, 1368), radius=44, fill=palette["surface"])
    draw.ellipse((112, 132, 184, 204), fill=palette["soft"])
    draw.text((112, 292), "从一件小事开始", font=fonts["display"], fill=palette["ink"])
    summary = note.intro or "不用一下子改变很多，选一件今天就能做到的小事，放进自己的生活节奏里。"
    _draw_wrapped(draw, summary, (112, 484), 824, fonts["body"], palette["muted"], line_gap=24, max_lines=7)
    draw.rounded_rectangle((112, 1112, 968, 1254), radius=30, fill=palette["background"])
    draw.text((178, 1156), "先收藏，今晚挑一件试试", font=fonts["title"], fill=palette["accent"])
    image.save(path, format="JPEG", quality=95, optimize=True)


def _draw_wrapped(draw: ImageDraw.ImageDraw, text: str, position: tuple[int, int], max_width: int, font: ImageFont.FreeTypeFont, fill: str, line_gap: int, max_lines: int) -> int:
    lines = _wrap_text(draw, text, font, max_width)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip("，。；、 ") + "..."
    x, y = position
    line_height = font.size + line_gap
    for index, line in enumerate(lines):
        draw.text((x, y + index * line_height), line, font=font, fill=fill)
    return y + len(lines) * line_height


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    normalized = _plain_text(text)
    if not normalized:
        return [""]
    lines: list[str] = []
    current = ""
    for character in normalized:
        candidate = current + character
        if current and draw.textlength(candidate, font=font) > max_width:
            lines.append(current)
            current = character
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _short_topic(title: str) -> str:
    clean = re.sub(r"[，,：:。！？!?].*$", "", title)
    return clean[:18] or "生活提案"


def _safe_basename(value: str) -> str:
    clean = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", value.strip(), flags=re.UNICODE).strip("-")
    return clean[:60] or "xiaohongshu"
