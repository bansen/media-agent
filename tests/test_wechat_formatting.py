import subprocess
import tempfile
import unittest
from pathlib import Path

from content_agent.exporters import build_wechat_draft_payload
from content_agent.formatters.wechat_gzh import format_wechat_markdown, write_gzh_outputs
from content_agent.mock_data import get_mock_candidates
from content_agent.workflow import run_keyword_workflow


class WeChatGzhFormattingTests(unittest.TestCase):
    def test_formatting_does_not_invent_a_date(self):
        html = format_wechat_markdown("# 赛事简报\n\n10月8日，朱思冰3比2获胜。")
        self.assertNotRegex(html, r"\d{4}\.\d{2}")
        self.assertIn("10月8日", html)

    def test_formats_markdown_as_gzh_section_fragment(self):
        html = format_wechat_markdown(
            """# 普通人用 AI 做副业，最容易踩的 5 个坑

> 不要先追风口，先跑通一个能交付的小流程。

## 先找真实需求

普通人做 AI 副业，第一步不是买课，而是找到一个明确场景。

### 最小动作

1. 记录别人反复问你的问题
2. 用 AI 做一个可交付样品

## 写在最后

不要承诺收益，先验证交付。
"""
        )

        self.assertTrue(html.strip().startswith("<section"))
        self.assertNotIn("<html", html)
        self.assertNotIn("<style", html)
        self.assertIn('span leaf=""', html)
        self.assertIn("普通人用 AI 做副业", html)
        self.assertIn("PART 01", html)
        self.assertIn("点赞、在看、转发", html)

    def test_formatted_html_does_not_include_author_placeholders(self):
        html = format_wechat_markdown("# 标题\n\n## 第一节\n\n正文内容。")

        self.assertNotIn("{{", html)
        self.assertNotIn("}}", html)
        self.assertNotIn("作者名", html)
        self.assertNotIn("一句话简介", html)

    def test_formatted_html_rewrites_overcommitted_follow_cta(self):
        html = format_wechat_markdown(
            """# 标题

## 写在最后

**关注我，每天分享一个 AI 副业避坑指南**
"""
        )

        self.assertNotIn("每天分享一个 AI 副业避坑指南", html)
        self.assertIn("关注我，一起拆解 AI 工具、副业实践和普通人的学习路径", html)

    def test_toc_slider_card_count_matches_article_sections(self):
        html = format_wechat_markdown(
            """# 普通人做 AI 副业，先避开这 5 个坑

## 第一坑

正文。

## 第二坑

正文。

## 第三坑

正文。

## 第四坑

正文。

## 第五坑

正文。
"""
        )

        self.assertIn("📦 5 Parts", html)
        self.assertEqual(html.count("width:110px"), 5)
        self.assertIn("PART 05", html)

    def test_cover_title_keeps_full_long_title(self):
        html = format_wechat_markdown("# 别再问“AI能干嘛”了，MiniMax H3的新模型\n\n## 第一节\n\n正文内容。")

        self.assertIn("别再问“AI能干嘛”了，", html)
        self.assertIn("MiniMax H3的新模型", html)

    def test_cover_uses_topic_subtitle_without_inventing_a_date(self):
        html = format_wechat_markdown(
            "# 用 AI 做视频，别再手工剪辑\n\n## 把文字变成可发布的视频\n\n正文内容。"
        )

        self.assertNotRegex(html, r"\d{4}\.\d{2}")
        self.assertIn("本文拆解：把文字变成可发布的视频", html)
        self.assertNotIn("2026.07", html)
        self.assertNotIn("先追风口", html)
        self.assertNotIn("真实需求 · 小步验证 · 可交付流程", html)

    def test_cover_label_matches_model_topic(self):
        html = format_wechat_markdown("# MiniMax H3有新变化，普通人先看懂这 3 点\n\n## 第一节\n\n正文内容。")

        self.assertIn("AI 模型观察", html)
        self.assertNotIn("AI 副业学习分享", html)

    def test_accepts_multiple_named_themes(self):
        markdown = "# 标题\n\n## 第一节\n\n正文内容。"

        green = format_wechat_markdown(markdown, theme="moyu-green")
        blue = format_wechat_markdown(markdown, theme="tech-blue")
        mono = format_wechat_markdown(markdown, theme="minimal-mono")
        warm = format_wechat_markdown(markdown, theme="warm-card")

        self.assertIn("#059669", green)
        self.assertIn("#2563EB", blue)
        self.assertIn("#111827", mono)
        self.assertIn("#B45309", warm)

    def test_formatted_html_passes_gzh_skill_validator(self):
        html = format_wechat_markdown(
            """# AI学习不是报课

## 先跑通一个场景

把一个真实任务拆成输入、处理、输出。
"""
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = Path(tmpdir) / "article.html"
            html_path.write_text(html, encoding="utf-8")
            completed = subprocess.run(
                [
                    "python3",
                    ".agents/skills/gzh-design/scripts/validate_gzh_html.py",
                    str(html_path),
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("完全合规", completed.stdout)

    def test_wechat_draft_payload_can_use_formatted_html(self):
        result = run_keyword_workflow("AI副业", get_mock_candidates("AI副业", channel="wechat"))
        formatted_html = format_wechat_markdown("# 标题\n\n## 第一节\n\n正文内容。")

        payload = build_wechat_draft_payload(result, thumb_media_id="MEDIA_ID", content_html=formatted_html)

        self.assertEqual(payload["articles"][0]["content"], formatted_html)

    def test_writes_clean_html_and_preview_files(self):
        html = format_wechat_markdown("# 标题\n\n## 第一节\n\n正文内容。")

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_gzh_outputs(html, Path(tmpdir), "demo", theme="tech-blue")

            self.assertTrue(paths.clean_html.exists())
            self.assertTrue(paths.preview_html.exists())
            self.assertIn("科技蓝(tech-blue)", paths.clean_html.name)
            self.assertIn("_预览.html", paths.preview_html.name)


if __name__ == "__main__":
    unittest.main()
