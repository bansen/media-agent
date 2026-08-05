import unittest

from content_agent.models import CandidateContent
from content_agent.workflow import run_keyword_workflow
from content_agent.exporters import build_wechat_draft_payload, export_xhs_markdown


class WorkflowExportTests(unittest.TestCase):
    def test_workflow_ranks_topics_and_builds_channel_outputs(self):
        candidates = [
            CandidateContent(
                title="普通人用 AI 做副业，最容易踩的 5 个坑",
                source="manual",
                url="https://example.com/a",
                heat=80,
                interaction=76,
                hook=90,
                pain=88,
                reuse=82,
                material=70,
            ),
            CandidateContent(
                title="下班后做副业前，先学会这 3 个 AI 工具",
                source="manual",
                url="https://example.com/b",
                heat=65,
                interaction=61,
                hook=74,
                pain=72,
                reuse=78,
                material=70,
            ),
        ]

        result = run_keyword_workflow("AI副业", candidates=candidates)

        self.assertEqual(result.keyword, "AI副业")
        self.assertEqual(result.topics[0].title, "普通人用 AI 做副业，最容易踩的 5 个坑")
        self.assertEqual(result.topics[0].score.level, "A")
        self.assertEqual(result.topics[0].platform_fit, ["wechat", "xiaohongshu"])
        self.assertIn("公众号", result.wechat_outline)
        self.assertIn("小红书", result.xhs_package)
        self.assertIn("Replicate", result.cover_prompt)

    def test_wechat_cover_prompt_avoids_blank_card_artifacts(self):
        candidates = [
            CandidateContent(
                title="普通人用 AI 做副业，最容易踩的 5 个坑",
                source="manual",
                url="https://example.com/a",
                heat=80,
                interaction=76,
                hook=90,
                pain=88,
                reuse=82,
                material=70,
            )
        ]

        result = run_keyword_workflow("AI副业", candidates=candidates, primary_channel="wechat")
        prompt = result.cover_prompt.lower()

        self.assertNotIn("knowledge-card", prompt)
        self.assertNotIn("empty space", prompt)
        self.assertIn("no blank white rectangle", prompt)
        self.assertIn("no poster board", prompt)
        self.assertIn("16:9 wide cover", prompt)
        self.assertNotIn("2.35:1", prompt)

    def test_wechat_cover_prompt_adapts_to_ai_side_hustle_risk_topic(self):
        candidates = [
            CandidateContent(
                title="普通人用 AI 做副业，最容易踩的 5 个坑",
                source="manual",
                url="https://example.com/a",
                heat=80,
                interaction=76,
                hook=90,
                pain=88,
                reuse=82,
                material=70,
            )
        ]

        result = run_keyword_workflow("AI副业", candidates=candidates, primary_channel="wechat")
        prompt = result.cover_prompt.lower()

        self.assertIn("risk-aware", prompt)
        self.assertIn("decision-making workspace", prompt)
        self.assertNotIn("medical", prompt.replace("no medical claims", ""))

    def test_wechat_cover_prompt_adapts_to_ai_learning_tool_topic(self):
        candidates = [
            CandidateContent(
                title="AI学习不是报课，普通人先跑通这 4 个场景",
                source="manual",
                url="https://example.com/a",
                heat=76,
                interaction=74,
                hook=82,
                pain=82,
                reuse=88,
                material=82,
            )
        ]

        result = run_keyword_workflow("AI学习", candidates=candidates, primary_channel="wechat")
        prompt = result.cover_prompt.lower()

        self.assertIn("hands-on ai learning workspace", prompt)
        self.assertIn("abstract software interfaces", prompt)
        self.assertNotIn("money piles", prompt.replace("no money piles", ""))

    def test_wechat_outline_keeps_keyword_and_selected_material_context(self):
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

        self.assertIn("用户关键词：minimax h3介绍", result.wechat_outline)
        self.assertIn("选中素材：MiniMax H3正式发布", result.wechat_outline)
        self.assertIn("不要改写成泛泛的 AI 学习或副业赚钱文章", result.wechat_outline)

    def test_tool_integration_keyword_stays_on_deepseek_codex_vision_task(self):
        candidates = [
            CandidateContent(
                title="Codex和DeepSeek-V4-Flash直连的稳定性如何?",
                source="baidu_search",
                url="https://example.com/stability",
                heat=82,
                interaction=76,
                hook=74,
                pain=72,
                reuse=70,
                material=76,
            ),
            CandidateContent(
                title="如何使用DeepSeek-V4-Flash的API?",
                source="baidu_search",
                url="https://example.com/api",
                heat=78,
                interaction=74,
                hook=84,
                pain=80,
                reuse=86,
                material=82,
            ),
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
            ),
        ]

        result = run_keyword_workflow("DeepSeek V4 Flash 接入 Codex + 识图，2分钟搞定", candidates, primary_channel="wechat")
        optimized_title = result.topics[0].optimized_title

        self.assertIn("DeepSeek V4 Flash", optimized_title)
        self.assertIn("Codex", optimized_title)
        self.assertIn("识图", optimized_title)
        self.assertIn("Codex", result.topics[0].title)
        self.assertNotIn("普通人学 AI", optimized_title)
        self.assertIn("工具接入教程", result.wechat_outline)
        self.assertIn("识图验证", result.wechat_outline)
        self.assertNotIn("副业/AI学习方法拆解", result.wechat_outline)

    def test_xiaohongshu_cover_prompt_adapts_to_health_topic(self):
        candidates = [
            CandidateContent(
                title="办公室久坐人群，一天 4 个时间点这样调整",
                source="manual",
                url="https://example.com/a",
                heat=78,
                interaction=80,
                hook=84,
                pain=88,
                reuse=90,
                material=72,
            )
        ]

        result = run_keyword_workflow("养生", candidates=candidates, primary_channel="xiaohongshu")
        prompt = result.cover_prompt.lower()

        self.assertIn("office wellness break", prompt)
        self.assertIn("4:5 vertical social cover", prompt)
        self.assertNotIn("laptop", prompt)
        self.assertNotIn("technology feeling", prompt)

    def test_exports_wechat_payload_and_xhs_markdown_package(self):
        candidates = [
            CandidateContent(
                title="职场女性的 5 个低成本养生习惯",
                source="manual",
                url=None,
                heat=78,
                interaction=80,
                hook=84,
                pain=88,
                reuse=90,
                material=72,
            )
        ]
        result = run_keyword_workflow("养生", candidates=candidates, primary_channel="xiaohongshu")

        payload = build_wechat_draft_payload(result, thumb_media_id="MEDIA_ID")
        markdown = export_xhs_markdown(result)

        self.assertEqual(payload["articles"][0]["thumb_media_id"], "MEDIA_ID")
        self.assertIn("职场女性", payload["articles"][0]["title"])
        self.assertIn("# 小红书发布包", markdown)
        self.assertIn("标签", markdown)

    def test_xiaohongshu_health_candidates_keep_health_positioning(self):
        candidates = [
            CandidateContent(
                title="办公室久坐人群，一天 4 个时间点这样调整",
                source="mock",
                url=None,
                heat=73,
                interaction=78,
                hook=80,
                pain=87,
                reuse=85,
                material=77,
            )
        ]

        result = run_keyword_workflow("养生", candidates=candidates, primary_channel="xiaohongshu")

        self.assertEqual(result.topics[0].platform_fit, ["xiaohongshu"])
        self.assertIn("职场女性和宝妈", result.topics[0].angle)
        self.assertIn("避免医疗诊断", result.topics[0].risk_notes)


if __name__ == "__main__":
    unittest.main()
