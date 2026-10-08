import json
import unittest
from dataclasses import replace

from content_agent.generation import generate_llm_drafts
from content_agent.mock_data import get_mock_candidates
from content_agent.models import CandidateContent
from content_agent.workflow import run_keyword_workflow


def passing_review_response(prompt: str) -> str:
    """Model a successful independent review using literal input quotations."""
    payload = json.loads(prompt.split("INPUT_JSON:\n", 1)[1])
    source = payload["source"]
    return json.dumps({
        "verdict": "pass",
        "checks": [{
            "claim": payload["article"],
            "source_quote": source["body"] or source["title"],
        }],
        "issues": [],
    }, ensure_ascii=False)


class FakeLLMProvider:
    def __init__(self, response: str = "模型生成内容"):
        self.prompts = []
        self.draft_prompts = []
        self.review_prompts = []
        self.response = response

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if prompt.startswith("FACT_REVIEW_V1"):
            self.review_prompts.append(prompt)
            return passing_review_response(prompt)
        self.draft_prompts.append(prompt)
        return self.response


class SequenceLLMProvider:
    def __init__(self, responses: list[str]):
        self.prompts = []
        self.draft_prompts = []
        self.review_prompts = []
        self.responses = iter(responses)

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if prompt.startswith("FACT_REVIEW_V1"):
            self.review_prompts.append(prompt)
            return passing_review_response(prompt)
        self.draft_prompts.append(prompt)
        return next(self.responses)


