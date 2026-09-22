import json
import unittest

from content_agent import cover_copy


ARTICLE = "# AIWriteX：让 AI 分工写文章\n\nAIWriteX 通过多个智能体协作，完成资料整理与文章创作。仍需人工核实和审核。"


class FakeLLM:
    def __init__(self, **updates):
        self.prompts = []
        self.response = {
            "headline": "让 AI 分工写文章",
            "scene": "多个不同颜色的角色围绕一条内容创作流水线协作，主体位于右侧",
            "evidence": "AIWriteX 通过多个智能体协作，完成资料整理与文章创作。",
            **updates,
        }

    def generate(self, prompt):
        self.prompts.append(prompt)
        return json.dumps(self.response, ensure_ascii=False)


class CoverCopyTests(unittest.TestCase):
    def test_uses_final_article_not_old_cover_instructions(self):
        llm = FakeLLM()
        payload = {"llm_drafts": {"wechat_article": ARTICLE, "xhs_note": "无关旧笔记"},
                   "cover_prompt": "old office desk full-bleed 6000x6000"}
        copy = cover_copy.prepare_cover_copy(payload, "wechat", llm)
        self.assertIn(ARTICLE, llm.prompts[0])
        self.assertNotIn("无关旧笔记", llm.prompts[0])
        self.assertNotIn("old office desk", llm.prompts[0])
        self.assertEqual(copy.headline, "让 AI 分工写文章")
        self.assertEqual(len(copy.article_sha256), 64)

    def test_title_is_the_only_allowed_image_text_and_has_no_size_instructions(self):
        copy = cover_copy.prepare_cover_copy({"llm_drafts": {"wechat_article": ARTICLE}}, "wechat", FakeLLM())
        prompt = cover_copy.build_image_prompt(copy, "wechat", "business-tech")
        self.assertIn("唯一允许出现的文字", prompt)
        self.assertEqual(prompt.count(copy.headline), 1)
        for leaked in ["16:9", "1600", "900", "full-bleed", "negative", "No text", "AIWriteX 通过"]:
            self.assertNotIn(leaked, prompt)

    def test_xhs_uses_its_own_article_and_keeps_background_text_free(self):
        llm = FakeLLM(evidence="小红书最终正文")
        copy = cover_copy.prepare_cover_copy({"llm_drafts": {"wechat_article": "旧公众号文章", "xhs_note": "小红书最终正文：让 AI 分工写文章"}}, "xiaohongshu", llm)
        self.assertNotIn("旧公众号文章", llm.prompts[0])
        prompt = cover_copy.build_image_prompt(copy, "xiaohongshu", "minimal-illustration")
        self.assertNotIn(copy.headline, prompt)
        self.assertIn("不要生成任何文字", prompt)

    def test_missing_article_stops_before_llm_or_image_call(self):
        llm = FakeLLM()
        with self.assertRaisesRegex(ValueError, "先生成.*正文"):
            cover_copy.prepare_cover_copy({"cover_prompt": "old prompt"}, "wechat", llm)
        self.assertEqual(llm.prompts, [])

    def test_unsupported_evidence_numbers_and_render_specs_are_rejected(self):
        for updates in [
            {"evidence": "这个工具保证赚钱"},
            {"headline": "效率提升100倍"},
            {"headline": "16:9高清封面"},
            {"scene": "创作者协作，1600x900 resolution output"},
            {"headline": "过长" * 20},
            {"headline": "点开https://example.com"},
            {"headline": "标题\n副标题"},
        ]:
            with self.subTest(updates=updates):
                llm = FakeLLM(**updates)
                with self.assertRaises(ValueError):
                    cover_copy.prepare_cover_copy({"llm_drafts": {"wechat_article": ARTICLE}}, "wechat", llm)
                self.assertEqual(len(llm.prompts), 2)

    def test_article_fingerprint_changes_after_edit(self):
        a = cover_copy.prepare_cover_copy({"llm_drafts": {"wechat_article": ARTICLE}}, "wechat", FakeLLM())
        b = cover_copy.prepare_cover_copy({"llm_drafts": {"wechat_article": ARTICLE + "新增说明"}}, "wechat", FakeLLM())
        self.assertNotEqual(a.article_sha256, b.article_sha256)
