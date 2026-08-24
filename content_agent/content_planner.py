from __future__ import annotations

from dataclasses import dataclass, field
import re

from .models import TopicBrief


@dataclass(frozen=True)
class ContentPlan:
    content_type: str
    project_name: str = ""
    project_kind: str = ""
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
        return _build_github_project_plan(text, url)
    if _is_knowledge_workflow(text):
        return ContentPlan(
            content_type="knowledge_workflow",
            reader_hook="笔记和资料越存越多，真正要用时却找不到，也无法复用",
            article_promise="搭建一条从资料进入、AI 整理、双向链接到检索复用的个人知识工作流。",
            title_angles=[
                "用 Codex + Obsidian，把零散资料变成个人知识库",
                "别再堆笔记了，用 Codex + Obsidian 搭一套个人知识库",
                "Codex + Obsidian 怎么配合？把零散资料变成个人知识库",
                "用 Codex 整理、Obsidian 沉淀，个人知识库这样搭",
                "资料总是找不到？用 Codex + Obsidian 重做个人知识库",
            ],
            title_rules=[
                "标题必须同时保留 Codex、Obsidian 和个人知识库这个读者结果。",
                "用痛点、结果或步骤制造点击理由，不要退化成泛 Codex 入门。",
                "只有正文明确规划了相同数量的并列主体时才使用数字，不为制造钩子虚构步数或要点数。",
            ],
            opening_rule="开头从资料越积越多却找不到、调不出的真实痛点切入。",
            section_flow=[
                "真实痛点：为什么收藏和笔记越多，知识反而越难调用。",
                "资料进入：网页、文档和临时想法如何进入统一入口。",
                "Codex 整理：如何提炼、归类并生成可维护的 Markdown 笔记。",
                "Obsidian 沉淀：如何用双向链接把孤立笔记连接成知识网络。",
                "检索复用：写作或工作时如何找到并组合已有知识。",
                "维护边界：哪些内容要人工确认，怎样避免知识库继续变乱。",
            ],
            evidence_rule="搜索素材只用于补充工具能力和实践依据，不能把主题改写成泛 Codex 入门。",
            ending_rule="结尾给出一个可以当天跑通的最小知识闭环。",
            repetition_rule="资料进入、整理、链接、检索四个环节各自解决不同问题，不重复罗列工具优点。",
            structure="结构：真实痛点 -> 资料进入 -> Codex 整理 -> Obsidian 链接沉淀 -> 检索复用 -> 维护边界。",
            cover_scene=(
                "personal knowledge system, linked-note knowledge graph, linked markdown notes, "
                "scattered notes flowing into organized knowledge clusters"
            ),
            cover_subject="AI organizing linked markdown notes into a personal knowledge map",
            cover_negative="generic office desk, laptop hero shot, headphones, potted plant, unreadable UI text",
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


def _is_knowledge_workflow(text: str) -> bool:
    has_knowledge_outcome = any(term in text for term in ["知识库", "第二大脑", "双向链接", "笔记整理", "知识工作流"])
    has_workflow_tool = any(term.lower() in text.lower() for term in ["Obsidian", "Codex"])
    return has_knowledge_outcome and has_workflow_tool


def _is_plugin_architecture(text: str) -> bool:
    return any(term in text.lower() for term in ["一切皆插件", "插件架构", "插件化", "可插拔", "plugin architecture", "plugin-based"])


def _is_video_creator_tool(text: str) -> bool:
    terms = ["短视频", "视频脚本", "视频生成", "生成字幕", "背景音乐", "文生视频", "video generator", "short video"]
    return sum(term in text.lower() for term in terms) >= 2


def _is_creator_ops_tool(text: str) -> bool:
    lower = text.lower()
    platform_hits = sum(term in text for term in ["抖音", "小红书", "快手", "视频号"])
    operation_hits = sum(term in text for term in ["内容管理", "管理面板", "作品监控", "评论监控", "内容下载", "发布作品", "发布", "通知"])
    return (
        "多平台内容" in text
        or ("web 面板" in lower and platform_hits >= 2 and operation_hits >= 2)
        or (platform_hits >= 3 and operation_hits >= 2)
    )


def _build_github_project_plan(text: str, url: str | None) -> ContentPlan:
    project_name = _github_project_name(text, url) or "这个开源项目"
    project_label = _github_project_label(project_name)
    common = {
        "content_type": "github_project_share",
        "project_name": project_name,
        "evidence_rule": "优先引用 WebSearch MCP 读取到的 README/项目摘要，不臆造 star、融资、作者背景或未给出的功能。",
        "link_policy": "链接只在文末以“项目地址：...”出现一次，正文中不要反复展示 URL。",
        "repetition_rule": "每个小节必须提供一个新判断，禁止连续两节重复“它能提升效率/值得关注”这类空话。",
    }
    if _is_video_creator_tool(text):
        return ContentPlan(
            **common,
            project_kind="creator_video_tool",
            reader_hook="做一条短视频要反复处理脚本、素材、配音、字幕、音乐和剪辑，流程长且容易卡住",
            article_promise="看懂 MoneyPrinterTurbo 如何把一个主题变成短视频、适合哪些创作者，以及自动化不能替代哪些判断。",
            title_angles=[
                f"不会剪视频？{project_label} 怎么把主题变成短视频",
                f"从脚本到成片，{project_label} 把短视频流程串起来了",
                f"做短视频太费时间？看看 {project_label} 能自动完成什么",
                f"{project_label} 值得用吗？先看它的短视频自动化链路",
            ],
            title_rules=[
                "标题必须同时保留可读项目名和短视频结果，不使用“项目分享”或“真实问题”等空泛描述。",
                "标题不暴露 URL、github.com 或仓库路径，不虚构收益和无人值守效果。",
            ],
            opening_rule="开头从创作者制作短视频时在脚本、找素材、配音、字幕和剪辑之间反复切换的痛点切入。",
            section_flow=[
                "创作痛点：做一条短视频为什么会被多个零散环节拖慢。",
                "项目定位：它是一站式 AI 短视频生成工具，不是 Agent 记忆或上下文管理框架。",
                "工作链路：输入主题或关键词后，如何生成视频脚本、匹配素材、生成配音字幕和背景音乐并合成高清成片。",
                "能力边界：横竖屏、批量、多语言、自有或在线素材以及可选平台发布分别解决什么问题。",
                "使用方式：WebUI、API、CLI 和 AI Agent 入口分别适合谁。",
                "成本与风险：部署环境、模型或素材服务、版权、成片质量和发布前人工审核。",
                "适用判断：哪些内容创作者值得试，哪些专业剪辑需求不应期待一键完成。",
                "项目地址：只在文末出现一次。",
            ],
            ending_rule="结尾建议读者用一个真实主题跑通样片，再根据成片质量和修改成本决定是否进入日常流程。",
            structure="结构：短视频制作痛点 -> 项目定位 -> 从主题到成片的完整链路 -> 关键能力 -> 使用方式 -> 成本与边界 -> 适用人群 -> 项目地址。",
            cover_scene="short-video production pipeline, storyboard, script page, media clips, voice waveform, subtitle timeline, vertical video frames",
            cover_subject="a visual journey from one topic through script, footage, voiceover and subtitles into a finished vertical short video",
            cover_negative="open-source agent system, circuit board, cryptocurrency symbols, generic AI network, raw URL text, unreadable interface text",
        )

    if _is_creator_ops_tool(text):
        return ContentPlan(
            **common,
            project_kind="creator_ops_tool",
            reader_hook="内容创作者同时运营抖音、小红书、快手和视频号时，账号、作品、评论、下载和发布会被拆在多个后台里来回切换",
            article_promise=f"基于 README 讲清 {project_label} 如何把多平台内容监控、采集下载、发布转发和通知集中到一个本地 Web 面板。",
            title_angles=[
                f"同时做抖音、小红书和视频号？{project_label} 把 4 个后台装进一个面板",
                f"4 个平台来回切换太累？{project_label} 想用一个面板全管起来",
                f"账号、评论、发布散在 4 个后台，{project_label} 把它们收进一处",
                f"{project_label} 怎么把多平台监控、下载、发布放进一个面板",
            ],
            title_rules=[
                "标题必须保留可读项目名和多平台内容管理结果，不使用“项目分享”或“真实问题”等空泛描述。",
                "标题要从 README 里的监控、下载、发布、通知等能力提炼具体钩子，不暴露 URL 或仓库路径。",
            ],
            opening_rule="开头从多平台创作者在账号、作品、评论、下载和发布之间反复切换的真实痛点切入。",
            section_flow=[
                "创作运营痛点：为什么多平台管理会被多个后台拖慢。",
                "项目定位：它是本地运行的多平台内容管理面板，不是泛 AI Agent 框架。",
                "核心能力：账号管理、作品监控、评论监控、内容下载、发布转发和通知分别解决什么问题。",
                "平台覆盖：抖音、小红书、快手、视频号的能力边界有什么不同。",
                "部署与成本：Python、FastAPI、Playwright、Node.js、ffmpeg 和本地数据存储带来的使用门槛。",
                "适用判断：哪些内容团队或个人创作者值得试，哪些高频自动操作要谨慎。",
                "项目地址：只在文末出现一次。",
            ],
            ending_rule="结尾建议读者先用一个账号和一个监控目标跑通，再决定是否纳入日常运营流程。",
            structure="结构：多平台运营痛点 -> 项目定位 -> 核心能力 -> 平台覆盖 -> 部署成本 -> 风控边界 -> 项目地址。",
            cover_scene="multi-platform creator operations, four distinct content channels converging into one dashboard, content monitoring queue, download status, publishing workflow, notification center",
            cover_subject="a local web dashboard unifying Douyin, Xiaohongshu, Kuaishou and video-account content operations",
            cover_negative="generic AI agent network, circuit board, raw URL text, GitHub screenshot, cryptocurrency symbols, unreadable UI text",
        )

    is_agent_project = bool(re.search(r"\bagent\b|harness|loopx|智能体|Codex|Claude|工作流|数字员工", text, flags=re.IGNORECASE))
    if is_agent_project and _is_plugin_architecture(text):
        title_angles = [
            f"{project_label} 开源：一个“一切皆插件”的 Agent 框架",
            f"Agent 框架还能这样搭？{project_label} 选择“一切皆插件”",
            f"{project_label} 值得看吗？关键在可插拔 Agent 架构",
            f"{project_label} 有什么不同？先看它的插件化 Agent 架构",
        ]
    elif is_agent_project:
        title_angles = [
            f"{project_label} 是什么？先看懂这个开源 Agent 框架",
            f"Agent 总是跑偏？{project_label} 给出了一套工作系统",
            f"别只会写 Prompt，{project_label} 想补上 Agent 工作流",
            f"让 Agent 连续工作，{project_label} 的思路值得看",
            f"{project_label} 值得关注吗？先看定位与使用边界",
        ]
    else:
        title_angles = [
            f"{project_label} 是什么？先看它解决了哪个真实问题",
            f"{project_label} 值得关注吗？先看定位与使用边界",
            f"别只看 Star，{project_label} 真正值得看的是这里",
            f"准备试 {project_label}？先判断它适不适合你",
        ]
    if is_agent_project:
        return ContentPlan(
            **common,
            project_kind="agent_framework",
            reader_hook="Agent 总是跑偏、断上下文、做不成长任务",
            article_promise="帮读者看懂这个项目如何改善 Agent 工作方式、适合谁用，以及值不值得收藏。",
            title_angles=title_angles,
            title_rules=[
                "标题用痛点、反差或结果钩子，不把 URL、github.com、仓库路径写进标题。",
                "标题必须使用可读项目名，不能用“这个开源项目”代替项目身份。",
            ],
            opening_rule="开头先写读者已经遇到的 Agent 失控场景，不要从链接、仓库名或“今天分享”开场。",
            section_flow=[
                "痛点开场：Agent 为什么会跑偏、断上下文、做不成长任务。",
                "项目定位：用一句话讲清这个项目补的是哪一层能力。",
                "关键机制：它如何让目标、上下文或执行过程更稳定。",
                "工作流价值：它如何把一次性对话变成可持续工作流。",
                "适用判断：谁该试，谁可以先观望。",
                "项目地址：只在文末出现一次。",
            ],
            ending_rule="结尾给判断建议，帮助读者确认项目是否解决了自己的 Agent 工作流问题。",
            structure="结构：Agent 痛点 -> 项目定位 -> 关键机制 -> 工作流价值 -> 适用判断 -> 项目地址。",
            cover_scene="open-source agent system, abstract workflow nodes, automation timeline, connected task graph, clean technical interface",
            cover_subject="由任务节点、上下文记忆和自动化时间线组成的 Agent 工作系统",
            cover_negative="generic workspace photography, computer hero shot, raw URL text, GitHub page screenshot, white card, poster board",
        )
    return ContentPlan(
        **common,
        project_kind="general_project",
        reader_hook="工具很多，但读者很难快速判断一个开源项目到底解决什么问题、是否值得投入时间",
        article_promise="基于 README 讲清项目定位、核心能力、使用门槛和适用人群。",
        title_angles=title_angles,
        title_rules=["标题必须使用可读项目名和具体价值，不暴露 URL，不使用空泛的“项目分享”。"],
        opening_rule="开头从项目对应的真实使用场景切入，不套用 Agent、副业或 AI 学习故事。",
        section_flow=["真实场景", "项目定位", "核心能力", "使用方式", "成本与边界", "适用人群", "项目地址"],
        ending_rule="结尾给出是否值得试用的判断标准。",
        structure="结构：真实场景 -> 项目定位 -> 核心能力 -> 使用方式 -> 成本与边界 -> 适用人群 -> 项目地址。",
        cover_scene="open-source product concept matching the README, clear functional workflow, editorial product visualization",
        cover_subject="the project's primary user outcome rather than a generic computer or circuit network",
        cover_negative="generic AI network, circuit board, raw URL text, GitHub screenshot, unreadable interface text",
    )


def _github_project_name(text: str, url: str | None) -> str:
    source = f"{url or ''} {text}"
    match = re.search(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)", source, flags=re.IGNORECASE)
    if match:
        return f"{match.group(1)}/{match.group(2).removesuffix('.git')}"
    match = re.search(r"GitHub 开源项目[:：]\s*([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)", text)
    return match.group(1) if match else ""


def _github_project_label(project_name: str) -> str:
    repository = project_name.rsplit("/", 1)[-1].removesuffix(".git")
    known_terms = {
        "ai": "AI",
        "codex": "Codex",
        "creatorhub": "CreatorHub",
        "deepseek": "DeepSeek",
        "harness": "Harness",
        "llm": "LLM",
        "loopx": "LoopX",
        "mcp": "MCP",
    }
    words = [word for word in re.split(r"[-_]+", repository) if word]
    return " ".join(known_terms.get(word.lower(), word if any(char.isupper() for char in word) else word.capitalize()) for word in words)