class GenerationTests(unittest.TestCase):
    def minimax_candidates(self):
        return [
            CandidateContent(
                title="MiniMax H3正式发布",
                source="baidu_search",
                url="https://example.com/minimax-h3",
                heat=72,
                interaction=70,
                hook=82,
                pain=76,
                reuse=80,
                material=78,
            )
        ]

    def test_generates_channel_drafts_with_llm_provider(self):
        result = run_keyword_workflow("AI副业", get_mock_candidates("AI副业", channel="wechat"))
        llm = FakeLLMProvider()

        drafts = generate_llm_drafts(result, llm)

        self.assertTrue(drafts["wechat_article"].startswith(f"# {result.topics[0].optimized_title}"))
        self.assertIn("模型生成内容", drafts["wechat_article"])
        self.assertNotIn("xhs_note", drafts)
        self.assertNotIn("baijiahao_article", drafts)
        self.assertEqual(len(llm.draft_prompts), 1)
        self.assertEqual(len(llm.review_prompts), 1)
        self.assertIn("公众号", llm.prompts[0])
        self.assertIn("不要承诺日更或固定更新频率", llm.prompts[0])
        self.assertIn("不设最低字数，篇幅由原文信息量决定", llm.prompts[0])

    def test_wechat_content_uses_persisted_llm_plan_and_wechat_skill(self):
        result = run_keyword_workflow(
            "https://github.com/msitarzewski/agency-agents/blob/main/README.md 分享",
            [
                CandidateContent(
                    title="GitHub 开源项目：msitarzewski/agency-agents - Agency Agents",
                    source="websearch_mcp",
                    url="https://github.com/msitarzewski/agency-agents/blob/main/README.md",
                    heat=92,
                    interaction=88,
                    hook=84,
                    pain=80,
                    reuse=92,
                    material=96,
                    summary="每个 AI 智能体都有明确岗位职责、协作关系和交付标准。",
                )
            ],
        )
        selected_title = "Agency Agents：把岗位职责变成一支 AI 团队"
        topic = replace(result.topics[0], optimized_title=selected_title)
        result = replace(
            result,
            topics=[topic],
            content_plan={
                "core_topic": "用岗位和组织结构定义 AI 团队",
                "target_audience": "多智能体开发者和小团队",
                "pain_point": "多智能体缺少岗位职责和协作边界",
                "core_value": "把岗位职责和协作流程变成可运行的 AI 团队",
                "key_points": ["岗位定义", "组织关系", "交付标准"],
                "article_structure": ["冲突开场", "岗位机制", "协作流程", "使用场景", "边界判断"],
                "cover_concept": "具有明确岗位分工的 AI 团队协作",
                "titles": [selected_title],
                "selected_title": selected_title,
            },
        )
        llm = FakeLLMProvider("# 临时标题\n\n正文")

        drafts = generate_llm_drafts(result, llm)

        prompt = llm.prompts[0]
        self.assertIn("公众号文案创作", prompt)
        self.assertIn("把岗位职责和协作流程变成可运行的 AI 团队", prompt)
        self.assertIn("冲突开场 -> 岗位机制 -> 协作流程 -> 使用场景 -> 边界判断", prompt)
        self.assertIn("原文优先，策划中的无依据结论必须舍弃", prompt)
        self.assertIn("不为填满小节补写信息", prompt)
        self.assertIn("不要询问用户上传风格", prompt)
        self.assertTrue(drafts["wechat_article"].startswith(f"# {selected_title}"))

    def test_wechat_content_plan_is_not_rejected_by_legacy_video_template(self):
        result = run_keyword_workflow(
            "在 Codex 里调用云端 GPU 生成 MiniMax H3 视频",
            [
                CandidateContent(
                    title="从视频脚本到短视频生成的云端 GPU 工作流",
                    source="websearch_mcp",
                    url="https://github.com/example/cloud-video/blob/main/README.md",
                    heat=90,
                    interaction=86,
                    hook=84,
                    pain=82,
                    reuse=88,
                    material=92,
                    summary="支持视频脚本和视频生成，并在任务结束后自动关闭云端 GPU。",
                )
            ],
        )
        selected_title = "Codex 调云端 GPU 跑 H3，结束自动关机"
        result = replace(
            result,
            topics=[replace(result.topics[0], optimized_title=selected_title)],
            content_plan={
                "core_topic": "Codex 调用云端 GPU 运行 MiniMax H3",
                "target_audience": "需要按需使用云端算力的视频创作者",
                "pain_point": "云端 GPU 闲置时仍持续计费",
                "core_value": "视频生成结束后自动关闭实例以控制成本",
                "key_points": ["Codex 发起任务", "云端 GPU 运行 H3", "任务结束自动关机"],
                "article_structure": ["成本痛点", "工作原理", "执行流程", "风险边界"],
                "selected_title": selected_title,
            },
        )
        llm = FakeLLMProvider(
            "# 临时标题\n\nCodex 可以发起云端任务，由 GPU 运行 MiniMax H3。"
            "视频生成完成后自动关闭实例，避免闲置计费。"
        )

        drafts = generate_llm_drafts(result, llm)

        self.assertEqual(len(llm.draft_prompts), 1)
        self.assertEqual(len(llm.review_prompts), 1)
        self.assertIn("自动关闭实例", drafts["wechat_article"])

    def test_generates_only_xhs_note_for_xiaohongshu_channel(self):
        result = run_keyword_workflow("养生", get_mock_candidates("养生", channel="xiaohongshu"), primary_channel="xiaohongshu")
        llm = FakeLLMProvider()

        drafts = generate_llm_drafts(result, llm)

        self.assertEqual(drafts["xhs_note"], "模型生成内容")
        self.assertNotIn("wechat_article", drafts)
        self.assertEqual(len(llm.draft_prompts), 1)
        self.assertEqual(len(llm.review_prompts), 0)
        self.assertIn("小红书", llm.prompts[0])
        self.assertIn("Xiaohongshu Content Skill", llm.prompts[0])
        self.assertIn("Viral hooks", llm.prompts[0])
        self.assertIn("Xiaohongshu Layout Skill", llm.prompts[0])
        self.assertIn("Exclude layout instructions", llm.prompts[0])
        self.assertIn("输出只包含标题、正文、标签", llm.prompts[0])
        self.assertIn("不要输出封面图组", llm.prompts[0])

    def test_xhs_content_uses_llm_plan_and_keeps_selected_title(self):
        result = run_keyword_workflow(
            "帮多智能体开发者介绍 Agency Agents",
            [
                CandidateContent(
                    title="Agency Agents 专业智能体角色库",
                    source="websearch_mcp",
                    url="https://example.com/agency-agents",
                    heat=90,
                    interaction=86,
                    hook=84,
                    pain=80,
                    reuse=90,
                    material=94,
                    summary="每个智能体都有明确岗位职责、组织关系和交付标准。",
                )
            ],
            primary_channel="xiaohongshu",
        )
        selected_title = "AI 团队先把岗位分清楚"
        result = replace(
            result,
            topics=[replace(result.topics[0], optimized_title=selected_title)],
            content_plan={
                "core_topic": "岗位化 AI 团队",
                "target_audience": "多智能体开发者",
                "pain_point": "智能体协作时职责混乱",
                "core_value": "用岗位职责和组织关系约束智能体协作",
                "key_points": ["岗位定义", "组织关系", "交付标准"],
                "article_structure": ["痛点", "机制", "场景", "边界"],
                "selected_title": selected_title,
            },
        )
        llm = FakeLLMProvider("标题：另一个标题\n\n正文：岗位分工很重要。\n\n标签：#AI")

        drafts = generate_llm_drafts(result, llm)

        self.assertIn("用岗位职责和组织关系约束智能体协作", llm.prompts[0])
        self.assertIn("痛点 -> 机制 -> 场景 -> 边界", llm.prompts[0])
        self.assertTrue(drafts["xhs_note"].startswith(f"标题：{selected_title}"))

    def test_wechat_prompt_locks_keyword_and_selected_material(self):
        result = run_keyword_workflow(
            "minimax h3介绍",
            self.minimax_candidates(),
        )
        llm = FakeLLMProvider()

        generate_llm_drafts(result, llm)

        self.assertIn("minimax h3介绍", llm.prompts[0])
        self.assertIn(result.topics[0].title, llm.prompts[0])
        self.assertIn(result.topics[0].optimized_title, llm.prompts[0])
        self.assertIn("禁止泛化成 AI 学习、副业赚钱等无关主题", llm.prompts[0])

    def test_wechat_prompt_uses_creative_brief_not_only_keyword_lock(self):
        prompt = (
            "我想写一篇公众号文章，主题是普通人如何用 AI 做副业，"
            "目标读者是想赚钱但没方向的打工族，内容要真实、不鸡血，最好有避坑和行动步骤。"
        )
        result = run_keyword_workflow(
            prompt,
            [
                CandidateContent(
                    title="AI副业避坑：这些卖课套路正在收割新人",
                    source="baidu_search",
                    url="https://example.com/risk",
                    heat=86,
                    interaction=80,
                    hook=84,
                    pain=88,
                    reuse=80,
                    material=76,
                )
            ],
        )
        llm = FakeLLMProvider()

        generate_llm_drafts(result, llm)

        self.assertIn("创作主题：普通人如何用 AI 做副业", llm.prompts[0])
        self.assertIn("目标读者：想赚钱但没方向的打工族", llm.prompts[0])
        self.assertIn("写作角度：避坑、行动步骤", llm.prompts[0])
        self.assertIn("写作语气：真实、不鸡血", llm.prompts[0])
        self.assertIn("必须先回应创作主题和目标读者", llm.prompts[0])

    def test_wechat_prompt_uses_tool_integration_positioning(self):
        result = run_keyword_workflow(
            "DeepSeek V4 Flash 接入 Codex + 识图，2分钟搞定",
            [
                CandidateContent(
                    title="DeepSeek-V4-Flash正式版API上线公测,Agent能力跃迁并原生适配Codex",
                    source="baidu_search",
                    url="https://example.com/codex",
                    heat=77,
                    interaction=72,
                    hook=80,
                    pain=82,
                    reuse=86,
                    material=84,
                )
            ],
        )
        llm = FakeLLMProvider()

        generate_llm_drafts(result, llm)

        self.assertIn("工具接入教程", llm.prompts[0])
        self.assertIn("DeepSeek V4 Flash", llm.prompts[0])
        self.assertIn("Codex", llm.prompts[0])
        self.assertIn("识图", llm.prompts[0])
        self.assertIn("开头必须直接进入工具接入场景", llm.prompts[0])
        self.assertIn("不要写“学 AI 做作品”", llm.prompts[0])
        self.assertNotIn("待业者", llm.prompts[0])

    def test_wechat_prompt_uses_github_project_article_structure(self):
        result = run_keyword_workflow(
            "写一篇分享 https://github.com/huangruiteng/loopx/blob/main/README.zh-CN.md 的文章",
            [
                CandidateContent(
                    title="GitHub 开源项目：huangruiteng/loopx - 项目资料",
                    source="websearch_mcp",
                    url="https://github.com/huangruiteng/loopx/blob/main/README.zh-CN.md",
                    heat=92,
                    interaction=88,
                    hook=84,
                    pain=80,
                    reuse=92,
                    material=96,
                    summary="LoopX 给现有 Agent 补上一层长期工作控制系统，让 Codex、Claude Code 这类 Agent 更接近真正的数字员工。",
                )
            ],
        )
        llm = FakeLLMProvider()

        generate_llm_drafts(result, llm)

        self.assertIn("GitHub Agent 项目解读", llm.prompts[0])
        self.assertIn("项目定位", llm.prompts[0])
        self.assertIn("适用判断", llm.prompts[0])
        self.assertIn("项目地址", llm.prompts[0])
        self.assertIn("内容运营蓝图", llm.prompts[0])
        self.assertIn("标题用痛点、反差或结果钩子", llm.prompts[0])
        self.assertIn("每个小节必须提供一个新判断", llm.prompts[0])
        self.assertIn("不要连续两个小节重复同一观点", llm.prompts[0])
        self.assertIn("不要用“今天分享一个 GitHub 链接/项目”开场", llm.prompts[0])
        self.assertIn("链接只在文末以“项目地址：...”出现一次", llm.prompts[0])
        self.assertIn("不要把链接写进标题", llm.prompts[0])
        self.assertIn("用户意图：分享 GitHub 开源项目", llm.prompts[0])
        self.assertNotIn("创作主题：分享 https", llm.prompts[0])
        self.assertNotIn("副业/AI学习方法拆解", llm.prompts[0])

    def test_wechat_prompt_uses_creator_workflow_for_github_video_tool(self):
        result = run_keyword_workflow(
            "https://github.com/harry0703/MoneyPrinterTurbo/blob/main/README.md 项目分享",
            [
                CandidateContent(
                    title="GitHub 开源项目：harry0703/MoneyPrinterTurbo - MoneyPrinterTurbo",
                    source="websearch_mcp",
                    url="https://github.com/harry0703/MoneyPrinterTurbo/blob/main/README.md",
                    heat=92,
                    interaction=88,
                    hook=84,
                    pain=80,
                    reuse=92,
                    material=96,
                    summary=(
                        "MoneyPrinterTurbo 是一站式 AI 短视频生成工具。输入主题或关键词，"
                        "自动生成视频脚本、匹配素材、生成字幕和背景音乐，并合成高清短视频。"
                    ),
                )
            ],
        )
        llm = FakeLLMProvider("# MoneyPrinterTurbo\n\n从视频脚本、匹配素材、配音字幕到高清短视频成片，逐项说明。")

        generate_llm_drafts(result, llm)

        prompt = llm.prompts[0]
        self.assertIn("短视频创作工具", prompt)
        self.assertIn("视频脚本", prompt)
        self.assertIn("匹配素材", prompt)
        self.assertIn("字幕", prompt)
        self.assertIn("高清成片", prompt)
        self.assertIn("不要改写成 Agent 跑偏、记忆或上下文管理", prompt)
        self.assertNotIn("开头必须先写 Agent 使用痛点", prompt)
        self.assertNotIn("先讲痛点，再讲项目定位、关键机制", prompt)

    def test_wechat_video_tool_rewrites_once_when_first_draft_drifts_to_agent_memory(self):
        result = run_keyword_workflow(
            "https://github.com/harry0703/MoneyPrinterTurbo/blob/main/README.md 项目分享",
            [
                CandidateContent(
                    title="GitHub 开源项目：harry0703/MoneyPrinterTurbo - MoneyPrinterTurbo",
                    source="websearch_mcp",
                    url="https://github.com/harry0703/MoneyPrinterTurbo/blob/main/README.md",
                    heat=92,
                    interaction=88,
                    hook=84,
                    pain=80,
                    reuse=92,
                    material=96,
                    summary="一站式 AI 短视频生成工具，可生成视频脚本、匹配素材、字幕和背景音乐并合成成片。",
                )
            ],
        )
        llm = SequenceLLMProvider(
            [
                "# 错误正文\n\nAgent 经常跑偏、遗忘上下文，需要长期记忆和任务控制。",
                "# 正确正文\n\n输入短视频主题后，依次生成视频脚本、匹配素材、配音字幕和背景音乐，最后合成高清成片。",
            ]
        )

        drafts = generate_llm_drafts(result, llm)

        self.assertEqual(len(llm.draft_prompts), 2)
        self.assertEqual(len(llm.review_prompts), 2)
        self.assertIn("只修订下列核查指出的问题", llm.draft_prompts[1])
        self.assertIn("Agent 记忆或上下文", llm.draft_prompts[1])
        self.assertIn("高清成片", drafts["wechat_article"])
        self.assertNotIn("Agent 经常跑偏", drafts["wechat_article"])

    def test_wechat_prompt_uses_creator_operations_readme_plan(self):
        result = run_keyword_workflow(
            "https://github.com/3441293738/creatorhub/blob/main/README.md 项目分享",
            [
                CandidateContent(
                    title="GitHub 开源项目：3441293738/creatorhub - CreatorHub",
                    source="websearch_mcp",
                    url="https://github.com/3441293738/creatorhub/blob/main/README.md",
                    heat=92,
                    interaction=88,
                    hook=84,
                    pain=80,
                    reuse=92,
                    material=96,
                    summary=(
                        "CreatorHub 是本地运行的多平台内容管理面板，支持抖音、小红书、快手、视频号。"
                        "统一管理账号、监控作品与评论、下载内容、发布作品和接收通知，数据保存在本地。"
                    ),
                )
            ],
        )
        llm = FakeLLMProvider("# CreatorHub\n\n多平台账号、作品监控、内容下载和发布都集中在本地面板。")

        generate_llm_drafts(result, llm)

        prompt = llm.prompts[0]
        self.assertIn("多平台内容运营工具", prompt)
        self.assertIn("抖音、小红书、快手和视频号", prompt)
        self.assertIn("账号管理、作品监控、评论监控、内容下载、发布转发和通知", prompt)
        self.assertIn("登录态和数据保存在本地", prompt)
        self.assertNotIn("开头必须先写 Agent 使用痛点", prompt)

    def test_wechat_article_title_is_forced_to_selected_topic(self):
        result = run_keyword_workflow(
            "minimax h3介绍",
            self.minimax_candidates(),
        )
        llm = FakeLLMProvider("# 别急着学AI，先看懂这三个变化\n\n正文内容。")

        drafts = generate_llm_drafts(result, llm)

        self.assertTrue(drafts["wechat_article"].startswith(f"# {result.topics[0].optimized_title}"))
        self.assertNotIn("# 别急着学AI", drafts["wechat_article"])
        reviewed = json.loads(llm.review_prompts[0].split("INPUT_JSON:\n", 1)[1])
        self.assertEqual(reviewed["article"], drafts["wechat_article"])
        self.assertEqual(drafts["fact_review"]["status"], "passed")

    def test_knowledge_workflow_prompt_and_forced_title_share_one_topic(self):
        result = run_keyword_workflow(
            "用 Codex + Obsidian 搭建个人知识库",
            [
                CandidateContent(
                    title="Codex怎么入门？先从三个真实场景开始",
                    source="baidu_search",
                    url="https://example.com/codex-start",
                    heat=82,
                    interaction=76,
                    hook=80,
                    pain=74,
                    reuse=78,
                    material=72,
                )
            ],
        )
        llm = FakeLLMProvider("# Codex 怎么入门\n\n泛化正文。")

        drafts = generate_llm_drafts(result, llm)

        selected = result.topics[0].optimized_title
        self.assertTrue(drafts["wechat_article"].startswith(f"# {selected}"))
        self.assertIn("Codex", selected)
        self.assertIn("Obsidian", selected)
        self.assertIn("知识库", selected)
        self.assertIn("资料进入", llm.prompts[0])
        self.assertIn("检索复用", llm.prompts[0])
        self.assertIn("不要改写成泛泛的 AI 工具介绍", llm.prompts[0])

    def test_wechat_article_strips_assistant_preamble_and_title_labels(self):
        result = run_keyword_workflow(
            "minimax h3介绍",
            self.minimax_candidates(),
        )
        llm = FakeLLMProvider(
            "好的，这是为您准备的公众号文章，已按照要求完成，可直接复制进入草稿箱。\n\n"
            "---\n\n"
            "标题：minimax h3介绍有新变化，普通人先看懂这 3 点\n\n"
            "最近，MiniMax H3 的发布让不少人开始重新评估国产模型能力。\n\n"
            "## MiniMax H3 到底变在哪\n\n"
            "正文内容。"
        )

        drafts = generate_llm_drafts(result, llm)

        self.assertTrue(drafts["wechat_article"].startswith(f"# {result.topics[0].optimized_title}"))
        self.assertNotIn("好的，这是", drafts["wechat_article"])
        self.assertNotIn("可直接复制进入草稿箱", drafts["wechat_article"])
        self.assertNotIn("标题：", drafts["wechat_article"])
        self.assertIn("最近，MiniMax H3", drafts["wechat_article"])

    def test_reports_progress_before_each_llm_call(self):
        result = run_keyword_workflow("AI副业", get_mock_candidates("AI副业", channel="wechat"))
        llm = FakeLLMProvider()
        events = []

        generate_llm_drafts(result, llm, progress=events.append)

        self.assertEqual(
            events,
            [
                "Generating wechat_article with LLM",
                "正在独立核查标题、正文与原文事实",
            ],
        )

    def test_xhs_prompt_uses_project_skill_for_health_note_generation(self):
        result = run_keyword_workflow(
            "小红书健康养生，写给 20-45 岁职场女性和宝妈，内容要生活化、可收藏",
            [
                CandidateContent(
                    title="办公室久坐人群，一天 4 个时间点这样调整",
                    source="baidu_search",
                    url="https://example.com/health",
                    heat=78,
                    interaction=80,
                    hook=84,
                    pain=88,
                    reuse=90,
                    material=72,
                    summary="久坐人群可以通过间歇活动、喝水提醒和睡前放松建立低成本习惯。",
                )
            ],
            primary_channel="xiaohongshu",
        )
        llm = FakeLLMProvider()

        generate_llm_drafts(result, llm)

        xhs_prompt = llm.prompts[0]
        self.assertIn("Treat the user input as a creative brief", xhs_prompt)
        self.assertIn("health/lifestyle notes", xhs_prompt)
        self.assertIn("never diagnose", xhs_prompt)
        self.assertIn("正文主要方法使用连续编号", xhs_prompt)
        self.assertIn("Use 3:4 portrait images", xhs_prompt)
        self.assertIn("办公室久坐人群", xhs_prompt)


