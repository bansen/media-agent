import io
import json
import tempfile
import unittest
from dataclasses import dataclass
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from content_agent.cli import main
from content_agent.models import CandidateContent
from content_agent.providers.image import ReplicateImageProvider
from content_agent.providers.llm import OpenAICompatibleLLMProvider
from content_agent.providers.wechat import WeChatAPIError, WeChatDraftPublisher


@dataclass(frozen=True)
class FakeGeneratedCover:
    path: Path
    url: str
    model: str


class ProviderCliTests(unittest.TestCase):
    def test_openai_compatible_provider_builds_deepseek_payload(self):
        provider = OpenAICompatibleLLMProvider(
            api_key="secret",
            base_url="https://api.deepseek.com",
            model="deepseek-chat",
        )

        payload = provider.build_payload("生成 3 个选题")

        self.assertEqual(payload["model"], "deepseek-chat")
        self.assertEqual(payload["messages"][0]["role"], "user")
        self.assertEqual(payload["messages"][0]["content"], "生成 3 个选题")

    def test_replicate_provider_builds_prediction_payload(self):
        provider = ReplicateImageProvider(api_token="secret", model_version="model-version")

        payload = provider.build_prediction_payload("clean cover")

        self.assertEqual(payload["version"], "model-version")
        self.assertEqual(payload["input"]["prompt"], "clean cover")

    def test_wechat_publisher_builds_draft_url(self):
        publisher = WeChatDraftPublisher(app_id="APPID", app_secret="SECRET")

        url = publisher.draft_add_url("ACCESS_TOKEN")

        self.assertIn("/cgi-bin/draft/add", url)
        self.assertIn("access_token=ACCESS_TOKEN", url)

    def test_wechat_publisher_builds_cover_upload_url(self):
        publisher = WeChatDraftPublisher(app_id="APPID", app_secret="SECRET")

        url = publisher.permanent_material_add_url("ACCESS_TOKEN", media_type="thumb")

        self.assertIn("/cgi-bin/material/add_material", url)
        self.assertIn("access_token=ACCESS_TOKEN", url)
        self.assertIn("type=thumb", url)

    def test_wechat_publisher_builds_multipart_image_body(self):
        publisher = WeChatDraftPublisher(app_id="APPID", app_secret="SECRET")

        content_type, body = publisher.build_media_upload_body(
            filename="cover.jpg",
            data=b"fake-image",
            mime_type="image/jpeg",
            boundary="BOUNDARY",
        )

        self.assertEqual(content_type, "multipart/form-data; boundary=BOUNDARY")
        self.assertIn(b'name="media"; filename="cover.jpg"', body)
        self.assertIn(b"Content-Type: image/jpeg", body)
        self.assertIn(b"fake-image", body)

    def test_wechat_access_token_ip_whitelist_error_is_actionable(self):
        publisher = WeChatDraftPublisher(app_id="APPID", app_secret="SECRET")

        error = publisher.error_from_response(
            {
                "errcode": 40164,
                "errmsg": "invalid ip 183.40.36.116 ipv6 ::ffff:183.40.36.116, not in whitelist",
            },
            operation="fetch_access_token",
        )

        self.assertIsInstance(error, WeChatAPIError)
        self.assertIn("183.40.36.116", str(error))
        self.assertIn("IP 白名单", str(error))

    def test_cli_prints_json_workflow_result(self):
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = main(["--keyword", "AI副业"])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["keyword"], "AI副业")
        self.assertGreaterEqual(len(payload["topics"]), 1)
        self.assertIn("cover_prompt", payload)

    def test_cli_can_use_public_search_collector(self):
        stdout = io.StringIO()
        public_candidate = CandidateContent(
            title="真实搜索来的 AI 副业案例",
            source="bing",
            url="https://example.com/public",
            heat=86,
            interaction=80,
            hook=82,
            pain=78,
            reuse=76,
            material=74,
        )

        with redirect_stdout(stdout), patch(
            "content_agent.cli.collect_public_search_candidates",
            return_value=[public_candidate],
        ) as collect:
            exit_code = main(["--keyword", "AI副业", "--collector", "public_search"])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["topics"][0]["title"], "真实搜索来的 AI 副业案例")
        collect.assert_called_once()

    def test_cli_can_use_free_hot_collector(self):
        stdout = io.StringIO()
        free_candidate = CandidateContent(
            title="免费热榜里的 AI 副业趋势",
            source="google_news_rss",
            url="https://example.com/free-hot",
            heat=88,
            interaction=82,
            hook=80,
            pain=78,
            reuse=76,
            material=75,
        )

        with redirect_stdout(stdout), patch(
            "content_agent.cli.collect_free_hot_candidates",
            return_value=[free_candidate],
        ) as collect:
            exit_code = main(["--keyword", "AI副业", "--collector", "free_hot"])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["topics"][0]["title"], "免费热榜里的 AI 副业趋势")
        collect.assert_called_once()

    def test_cli_formats_gzh_preview_without_llm(self):
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as tmpdir:
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--keyword",
                        "AI副业",
                        "--channel",
                        "wechat",
                        "--format-gzh",
                        "--output-dir",
                        tmpdir,
                    ]
                )

            payload = json.loads(stdout.getvalue())
            clean_html = Path(payload["gzh_formatting"]["clean_html"])
            preview_html = Path(payload["gzh_formatting"]["preview_html"])

        self.assertEqual(exit_code, 0)
        self.assertTrue(clean_html.name.endswith(".html"))
        self.assertTrue(preview_html.name.endswith("_预览.html"))

    def test_cli_requires_cover_image_when_submitting_wechat_draft(self):
        stderr = io.StringIO()

        with patch("sys.stderr", stderr):
            exit_code = main(
                [
                    "--keyword",
                    "AI副业",
                    "--channel",
                    "wechat",
                    "--format-gzh",
                    "--submit-wechat-draft",
                ]
            )

        self.assertEqual(exit_code, 2)
        self.assertIn("--wechat-cover-image is required", stderr.getvalue())

    def test_cli_submit_can_generate_cover_instead_of_manual_cover_path(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        with tempfile.TemporaryDirectory() as tmpdir, redirect_stdout(stdout), patch("sys.stderr", stderr), patch(
            "content_agent.cli.generate_cover_image",
            return_value=FakeGeneratedCover(
                path=Path(tmpdir) / "generated-cover.jpg",
                url="https://replicate.delivery/mock/output.jpg",
                model="black-forest-labs/flux-1.1-pro",
            ),
        ), patch("content_agent.cli.publish_wechat_draft") as publish:
            publish.return_value.thumb_media_id = "MEDIA_ID"
            publish.return_value.response = {"errcode": 0, "media_id": "DRAFT_ID"}
            exit_code = main(
                [
                    "--keyword",
                    "AI副业",
                    "--channel",
                    "wechat",
                    "--format-gzh",
                    "--submit-wechat-draft",
                    "--generate-cover",
                    "--output-dir",
                    tmpdir,
                ]
            )

        self.assertNotEqual(exit_code, 2)
        self.assertNotIn("--wechat-cover-image is required", stderr.getvalue())

    def test_cli_returns_partial_payload_when_wechat_submit_fails(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        with tempfile.TemporaryDirectory() as tmpdir, redirect_stdout(stdout), patch("sys.stderr", stderr), patch(
            "content_agent.cli.generate_cover_image",
            return_value=FakeGeneratedCover(
                path=Path(tmpdir) / "generated-cover.jpg",
                url="https://replicate.delivery/mock/output.jpg",
                model="black-forest-labs/flux-1.1-pro",
            ),
        ), patch("content_agent.cli.publish_wechat_draft", side_effect=RuntimeError("IP 白名单错误")):
            exit_code = main(
                [
                    "--keyword",
                    "AI副业",
                    "--channel",
                    "wechat",
                    "--format-gzh",
                    "--submit-wechat-draft",
                    "--generate-cover",
                    "--output-dir",
                    tmpdir,
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertIn("gzh_formatting", payload)
        self.assertIn("cover_image", payload)
        self.assertIn("wechat_draft_error", payload)
        self.assertIn("IP 白名单错误", payload["wechat_draft_error"])

    def test_cli_can_submit_existing_wechat_html_and_cover_without_regenerating(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        with tempfile.TemporaryDirectory() as tmpdir:
            content_html = Path(tmpdir) / "article.html"
            content_html.write_text("<section>已经排版好的正文</section>", encoding="utf-8")
            cover_image = Path(tmpdir) / "cover.jpg"
            cover_image.write_bytes(b"fake-image")

            with redirect_stdout(stdout), patch("sys.stderr", stderr), patch(
                "content_agent.cli.generate_cover_image"
            ) as generate_cover, patch("content_agent.cli.format_wechat_markdown") as format_markdown, patch(
                "content_agent.cli.publish_wechat_draft"
            ) as publish:
                publish.return_value.thumb_media_id = "MEDIA_ID"
                publish.return_value.response = {"errcode": 0, "media_id": "DRAFT_ID"}
                exit_code = main(
                    [
                        "--keyword",
                        "AI副业",
                        "--channel",
                        "wechat",
                        "--submit-wechat-draft",
                        "--wechat-content-html",
                        str(content_html),
                        "--wechat-cover-image",
                        str(cover_image),
                    ]
                )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["wechat_content_html"], str(content_html))
        generate_cover.assert_not_called()
        format_markdown.assert_not_called()
        publish.assert_called_once()
        self.assertEqual(publish.call_args.kwargs["content_html"], "<section>已经排版好的正文</section>")


if __name__ == "__main__":
    unittest.main()
