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
        self.assertIn("AI", optimized_title)
        self.assertTrue(any(term in optimized_title for term in ["第一单", "切入", "机会", "服务"]))
        self.assertNotEqual(optimized_title, "普通人做 AI 副业，先看懂这 3 个真实信号")
        self.assertIn(f"公众号文章：《{optimized_title}》", result.wechat_outline)
        self.assertIn(f"Main idea: {optimized_title}.", result.cover_prompt)
        self.assertNotIn("封面新闻", optimized_title)
        self.assertNotIn("暴富", optimized_title)
        self.assertNotIn("稳赚", optimized_title)
        self.assertNotIn("月入", optimized_title)
        self.assertNotIn("躺赚", optimized_title)

    def test_wechat_ai_titles_vary_by_topic_angle(self):
        candidates = [
            CandidateContent(
                title="AI副业避坑：这些卖课套路正在收割新人",
                source="baidu_search",
                url="https://example.com/risk",
                heat=90,
                interaction=84,
                hook=88,
                pain=86,
                reuse=77,
                material=76,
            ),
            CandidateContent(
                title="普通人学AI工具的完整路线和提示词教程",
                source="baidu_search",
                url="https://example.com/tool",
                heat=86,
                interaction=80,
                hook=82,
                pain=78,
                reuse=84,
                material=80,
            ),
        ]

        risk = run_keyword_workflow("AI副业", candidates=[candidates[0]], primary_channel="wechat").topics[0].optimized_title
        tool = run_keyword_workflow("AI学习", candidates=[candidates[1]], primary_channel="wechat").topics[0].optimized_title

        self.assertNotEqual(risk, tool)
        self.assertIn("坑", risk)
        self.assertTrue(any(term in tool for term in ["工具", "场景", "路线"]))

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

    def test_wechat_non_ai_keyword_keeps_keyword_context(self):
        candidates = [
            CandidateContent(
                title="GitHub 项目：fighting41love/funNLP",
                source="github",
                url="https://example.com/funnlp",
                heat=92,
                interaction=88,
                hook=74,
                pain=65,
                reuse=84,
                material=80,
            ),
            CandidateContent(
                title="[云框架]SMACK大数据架构 / [Cloudframeworks]SMACK big data architecture",
                source="hn_algolia",
                url="https://example.com/big-data",
                heat=70,
                interaction=68,
                hook=72,
                pain=76,
                reuse=80,
                material=78,
            ),
        ]

        result = run_keyword_workflow("大数据架构", candidates=candidates, primary_channel="wechat")
        optimized_title = result.topics[0].optimized_title

        self.assertEqual(result.topics[0].title, "[云框架]SMACK大数据架构 / [Cloudframeworks]SMACK big data architecture")
        self.assertIn("大数据架构", optimized_title)
        self.assertNotIn("普通人学 AI", optimized_title)
        self.assertIn(f"公众号文章：《{optimized_title}》", result.wechat_outline)

    def test_wechat_model_release_keyword_uses_source_entity_not_raw_search_phrase(self):
        candidates = [
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

        result = run_keyword_workflow("minimax h3介绍", candidates=candidates, primary_channel="wechat")
        optimized_title = result.topics[0].optimized_title

        self.assertIn("MiniMax H3", optimized_title)
        self.assertNotIn("minimax h3介绍", optimized_title)
        self.assertTrue(any(term in optimized_title for term in ["发布", "变化", "看懂"]))

    def test_wechat_title_summarizes_descriptive_keyword_instead_of_copying_it(self):
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

        result = run_keyword_workflow(
            "minimax h3介绍，要突出核心能力（如视频相关等）",
            candidates=candidates,
            primary_channel="wechat",
        )
        optimized_title = result.topics[0].optimized_title

        self.assertIn("MiniMax H3", optimized_title)
        self.assertIn("视频", optimized_title)
        self.assertNotIn("介绍", optimized_title)
        self.assertNotIn("要突出", optimized_title)
        self.assertNotIn("如视频相关等", optimized_title)
        self.assertLessEqual(len(optimized_title), 28)


if __name__ == "__main__":
    unittest.main()
