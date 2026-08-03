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

    def test_wechat_article_title_is_forced_to_selected_topic(self):
        result = run_keyword_workflow(
            "minimax h3介绍",
            self.minimax_candidates(),
        )
        llm = FakeLLMProvider("# 别急着学AI，先看懂这三个变化\n\n正文内容。")

        drafts = generate_llm_drafts(result, llm)

        self.assertTrue(drafts["wechat_article"].startswith(f"# {result.topics[0].optimized_title}"))
        self.assertNotIn("# 别急着学AI", drafts["wechat_article"])

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
