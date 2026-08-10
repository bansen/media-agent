import unittest

from content_agent.generation import generate_llm_drafts
from content_agent.mock_data import get_mock_candidates
from content_agent.models import CandidateContent
from content_agent.workflow import run_keyword_workflow


class FakeLLMProvider:
    def __init__(self, response: str = "模型生成内容"):
        self.prompts = []
        self.response = response

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


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
        self.assertEqual(drafts["xhs_note"], "模型生成内容")
        self.assertNotIn("baijiahao_article", drafts)
        self.assertEqual(len(llm.prompts), 2)
        self.assertIn("公众号", llm.prompts[0])
        self.assertIn("不要承诺日更或固定更新频率", llm.prompts[0])
        self.assertIn("小红书", llm.prompts[1])

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

        self.assertIn("GitHub 开源项目分享", llm.prompts[0])
        self.assertIn("项目一句话定位", llm.prompts[0])
        self.assertIn("适合谁用", llm.prompts[0])
        self.assertIn("项目地址", llm.prompts[0])
        self.assertIn("链接只在文末作为项目地址出现", llm.prompts[0])
        self.assertIn("不要把链接写进标题", llm.prompts[0])
        self.assertIn("用户意图：分享 GitHub 开源项目", llm.prompts[0])
        self.assertNotIn("创作主题：分享 https", llm.prompts[0])
        self.assertNotIn("副业/AI学习方法拆解", llm.prompts[0])

    def test_wechat_article_title_is_forced_to_selected_topic(self):
        result = run_keyword_workflow(
            "minimax h3介绍",
            self.minimax_candidates(),
        )
        llm = FakeLLMProvider("# 别急着学AI，先看懂这三个变化\n\n正文内容。")

        drafts = generate_llm_drafts(result, llm)

        self.assertTrue(drafts["wechat_article"].startswith(f"# {result.topics[0].optimized_title}"))
        self.assertNotIn("# 别急着学AI", drafts["wechat_article"])

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
                "Generating xhs_note with LLM",
            ],
        )


if __name__ == "__main__":
    unittest.main()
