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

    def test_knowledge_workflow_title_keeps_tools_and_user_outcome(self):
        result = run_keyword_workflow(
            "用 Codex + Obsidian 搭建个人知识库",
            candidates=[
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
            primary_channel="wechat",
        )

        title = result.topics[0].optimized_title
        self.assertIn("Codex", title)
        self.assertIn("Obsidian", title)
        self.assertIn("知识库", title)
        self.assertNotIn("Codex怎么入门", title)
        self.assertIn("个人知识工作流", result.wechat_outline)

    def test_workflow_deduplicates_repeated_optimized_titles_from_similar_sources(self):
        prompt = (
            "我想写一篇公众号文章，主题是普通人如何用 AI 做副业，"
            "目标读者是新手，内容要真实、不鸡血，最好有避坑和行动步骤。"
        )
        candidates = [
            CandidateContent(
                title="苏小兵:别再被 AI 赚钱骗了,2026年普通人最该看清这5个真相?",
                source="baidu_search",
                url="https://example.com/a",
                heat=72,
                interaction=68,
                hook=80,
                pain=86,
                reuse=76,
                material=72,
            ),
            CandidateContent(
                title="苏小兵:不用学编程,普通人靠AI赚钱的5种真实方式!",
                source="baidu_search",
                url="https://example.com/b",
                heat=71,
                interaction=67,
                hook=79,
                pain=84,
                reuse=75,
                material=72,
            ),
            CandidateContent(
                title="AI副业避坑：这些卖课套路正在收割新人",
                source="baidu_search",
                url="https://example.com/c",
                heat=70,
                interaction=66,
                hook=78,
                pain=85,
                reuse=74,
                material=71,
            ),
        ]

        result = run_keyword_workflow(prompt, candidates=candidates, primary_channel="wechat")
        optimized_titles = [topic.optimized_title for topic in result.topics]

        self.assertEqual(len(optimized_titles), len(set(optimized_titles)))
        self.assertEqual(optimized_titles.count("普通人用 AI 做副业，先避开这 5 个坑"), 1)


if __name__ == "__main__":
    unittest.main()
