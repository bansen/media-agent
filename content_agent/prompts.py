from __future__ import annotations

from .models import TopicBrief


COVER_STYLE_GUIDANCE = {
    "business-tech": "full-bleed business technology editorial photo, sharp focus, high-resolution, clean modern lighting",
    "real-photo": "realistic lifestyle photography, natural light, sharp focus, high-resolution, believable daily scene",
    "minimal-illustration": "minimal editorial illustration, refined shapes, high-resolution, clean composition, soft depth",
    "knowledge-card": "knowledge-sharing cover image, clear subject hierarchy, sharp focus, high-resolution, editorial composition",
}


def build_wechat_outline(topic: TopicBrief) -> str:
    return "\n".join(
        [
            f"公众号文章：《{topic.optimized_title}》",
            "定位：写给想做副业的打工族或待业者。",
            "结构：痛点开场 -> 真实案例 -> 方法拆解 -> 避坑提醒 -> 行动清单。",
            f"角度：{topic.angle}",
            "合规：不承诺收益，不制造暴富焦虑，所有案例需标注来源或改为匿名经验。",
        ]
    )


def build_xhs_package(topic: TopicBrief) -> str:
    return "\n".join(
        [
            f"小红书标题：{topic.optimized_title}",
            "小红书正文：",
            "1. 先写一个生活场景痛点。",
            "2. 给出 3-5 条可收藏的小方法。",
            "3. 用个人体验语气收尾，引导评论补充。",
            "标签：#职场女性 #宝妈 #健康养生 #生活习惯 #低成本养生",
            "提示：避免医疗诊断、治疗承诺和夸大功效。",
        ]
    )


def build_cover_prompt(topic: TopicBrief, channel: str = "wechat") -> str:
    style = _cover_style_for(topic, channel)
    return (
        "Replicate image prompt: "
        f"{style}. Main idea: {topic.optimized_title}. "
        "Use a complete background scene with balanced composition and subtle clear area formed by natural lighting only. "
        "No text, no blank white rectangle, no paper sheet, no poster board, no floating card, "
        "no money piles, no medical claims, no exaggerated symbols."
    )


def apply_cover_style(base_style: str, cover_style: str = "business-tech") -> str:
    selected = (cover_style or "business-tech").strip()
    if selected not in COVER_STYLE_GUIDANCE:
        raise ValueError(f"unsupported cover style: {cover_style}")
    return f"{COVER_STYLE_GUIDANCE[selected]}, {base_style}"


def _cover_style_for(topic: TopicBrief, channel: str) -> str:
    title = f"{topic.title} {topic.optimized_title} {topic.angle}"
    ratio = "4:5 vertical social cover" if channel == "xiaohongshu" else "16:9 wide cover"

    if _contains_any(title, ["久坐", "办公室", "肩颈", "腰背"]):
        return (
            f"office wellness break, bright lifestyle photo, calm workplace corner, "
            f"ergonomic chair, water bottle, soft morning daylight, {ratio}"
        )
    if _contains_any(title, ["睡前", "放松", "睡眠", "熬夜"]):
        return (
            f"calm bedtime routine, warm lifestyle photo, tidy bedroom corner, "
            f"soft bedside light, relaxed daily habit atmosphere, {ratio}"
        )
    if channel == "xiaohongshu" or _contains_any(title, ["养生", "健康", "气色", "宝妈", "女性", "习惯"]):
        return (
            f"everyday wellness habit scene, bright lifestyle photo, tidy home corner, "
            f"glass cup, fresh towel, warm daylight, {ratio}"
        )
    if _contains_any(title, ["坑", "避坑", "骗局", "卖课", "割韭菜", "造假"]):
        return (
            f"risk-aware decision-making workspace, full-bleed editorial photo, "
            f"thoughtful office worker, laptop with subtle abstract dashboard glow, balanced shadow and daylight, {ratio}"
        )
    if _contains_any(title, ["工具", "学习", "路线", "教程", "提示词", "场景"]):
        return (
            f"hands-on AI learning workspace, full-bleed editorial photo, "
            f"abstract software interfaces on screen, phone and headphones, focused desk lamp, {ratio}"
        )
    if _contains_any(title, ["副业", "轻创业", "接单", "AI服务", "交易", "趋势", "信号"]):
        return (
            f"independent creator workspace, full-bleed editorial photo, "
            f"laptop, phone, calendar app glow, quiet planning mood, {ratio}"
        )
    return (
        f"full-bleed editorial photo cover, practical modern workspace, "
        f"natural daylight, balanced composition, {ratio}"
    )


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)
