import unittest

from content_agent.models import CandidateContent
from content_agent.workflow import run_keyword_workflow


class TitleLabTests(unittest.TestCase):
    def test_title_lab_builds_multiple_scored_titles_from_creative_prompt(self):
        prompt = (
            "我想写一篇公众号文章，主题是普通人如何用 AI 做副业，"
            "目标读者是想赚钱但没方向的打工族，内容要真实、不鸡血，最好有避坑和行动步骤。"
        )
        candidates = [
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
        ]

        result = run_keyword_workflow(prompt, candidates=candidates, primary_channel="wechat")
        topic = result.topics[0]

        self.assertGreaterEqual(len(topic.title_candidates), 5)
        self.assertEqual(topic.optimized_title, topic.title_candidates[0]["title"])
        self.assertTrue(any("第一单" in item["title"] for item in topic.title_candidates))
        self.assertTrue(any("坑" in item["title"] for item in topic.title_candidates))
        self.assertNotIn("目标读者", topic.optimized_title)
        self.assertNotIn("内容要", topic.optimized_title)
        self.assertNotIn("我想写", topic.optimized_title)

    def test_specific_model_prompt_title_keeps_entity_and_focus(self):
        prompt = "帮我写公众号，主题是 MiniMax H3 的视频能力，要求突出普通创作者能怎么用，不要写成泛泛 AI 学习"
        candidates = [
            CandidateContent(
                title="MiniMax H3官网入口分享:AI视频生成工具到底好不好用?",
                source="baidu_search",
                url="https://example.com/minimax-h3-video",
                heat=75,
                interaction=70,
                hook=82,
                pain=78,
                reuse=80,
                material=78,
            )
        ]

        result = run_keyword_workflow(prompt, candidates=candidates, primary_channel="wechat")

        self.assertIn("MiniMax H3", result.topics[0].optimized_title)
        self.assertIn("视频", result.topics[0].optimized_title)
        self.assertNotIn("泛泛 AI 学习", result.topics[0].optimized_title)


if __name__ == "__main__":
    unittest.main()
