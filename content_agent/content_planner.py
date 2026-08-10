from __future__ import annotations

from dataclasses import dataclass, field
import re

from .models import TopicBrief


@dataclass(frozen=True)
class ContentPlan:
    content_type: str
    project_name: str = ""
    reader_hook: str = ""
    article_promise: str = ""
    title_angles: list[str] = field(default_factory=list)
    title_rules: list[str] = field(default_factory=list)
    opening_rule: str = ""
    section_flow: list[str] = field(default_factory=list)
    evidence_rule: str = ""
    link_policy: str = ""
    ending_rule: str = ""
    repetition_rule: str = ""
    structure: str = ""
    cover_scene: str = ""
    cover_subject: str = ""
    cover_negative: str = ""


def build_content_plan(topic: TopicBrief, prompt: str = "") -> ContentPlan:
    return build_content_plan_for_text(topic.title, prompt=prompt, source_summary=topic.source_summary, url=topic.url)


def build_content_plan_for_text(title: str, prompt: str = "", source_summary: str = "", url: str | None = None) -> ContentPlan:
    text = f"{title} {source_summary} {prompt}"
    if _is_github_project(text, url):
        project_name = _github_project_name(text, url) or "这个开源项目"
        agent_focus = (
            "Agent"
            if re.search(r"\bagent\b|loopx|智能体|Codex|Claude|工作流|数字员工", text, flags=re.IGNORECASE)
            else "开源项目"
        )
        return ContentPlan(
            content_type="github_project_share",
            project_name=project_name,
            reader_hook=f"{agent_focus} 总是跑偏、断上下文、做不成长任务",
            article_promise="帮读者看懂这个项目解决的真实问题、适合谁用，以及值不值得收藏。",
            title_angles=[
                f"{agent_focus} 总是跑偏？这个开源项目给了一套工作系统",
                f"别只会写 Prompt，{agent_focus} 真正缺的是这套工作流",
                f"让 {agent_focus} 连续工作，这个开源项目的思路值得看",
                f"做 {agent_focus} 的人，应该看看这个开源项目",
                f"{agent_focus} 走向数字员工，差的可能不是模型",
            ],
            title_rules=[
                "标题用痛点、反差或结果钩子，不把 URL、github.com、仓库路径写进标题。",
                "标题不要写成“分享某链接”“介绍某仓库”，要让读者先关心问题本身。",
                "标题可以出现 Agent、Prompt、工作流、数字员工等读者熟悉的概念。",
            ],
            opening_rule="开头先写读者已经遇到的 Agent 失控场景，不要从链接、仓库名或“今天分享”开场。",
            section_flow=[
                "痛点开场：Agent 为什么会跑偏、断上下文、做不成长任务。",
                "项目定位：用一句话讲清这个项目补的是哪一层能力。",
                "关键问题 1：它如何让任务目标、上下文或执行过程更稳定。",
                "关键问题 2：它如何把一次性对话变成可持续工作流。",
                "关键问题 3：它适合哪些人试用，哪些人暂时不用急。",
                "上手判断：先看 README、示例和适配场景，再决定是否收藏或试用。",
                "项目地址：只在文末出现一次，作为补充资料。",
            ],
            evidence_rule="优先引用 WebSearch MCP 读取到的 README/项目摘要，不臆造 star、融资、作者背景或未给出的功能。",
            link_policy="链接只在文末以“项目地址：...”出现一次，正文中不要反复展示 URL。",
            ending_rule="结尾给判断建议，引导读者关注“这个项目解决的问题是否正好是自己工作流里的问题”。",
            repetition_rule="每个小节必须提供一个新判断，禁止连续两节重复“它能提升效率/值得关注”这类空话。",
            structure="结构：痛点开场 -> 项目一句话定位 -> 它解决的 3 个关键问题 -> 适合谁用 -> 怎么开始看 -> 项目地址与判断建议。",
            cover_scene=(
                "open-source agent system, abstract workflow nodes, automation timeline, "
                "connected task graph, clean technical interface, abstract product visualization"
            ),
            cover_subject="由任务节点、上下文记忆、自动化时间线组成的 Agent 工作系统，而不是办公桌或普通电脑照片",
            cover_negative="generic workspace photography, computer hero shot, raw URL text, GitHub page screenshot, white card, poster board",
        )
    if _is_health_topic(text):
        return ContentPlan(
            content_type="lifestyle_health",
            reader_hook="职场女性或宝妈想改善状态，但不想被复杂养生方案绑架",
            article_promise="把健康养生写成低成本、可坚持、可收藏的日常习惯清单。",
            title_angles=[
                "职场女性可收藏的低成本养生习惯清单",
                "每天 10 分钟，把状态慢慢养回来",
                "别把养生复杂化，先做好这几件小事",
                "宝妈也能坚持的低成本放松清单",
            ],
            title_rules=["标题生活化、可收藏，不写治疗承诺，不制造健康焦虑。"],
            opening_rule="开头写一个真实生活场景，如久坐、睡前疲惫、带娃后没时间照顾自己。",
            section_flow=[
                "场景痛点：读者为什么会被这个问题困住。",
                "习惯清单：给 3-5 个低门槛动作。",
                "执行提醒：每个动作说明适合什么时候做。",
                "避坑边界：不替代诊断，不承诺治疗效果。",
                "收藏式收尾：鼓励从一个动作开始。",
            ],
            evidence_rule="只写通用健康常识，不写诊断、治疗、处方和夸大功效。",
            ending_rule="结尾强调先从一个可坚持的小习惯开始。",
            repetition_rule="每条建议必须对应不同生活场景，避免重复说“多休息、多喝水”。",
            structure="结构：生活场景 -> 低成本习惯 -> 执行时间点 -> 避坑边界 -> 收藏提醒。",
            cover_scene="bright lived-in wellness routine, soft daylight, tidy home or workplace corner, practical daily habit scene",
            cover_subject="具体生活习惯场景，例如伸展、睡前放松、喝水记录或办公间隙休息",
            cover_negative="medical symbols, pills, hospital scene, diagnosis chart, exaggerated body transformation",
        )
    if _is_side_hustle_topic(text):
        return ContentPlan(
            content_type="ai_side_hustle",
            reader_hook="想做 AI 副业的人卡在不知道做什么、怎么开始、怕被卖课套路收割",
            article_promise="把模糊的赚钱焦虑拆成真实需求、低风险切入点和下一步行动。",
            title_angles=[
                "想做 AI 副业，先别踩这 5 个坑",
                "AI 副业别急着买课，先看懂真实需求",
                "普通人用 AI 找到第一单，先跑通这 3 个小任务",
                "很多人做 AI 副业卡住，是因为一开始就学错了",
            ],
            title_rules=["标题要给出明确点击理由：避坑、第一单、真实需求或低成本行动。", "不使用暴富、稳赚、月入、躺赚等承诺。"],
            opening_rule="开头先承认读者想做副业但信息混乱的处境，再给出本文能帮他避开的具体问题。",
            section_flow=[
                "痛点开场：为什么很多人还没开始就先被课程和工具淹没。",
                "真实需求：市场上到底有人愿意为什么 AI 服务付费。",
                "切入任务：列出 3 个普通人能练成作品的小任务。",
                "避坑判断：哪些内容看起来诱人但不适合新手。",
                "行动清单：今天可以完成的第一步。",
            ],
            evidence_rule="可以引用搜索素材中的趋势、案例和工具，但必须转成普通人可执行的判断。",
            ending_rule="结尾不要承诺收益，只给下一步行动和判断标准。",
            repetition_rule="每一节分别解决需求、能力、获客、交付或风险中的一个问题，不重复鸡血鼓励。",
            structure="结构：痛点开场 -> 真实需求 -> 可执行任务 -> 避坑判断 -> 行动清单。",
            cover_scene="risk-aware creator decision scene, abstract task board, practical service workflow, clear progress path",
            cover_subject="普通创作者从混乱信息中筛出可交付任务的过程",
            cover_negative="money piles, luxury cars, exaggerated income chart, fake success symbols, blank card",
        )
    if _is_ai_tool_topic(text):
        return ContentPlan(
            content_type="ai_tool_or_model",
            reader_hook="读者看到新工具或新模型，但不知道和自己的创作、工作有什么关系",
            article_promise="把工具能力翻译成真实使用场景、适合人群和上手判断。",
            title_angles=[
                "别只看发布稿，这个 AI 工具真正影响这几类人",
                "这个 AI 能不能用起来？先看真实场景",
                "普通创作者看懂这个工具，先抓 3 个能力",
                "新工具很多，但真正值得试的是这些场景",
            ],
            title_rules=["标题保留核心工具名或模型名，避免把提示词里的要求原样复制进去。"],
            opening_rule="开头直接说明这个工具和读者的具体任务有什么关系。",
            section_flow=[
                "场景开场：读者在哪个任务里可能用到它。",
                "能力拆解：讲 3 个最值得关注的能力。",
                "适用人群：谁该试，谁可以先观望。",
                "上手方式：先做一个小测试，而不是一次性全面学习。",
                "避坑提醒：别被参数和宣传带偏。",
            ],
            evidence_rule="用搜索素材解释能力边界，不把发布稿改写成广告稿。",
            ending_rule="结尾给一个可验证的小任务。",
            repetition_rule="能力、场景、上手建议分开写，不重复堆工具形容词。",
            structure="结构：真实场景 -> 能力拆解 -> 适用人群 -> 小测试 -> 避坑提醒。",
            cover_scene="creator workflow with abstract AI interface, model capability map, clean product visualization",
            cover_subject="AI 工具能力如何进入创作者工作流",
            cover_negative="generic office desk, unreadable UI text, product logo imitation, white poster",
        )
    return ContentPlan(content_type="general")