if __name__ == "__main__":
    unittest.main()


class FactualGenerationTests(unittest.TestCase):
    def test_rewrites_article_that_inverts_market_move(self):
        result = run_keyword_workflow(
            "湖南卫视 AI 猴子闹出约 133 亿市值",
            [
                CandidateContent(
                    title="湖南卫视一只“AI猴子”，闹出133亿",
                    source="baidu_search",
                    url="https://www.thepaper.cn/newsDetail_forward_34020108",
                    heat=90,
                    interaction=80,
                    hook=88,
                    pain=70,
                    reuse=75,
                    material=86,
                    summary="截至9月4日，芒果超媒近5个交易日累计上涨50.18%，公司市值大涨约132.84亿元。",
                )
            ],
        )
        topic = replace(result.topics[0], optimized_title="芒果超媒市值大涨，AI长剧还要算口碑")
        result = replace(result, topics=[topic, *result.topics[1:]])
        bad = "# 错误\n\n一只猴子，让湖南卫视市值一天蒸发133亿。"
        good = "# 正确\n\n芒果超媒近5个交易日市值大涨约132.84亿元。"
        llm = SequenceLLMProvider([bad, good])

        drafts = generate_llm_drafts(result, llm)

        self.assertIn("市值大涨", drafts["wechat_article"])
        self.assertNotIn("蒸发", drafts["wechat_article"])
        self.assertEqual(len(llm.draft_prompts), 2)
        self.assertEqual(len(llm.review_prompts), 1)
        self.assertIn("事实红线", llm.draft_prompts[0])
        self.assertIn("不得写成蒸发", llm.draft_prompts[1])
        self.assertEqual(drafts["fact_review"]["status"], "passed")
