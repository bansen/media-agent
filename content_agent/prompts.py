from __future__ import annotations

from .content_planner import build_content_plan, render_wechat_content_playbook, strip_urls
from .creative_brief import CreativeBrief, build_creative_brief
from .keyword_intent import parse_keyword_intent
from .models import TopicBrief


COVER_STYLE_GUIDANCE = {
    "business-tech": "full-bleed business technology editorial photo, sharp focus, high-resolution, clean modern lighting",
    "real-photo": "realistic lifestyle photography, natural light, sharp focus, high-resolution, believable daily scene",
    "minimal-illustration": "minimal editorial illustration, refined shapes, high-resolution, clean composition, soft depth",
    "knowledge-card": "knowledge-sharing cover image, clear subject hierarchy, sharp focus, high-resolution, editorial composition",
}


def build_wechat_outline(topic: TopicBrief, keyword: str = "") -> str:
    intent = parse_keyword_intent(keyword)
    brief = build_creative_brief(keyword)
    plan = build_content_plan(topic, keyword)
    keyword_line = f"用户关键词：{keyword.strip()}" if keyword.strip() else "用户关键词：未提供"
    brief_lines = _creative_brief_lines(brief)
    source_line = f"选中素材：{topic.title}"
    if plan.content_type == "github_project_share":
        keyword_line = "用户意图：分享 GitHub 开源项目"
        brief_lines = []
        if topic.url:
            brief_lines.append(f"项目地址：{topic.url}")
        if plan.project_kind == "creator_video_tool":
            positioning = "定位：GitHub 短视频创作工具实测解读，写给想缩短脚本、素材、配音、字幕和剪辑流程的内容创作者。"
            topic_lock = (
                "主题锁定：全文必须围绕从主题到高清成片的短视频自动化链路展开；"
                "不要改写成 Agent 跑偏、记忆或上下文管理，也不要承诺无人值守赚钱。"
            )
        elif plan.project_kind == "creator_ops_tool":
            positioning = "定位：GitHub 多平台内容运营工具解读，写给同时运营多个内容平台的创作者和小团队。"
            topic_lock = (
                "主题锁定：全文必须围绕抖音、小红书、快手和视频号的账号管理、作品与评论监控、"
                "内容下载、发布转发和通知展开；明确登录态和数据保存在本地，并写清平台能力差异与风控边界。"
            )
        elif plan.project_kind == "story_video_tool":
            positioning = "定位：GitHub AI 叙事视频生产工具解读，写给需要把脚本转成连续镜头的视频创作者和团队。"
            topic_lock = (
                "主题锁定：全文必须围绕脚本拆解、镜头生成、动态音频和跨场景风格一致性展开；"
                "不要改写成泛 AI 视频工具清单或 Agent 工作流介绍。"
            )
        elif plan.project_kind == "presentation_tool":
            positioning = "定位：GitHub PPT 生产与编辑工具解读，写给需要快速完成职场汇报、方案和演示文稿的读者。"
            topic_lock = (
                "主题锁定：全文必须围绕 AI 生成 PPT 后难修改、版式难控制和难交付的问题展开；"
                "重点解释浏览器编辑控制台、版式主题和可编辑 PPTX 导出，不得改写成 Agent 跑偏或上下文管理。"
            )
        elif plan.project_kind == "agent_framework":
            positioning = "定位：GitHub Agent 项目解读，写给关注智能体工作流和开发效率的读者。"
            topic_lock = "主题锁定：全文必须围绕 Agent 项目解决的问题、关键机制和适用人群展开，不要把链接写进标题。"
        else:
            positioning = "定位：GitHub 开源项目解读，写给正在判断工具价值和使用成本的读者。"
            topic_lock = "主题锁定：全文必须以 README 为事实依据，围绕项目定位、核心能力、使用成本和适用人群展开。"
        structure = plan.structure
    elif plan.content_type == "knowledge_workflow":
        positioning = "定位：个人知识工作流搭建教程，写给想把零散资料变成可检索、可复用知识的人。"
        topic_lock = (
            "主题锁定：全文必须同时围绕 Codex、Obsidian 和个人知识库展开，"
            "搜索素材只作论据；不要改写成泛泛的 AI 工具介绍或 Codex 入门文章。"
        )
        structure = plan.structure
    elif intent.task_kind == "tool_integration":
        positioning = "定位：工具接入教程，写给正在尝试把 AI 模型接入实际工作流的人。"
        topic_lock = "主题锁定：全文必须围绕工具接入、配置步骤和结果验证展开，不要改写成泛泛的 AI 学习、副业赚钱或人生建议。"
        structure = "结构：使用场景 -> 准备条件 -> 接入步骤 -> 识图验证 -> 常见问题 -> 行动清单。"
    else:
        audience = brief.audience or "想做副业的打工族或待业者"
        positioning = f"定位：写给{audience}。"
        topic_lock = "主题锁定：全文必须先回应创作主题和目标读者，再结合选中素材展开，不要改写成泛泛的 AI 学习或副业赚钱文章。"
        structure = _structure_for(brief)
    playbook_lines = render_wechat_content_playbook(plan)
    return "\n".join(
        [
            f"公众号文章：《{topic.optimized_title}》",
            keyword_line,
            *brief_lines,
            source_line,
            positioning,
            topic_lock,
            *playbook_lines,
            structure,
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


def build_cover_strategy(topic: TopicBrief, brief: CreativeBrief, channel: str = "wechat") -> dict[str, str]:
    plan = build_content_plan(topic, brief.raw_prompt)
    core_message = strip_urls(brief.topic)
    if plan.content_type == "github_project_share" or not core_message or len(core_message) < 4:
        core_message = topic.optimized_title
    audience = brief.audience or ("20-45 岁职场女性或宝妈" if channel == "xiaohongshu" else "普通内容创作者")
    emotion = _cover_emotion_for(topic, brief, channel)
    scene = plan.cover_scene if plan.cover_scene else _cover_scene_for(topic, brief, channel)
    return {
        "core_message": core_message,
        "audience": audience,
        "emotion": emotion,
        "scene": scene,
        "subject": plan.cover_subject or _cover_subject_for(topic, brief, channel),
        "avoid": "文字、白色卡片、纸张、海报板、夸张金钱符号、医疗承诺",
        "negative": plan.cover_negative,
    }


def build_cover_prompt_from_strategy(topic: TopicBrief, strategy: dict[str, str], channel: str = "wechat") -> str:
    style = _cover_style_for(topic, channel)
    dimensions = "1080x1440" if channel == "xiaohongshu" else "1600x900"
    return (
        "Replicate image prompt: "
        f"{style}. Main idea: {topic.optimized_title}. "
        f"Core message: {strategy.get('core_message', topic.optimized_title)}. "
        f"Audience mood: {strategy.get('emotion', 'practical and clear')}. "
        f"Primary subject: {strategy.get('subject', 'a vivid scene matching the article topic')}. "
        f"Scene concept: {strategy.get('scene', 'complete realistic editorial scene')}. "
        "Use a complete background scene with balanced composition, vivid subject, sharp details, "
        f"natural negative space for later title overlay, {dimensions} high-resolution output. "
        "No text, no blank white rectangle, no paper sheet, no poster board, no floating card, "
        "no money piles, no medical claims, no exaggerated symbols. "
        f"Avoid: {strategy.get('negative', '')}."
    )


def apply_cover_style(base_style: str, cover_style: str = "business-tech") -> str:
    selected = (cover_style or "business-tech").strip()
    if selected not in COVER_STYLE_GUIDANCE:
        raise ValueError(f"unsupported cover style: {cover_style}")
    if "short-video production pipeline" in base_style:
        style_note = {
            "business-tech": "polished creator-tool editorial visualization, cinematic color, high-resolution",
            "real-photo": "realistic creator studio workflow with visible storyboard and vertical video frames",
            "minimal-illustration": "minimal editorial illustration of script-to-video production stages",
            "knowledge-card": "clear educational composition showing the short-video creation pipeline, no text",
        }[selected]
        return f"{base_style}, {style_note}"
    if "story-to-video production pipeline" in base_style:
        style_note = {
            "business-tech": "cinematic story-production visualization, consistent character across frames, crisp high-resolution detail",
            "real-photo": "realistic film preproduction wall with a coherent character and location repeated across consecutive shots",
            "minimal-illustration": "minimal editorial illustration of one script becoming a consistent sequence of cinematic frames",
            "knowledge-card": "clear educational composition of script analysis, frames, motion and audio, no text",
        }[selected]
        return f"{base_style}, {style_note}"
    if "editable presentation workflow" in base_style:
        style_note = {
            "business-tech": "polished presentation-production visualization, crisp editable slide layers, high-resolution",
            "real-photo": "realistic presentation editing session with clearly visible slide layout adjustments, no generic laptop hero shot",
            "minimal-illustration": "minimal editorial illustration of a document becoming editable presentation slides and PPTX",
            "knowledge-card": "clear educational composition of document, editable slides and PPTX export, no text",
        }[selected]
        return f"{base_style}, {style_note}"
    if "multi-platform creator operations" in base_style:
        style_note = {
            "business-tech": "polished creator operations editorial visualization, distinct channel lanes, crisp high-resolution detail",
            "real-photo": "realistic content operations control room with multiple publishing feeds, no generic computer hero shot",
            "minimal-illustration": "minimal editorial illustration of four content channels converging into one operating dashboard",
            "knowledge-card": "clear educational composition of monitoring, download and publishing stages, no text",
        }[selected]
        return f"{base_style}, {style_note}"
    if "personal knowledge system" in base_style:
        style_note = {
            "business-tech": "refined editorial visualization of connected knowledge, crisp depth, high-resolution",
            "real-photo": "tactile mixed-media knowledge map with believable linked notes, no generic workplace setup",
            "minimal-illustration": "minimal editorial illustration of linked notes and organized knowledge clusters",
            "knowledge-card": "knowledge-sharing composition with a clear linked-note graph, no text",
        }[selected]
        return f"{base_style}, {style_note}"
    if "open-source agent system" in base_style:
        style_note = {
            "business-tech": "technical product visualization, crisp interface-like lighting, high-resolution",
            "real-photo": "realistic cinematic product visualization, believable depth, no generic workplace setup",
            "minimal-illustration": "minimal editorial illustration of connected agent workflow nodes",
            "knowledge-card": "knowledge-sharing composition with abstract task graph, no text",
        }[selected]
        return f"{base_style}, {style_note}"
    return f"{COVER_STYLE_GUIDANCE[selected]}, {base_style}"


def _cover_style_for(topic: TopicBrief, channel: str) -> str:
    title = f"{topic.title} {topic.optimized_title} {topic.angle} {topic.source_summary}"
    ratio = "3:4 vertical social cover" if channel == "xiaohongshu" else "16:9 wide cover"

    if _contains_any(title, ["Obsidian", "个人知识库", "第二大脑", "双向链接", "知识工作流"]):
        return (
            f"personal knowledge system, linked-note knowledge graph, linked markdown notes, "
            f"organized knowledge clusters, high-resolution editorial cover, {ratio}"
        )
    if _contains_any(title, ["多平台内容", "多平台运营", "作品监控", "评论监控", "发布转发", "CreatorHub"]):
        return (
            f"multi-platform creator operations, four distinct content channels converging into one dashboard, "
            f"monitoring feed, download queue, publishing workflow, high-resolution editorial cover, {ratio}"
        )
    if _contains_any(title, ["短视频", "视频脚本", "视频生成", "字幕", "背景音乐", "MoneyPrinterTurbo"]):
        return (
            f"short-video production pipeline, storyboard, script page, media clips, voice waveform, "
            f"subtitle timeline, finished vertical video frames, high-resolution editorial cover, {ratio}"
        )
    if _contains_any(title, ["脚本变视频", "跨镜头", "连续镜头", "motion video", "AI-generated frames", "style consistency", "Openstory"]):
        return (
            f"story-to-video production pipeline, screenplay breaking into cinematic frames, "
            f"one consistent character and location across scenes, motion and audio layers, high-resolution editorial cover, {ratio}"
        )
    if _contains_any(title, ["PPT", "PPTX", "演示文稿", "编辑控制台", "Dashi"]):
        return (
            f"editable presentation workflow, document transforming into polished editable slides, "
            f"layout controls, color adjustments, PPTX export, high-resolution editorial cover, {ratio}"
        )
    if _contains_any(title, ["GitHub 开源项目", "开源项目", "Agent", "智能体", "数字员工", "工作系统"]):
        return (
            f"open-source agent system, abstract workflow nodes, automation timeline, "
            f"connected task graph, clean technical interface, high-resolution editorial cover, {ratio}"
        )
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


def _creative_brief_lines(brief: CreativeBrief) -> list[str]:
    lines = []
    if brief.topic:
        lines.append(f"创作主题：{brief.topic}")
    if brief.audience:
        lines.append(f"目标读者：{brief.audience}")
    if brief.angles:
        lines.append(f"写作角度：{'、'.join(brief.angles)}")
    if brief.tone:
        lines.append(f"写作语气：{'、'.join(brief.tone)}")
    return lines


def _structure_for(brief: CreativeBrief) -> str:
    if "避坑" in brief.angles and "行动步骤" in brief.angles:
        return "结构：痛点开场 -> 为什么会踩坑 -> 真实素材拆解 -> 可执行步骤 -> 避坑清单 -> 行动建议。"
    if "真实案例" in brief.angles:
        return "结构：真实场景开场 -> 案例拆解 -> 方法提炼 -> 适用边界 -> 行动清单。"
    return "结构：痛点开场 -> 真实素材 -> 方法拆解 -> 避坑提醒 -> 行动清单。"


def _cover_emotion_for(topic: TopicBrief, brief: CreativeBrief, channel: str) -> str:
    text = f"{topic.optimized_title} {brief.topic} {' '.join(brief.angles)}"
    if channel == "xiaohongshu":
        return "warm, relaxed, useful, easy to save"
    if _contains_any(text, ["避坑", "坑", "风险", "误区"]):
        return "clear-minded, practical, alert but not anxious"
    if _contains_any(text, ["第一单", "行动步骤", "步骤", "接单"]):
        return "focused, actionable, quietly optimistic"
    return "professional, useful, calm"


def _cover_scene_for(topic: TopicBrief, brief: CreativeBrief, channel: str) -> str:
    text = f"{topic.optimized_title} {topic.title} {brief.topic}"
    if channel == "xiaohongshu":
        return "bright lived-in lifestyle scene matching the daily habit topic"
    if _contains_any(text, ["GitHub 开源项目", "开源项目", "Agent", "智能体", "数字员工", "工作系统"]):
        return "open-source agent system with workflow nodes, automation timeline, connected task graph, clean technical interface"
    if _contains_any(text, ["视频", "创作者"]):
        return "creator desk with laptop timeline interface glow, camera or phone nearby, active planning moment"
    if _contains_any(text, ["接单", "副业", "第一单"]):
        return "independent creator workspace, laptop and notebook showing planning flow, believable evening work scene"
    if _contains_any(text, ["接入", "API", "Codex", "DeepSeek"]):
        return "developer workspace with code editor and image preview on screen, clean technical atmosphere"
    return "modern editorial workspace connected to the article topic"


def _cover_subject_for(topic: TopicBrief, brief: CreativeBrief, channel: str) -> str:
    text = f"{topic.optimized_title} {topic.title} {brief.topic}"
    if channel == "xiaohongshu":
        return "a concrete lifestyle habit scene matching the note topic"
    if _contains_any(text, ["GitHub 开源项目", "开源项目", "Agent", "智能体", "数字员工", "工作系统"]):
        return "an abstract agent workflow system made of task nodes, memory context and automation timeline"
    if _contains_any(text, ["视频", "创作者"]):
        return "a creator planning a video workflow with timeline and media controls"
    if _contains_any(text, ["接单", "副业", "第一单"]):
        return "an independent creator turning ideas into a small deliverable service workflow"
    if _contains_any(text, ["接入", "API", "Codex", "DeepSeek"]):
        return "a developer validating an AI tool integration with a clean technical interface"
    return "a concrete subject that visually represents the article's main problem"
