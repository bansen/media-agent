import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from content_agent.models import CandidateContent
from content_agent.config import AgentConfig
from content_agent.web import (
    SESSION_COOKIE,
    ContentAgentHandler,
    JobStore,
    WebJob,
    WebRunOptions,
    validate_step_prerequisites,
    render_index_html,
    render_landing_html,
    render_trial_html,
    run_agent_workflow,
    submit_stored_previewed_wechat_draft,
    submit_previewed_wechat_draft,
    _options_from_json,
    _options_to_json,
)


class WebTests(unittest.TestCase):
    def test_index_html_contains_workbench_controls(self):
        html = render_index_html()

        self.assertIn('id="keyword"', html)
        self.assertIn('value="baidu_search"', html)
        self.assertNotIn('value="free_hot"', html)
        self.assertNotIn('value="mock"', html)
        self.assertNotIn('value="public_search"', html)
        self.assertNotIn("public_search API", html)
        self.assertIn('id="useLlm"', html)
        self.assertIn('id="formatGzh"', html)
        self.assertIn('id="formatTheme"', html)
        self.assertIn('id="coverStyle"', html)
        self.assertIn('data-step="materials"', html)
        self.assertIn('data-step="content"', html)
        self.assertIn('data-step="format"', html)
        self.assertIn('data-step="cover"', html)
        self.assertIn('id="submitDraftButton"', html)
        self.assertIn('id="historyList"', html)
        self.assertIn("历史记录", html)
        self.assertIn("loadHistory", html)
        self.assertIn("statusLabels", html)
        self.assertIn("publishLabel", html)
        self.assertIn('href="/settings/wechat"', html)
        self.assertIn("公众号参数", html)
        self.assertIn('href="/auth/wechat-official/start"', html)
        self.assertIn("授权公众号", html)
        self.assertNotIn('id="submitWechatDraft"', html)

    def test_landing_html_introduces_product_with_platform_neutral_ctas(self):
        html = render_landing_html()

        self.assertIn("Media Agent", html)
        self.assertIn("把自媒体创作从想法推进到可发布", html)
        self.assertIn("自动筛选爆款数据", html)
        self.assertIn("公众号", html)
        self.assertIn("小红书", html)
        self.assertIn("百家号", html)
        self.assertIn('href="/trial"', html)
        self.assertNotIn("微信授权试用", html)
        self.assertNotIn("手动填写公众号参数", html)
        self.assertNotIn('id="runForm"', html)

    def test_trial_html_lists_available_and_coming_platforms(self):
        html = render_trial_html()

        self.assertIn("选择要试用的平台", html)
        self.assertIn("微信公众号", html)
        self.assertIn('href="/auth/wechat/start?next=/app"', html)
        self.assertIn('href="/auth/wechat-official/start"', html)
        self.assertIn('href="/auth/manual"', html)
        self.assertIn("百家号", html)
        self.assertIn("小红书", html)
        self.assertIn("敬请期待", html)

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

        with patch("content_agent.web.collect_baidu_search_candidates", return_value=[candidate]):
            payload = run_agent_workflow(
                WebRunOptions(
                    keyword="AI副业",
                    channel="wechat",
                    collector="baidu_search",
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
        self.assertIn("正在用百度搜索收集候选素材", events)
        self.assertIn("正在评分并生成选题", events)

    def test_run_agent_workflow_falls_back_to_keyword_seed_when_baidu_search_is_empty(self):
        events = []

        with patch("content_agent.web.collect_baidu_search_candidates", return_value=[]):
            payload = run_agent_workflow(
                WebRunOptions(
                    keyword="codex制作出海网站",
                    channel="wechat",
                    collector="baidu_search",
                    use_llm=False,
                    format_gzh=False,
                    generate_cover=False,
                    submit_wechat_draft=False,
                    output_dir=Path("output"),
                ),
                progress=events.append,
            )

        self.assertEqual(payload["keyword"], "codex制作出海网站")
        self.assertGreaterEqual(len(payload["topics"]), 1)
        self.assertIn("codex制作出海网站", payload["topics"][0]["title"])
        self.assertEqual(payload["topics"][0]["source"], "keyword_seed")
        self.assertIn("百度搜索暂无结果，已改用关键词种子选题", events)

    def test_run_agent_workflow_can_use_baidu_search_collector(self):
        candidate = CandidateContent(
            title="Codex 制作出海网站的 5 个关键步骤",
            source="baidu_search",
            url="https://example.com/codex-site",
            heat=84,
            interaction=76,
            hook=86,
            pain=80,
            reuse=88,
            material=78,
        )
        events = []

        with patch("content_agent.web.collect_baidu_search_candidates", return_value=[candidate]):
            payload = run_agent_workflow(
                WebRunOptions(
                    keyword="codex制作出海网站",
                    channel="wechat",
                    collector="baidu_search",
                    use_llm=False,
                    format_gzh=False,
                    generate_cover=False,
                    submit_wechat_draft=False,
                    output_dir=Path("output"),
                ),
                progress=events.append,
            )

        self.assertEqual(payload["topics"][0]["source"], "baidu_search")
        self.assertIn("Codex 制作出海网站", payload["topics"][0]["title"])
        self.assertIn("正在用百度搜索收集候选素材", events)

    def test_web_rejects_paid_public_search_collector(self):
        with self.assertRaisesRegex(ValueError, "collector must be baidu_search"):
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

        with patch("content_agent.web.collect_baidu_search_candidates", return_value=[candidate]):
            payload = run_agent_workflow(
                WebRunOptions(
                    keyword="AI副业",
                    channel="wechat",
                    collector="baidu_search",
                    use_llm=False,
                    format_gzh=True,
                    generate_cover=False,
                    submit_wechat_draft=False,
                    output_dir=Path("output"),
                ),
                progress=events.append,
            )

        self.assertIn("gzh_formatting", payload)
        self.assertIn("正在进行公众号排版", events)

    def test_web_run_options_persist_format_and_cover_styles(self):
        options = WebRunOptions(
            keyword="AI副业",
            format_theme="tech-blue",
            cover_style="real-photo",
        )

        stored = _options_from_json(_options_to_json(options))

        self.assertEqual(stored.format_theme, "tech-blue")
        self.assertEqual(stored.cover_style, "real-photo")

    def test_run_agent_workflow_applies_selected_cover_style_once(self):
        candidate = CandidateContent(
            title="AI副业真实案例",
            source="baidu_search",
            url="https://example.com/topic",
            heat=88,
            interaction=82,
            hook=80,
            pain=78,
            reuse=76,
            material=75,
        )

        with patch("content_agent.web.collect_baidu_search_candidates", return_value=[candidate]):
            payload = run_agent_workflow(
                WebRunOptions(
                    keyword="AI副业",
                    channel="wechat",
                    collector="baidu_search",
                    cover_style="real-photo",
                    format_gzh=False,
                )
            )

        self.assertIn("realistic lifestyle photography", payload["cover_prompt"])
        self.assertNotIn("business technology editorial photo", payload["cover_prompt"])

    def test_step_prerequisites_block_missing_previous_steps(self):
        with self.assertRaisesRegex(ValueError, "请先搜素材"):
            validate_step_prerequisites("content", None)
        with self.assertRaisesRegex(ValueError, "请先生成内容"):
            validate_step_prerequisites("format", {"topics": [{}]})
        with self.assertRaisesRegex(ValueError, "请先生成封面"):
            validate_step_prerequisites(
                "submit",
                {"topics": [{}], "gzh_formatting": {"clean_html": "output/a.html"}},
            )

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

        with patch("content_agent.web.collect_baidu_search_candidates", return_value=[candidate]):
            payload = run_agent_workflow(
                WebRunOptions(
                    keyword="AI副业",
                    channel="wechat",
                    collector="baidu_search",
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
        self.assertIn("正在从预览提交公众号草稿箱", events)
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

    def test_submit_stored_previewed_wechat_draft_uses_snapshot_before_publishing_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JobStore(database_url=f"sqlite:///{Path(tmpdir) / 'web.db'}", auto_start=False)
            clean_html = Path(tmpdir) / "preview.html"
            clean_html.write_text("<p>已预览内容</p>", encoding="utf-8")
            cover_image = Path(tmpdir) / "cover.jpg"
            cover_image.write_bytes(b"fake-image")
            job = store.create(WebRunOptions(keyword="AI副业"), user_id=1)
            result_payload = {
                "keyword": "AI副业",
                "expanded_keywords": ["AI副业"],
                "topics": [
                    {
                        "title": "来源标题",
                        "optimized_title": "普通人做 AI 副业，先看懂这 3 个真实信号",
                        "score": {"total": 81.1, "level": "A", "reasons": []},
                        "source": "baidu_search",
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
            }
            store._update(job.id, status="preview_ready", result=result_payload, event="Job completed")

            with patch("content_agent.web.publish_wechat_draft") as publish:
                publish.return_value.thumb_media_id = "MEDIA_ID"
                publish.return_value.response = {"errcode": 0, "media_id": "DRAFT_ID"}
                submitted = submit_stored_previewed_wechat_draft(store, job.id, config=object())

        self.assertEqual(submitted.status, "published_draft")
        self.assertEqual(submitted.result["wechat_draft"]["thumb_media_id"], "MEDIA_ID")
        self.assertIn("开始提交草稿箱", submitted.events)
        self.assertIn("草稿箱提交完成", submitted.events)

    def test_wechat_publish_config_prefers_component_authorized_account(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JobStore(database_url=f"sqlite:///{Path(tmpdir) / 'web.db'}", auto_start=False)
            user = store.auth.upsert_external_user(provider="wechat", provider_user_id="openid-1", display_name="用户")
            store.auth.update_manual_wechat_account(
                user_id=user.id,
                display_name="手动公众号",
                app_id="wx-manual",
                app_secret="manual-secret",
                access_token="manual-token",
            )
            store.auth.upsert_component_wechat_account(
                user_id=user.id,
                authorizer_appid="wx-authorizer",
                display_name="授权公众号",
                authorizer_refresh_token="refresh-token",
                authorizer_access_token="component-token",
                expires_in=7200,
                profile={},
            )
            handler = object.__new__(ContentAgentHandler)
            handler.store = store
            base_config = AgentConfig(
                llm_provider="deepseek",
                llm_base_url="https://api.deepseek.com",
                llm_model="deepseek-chat",
                llm_api_key="secret",
                replicate_api_token="replicate-secret",
                replicate_cover_model_version="",
                replicate_cover_model="black-forest-labs/flux-1.1-pro",
                wechat_app_id="env-app",
                wechat_app_secret="env-secret",
                wechat_access_token="",
                free_hot_sources=["google_news_rss"],
                database_url=f"sqlite:///{Path(tmpdir) / 'web.db'}",
            )

            with patch("content_agent.web.AgentConfig.from_env_file", return_value=base_config):
                publish_config = handler._wechat_publish_config_for_user(user.id)

        self.assertEqual(publish_config.wechat_app_id, "wx-authorizer")
        self.assertEqual(publish_config.wechat_app_secret, "")
        self.assertEqual(publish_config.wechat_access_token, "component-token")


if __name__ == "__main__":
    unittest.main()
