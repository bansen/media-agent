from __future__ import annotations

import re

from .content_planner import ContentPlan, build_content_plan_for_text, strip_urls
from .creative_brief import CreativeBrief, build_creative_brief, is_creative_prompt
from .keyword_intent import extract_keyword_entity, extract_keyword_modifiers, parse_keyword_intent
from .models import ContentChannel


FORBIDDEN_TITLE_TERMS = [
    "暴富",
    "稳赚",
    "月入",
    "躺赚",
    "保证",
    "根治",
    "治愈",
    "治疗",
    "诊断",
]

SOURCE_ONLY_TITLE_TERMS = ["README", "项目资料", "项目分享", "素材摘要", "仓库路径"]


def optimize_title(
    title: str,
    channel: ContentChannel,
    keyword: str = "",
    source_summary: str = "",
    url: str | None = None,
) -> str:
    candidates = build_title_candidates(title, channel, keyword=keyword, source_summary=source_summary, url=url)
    if candidates:
        return str(candidates[0]["title"])
    return _sanitize_title(_legacy_optimize_title(title, channel, keyword=keyword))


def build_title_candidates(
    title: str,
    channel: ContentChannel,
    keyword: str = "",
    source_summary: str = "",
    url: str | None = None,
) -> list[dict[str, float | str]]:
    clean_title = clean_source_title(title)
    brief = build_creative_brief(keyword, channel=channel)
    plan = build_content_plan_for_text(clean_title, prompt=keyword, source_summary=source_summary, url=url)
    legacy = _sanitize_title(_legacy_optimize_title(title, channel, keyword=keyword))
    raw_candidates = _candidate_titles(clean_title, channel, keyword, brief, source_summary=source_summary, url=url)
    scored = [
        {
            "title": _sanitize_title(candidate),
            "score": _score_title(candidate, clean_title, brief, channel, plan=plan),
            "reason": _title_reason(candidate, brief),
        }
        for candidate in raw_candidates
        if candidate.strip()
    ]
    if not is_creative_prompt(keyword) and plan.content_type not in {"github_project_share", "knowledge_workflow"}:
        scored.insert(0, {"title": legacy, "score": 999.0, "reason": "兼容短关键词默认标题"})
    unique: dict[str, dict[str, float | str]] = {}
    for item in scored:
        title_key = str(item["title"])
        if not title_key or _contains_any(title_key, FORBIDDEN_TITLE_TERMS):
            continue
        if any(term.lower() in title_key.lower() for term in SOURCE_ONLY_TITLE_TERMS):
            continue
        if title_key not in unique or float(item["score"]) > float(unique[title_key]["score"]):
            unique[title_key] = item
    return sorted(unique.values(), key=lambda item: float(item["score"]), reverse=True)[:8]


def _legacy_optimize_title(title: str, channel: ContentChannel, keyword: str = "") -> str:
    clean_title = clean_source_title(title)
    if channel == "xiaohongshu" or _looks_like_health(clean_title):
        return _sanitize_title(_optimize_health_title(clean_title))
    intent = parse_keyword_intent(keyword)
    if intent.task_kind == "tool_integration":
        return _sanitize_title(_optimize_tool_integration_title(clean_title, intent.entities, intent.modifiers))
    if intent.task_kind == "model_analysis":
        brief = build_creative_brief(keyword, channel=channel)
        return _sanitize_title(_optimize_keyword_title(clean_title, brief.topic or keyword.strip()))
    if keyword.strip() and not _looks_like_ai_focus(keyword):
        return _sanitize_title(_optimize_keyword_title(clean_title, keyword.strip()))
    return _sanitize_title(_optimize_ai_side_hustle_title(clean_title))


def _candidate_titles(
    title: str,
    channel: ContentChannel,
    keyword: str,
    brief: CreativeBrief,
    source_summary: str = "",
    url: str | None = None,
) -> list[str]:
    legacy = _legacy_optimize_title(title, channel, keyword=keyword)
    plan = build_content_plan_for_text(title, prompt=keyword, source_summary=source_summary, url=url)
    if plan.content_type in {"github_project_share", "knowledge_workflow"} and plan.title_angles:
        return _dedupe(plan.title_angles)
    if _looks_like_github_project(title, keyword):
        return _dedupe(_github_project_title_candidates(title))
    if channel == "xiaohongshu" or _looks_like_health(f"{title} {brief.topic}"):
        return _health_title_candidates(title, brief, legacy)
    intent = parse_keyword_intent(keyword)
    if intent.task_kind == "tool_integration":
        return _dedupe([legacy, *_tool_title_candidates(intent.entities, intent.modifiers)])
    if intent.task_kind == "model_analysis":
        return _dedupe([legacy, *_model_title_candidates(title, brief)])
    if _looks_like_side_hustle(f"{title} {brief.topic} {keyword}"):
        return _dedupe([legacy, *_side_hustle_title_candidates(title, brief)])
    return _dedupe([legacy, *_general_title_candidates(title, brief)])


