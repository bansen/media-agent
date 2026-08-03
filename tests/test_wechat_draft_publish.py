import tempfile
import unittest
from pathlib import Path

from PIL import Image

from content_agent.config import AgentConfig
from content_agent.formatters.wechat_gzh import format_wechat_markdown
from content_agent.mock_data import get_mock_candidates
from content_agent.wechat_publish import prepare_wechat_thumb_image, publish_wechat_draft
from content_agent.workflow import run_keyword_workflow


class FakeWeChatPublisher:
    def __init__(self):
        self.uploaded = []
        self.submitted = []

    def upload_thumb_material(self, access_token, image_path, mime_type="image/jpeg"):
        self.uploaded.append((access_token, Path(image_path).name, mime_type))
        return "NEW_MEDIA_ID"

    def submit_draft(self, access_token, payload):
        self.submitted.append((access_token, payload))
        return {"errcode": 0, "media_id": "DRAFT_MEDIA_ID"}


class WeChatDraftPublishTests(unittest.TestCase):
    def test_publishes_formatted_article_to_wechat_draft(self):
        result = run_keyword_workflow("AI副业", get_mock_candidates("AI副业", channel="wechat"))
        html = format_wechat_markdown("# 标题\n\n## 第一节\n\n正文内容。")
        config = AgentConfig(
            llm_provider="deepseek",
            llm_base_url="https://api.deepseek.com",
            llm_model="deepseek-chat",
            llm_api_key="",
            replicate_api_token="",
            replicate_cover_model_version="",
            replicate_cover_model="black-forest-labs/flux-1.1-pro",
            wechat_app_id="appid",
            wechat_app_secret="secret",
            wechat_access_token="ACCESS_TOKEN",
            free_hot_sources=["google_news_rss", "hn", "github"],
            database_url="",
        )
        publisher = FakeWeChatPublisher()

        with tempfile.TemporaryDirectory() as tmpdir:
            cover = Path(tmpdir) / "cover.jpg"
            _write_test_image(cover, image_format="JPEG")
            published = publish_wechat_draft(
                result=result,
                content_html=html,
                cover_image_path=cover,
                config=config,
                publisher=publisher,
            )

        self.assertEqual(publisher.uploaded, [("ACCESS_TOKEN", "cover.jpg", "image/jpeg")])
        self.assertEqual(publisher.submitted[0][0], "ACCESS_TOKEN")
        self.assertEqual(publisher.submitted[0][1]["articles"][0]["thumb_media_id"], "NEW_MEDIA_ID")
        self.assertEqual(publisher.submitted[0][1]["articles"][0]["content"], html)
        self.assertEqual(published.response["media_id"], "DRAFT_MEDIA_ID")

    def test_converts_webp_cover_to_wechat_jpeg_thumb(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cover = Path(tmpdir) / "cover.jpg"
            _write_test_image(cover, image_format="WEBP")

            thumb = prepare_wechat_thumb_image(cover)

            self.assertEqual(thumb.name, "cover_wechat_thumb.jpg")
            self.assertLessEqual(thumb.stat().st_size, 64 * 1024)
            self.assertEqual(thumb.read_bytes()[:2], b"\xff\xd8")

    def test_wechat_thumb_preserves_sixteen_to_nine_cover_ratio(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cover = Path(tmpdir) / "cover.webp"
            image = Image.new("RGB", (1000, 1000), color=(28, 92, 78))
            image.save(cover, format="WEBP")

            thumb = prepare_wechat_thumb_image(cover)

            with Image.open(thumb) as thumb_image:
                width, height = thumb_image.size

            self.assertGreaterEqual(width, 890)
            self.assertLessEqual(width, 900)
            self.assertLessEqual(height, 506)
            self.assertAlmostEqual(width / height, 16 / 9, places=2)

    def test_publish_converts_webp_cover_before_upload(self):
        result = run_keyword_workflow("AI副业", get_mock_candidates("AI副业", channel="wechat"))
        config = AgentConfig(
            llm_provider="deepseek",
            llm_base_url="https://api.deepseek.com",
            llm_model="deepseek-chat",
            llm_api_key="",
            replicate_api_token="",
            replicate_cover_model_version="",
            replicate_cover_model="black-forest-labs/flux-1.1-pro",
            wechat_app_id="appid",
            wechat_app_secret="secret",
            wechat_access_token="ACCESS_TOKEN",
            free_hot_sources=["google_news_rss", "hn", "github"],
            database_url="",
        )
        publisher = FakeWeChatPublisher()

        with tempfile.TemporaryDirectory() as tmpdir:
            cover = Path(tmpdir) / "cover.jpg"
            _write_test_image(cover, image_format="WEBP")
            publish_wechat_draft(
                result=result,
                content_html="<section>正文</section>",
                cover_image_path=cover,
                config=config,
                publisher=publisher,
            )

        self.assertEqual(publisher.uploaded, [("ACCESS_TOKEN", "cover_wechat_thumb.jpg", "image/jpeg")])

    def test_requires_cover_image_for_wechat_draft(self):
        result = run_keyword_workflow("AI副业", get_mock_candidates("AI副业", channel="wechat"))
        config = AgentConfig(
            llm_provider="deepseek",
            llm_base_url="https://api.deepseek.com",
            llm_model="deepseek-chat",
            llm_api_key="",
            replicate_api_token="",
            replicate_cover_model_version="",
            replicate_cover_model="black-forest-labs/flux-1.1-pro",
            wechat_app_id="appid",
            wechat_app_secret="secret",
            wechat_access_token="ACCESS_TOKEN",
            free_hot_sources=["google_news_rss", "hn", "github"],
            database_url="",
        )

        with self.assertRaises(FileNotFoundError):
            publish_wechat_draft(
                result=result,
                content_html="<section></section>",
                cover_image_path=Path("missing.jpg"),
                config=config,
                publisher=FakeWeChatPublisher(),
            )


def _write_test_image(path: Path, image_format: str) -> None:
    image = Image.new("RGB", (320, 180), color=(28, 92, 78))
    image.save(path, format=image_format)


if __name__ == "__main__":
    unittest.main()
