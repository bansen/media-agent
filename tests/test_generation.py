import unittest

from content_agent.generation import generate_llm_drafts
from content_agent.mock_data import get_mock_candidates
from content_agent.workflow import run_keyword_workflow


class FakeLLMProvider:
    def __init__(self):
        self.prompts = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return "模型生成内容"


class GenerationTests(unittest.TestCase):
    def test_generates_channel_drafts_with_llm_provider(self):
        result = run_keyword_workflow("AI副业", get_mock_candidates("AI副业", channel="wechat"))
        llm = FakeLLMProvider()

        drafts = generate_llm_drafts(result, llm)

        self.assertEqual(drafts["wechat_article"], "模型生成内容")
        self.assertEqual(drafts["xhs_note"], "模型生成内容")
        self.assertNotIn("baijiahao_article", drafts)
        self.assertEqual(len(llm.prompts), 2)
        self.assertIn("公众号", llm.prompts[0])
        self.assertIn("不要承诺日更或固定更新频率", llm.prompts[0])
        self.assertIn("小红书", llm.prompts[1])

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