def _side_hustle_title_candidates(title: str, brief: CreativeBrief) -> list[str]:
    topic = _compact_topic(brief.topic, fallback="AI 副业")
    candidates = [
        f"{topic}，先避开这 5 个坑",
        "想用 AI 找到第一单，先跑通这 3 个小任务",
        "AI 副业别急着买课，先看懂真实需求",
        "很多人做 AI 副业卡住，是因为一开始就学错了",
        "普通人做 AI 副业，先从这份行动清单开始",
        "AI 接单怎么开始？给新手的第一步清单",
    ]
    if _contains_any(title, ["交易", "服务", "需求", "增长"]):
        candidates.insert(0, "AI 服务需求变多了，普通人怎么找到第一单？")
    if _contains_any(title, ["坑", "骗局", "卖课", "割韭菜", "避坑"]):
        candidates.insert(0, "想做 AI 副业，先别踩这 5 个坑")
    return candidates


def _model_title_candidates(title: str, brief: CreativeBrief) -> list[str]:
    entity = extract_keyword_entity(brief.topic) or _model_entity_from_source_title(title) or _compact_topic(brief.topic, "AI 工具")
    if "视频" in f"{brief.topic} {title}":
        return [
            f"{entity} 视频能力，普通创作者先看这 3 点",
            f"{entity} 能不能做视频？先看真实使用场景",
            f"{entity} 更新后，视频创作最值得关注什么",
            f"别只看参数，{entity} 视频能力要这样理解",
            f"{entity} 适合谁用？从视频场景说清楚",
        ]
    return [
        f"{entity} 核心能力，先看懂这 3 点",
        f"{entity} 有新变化，普通人先看懂什么",
        f"别只看发布稿，{entity} 真正影响这 3 类人",
        f"{entity} 怎么用？先从真实场景判断",
        f"{entity} 值不值得关注，看这 3 个信号",
    ]


def _tool_title_candidates(entities: list[str], modifiers: list[str]) -> list[str]:
    primary = entities[0] if entities else "AI 工具"
    secondary = entities[1] if len(entities) > 1 else ""
    if secondary and "识图" in modifiers:
        return [
            f"{primary} 接入 {secondary}，识图怎么跑通？",
            f"{primary} + {secondary} 识图接入，先解决这 3 个问题",
            f"把 {primary} 接进 {secondary}，识图验证这样做",
            f"{primary} 接入实战：从配置到识图验证",
            f"{secondary} 想用 {primary}，先看这份接入清单",
        ]
    if secondary:
        return [
            f"{primary} 接入 {secondary}，先看懂这 3 点",
            f"{primary} + {secondary} 怎么跑通？",
            f"把 {primary} 接进 {secondary}，这几步别漏",
            f"{primary} 接入实战：配置、验证和避坑",
            f"{secondary} 使用 {primary}，先从这份清单开始",
        ]
    return [f"{primary} API 接入，先看懂这 3 点", f"{primary} 怎么接入？新手先看这份清单"]


def _health_title_candidates(title: str, brief: CreativeBrief, legacy: str) -> list[str]:
    topic = _compact_topic(brief.topic, "低成本养生")
    return [
        legacy,
        f"{topic}，职场女性先从这 4 个习惯开始",
        f"宝妈也能做的 {topic}，别一上来就复杂化",
        f"每天 10 分钟，把 {topic} 变成生活习惯",
        f"{topic}避坑：这 3 件事别盲目跟风",
    ]


def _general_title_candidates(title: str, brief: CreativeBrief) -> list[str]:
    topic = _compact_topic(strip_urls(brief.topic) or title, "这个主题")
    return [
        f"{topic}，先看懂这 3 个关键问题",
        f"别急着开始，{topic}先想清楚这件事",
        f"{topic}怎么做？一份新手执行清单",
        f"关于{topic}，真正值得关注的是这些细节",
        title if 10 <= len(title) <= 30 else f"{topic}入门：从真实场景开始",
    ]