def render_wechat_content_playbook(plan: ContentPlan) -> list[str]:
    if plan.content_type == "general":
        return [
            "内容运营蓝图：标题先提炼主题钩子，正文按“痛点-信息-方法-判断-行动”推进。",
            "标题规则：不要复制用户提示词中的描述性要求，不要把搜索词直接当标题。",
            "正文规则：每个小节必须解决一个新问题，禁止重复铺陈同一观点。",
        ]
    lines = ["内容运营蓝图："]
    if plan.reader_hook:
        lines.append(f"读者钩子：{plan.reader_hook}")
    if plan.article_promise:
        lines.append(f"文章承诺：{plan.article_promise}")
    if plan.title_rules:
        lines.append(f"标题规则：{'；'.join(plan.title_rules)}")
    if plan.opening_rule:
        lines.append(f"开头规则：{plan.opening_rule}")
    if plan.section_flow:
        lines.append("正文分工：" + " | ".join(plan.section_flow))
    if plan.evidence_rule:
        lines.append(f"素材规则：{plan.evidence_rule}")
    if plan.link_policy:
        lines.append(f"链接规则：{plan.link_policy}")
    if plan.ending_rule:
        lines.append(f"结尾规则：{plan.ending_rule}")
    if plan.repetition_rule:
        lines.append(f"去重规则：{plan.repetition_rule}")
    return lines


