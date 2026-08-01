import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from content_agent.models import CandidateContent
from content_agent.web import (
    SESSION_COOKIE,
    WebJob,
    WebRunOptions,
    render_index_html,
    render_landing_html,
    run_agent_workflow,
    submit_previewed_wechat_draft,
)


class WebTests(unittest.TestCase):
    def test_index_html_contains_workbench_controls(self):
        html = render_index_html()

        self.assertIn('id="keyword"', html)
        self.assertIn('value="free_hot"', html)
        self.assertNotIn('value="public_search"', html)
        self.assertNotIn("public_search API", html)
        self.assertIn('id="useLlm"', html)
        self.assertIn('id="formatGzh"', html)
        self.assertIn('id="submitDraftButton"', html)
        self.assertIn('id="historyList"', html)
        self.assertIn("历史记录", html)
        self.assertIn("loadHistory", html)
        self.assertIn('href="/settings/wechat"', html)
        self.assertIn("公众号参数", html)
        self.assertNotIn('id="submitWechatDraft"', html)

    def test_landing_html_introduces_product_and_links_to_wechat_trial(self):
        html = render_landing_html()

        self.assertIn("Media Agent", html)
        self.assertIn("从爆款选题到公众号草稿箱", html)
        self.assertIn('href="/auth/wechat/start?next=/app"', html)
        self.assertIn('href="/auth/manual"', html)
        self.assertIn("手动填写公众号参数", html)
        self.assertNotIn('id="runForm"', html)

    def test_session_cookie_name_is_stable(self):
        self.assertEqual(SESSION_COOKIE, "media_agent_session")

    def test_index_html_keeps_long_names_readable(self):
        html = render_index_html()

        self.assertIn("Content Agent 内容工作台", html)
        self.assertIn("overflow-wrap: anywhere", html)
        self.assertIn("source-title", html)

    def test_run_agent_workflow_returns_progress_and_payload(self):
        candidate = CandidateContent(
            title="真实热榜里的 AI 副业趋势",
            source="google_news_rss",
            url="https://example.com/topic",
            heat=88,
            interaction=82,
            hook=80,
            pain=78,
            reuse=76,
            material=75,
        )
        events = []

        with patch("content_agent.web.collect_free_hot_candidates", return_value=[candidate]):
            payload = run_agent_workflow(
                WebRunOptions(
                    keyword="AI副业",
                    channel="wechat",
                    collector="free_hot",
                    use_llm=False,
                    format_gzh=False,
                    generate_cover=False,
                    submit_wechat_draft=False,
                    output_dir=Path("output"),
                ),
                progress=events.append,
            )

        self.assertEqual(payload["keyword"], "AI副业")
        self.assertEqual(payload["topics"][0]["title"], "真实热榜里的 AI 副业趋势")
        self.assertIn("Collecting candidates with free_hot", events)
        self.assertIn("Scoring and building channel outputs", events)

    def test_web_rejects_paid_public_search_collector(self):
        with self.assertRaisesRegex(ValueError, "collector must be mock or free_hot"):
            run_agent_workflow(WebRunOptions(keyword="AI副业", channel="wechat", collector="public_search"))

    def test_run_agent_workflow_can_format_gzh_preview(self):
        candidate = CandidateContent(
            title="公众号排版测试",
            source="mock",
            url="https://example.com/topic",
            heat=88,
            interaction=82,
            hook=80,
            pain=78,
            reuse=76,
            material=75,
        )
        events = []

        with patch("content_agent.web.get_mock_candidates", return_value=[candidate]):
            payload = run_agent_workflow(
                WebRunOptions(
                    keyword="AI副业",
                    channel="wechat",
                    collector="mock",
                    use_llm=False,
                    format_gzh=True,
                    generate_cover=False,
                    submit_wechat_draft=False,
                    output_dir=Path("output"),
                ),
                progress=events.append,
            )

        self.assertIn("gzh_formatting", payload)
        self.assertIn("Formatting WeChat article", events)

    def test_run_agent_workflow_exposes_existing_cover_for_preview_submit(self):
        candidate = CandidateContent(
            title="已有封面图测试",
            source="mock",
            url="https://example.com/topic",
            heat=88,
            interaction=82,
            hook=80,
            pain=78,
            reuse=76,
            material=75,
        )

        with patch("content_agent.web.get_mock_candidates", return_value=[candidate]):
            payload = run_agent_workflow(
                WebRunOptions(
                    keyword="AI副业",
                    channel="wechat",
                    collector="mock",
                    use_llm=False,
                    format_gzh=False,
                    generate_cover=False,
                    submit_wechat_draft=False,
                    wechat_cover_image="output/manual-cover.jpg",
                    output_dir=Path("output"),
                )
            )

        self.assertEqual(payload["cover_image"]["path"], "output/manual-cover.jpg")
        self.assertEqual(payload["cover_image"]["model"], "manual")

    def test_submit_previewed_wechat_draft_uses_existing_preview_and_cover(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            clean_html = Path(tmpdir) / "preview.html"
            clean_html.write_text("<p>已预览内容</p>", encoding="utf-8")
            cover_image = Path(tmpdir) / "cover.jpg"
            cover_image.write_bytes(b"fake-image")
            job = WebJob(
                id="job1",
                options=WebRunOptions(keyword="AI副业"),
                status="completed",
                result={
                    "keyword": "AI副业",
                    "expanded_keywords": ["AI副业"],
                    "topics": [
                        {
                            "title": "来源标题",
                            "optimized_title": "普通人做 AI 副业，先看懂这 3 个真实信号",
                            "score": {"total": 81.1, "level": "A", "reasons": []},
                            "source": "mock",
                            "url": "https://example.com/topic",
                            "platform_fit": ["wechat"],
                            "angle": "普通人视角",
                            "material_needs": ["案例"],
                            "risk_notes": ["避免承诺收益"],
                        }
                    ],
                    "wechat_outline": "公众号文章：《普通人做 AI 副业，先看懂这 3 个真实信号》",
                    "xhs_package": "小红书标题：普通人做 AI 副业，先看懂这 3 个真实信号",
                    "cover_prompt": "Replicate image prompt",
                    "gzh_formatting": {"clean_html": str(clean_html), "preview_html": str(clean_html)},
                    "cover_image": {"path": str(cover_image), "url": "", "model": "mock", "prompt": "mock"},
                },
            )
            events = []

            with patch("content_agent.web.AgentConfig.from_env_file", return_value=object()), patch(
                "content_agent.web.publish_wechat_draft"
            ) as publish:
                publish.return_value.thumb_media_id = "MEDIA_ID"
                publish.return_value.response = {"errcode": 0, "media_id": "DRAFT_ID"}

                result = submit_previewed_wechat_draft(job, progress=events.append)

        self.assertEqual(result["wechat_draft"]["thumb_media_id"], "MEDIA_ID")
        self.assertIn("Submitting WeChat draft from preview", events)
        self.assertEqual(publish.call_args.kwargs["content_html"], "<p>已预览内容</p>")
        self.assertEqual(publish.call_args.kwargs["cover_image_path"], str(cover_image))

    def test_submit_previewed_wechat_draft_requires_completed_preview(self):
        job = WebJob(
            id="job1",
            options=WebRunOptions(keyword="AI副业"),
            status="running",
            result=None,
        )

        with self.assertRaisesRegex(ValueError, "completed preview"):
            submit_previewed_wechat_draft(job)


if __name__ == "__main__":
    unittest.main()