def _score_title(
    title: str,
    source_title: str,
    brief: CreativeBrief,
    channel: ContentChannel,
    plan: ContentPlan | None = None,
) -> float:
    text = f"{title} {source_title}"
    score = 50.0
    topic_terms = _title_terms(brief.topic)
    score += min(24, sum(6 for term in topic_terms if term and term in text))
    score += min(14, sum(4 for angle in brief.angles if angle[:2] in title or angle in title))
    score += 8 if any(term in title for term in ["坑", "别急", "先", "怎么", "为什么"]) else 0
    score += 6 if any(char.isdigit() for char in title) else 0
    score += 6 if "？" in title or "?" in title else 0
    score += 4 if "同时" in title else 0
    score += 6 if "来回切" in title else 0
    score += 6 if "全收进" in title else 0
    score += 6 if "多平台运营" in title else 0
    score += 6 if "太分散" in title else 0
    score += 6 if "收进一处" in title else 0
    score += min(8, sum(4 for term in ["抖音", "小红书", "快手", "视频号"] if term in title))
    score += 6 if any(term in title for term in ["后台", "一个面板", "成片", "第一单"]) else 0
    score += 4 if channel == "xiaohongshu" and any(term in title for term in ["收藏", "习惯", "清单"]) else 0
    if len(title) < 12 or len(title) > 34:
        score -= 8
    if any(term in title for term in ["我想写", "目标读者", "内容要", "要求", "风格", "http", "github.com"]):
        score -= 30
    if any(term in title for term in ["想用", "试试看", "可能"]):
        score -= 8
    if any(term in title for term in ["是什么", "真实问题", "值得关注吗", "准备试", "适不适合你", "先看懂这 3 点"]):
        score -= 18
    value_keywords = list(getattr(plan, "value_keywords", []) or [])
    if value_keywords:
        value_hits = sum(1 for term in value_keywords if term and term.lower() in title.lower())
        score += min(30, value_hits * 6)
        if getattr(plan, "content_type", "") == "github_project_share" and value_hits == 0:
            score -= 24
    if any(term in title for term in ["是什么", "值得关注吗", "README 里的核心能力", "工作系统"]):
        score -= 12
    if _contains_any(source_title, ["坑", "骗局", "卖课", "割韭菜"]) and "坑" in title:
        score += 10
    if _contains_any(source_title, ["交易", "服务", "需求", "增长"]) and "第一单" in title:
        score += 10
    return round(score, 1)


def _title_reason(title: str, brief: CreativeBrief) -> str:
    if "坑" in title:
        return "避坑角度，点击动机明确"
    if "第一单" in title:
        return "结果导向，适合新手读者"
    if any(angle in title for angle in brief.angles):
        return "贴合用户指定角度"
    return "主题相关且表达克制"


def clean_source_title(title: str) -> str:
    clean = re.sub(r"\s+", " ", title).strip()
    clean = strip_urls(clean)
    clean = re.split(r"\s+[—-]\s+|[丨｜]", clean, maxsplit=1)[0].strip()
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip(" -_｜丨")


def _optimize_ai_side_hustle_title(title: str) -> str:
    if _contains_any(title, ["坑", "骗局", "卖课", "割韭菜", "造假", "避坑"]):
        return "AI 副业可以做，但这 5 个坑先别踩"
    if _contains_any(title, ["轻创业", "副业", "声音变现", "AI服务", "交易", "爆发", "接单", "赚钱"]):
        if _contains_any(title, ["交易", "服务", "AI服务", "爆发", "增长"]):
            return "AI 服务需求变多了，普通人怎么找到第一单？"
        if _contains_any(title, ["接单", "赚钱"]):
            return "想用 AI 接单，先从这 3 类小服务切入"
        return "AI 副业不是玄学，普通人先抓住这 3 个切入口"
    if _contains_any(title, ["工具", "学习", "路线", "教程", "提示词"]):
        if _contains_any(title, ["提示词", "教程"]):
            return "别只收藏提示词，先跑通这 3 个 AI 交付场景"
        return "学 AI 工具别贪多，先搭一条可交付路线"
    if 10 <= len(title) <= 28 and not _contains_any(title, FORBIDDEN_TITLE_TERMS):
        return title
    return "普通人学 AI，先把一个真实任务做成作品"


def _optimize_keyword_title(title: str, keyword: str) -> str:
    keyword = strip_urls(keyword)
    clean_keyword = extract_keyword_entity(keyword) or keyword.strip()
    keyword_modifiers = extract_keyword_modifiers(keyword)
    model_entity = _model_entity_from_source_title(title)
    if model_entity and ("视频" in keyword_modifiers or "视频" in title):
        return f"{model_entity}视频能力，先看懂这 3 点"
    if model_entity and ("核心能力" in keyword_modifiers or _contains_any(title, ["能力", "参数", "API", "工具"])):
        return f"{model_entity}核心能力，先看懂这 3 点"
    if model_entity and _contains_any(title, ["发布", "上线", "更新", "模型"]):
        return f"{model_entity}有新变化，普通人先看懂这 3 点"
    if clean_keyword in title and 10 <= len(title) <= 30 and not _contains_any(title, FORBIDDEN_TITLE_TERMS):
        return title
    if _contains_any(title, ["架构", "系统", "平台", "工程", "数据", "项目", "技术"]):
        return f"{clean_keyword}入门：先看懂这 3 个核心问题"
    if _contains_any(title, ["发布", "更新", "趋势", "报告", "方案"]):
        return f"{clean_keyword}有新变化，普通人先看懂这 3 点"
    return f"{clean_keyword}怎么入门？先从这 3 个真实场景开始"


