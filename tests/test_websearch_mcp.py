import unittest

from content_agent.collectors.websearch_mcp import (
    collect_websearch_mcp_candidates,
    extract_prompt_urls,
)
from content_agent.generation import generate_llm_drafts
from content_agent.workflow import run_keyword_workflow


class FakeMCPRunner:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return self.result


class FakeLLMProvider:
    def __init__(self):
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return "正文"


class WebSearchMCPTests(unittest.TestCase):
    def test_extracts_urls_from_creative_prompt(self):
        urls = extract_prompt_urls("分享这个项目：https://github.com/bansen/media-agent/tree/main，适合公众号")

        self.assertEqual(urls, ["https://github.com/bansen/media-agent/tree/main"])

    def test_extracts_github_url_without_swallowing_chinese_instruction(self):
        urls = extract_prompt_urls("https://github.com/harry0703/MoneyPrinterTurbo项目分享")

        self.assertEqual(urls, ["https://github.com/harry0703/MoneyPrinterTurbo"])

    def test_mcp_extract_maps_github_link_to_candidate(self):
        runner = FakeMCPRunner(
            {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            '{"results":[{"url":"https://github.com/bansen/media-agent",'
                            '"title":"bansen/media-agent",'
                            '"raw_content":"AI content agent for self-media workflows. '
                            '从选题、素材、正文、封面到公众号草稿箱的自动化内容工作台。"}]}'
                        ),
                    }
                ]
            }
        )

        candidates = collect_websearch_mcp_candidates(
            "帮我写公众号，分享这个项目 https://github.com/bansen/media-agent",
            runner=runner,
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].source, "websearch_mcp")
        self.assertEqual(candidates[0].url, "https://github.com/bansen/media-agent")
        self.assertIn("GitHub 开源项目", candidates[0].title)
        self.assertIn("bansen/media-agent", candidates[0].title)
        self.assertIn("公众号草稿箱", candidates[0].summary)
        self.assertEqual(runner.calls[0][0], "tavily-extract")
        self.assertEqual(runner.calls[0][1]["urls"], ["https://github.com/bansen/media-agent"])

    def test_mcp_extract_reads_github_readme_from_raw_markdown(self):
        github_url = "https://github.com/3441293738/creatorhub/blob/main/README.md"
        runner = FakeMCPRunner(
            {
                "results": [
                    {
                        "content": (
                            "# CreatorHub\n"
                            "本地运行的多平台内容管理面板，支持抖音、小红书、快手、视频号。\n"
                            "统一管理账号、监控作品与评论、下载内容、发布作品和接收通知。"
                        )
                    }
                ]
            }
        )

        candidates = collect_websearch_mcp_candidates(github_url + "项目分享", runner=runner)

        self.assertEqual(
            runner.calls[0][1]["urls"],
            ["https://raw.githubusercontent.com/3441293738/creatorhub/main/README.md"],
        )
        self.assertEqual(candidates[0].url, github_url)
        self.assertIn("多平台内容管理面板", candidates[0].summary)
        self.assertNotIn("Sign in", candidates[0].summary)

    def test_mcp_extract_prioritizes_readme_description_over_badge_noise(self):
        github_url = "https://github.com/chuspeeism/dashi-ppt-skill/blob/main/README.md"
        badge = "[![GitHub stars](https://img.shields.io/badge/stars-blue)](https://example.com)"
        runner = FakeMCPRunner(
            {
                "results": [
                    {
                        "content": (
                            "# Dashi PPT Skill\n"
                            + "\n".join([badge] * 30)
                            + "\n一个真正适合职场人的 PPT Skill。"
                            "每一页都自带编辑控制台，还能一键导出可编辑 PPTX。"
                        )
                    }
                ]
            }
        )

        candidates = collect_websearch_mcp_candidates(github_url + "项目分享", runner=runner)

        self.assertIn("适合职场人的 PPT Skill", candidates[0].summary)
        self.assertIn("导出可编辑 PPTX", candidates[0].summary)
        self.assertNotIn("img.shields.io", candidates[0].summary)

    def test_mcp_extract_rejects_github_readme_navigation_shell(self):
        github_url = "https://github.com/3441293738/creatorhub/blob/main/README.md"
        runner = FakeMCPRunner(
            {
                "results": [
                    {
                        "content": (
                            "Skip to content Navigation Menu Sign in Sign up Appearance settings "
                            "Notifications Fork Star You must be signed in to change notification settings"
                        )
                    }
                ]
            }
        )

        with self.assertRaisesRegex(RuntimeError, "README 正文读取失败"):
            collect_websearch_mcp_candidates(github_url, runner=runner)

    def test_mcp_search_maps_results_to_candidates_when_prompt_has_no_url(self):
        runner = FakeMCPRunner(
            {
                "results": [
                    {
                        "title": "AI副业避坑：普通人先看懂这 5 件事",
                        "url": "https://example.com/ai-side-hustle",
                        "content": "适合打工族的 AI 副业避坑和行动步骤。",
                    }
                ]
            }
        )

        candidates = collect_websearch_mcp_candidates("普通人如何用 AI 做副业", runner=runner)

        self.assertEqual(candidates[0].title, "AI副业避坑：普通人先看懂这 5 件事")
        self.assertIn("AI 副业避坑", candidates[0].summary)
        self.assertEqual(runner.calls[0][0], "tavily-search")
        self.assertEqual(runner.calls[0][1]["query"], "普通人如何用 AI 做副业")

    def test_websearch_material_summary_is_used_in_generation_prompt(self):
        candidates = collect_websearch_mcp_candidates(
            "帮我写公众号，分享这个开源项目 https://github.com/bansen/media-agent，突出适合自媒体人的工作流",
            runner=FakeMCPRunner(
                {
                    "results": [
                        {
                            "url": "https://github.com/bansen/media-agent",
                            "title": "bansen/media-agent",
                            "content": "从选题、素材、正文、封面到公众号草稿箱的自动化内容工作台。",
                        }
                    ]
                }
            ),
        )
        result = run_keyword_workflow(
            "帮我写公众号，分享这个开源项目 https://github.com/bansen/media-agent，突出适合自媒体人的工作流",
            candidates=candidates,
            primary_channel="wechat",
        )
        llm = FakeLLMProvider()

        generate_llm_drafts(result, llm)

        self.assertEqual(result.topics[0].source, "websearch_mcp")
        self.assertIn("素材摘要：", llm.prompts[0])
        self.assertIn("bansen/media-agent", llm.prompts[0])
        self.assertIn("公众号草稿箱", llm.prompts[0])


if __name__ == "__main__":
    unittest.main()
