import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from content_agent.web import JobStore, WebRunOptions, run_agent_step, _to_jsonable, _status_for_result
from content_agent.workflow import run_keyword_workflow
from content_agent.mock_data import get_mock_candidates
from content_agent.cover_copy import prepare_cover_copy
from tests.test_cover_copy import FakeLLM


def initial_payload():
    value = _to_jsonable(run_keyword_workflow('AI写作', get_mock_candidates('AI写作', channel='wechat'), primary_channel='wechat'))
    value.update(content_plan={'core_topic': 'AI写作'}, llm_drafts={'wechat_article': '# 旧正文'},
                 gzh_formatting={'clean_html': '/tmp/old.html'}, cover_image={'path': '/tmp/old.jpg'},
                 cover_copy={'article_sha256': 'old'}, wechat_content_html='/tmp/old.html',
                 wechat_draft={'response': {'media_id': 'old'}})
    return value


class RecoveryTests(unittest.TestCase):
    def test_new_content_invalidates_old_assets_and_submission(self):
        payload = initial_payload()
        with patch('content_agent.web.AgentConfig.from_env_file'), patch('content_agent.web.generate_llm_drafts', return_value={'wechat_article': '# 新正文'}):
            result = run_agent_step(WebRunOptions(keyword='AI写作'), 'content', payload)
        for key in ('gzh_formatting', 'cover_image', 'cover_copy', 'wechat_draft', 'wechat_content_html'):
            self.assertNotIn(key, result)
        self.assertEqual(_status_for_result(result), 'completed')
        self.assertIn('wechat_draft', payload)

    def test_failed_cover_preserves_durable_article_and_can_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            database_url = f'sqlite:///{directory}/jobs.db'
            store = JobStore(database_url=database_url, auto_start=False)
            options = WebRunOptions(keyword='AI写作', use_llm=True, generate_cover=True, output_dir=Path(directory))
            job = store.create(options)
            with patch('content_agent.web._collect_candidates', return_value=get_mock_candidates('AI写作', channel='wechat')), patch('content_agent.web.AgentConfig.from_env_file'), patch('content_agent.web.generate_llm_content_plan', return_value={}), patch('content_agent.web.apply_llm_content_plan', side_effect=lambda result,*a,**kw: result), patch('content_agent.web.generate_llm_drafts', return_value={'wechat_article': '# 新正文\n\n已完成内容'}), patch('content_agent.web._prepare_article_cover'), patch('content_agent.web.generate_cover_image', side_effect=RuntimeError('图片服务失败')):
                store._run_job(job.id)
            reloaded = JobStore(database_url=database_url, auto_start=False)
            saved = reloaded.get(job.id)
            self.assertEqual(saved.status, 'failed')
            self.assertIsNotNone(saved.result)
            self.assertEqual(saved.result['llm_drafts']['wechat_article'], '# 新正文\n\n已完成内容')
            self.assertTrue(Path(saved.result['gzh_formatting']['clean_html']).exists())
            with patch('content_agent.web.AgentConfig.from_env_file') as config, patch('content_agent.web.generate_cover_image') as image:
                config.return_value.build_llm_provider.return_value = FakeLLM(headline='已完成内容', evidence='已完成内容')
                image.return_value.path = Path(directory) / 'cover.jpg'
                image.return_value.url = ''
                image.return_value.model = 'fake'
                image.return_value.prompt = '绘图'
                resumed = reloaded.start_step(job.id, 'cover')
            self.assertEqual(resumed.status, 'preview_ready')
            self.assertEqual(resumed.error, '')
            self.assertIn('cover_image', resumed.result)
            store._engine.dispose()
            reloaded._engine.dispose()

    def test_cover_rejects_reversed_fact_and_allows_correction(self):
        article = '公司股价暴跌20%，投资者需要警惕风险。'
        with self.assertRaisesRegex(ValueError, '下跌'):
            prepare_cover_copy({'llm_drafts': {'wechat_article': article}}, 'wechat', FakeLLM(headline='公司股价暴涨20%', evidence=article))
        class CorrectingLLM:
            def __init__(self):
                self.count = 0
            def generate(self, prompt):
                self.count += 1
                return json.dumps({'headline': '公司股价暴涨20%' if self.count == 1 else '公司股价暴跌20%', 'scene': '红色下降曲线', 'evidence': article})
        llm = CorrectingLLM()
        result = prepare_cover_copy({'llm_drafts': {'wechat_article': article}}, 'wechat', llm)
        self.assertEqual(result.headline, '公司股价暴跌20%')
        self.assertEqual(llm.count, 2)

    def test_external_html_is_cover_source_instead_of_generated_draft(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'article.html'
            path.write_text('<style>隐藏样式</style><h1>种花指南</h1><p>浇水和<strong>施肥</strong>。</p><script>隐藏脚本</script>', encoding='utf-8')
            llm = FakeLLM(headline='种花指南', evidence='浇水和施肥。')
            result = prepare_cover_copy({'wechat_content_html': str(path), 'llm_drafts': {'wechat_article': '无关旧草稿'}}, 'wechat', llm)
            self.assertEqual(result.headline, '种花指南')
            self.assertIn('浇水和施肥。', llm.prompts[0])
            for text in ('隐藏样式', '隐藏脚本', '无关旧草稿', '<strong>'):
                self.assertNotIn(text, llm.prompts[0])

    def test_reformatting_clears_previous_submission_and_external_html(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_agent_step(WebRunOptions(keyword='AI写作', output_dir=Path(directory)), 'format', initial_payload())
        self.assertNotIn('wechat_draft', result)
        self.assertNotIn('wechat_content_html', result)
        self.assertNotIn('cover_image', result)
        self.assertNotIn('cover_copy', result)

    def test_theme_change_preserves_cover_for_same_article(self):
        payload = initial_payload()
        payload.pop('wechat_content_html')
        with tempfile.TemporaryDirectory() as directory:
            result = run_agent_step(WebRunOptions(keyword='AI写作', output_dir=Path(directory)), 'format', payload)
        self.assertIn('cover_image', result)
        self.assertNotIn('wechat_draft', result)

    def test_external_html_cli_cover_does_not_require_new_article(self):
        import io
        from contextlib import redirect_stdout
        from content_agent.cli import main
        from content_agent.cover_generation import GeneratedCover
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'final.html'
            path.write_text('<h1>种花指南</h1><p>浇水和施肥。</p>', encoding='utf-8')
            llm = FakeLLM(headline='种花指南', evidence='浇水和施肥。')
            with patch('content_agent.cli._collect_candidates', return_value=get_mock_candidates('种花', channel='wechat')), patch('content_agent.cli.AgentConfig.from_env_file') as config, patch('content_agent.cli.generate_llm_drafts') as drafts, patch('content_agent.cli.generate_cover_image', return_value=GeneratedCover(Path(directory) / 'cover.jpg', '', 'fake', '绘图')), redirect_stdout(io.StringIO()) as output:
                config.return_value.build_llm_provider.return_value = llm
                code = main(['--keyword', '种花', '--wechat-content-html', str(path), '--generate-cover'])
            self.assertEqual(code, 0)
            drafts.assert_not_called()
            self.assertEqual(json.loads(output.getvalue())['cover_copy']['headline'], '种花指南')