def _github_project_title_candidates(title: str) -> list[str]:
    focus = "Agent" if _contains_any(title, ["Agent", "智能体", "Codex", "Claude", "loopx", "LoopX"]) else "这个工具"
    return [
        f"{focus} 总是跑偏？这个开源项目给了一套工作系统",
        f"别只会写 Prompt，{focus} 真正缺的是这套工作流",
        f"让 {focus} 连续工作，这个开源项目的思路值得看",
        f"做 {focus} 的人，应该看看这个开源项目",
        f"{focus} 走向数字员工，差的可能不是模型",
    ]


def _optimize_tool_integration_title(title: str, entities: list[str], modifiers: list[str]) -> str:
    primary = entities[0] if entities else (_model_entity_from_source_title(title) or "AI 工具")
    secondary = next((entity for entity in entities[1:] if entity != primary), "")
    action = "接入"
    if "识图" in modifiers:
        focus = "识图"
    elif "API" in modifiers or "API" in title:
        focus = "API"
    else:
        focus = "能力"

    if secondary and focus == "识图":
        return f"{primary} 接入 {secondary}，识图怎么跑通？"
    if secondary:
        return f"{primary} {action} {secondary}，先看懂这 3 点"
    if focus == "识图":
        return f"{primary} 识图能力，怎么跑通？"
    if focus == "API":
        return f"{primary} API 接入，先看懂这 3 点"
    return f"{primary} 核心能力，先看懂这 3 点"


def _optimize_health_title(title: str) -> str:
    if _contains_any(title, ["久坐", "办公室", "肩颈", "腰背"]):
        return "久坐职场女性可收藏的 4 个低成本习惯"
    if _contains_any(title, ["睡前", "放松", "睡眠", "熬夜"]):
        return "宝妈睡前 10 分钟，试试这份放松清单"
    if _contains_any(title, ["气色", "养生", "健康", "习惯"]):
        return "职场女性可收藏的 5 个低成本养生习惯"
    return "职场女性可收藏的低成本习惯清单"


def _sanitize_title(title: str) -> str:
    safe_title = title
    replacements = {
        "暴富": "增长",
        "稳赚": "更稳",
        "月入": "收入",
        "躺赚": "轻量尝试",
        "保证": "更容易",
        "根治": "改善",
        "治愈": "调整",
        "治疗": "调理",
        "诊断": "观察",
    }
    for unsafe, safe in replacements.items():
        safe_title = safe_title.replace(unsafe, safe)
    return safe_title.strip()


def _compact_topic(topic: str, fallback: str) -> str:
    clean = topic.strip() or fallback
    clean = clean.replace("如何用", "用")
    clean = clean.replace("怎么找到", "找到")
    clean = re.sub(r"[，,。；;].*$", "", clean).strip()
    return clean if len(clean) <= 18 else clean[:18].rstrip()


def _looks_like_side_hustle(text: str) -> bool:
    return _contains_any(text, ["副业", "赚钱", "变现", "接单", "第一单", "轻创业"])


def _title_terms(topic: str) -> list[str]:
    terms = [part for part in re.split(r"[\s/+-]+", topic) if len(part) >= 2]
    for term in ["AI", "副业", "接单", "第一单", "视频", "养生", "MiniMax", "DeepSeek", "Codex", "Obsidian", "知识库"]:
        if term in topic:
            terms.append(term)
    if not terms and len(topic) > 2:
        terms = [topic[index : index + 2] for index in range(0, len(topic) - 1)]
    return _dedupe(terms)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _looks_like_health(title: str) -> bool:
    return _contains_any(title, ["养生", "女性", "宝妈", "健康", "久坐", "气色", "睡前", "办公室"])


def _looks_like_ai_focus(text: str) -> bool:
    return _contains_any(
        text,
        [
            "AI",
            "ai",
            "DeepSeek",
            "deepseek",
            "大模型",
            "副业",
            "赚钱",
            "变现",
            "轻创业",
            "接单",
        ],
    )


def _looks_like_github_project(title: str, keyword: str) -> bool:
    text = f"{title} {keyword}"
    return "github.com" in text.lower() or _contains_any(text, ["GitHub 开源项目", "开源项目"])


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _model_entity_from_source_title(title: str) -> str:
    match = re.match(r"([A-Za-z][A-Za-z0-9]*(?:\s+[A-Za-z0-9]+){0,3})", title.strip())
    if not match:
        return ""
    entity = re.sub(r"\s+", " ", match.group(1)).strip()
    if len(entity) < 3 or not re.search(r"\d|[A-Z]", entity):
        return ""
    return entity
