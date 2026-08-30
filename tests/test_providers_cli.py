import io
import json
import tempfile
import unittest
from urllib.error import HTTPError
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


class FakeTwoStageLLM:
    def __init__(self):
        self.prompts = []
        self.responses = iter([_editorial_plan_json(), "# 临时标题\n\n正文内容"])

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return next(self.responses)


def _editorial_plan_json() -> str:
    return json.dumps(
        {
            "core_topic": "用岗位定义可协作的 AI 团队",
            "target_audience": "多智能体开发者",
            "pain_point": "智能体缺少岗位职责和协作边界",
            "core_value": "把岗位职责变成可运行的 AI 团队",
            "key_points": ["岗位定义", "组织关系", "交付标准"],
            "article_structure": ["冲突开场", "岗位机制", "协作流程", "真实场景", "边界判断"],
            "cover_concept": "多个有明确岗位分工的 AI 角色共同协作",
            "titles": [
                "Agency Agents：把岗位职责变成一支 AI 团队",
                "多智能体不只会聊天，它把岗位关系也做进去了",
                "想组一支 AI 团队，先给智能体写岗位说明书",
                "把组织架构搬进 AI，多智能体终于有明确分工",
                "AI 团队总抢活？先把智能体的岗位边界定清楚",
            ],
            "selected_title": "Agency Agents：把岗位职责变成一支 AI 团队",
        },
        ensure_ascii=False,
    )


class ProviderCliTests(unittest.TestCase):
    def test_cli_use_llm_generates_plan_before_article(self):
        llm = FakeTwoStageLLM()
        config = type("Config", (), {"build_llm_provider": lambda self: llm})()
        candidate = CandidateContent(
            title="GitHub 开源项目：msitarzewski/agency-agents - Agency Agents",
            source="websearch_mcp",
            url="https://github.com/msitarzewski/agency-agents/blob/main/README.md",
            heat=92,
            interaction=88,
            hook=84,
            pain=80,
            reuse=92,
            material=96,
            summary="每个 AI 智能体都有明确岗位职责、组织关系和交付标准。",
        )
        stdout = io.StringIO()

        with redirect_stdout(stdout), patch("content_agent.cli._collect_candidates", return_value=[candidate]), patch(
            "content_agent.cli.AgentConfig.from_env_file", return_value=config
        ):
            exit_code = main(
                [
                    "--keyword",
                    "https://github.com/msitarzewski/agency-agents/blob/main/README.md 分享",
                    "--use-llm",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(len(llm.prompts), 2)
        self.assertIn("请先做内容策划，不要写正文", llm.prompts[0])
        self.assertIn("公众号文案创作", llm.prompts[1])
        self.assertEqual(payload["topics"][0]["optimized_title"], "Agency Agents：把岗位职责变成一支 AI 团队")
        self.assertIn("content_plan", payload)

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

    def test_openai_compatible_provider_requires_llm_api_key(self):
        provider = OpenAICompatibleLLMProvider(
            api_key="",
            base_url="https://api.deepseek.com",
            model="deepseek-chat",
        )

        with self.assertRaisesRegex(RuntimeError, "LLM_API_KEY"):
            provider.generate("生成 3 个选题")

    def test_openai_compatible_provider_reports_unauthorized_as_config_error(self):
        provider = OpenAICompatibleLLMProvider(
            api_key="wrong-secret",
            base_url="https://api.deepseek.com",
            model="deepseek-chat",
        )

        with patch(
            "content_agent.providers.llm.request.urlopen",
            side_effect=HTTPError(
                url="https://api.deepseek.com/chat/completions",
                code=401,
                msg="Unauthorized",
                hdrs=None,
                fp=io.BytesIO(b'{"error":{"message":"invalid api key"}}'),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "LLM_API_KEY"):
                provider.generate("生成 3 个选题")

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

        with redirect_stdout(stdout), patch("content_agent.cli.collect_baidu_search_candidates", return_value=[_baidu_candidate()]):
            exit_code = main(["--keyword", "AI副业"])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["keyword"], "AI副业")
        self.assertGreaterEqual(len(payload["topics"]), 1)
        self.assertIn("cover_prompt", payload)

    def test_cli_rejects_non_baidu_search_collector(self):
        with self.assertRaises(SystemExit) as raised:
            main(["--keyword", "AI副业", "--collector", "free_hot"])

        self.assertEqual(raised.exception.code, 2)

    def test_cli_can_use_baidu_search_collector(self):
        stdout = io.StringIO()

        with redirect_stdout(stdout), patch(
            "content_agent.cli.collect_baidu_search_candidates",
            return_value=[_baidu_candidate()],
        ) as collect:
            exit_code = main(["--keyword", "AI副业"])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["topics"][0]["title"], "百度搜索里的 AI 副业趋势")
        collect.assert_called_once()

    def test_cli_formats_gzh_preview_without_llm(self):
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as tmpdir:
            with redirect_stdout(stdout), patch(
                "content_agent.cli.collect_baidu_search_candidates", return_value=[_baidu_candidate()]
            ):
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
            "content_agent.cli.collect_baidu_search_candidates", return_value=[_baidu_candidate()]
        ), patch(
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
            "content_agent.cli.collect_baidu_search_candidates", return_value=[_baidu_candidate()]
        ), patch(
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
                "content_agent.cli.collect_baidu_search_candidates", return_value=[_baidu_candidate()]
            ), patch(
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


def _baidu_candidate() -> CandidateContent:
    return CandidateContent(
        title="百度搜索里的 AI 副业趋势",
        source="baidu_search",
        url="https://example.com/baidu",
        heat=88,
        interaction=82,
        hook=80,
        pain=78,
        reuse=76,
        material=75,
    )


if __name__ == "__main__":
    unittest.main()