def strip_urls(text: str) -> str:
    clean = re.sub(r"https?://[^\s，。；、）)】\]\"'<>]+", "", text)
    clean = re.sub(r"^(?:写一篇|帮我写|分享|介绍|生成一篇)\s*", "", clean)
    clean = re.sub(r"(?:的)?(?:文章|内容|公众号文章)\s*$", "", clean)
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip(" ，,。；;：:")


def _is_github_project(text: str, url: str | None) -> bool:
    return "github.com" in f"{text} {url or ''}".lower() or "GitHub 开源项目" in text


def _is_health_topic(text: str) -> bool:
    return any(term in text for term in ["养生", "健康", "久坐", "肩颈", "睡前", "宝妈", "职场女性", "气色", "放松"])


def _is_side_hustle_topic(text: str) -> bool:
    return any(term in text for term in ["副业", "赚钱", "变现", "接单", "第一单", "轻创业", "卖课", "避坑"])


def _is_ai_tool_topic(text: str) -> bool:
    return any(term in text for term in ["AI", "大模型", "DeepSeek", "MiniMax", "Codex", "Claude", "工具", "模型", "API", "接入"])


def _github_project_name(text: str, url: str | None) -> str:
    source = f"{url or ''} {text}"
    match = re.search(r"github\.com/([^/\s]+)/([^/\s?#]+)", source, flags=re.IGNORECASE)
    if match:
        return f"{match.group(1)}/{match.group(2).removesuffix('.git')}"
    match = re.search(r"GitHub 开源项目[:：]\s*([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)", text)
    return match.group(1) if match else ""
