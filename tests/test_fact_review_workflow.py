import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from content_agent.fact_review import FactReviewError, review_article
from content_agent.formatters.wechat_gzh import format_wechat_markdown
from content_agent.publication_review import ensure_article_review
from content_agent.web import (JobStore, WebRunOptions, run_agent_step, _to_jsonable,
                               submit_stored_previewed_wechat_draft)
from tests.test_fact_review import news_result, ScriptedLLM, passed, rejected


SOURCE = '过去10天该研究所工作人员中无传染病发病报告。'
BAD = '所有密切接触者10天内没有新增病例。'


def payload():
    value = _to_jsonable(news_result(SOURCE))
    value['llm_drafts'] = {'wechat_article': '# 新闻简报\n\n' + SOURCE}
    return value


class ReviewWorkflowTests(unittest.TestCase):
    def test_exact_render_of_reviewed_url_article_does_not_need_a_second_model_verdict(self):
        result = news_result(SOURCE)
        source_url = result.topics[0].url
        value = payload()
        article = value['llm_drafts']['wechat_article']
        value['llm_drafts']['fact_review'] = review_article(result, article, ScriptedLLM(passed(SOURCE, SOURCE)))
        with tempfile.TemporaryDirectory() as directory:
            html, cover = Path(directory) / 'article.html', Path(directory) / 'cover.jpg'
            html.write_text(format_wechat_markdown(article + '\n\n原文链接：' + source_url))
            cover.write_bytes(b'cover')
            value.update(gzh_formatting={'clean_html': str(html)}, cover_image={'path': str(cover)})
            store = JobStore(database_url=f'sqlite:///{directory}/jobs.db', auto_start=False)
            job = store.create(WebRunOptions(keyword=source_url))
            store._update(job.id, status='preview_ready', result=value)
            config = Mock()
            config.build_llm_provider.return_value.generate.side_effect = AssertionError('second review should not run')
            published = Mock(thumb_media_id='thumb', response={'media_id': 'draft'})
            with patch('content_agent.web.publish_wechat_draft', return_value=published):
                submitted = submit_stored_previewed_wechat_draft(store, job.id, config)
            self.assertEqual(submitted.status, 'published_draft')
            self.assertEqual(submitted.result['publication_fact_review']['status'], 'passed')
            self.assertEqual(submitted.result['publication_fact_review']['method'], 'verified_render')
            config.build_llm_provider.return_value.generate.assert_not_called()
            store._engine.dispose()

    def test_optional_head_and_body_tags_do_not_hide_submitted_body(self):
        from content_agent.publication_review import html_review_text
        for start in ('<body>', ''):
            html = '<html><head><title>新闻简报</title>' + start + '<p>' + BAD + '</p></html>'
            self.assertIn(BAD, html_review_text(news_result(SOURCE), html))
            with self.assertRaises(FactReviewError):
                ensure_article_review(news_result(SOURCE), payload(), ScriptedLLM(rejected(BAD, SOURCE, '扩大范围')), html)

    def test_empty_body_cannot_pass_with_only_a_valid_published_title(self):
        with self.assertRaises(FactReviewError):
            ensure_article_review(news_result(SOURCE), payload(), Mock(), '<head><title>新闻简报</title></head>')

    def test_bare_text_after_implicit_head_end_is_also_reviewed(self):
        from content_agent.publication_review import html_review_text
        html = '<html><head><title>新闻简报</title>' + BAD + '<p>' + SOURCE + '</p></html>'
        text = html_review_text(news_result(SOURCE), html)
        self.assertIn(BAD, text)
        self.assertIn(SOURCE, text)
        with self.assertRaises(FactReviewError):
            ensure_article_review(news_result(SOURCE), payload(), ScriptedLLM(rejected(BAD, SOURCE, '扩大范围')), html)

    def test_html_link_targets_are_included_in_audit(self):
        from content_agent.publication_review import html_review_text
        text = html_review_text(news_result(SOURCE), '<p><a href="https://wrong.example/news">来源</a>' + SOURCE + '</p>')
        self.assertIn('https://wrong.example/news', text)

    def test_current_generated_review_is_reused_but_source_changes_require_review(self):
        result = news_result(SOURCE)
        value = payload()
        article = value['llm_drafts']['wechat_article']
        report = review_article(result, article, ScriptedLLM(passed(SOURCE, SOURCE)))
        value['llm_drafts']['fact_review'] = report
        llm = Mock()
        self.assertEqual(ensure_article_review(result, value, llm), report)
        llm.generate.assert_not_called()
        with self.assertRaises(FactReviewError):
            ensure_article_review(news_result('未公布监测结果。'), value, ScriptedLLM('invalid'))

    def test_legacy_cover_blocks_before_image_and_retains_report(self):
        value = payload()
        value['llm_drafts']['wechat_article'] = '# 新闻简报\n\n' + BAD
        with patch('content_agent.web.AgentConfig.from_env_file') as config, patch('content_agent.web.generate_cover_image') as image:
            config.return_value.build_llm_provider.return_value = ScriptedLLM(rejected(BAD, SOURCE, '扩大范围'))
            with self.assertRaises(FactReviewError) as caught:
                run_agent_step(WebRunOptions(keyword='新闻'), 'cover', value)
        image.assert_not_called()
        self.assertEqual(caught.exception.payload['fact_review']['status'], 'failed')
        self.assertIn(BAD, caught.exception.payload['llm_drafts']['wechat_article'])

    def test_external_html_overrides_passed_markdown_and_is_rechecked_after_changes(self):
        result, value = news_result(SOURCE), payload()
        article = value['llm_drafts']['wechat_article']
        value['llm_drafts']['fact_review'] = review_article(result, article, ScriptedLLM(passed(SOURCE, SOURCE)))
        with tempfile.TemporaryDirectory() as directory:
            html = Path(directory) / 'article.html'
            html.write_text('<p>' + SOURCE + '</p>')
            value['wechat_content_html'] = str(html)
            llm = ScriptedLLM(passed(SOURCE, SOURCE), rejected(BAD, SOURCE, '扩大范围'))
            ensure_article_review(result, value, llm)
            html.write_text('<p>' + BAD + '</p>')
            with self.assertRaises(FactReviewError):
                ensure_article_review(result, value, llm)
        self.assertEqual(len(llm.prompts), 2)

    def test_content_failure_is_persisted_and_old_assets_invalidated(self):
        value = payload()
        value.update(gzh_formatting={'clean_html':'old.html'}, cover_image={'path':'old.jpg'},
                     wechat_draft={'response':{'media_id':'old'}}, publication_fact_review={'status':'passed'})
        error = FactReviewError(BAD, {'status':'failed', 'issues':[{'reason':'扩大范围'}]})
        with tempfile.TemporaryDirectory() as directory:
            url = f'sqlite:///{directory}/jobs.db'
            store = JobStore(database_url=url, auto_start=False)
            job = store.create(WebRunOptions(keyword='新闻'))
            store._update(job.id, result=value)
            with patch('content_agent.web.AgentConfig.from_env_file'), patch('content_agent.web.generate_llm_drafts', side_effect=error):
                store._run_job(job.id, 'content')
            restored = JobStore(database_url=url, auto_start=False)
            failed = restored.get(job.id)
            self.assertEqual(failed.status, 'failed')
            self.assertIn('扩大范围', failed.error)
            self.assertEqual(failed.result['llm_drafts']['wechat_article'], BAD)
            for key in ('gzh_formatting','cover_image','wechat_draft','publication_fact_review'):
                self.assertNotIn(key, failed.result)
            store._engine.dispose()
            restored._engine.dispose()

    def test_actual_submitted_html_and_published_title_are_checked_before_publisher(self):
        with tempfile.TemporaryDirectory() as directory:
            html, cover = Path(directory)/'article.html', Path(directory)/'cover.jpg'
            html.write_text('<p>' + BAD + '</p>')
            cover.write_bytes(b'cover')
            value = payload()
            value.update(gzh_formatting={'clean_html':str(html)}, cover_image={'path':str(cover)})
            # Original Markdown passed; edited HTML must not inherit its approval.
            value['llm_drafts']['fact_review'] = review_article(news_result(SOURCE), value['llm_drafts']['wechat_article'], ScriptedLLM(passed(SOURCE,SOURCE)))
            store = JobStore(database_url=f'sqlite:///{directory}/jobs.db', auto_start=False)
            job = store.create(WebRunOptions(keyword='新闻'))
            store._update(job.id, status='preview_ready', result=value)
            config = Mock()
            llm = ScriptedLLM(rejected(BAD, SOURCE, '扩大范围'))
            config.build_llm_provider.return_value = llm
            with patch('content_agent.web.publish_wechat_draft') as publish, self.assertRaises(FactReviewError):
                submit_stored_previewed_wechat_draft(store, job.id, config)
            publish.assert_not_called()
            saved = store.get(job.id)
            self.assertEqual(saved.status, 'failed')
            self.assertEqual(saved.result['publication_fact_review']['status'], 'failed')
            self.assertEqual(saved.publish_attempts[-1]['status'], 'failed')
            self.assertIn('新闻简报', llm.prompts[0])
            store._engine.dispose()

    def test_title_change_invalidates_existing_review(self):
        from dataclasses import replace
        result, value = news_result(SOURCE), payload()
        value['llm_drafts']['fact_review'] = review_article(result, value['llm_drafts']['wechat_article'], ScriptedLLM(passed(SOURCE, SOURCE)))
        changed = replace(result, topics=[replace(result.topics[0], optimized_title=BAD)])
        with self.assertRaises(FactReviewError):
            ensure_article_review(changed, value, ScriptedLLM(rejected(BAD, SOURCE, '标题扩大范围')))


if __name__ == '__main__':
    unittest.main()
