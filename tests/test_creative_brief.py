import unittest

from content_agent.creative_brief import build_creative_brief
from content_agent.keyword_intent import build_search_queries, clean_search_keyword


class CreativeBriefTests(unittest.TestCase):
    def test_creative_prompt_is_parsed_into_topic_audience_and_queries(self):
        prompt = (
            "我想写一篇公众号文章，主题是普通人如何用 AI 做副业，"
            "目标读者是想赚钱但没方向的打工族，内容要真实、不鸡血，最好有避坑和行动步骤。"
        )

        brief = build_creative_brief(prompt, channel="wechat")

        self.assertEqual(brief.raw_prompt, prompt)
        self.assertEqual(brief.topic, "普通人如何用 AI 做副业")
        self.assertEqual(brief.audience, "想赚钱但没方向的打工族")
        self.assertIn("避坑", brief.angles)
        self.assertIn("行动步骤", brief.angles)
        self.assertIn("真实", brief.tone)
        self.assertIn("不鸡血", brief.tone)
        self.assertGreaterEqual(len(brief.search_queries), 4)
        self.assertEqual(brief.search_queries[0], "普通人如何用 AI 做副业 避坑")
        self.assertNotIn("我想写一篇公众号文章", " ".join(brief.search_queries))

    def test_search_queries_use_prompt_brief_instead_of_raw_prompt(self):
        prompt = "帮我写公众号，主题是 AI 接单怎么找到第一单，目标读者是新手，要求真实案例和避坑"

        queries = build_search_queries(prompt)

        self.assertIn("AI 接单怎么找到第一单 避坑", queries)
        self.assertIn("AI 接单怎么找到第一单 真实案例", queries)
        self.assertNotIn(prompt, queries)
        self.assertNotIn("帮我写公众号", " ".join(queries))

    def test_clean_search_keyword_returns_topic_for_creative_prompt(self):
        prompt = "写一篇小红书，主题是职场女性低成本养生，面向宝妈，风格生活化"

        self.assertEqual(clean_search_keyword(prompt), "职场女性低成本养生")


if __name__ == "__main__":
    unittest.main()
