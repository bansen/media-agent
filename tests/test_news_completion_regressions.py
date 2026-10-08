import unittest
from unittest.mock import Mock
from content_agent.factual_guard import factual_conflicts
from content_agent.fact_review import review_article, review_is_current
from content_agent.cover_copy import prepare_cover_copy
from tests.test_cover_copy import ARTICLE, FakeLLM
from tests.test_fact_review import news_result, ScriptedLLM, passed

SOURCE='近日网传研究所员工感染鼠疫死亡。俄方通告称病因诊断为“不明原因肺炎”，样本中未发现与其专业活动相关的微生物。'

class CompletionRegressions(unittest.TestCase):
    def test_unknown_pneumonia_cannot_be_promoted_to_excluded_plague(self):
        for claim in ['俄官方：鼠疫研究所员工非鼠疫感染','诊断为不明原因肺炎，而非鼠疫。','俄官方辟谣鼠疫死亡','官方已经排除鼠疫','俄方否认鼠疫感染']:
            with self.subTest(claim=claim):
                self.assertTrue(factual_conflicts(SOURCE,claim))
        for claim in ['诊断为不明原因肺炎。','不能据此排除鼠疫。','尚未排除鼠疫。','未发现不等于排除鼠疫。','没有证据证明非鼠疫感染。','目前未排除鼠疫。','通告没有排除鼠疫。','不排除鼠疫感染可能。']:
            with self.subTest(claim=claim):
                self.assertFalse(factual_conflicts(SOURCE,claim))
        self.assertFalse(factual_conflicts(SOURCE+'后续调查已排除鼠疫。','官方已排除鼠疫。'))
        self.assertTrue(factual_conflicts(SOURCE+'目前未排除鼠疫。','官方已排除鼠疫。'))

    def test_known_certainty_error_is_blocked_before_model_can_approve_it(self):
        llm=Mock()
        llm.generate.return_value=passed('非鼠疫感染',SOURCE)
        report=review_article(news_result(SOURCE),'俄官方：员工非鼠疫感染',llm)
        self.assertEqual(report['status'],'failed')
        llm.generate.assert_not_called()

    def test_previous_review_version_is_not_reused(self):
        result=news_result('比分为3比2。'); article='比分为3比2。'
        report=review_article(result,article,ScriptedLLM(passed(article,article)))
        report['version']=1
        self.assertFalse(review_is_current(result,article,report))

    def test_cover_scene_cannot_demand_text_or_scoreboard(self):
        for scene in ['背景是比赛计分屏。','行情看板上标出各板块名称和跌幅。','柱状图上标注数字。']:
            with self.subTest(scene=scene),self.assertRaisesRegex(ValueError,'无字|文字|数字|计分|行情'):
                prepare_cover_copy({'llm_drafts':{'wechat_article':ARTICLE}},'wechat',FakeLLM(scene=scene))
        self.assertTrue(prepare_cover_copy({'llm_drafts':{'wechat_article':ARTICLE}},'wechat',FakeLLM(scene='抽象的半导体芯片与无标签色块，以几何造型表现主题。')).scene)
        for scene in ['球拍与球台构成主体，不显示文字和数字。','芯片与无标签色块构成主体，不使用行情看板。']:
            self.assertTrue(prepare_cover_copy({'llm_drafts':{'wechat_article':ARTICLE}},'wechat',FakeLLM(scene=scene)).scene)
