import json
import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from PIL import Image

from content_agent.config import AgentConfig
from content_agent.cover_generation import SeedreamHttpRunner, generate_cover_image
from tests.test_cover_copy import ARTICLE, FakeLLM


class SeedreamTests(unittest.TestCase):
    def test_web_workflow_and_cover_step_use_selected_provider(self):
        from content_agent.web import WebRunOptions, run_agent_step, run_agent_workflow
        from content_agent.cover_generation import GeneratedCover
        from content_agent.mock_data import get_mock_candidates

        with patch.dict(os.environ, {"IMAGE_PROVIDER": "seedream", "ARK_API_KEY": "ark-secret", "SEEDREAM_MODEL": "my-model"}):
            config = AgentConfig.from_env_file("/nonexistent-seedream-env")
        with tempfile.TemporaryDirectory() as tmp:
            options = WebRunOptions(keyword="AI工具", use_llm=True, format_gzh=False, generate_cover=True, output_dir=Path(tmp))
            cover = GeneratedCover(Path(tmp) / "cover.jpg", "https://example.com/cover.jpg", "my-model", "cover")
            llm = FakeLLM()
            with patch("content_agent.web.AgentConfig.from_env_file", return_value=config), patch("content_agent.web._collect_candidates", return_value=get_mock_candidates("AI副业", channel="wechat")), patch("content_agent.web.generate_cover_image", return_value=cover) as generate, patch.object(AgentConfig, "build_llm_provider", return_value=llm), patch("content_agent.web.generate_llm_content_plan"), patch("content_agent.web.apply_llm_content_plan", side_effect=lambda result, *args, **kwargs: result), patch("content_agent.web.generate_llm_drafts", return_value={"wechat_article": ARTICLE}):
                payload = run_agent_workflow(options)
                payload["cover_prompt"] = "old prompt 16:9 full-bleed"
                regenerated = run_agent_step(options, "cover", payload)
            self.assertEqual(regenerated["cover_copy"]["headline"], "让 AI 分工写文章")
            self.assertEqual(regenerated["cover_image"]["headline"], "让 AI 分工写文章")
            self.assertEqual(len(llm.prompts), 2)
            self.assertEqual(len(llm.review_prompts), 1)  # Unchanged article reuses its review.
            self.assertEqual(generate.call_count, 2)
            for call in generate.call_args_list:
                self.assertEqual(call.kwargs["provider"], "seedream")
                self.assertEqual(call.kwargs["api_token"], "ark-secret")
                self.assertEqual(call.kwargs["model"], "my-model")
                self.assertIn("不要生成任何文字", call.kwargs["prompt"])
                self.assertNotIn("让 AI 分工写文章", call.kwargs["prompt"])
                self.assertNotIn("16:9", call.kwargs["prompt"])
                self.assertNotIn("full-bleed", call.kwargs["prompt"])

    def test_config_selects_seedream_without_exposing_key(self):
        with patch.dict(os.environ, {"IMAGE_PROVIDER": "seedream", "ARK_API_KEY": "ark-secret", "SEEDREAM_MODEL": "my-model"}):
            config = AgentConfig.from_env_file("/nonexistent-seedream-env")
        self.assertEqual(config.image_model, "my-model")
        self.assertEqual(config.image_api_key, "ark-secret")
        self.assertEqual(config.redacted_status()["ARK_API_KEY"], "SET")
        self.assertNotIn("ark-secret", str(config.redacted_status()))

    def test_generation_downloads_and_saves_both_channel_ratios(self):
        for ratio, expected_size, api_size in [("16:9", (1600, 900), "2560x1440"), ("3:4", (1080, 1440), "1728x2304")]:
            with self.subTest(ratio=ratio), tempfile.TemporaryDirectory() as tmp:
                image_bytes = BytesIO()
                Image.new("RGB", expected_size, "green").save(image_bytes, "PNG")
                response = BytesIO(json.dumps({"data": [{"url": "https://example.com/generated.png"}]}).encode())
                with patch("content_agent.cover_generation.request.urlopen", side_effect=[response, BytesIO(image_bytes.getvalue())]) as opened:
                    cover = generate_cover_image("Replicate image prompt: a book", Path(tmp), "demo", "model-id", api_token="ark-secret", provider="seedream", aspect_ratio=ratio)
                req = opened.call_args_list[0].args[0]
                payload = json.loads(req.data)
                self.assertEqual(req.full_url, "https://ark.cn-beijing.volces.com/api/v3/images/generations")
                self.assertEqual(req.get_header("Authorization"), "Bearer ark-secret")
                self.assertEqual(payload["size"], api_size)
                self.assertEqual(payload["prompt"], "a book")
                self.assertEqual(payload["sequential_image_generation"], "disabled")
                self.assertIs(payload["watermark"], False)
                self.assertNotIn("prompt_upsampling", payload)
                with Image.open(cover.path) as saved:
                    self.assertEqual(saved.size, expected_size)
                    self.assertEqual(saved.format, "JPEG")

    def test_missing_key_does_not_make_request(self):
        with patch("content_agent.cover_generation.request.urlopen") as opened:
            with self.assertRaisesRegex(ValueError, "ARK_API_KEY"):
                SeedreamHttpRunner("").run("model", {"prompt": "cover", "aspect_ratio": "16:9"})
        opened.assert_not_called()

    def test_api_errors_are_sanitized(self):
        error = HTTPError("https://example.com", 401, "secret detail", {}, BytesIO(b"secret"))
        with patch("content_agent.cover_generation.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "API Key 无效") as caught:
                SeedreamHttpRunner("ark-secret").run("model", {"prompt": "cover", "aspect_ratio": "16:9"})
        self.assertNotIn("secret", str(caught.exception))

    def test_unavailable_model_has_actionable_message(self):
        error = HTTPError("https://example.com", 404, "Not found", {}, BytesIO(b"{}"))
        with patch("content_agent.cover_generation.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "SEEDREAM_MODEL.*开通"):
                SeedreamHttpRunner("key").run("model", {"prompt": "cover", "aspect_ratio": "16:9"})

    def test_empty_or_rejected_response_is_not_saved(self):
        for payload in [{"data": []}, {"data": [{"error": {"code": "blocked"}}]}, {"error": {"code": "blocked"}}]:
            with self.subTest(payload=payload), patch("content_agent.cover_generation.request.urlopen", return_value=BytesIO(json.dumps(payload).encode())):
                with self.assertRaisesRegex(RuntimeError, "未返回图片"):
                    SeedreamHttpRunner("key").run("model", {"prompt": "cover", "aspect_ratio": "16:9"})
