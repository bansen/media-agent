import unittest

from content_agent.models import CandidateContent
from content_agent.workflow import run_keyword_workflow


class TitleOptimizerTests(unittest.TestCase):
    def test_wechat_ai_side_hustle_title_is_optimized_for_attention(self):
        candidates = [
            CandidateContent(
                title="上半年AI服务交易迎爆发式增长 年轻人开始用AI轻创业丨封面有数 - 封面新闻",
                source="google_news_rss",
                url="https://example.com/topic",
                heat=90,
                interaction=84,
                hook=78,
                pain=80,
                reuse=77,
                material=76,
            )
        ]

        result = run_keyword_workflow("AI副业", candidates=candidates, primary_channel="wechat")
        optimized_title = result.topics[0].optimized_title

        self.assertEqual(result.topics[0].title, "上半年AI服务交易迎爆发式增长 年轻人开始用AI轻创业丨封面有数 - 封面新闻")
        self.assertEqual(optimized_title, "普通人做 AI 副业，先看懂这 3 个真实信号")
        self.assertIn(f"公众号文章：《{optimized_title}》", result.wechat_outline)
        self.assertIn(f"Main idea: {optimized_title}.", result.cover_prompt)
        self.assertNotIn("封面新闻", optimized_title)
        self.assertNotIn("暴富", optimized_title)
        self.assertNotIn("稳赚", optimized_title)
        self.assertNotIn("月入", optimized_title)
        self.assertNotIn("躺赚", optimized_title)

    def test_xiaohongshu_health_title_keeps_lifestyle_positioning(self):
        candidates = [
            CandidateContent(
                title="办公室久坐人群，一天 4 个时间点这样调整 - 健康时报",
                source="google_news_rss",
                url="https://example.com/health",
                heat=78,
                interaction=80,
                hook=84,
                pain=88,
                reuse=90,
                material=72,
            )
        ]

        result = run_keyword_workflow("养生", candidates=candidates, primary_channel="xiaohongshu")
        optimized_title = result.topics[0].optimized_title

        self.assertEqual(optimized_title, "久坐职场女性可收藏的 4 个低成本习惯")
        self.assertIn(f"小红书标题：{optimized_title}", result.xhs_package)
        self.assertNotIn("治疗", optimized_title)
        self.assertNotIn("诊断", optimized_title)


if __name__ == "__main__":
    unittest.main()
