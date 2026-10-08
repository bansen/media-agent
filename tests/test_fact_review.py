import json
import unittest
from dataclasses import replace

from content_agent.factual_guard import factual_conflicts
from content_agent.generation import generate_llm_drafts, _wechat_prompt
from content_agent.models import CandidateContent
from content_agent.workflow import run_keyword_workflow


def news_result(source, title="新闻简报"):
    candidate = CandidateContent(title=title, source="source_urls", url="https://example.com/news",
                                 heat=80, interaction=80, hook=80, pain=80, reuse=80, material=80,
                                 summary=source)
    result = run_keyword_workflow(candidate.url, [candidate], primary_channel="wechat")
    return replace(result, topics=[replace(result.topics[0], optimized_title=title)],
                   content_plan={"core_topic": "不可用于核查的策划", "article_structure": ["新闻事实"]})


def passed(claim, quote):
    return json.dumps({"verdict": "pass", "issues": [], "checks": [{"claim": claim, "source_quote": quote}]}, ensure_ascii=False)


def rejected(claim, quote, reason):
    return json.dumps({"verdict": "fail", "checks": [], "issues": [{"claim": claim, "source_quote": quote, "reason": reason}]}, ensure_ascii=False)


class ScriptedLLM:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        value = next(self.responses)
        if isinstance(value, Exception):
            raise value
        return value


class FactReviewTests(unittest.TestCase):
    def test_score_arithmetic_blocks_wrong_maximum_without_model(self):
        source = "五局比分：5-11、12-10、9-11、11-9、11-7。"
        self.assertTrue(factual_conflicts(source, "决胜局11比7。从比分上看，这是五局中分差最大的一局。"))
        self.assertFalse(factual_conflicts(source, "首局5比11，分差最大，为6分。"))
        self.assertFalse(factual_conflicts(source, "11比7并不是五局最大分差。"))

    def test_short_factual_article_is_reviewed_with_original_source_not_plan(self):
        source = "朱思冰3比2战胜蒯曼。"
        result = news_result(source)
        llm = ScriptedLLM("# 临时标题\n\n" + source, passed(source, source))
        drafts = generate_llm_drafts(result, llm)
        self.assertEqual(drafts["fact_review"]["status"], "passed")
        self.assertEqual(len(llm.prompts), 2)
        self.assertIn(source, llm.prompts[1])
        self.assertNotIn("不可用于核查的策划", llm.prompts[1])
        self.assertTrue(drafts["wechat_article"].startswith("# 新闻简报"))

    def test_scope_and_causality_regressions_get_one_targeted_repair(self):
        cases = [
            ("过去10天该研究所工作人员中无传染病发病报告。", "所有密切接触者10天内没有新增病例。", "扩大了监测对象范围"),
            ("沪指跌0.79%，油气煤炭股逆势走强。", "资金从科技股流入高股息板块。", "原文没有资金流量证据"),
        ]
        for source, bad, reason in cases:
            with self.subTest(reason=reason):
                llm = ScriptedLLM("# 临时\n\n" + bad, rejected(bad, source, reason),
                                  "# 新闻简报\n\n" + source, passed(source, source))
                drafts = generate_llm_drafts(news_result(source), llm)
                self.assertEqual(drafts["fact_review"]["status"], "passed")
                self.assertEqual(len(llm.prompts), 4)
                self.assertIn(bad, llm.prompts[2])
                self.assertIn(reason, llm.prompts[2])
                self.assertIn("只修订", llm.prompts[2])

    def test_second_failure_retains_draft_and_stops(self):
        from content_agent.fact_review import FactReviewError
        source, bad = "研究所工作人员无新增病例。", "全部接触者无新增病例。"
        failure = rejected(bad, source, "扩大范围")
        llm = ScriptedLLM(bad, failure, bad, failure)
        with self.assertRaises(FactReviewError) as caught:
            generate_llm_drafts(news_result(source), llm)
        self.assertIn(bad, caught.exception.article)
        self.assertEqual(caught.exception.report["status"], "failed")
        self.assertEqual(len(llm.prompts), 4)

    def test_malformed_review_and_service_error_cannot_pass_or_trigger_rewrite(self):
        from content_agent.fact_review import FactReviewError
        for response in ("not JSON", '{"verdict":"pass","issues":[],"checks":[]}', RuntimeError("offline")):
            llm = ScriptedLLM("# 新闻简报\n\n比分为3比2。", response)
            with self.subTest(response=response), self.assertRaises(FactReviewError):
                generate_llm_drafts(news_result("比分为3比2。"), llm)
            self.assertEqual(len(llm.prompts), 2)

    def test_final_title_must_be_part_of_audit(self):
        from content_agent.fact_review import FactReviewError
        result = news_result("俄方称病因为不明原因肺炎。", title="已经排除鼠疫")
        reject = rejected("已经排除鼠疫", "俄方称病因为不明原因肺炎。", "原文未排除")
        llm = ScriptedLLM("俄方称病因为不明原因肺炎。", reject,
                          "俄方称病因为不明原因肺炎。", reject)
        with self.assertRaises(FactReviewError):
            generate_llm_drafts(result, llm)
        self.assertIn("已经排除鼠疫", llm.prompts[1])

    def test_repair_service_error_retains_first_rejected_draft(self):
        from content_agent.fact_review import FactReviewError
        source, bad = "工作人员无病例。", "全部接触者无病例。"
        llm = ScriptedLLM(bad, rejected(bad, source, "扩大范围"), RuntimeError("offline"))
        with self.assertRaises(FactReviewError) as caught:
            generate_llm_drafts(news_result(source), llm)
        self.assertIn(bad, caught.exception.article)
        self.assertEqual(caught.exception.report["status"], "error")
        self.assertEqual(len(llm.prompts), 3)

    def test_review_binds_source_and_article_and_rejects_fabricated_evidence(self):
        from content_agent.fact_review import review_article, review_is_current
        result = news_result("比分为3比2。")
        article = "# 新闻简报\n\n比分为3比2。"
        report = review_article(result, article, ScriptedLLM(passed("比分为3比2。", "比分为3比2。")))
        self.assertTrue(review_is_current(result, article, report))
        self.assertFalse(review_is_current(result, article + "无关结论", report))
        self.assertFalse(review_is_current(news_result("比分为3比1。"), article, report))
        self.assertFalse(review_is_current(result, article, {}))
        self.assertFalse(review_is_current(result, article, dict(report, checks=[{}])))
        self.assertFalse(review_is_current(result, article, dict(report, checks=[{"claim":"比分为3比2。", "source_quote":"捏造的证据"}])))
        report = review_article(result, article, ScriptedLLM(passed("比分为3比2。", "虚构的原文证据")))
        self.assertEqual(report["status"], "error")

    def test_no_length_floor_and_original_source_overrides_plan(self):
        prompt = _wechat_prompt(news_result("比分为3比2。"))
        self.assertNotIn("1200-1800", prompt)
        self.assertNotIn("1500 字", prompt)
        self.assertNotIn("事实与结构的唯一主线", prompt)
        self.assertIn("不设最低字数", prompt)
        self.assertIn("原文优先", prompt)


if __name__ == "__main__":
    unittest.main()
