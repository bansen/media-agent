import unittest

from content_agent.collectors.source_urls import _extract_title_and_text


class SourceBodyTests(unittest.TestCase):
    def extract(self, body):
        return _extract_title_and_text(body, "https://example.com/news", "https://example.com/news")

    def test_article_body_excludes_page_chrome_and_nested_recommendations(self):
        title, text = self.extract('''<title>News &amp; facts</title><body>
            <div>Breaking headlines outside the article</div>
            <article><p>First <strong>verified</strong> fact.</p>
            <div class="related-posts"><article>Unrelated story</article></div>
            <div class="advertisement"><p>Buy now</p></div>
            <div role="navigation">Next page</div>
            <p>Second fact.</p></article><footer>Footer text</footer></body>''')
        self.assertEqual(title, "News & facts")
        self.assertEqual(text, "News & facts；First verified fact.\n\nSecond fact.")

    def test_trusted_body_is_preferred_to_unrelated_article_cards(self):
        _, text = self.extract('''<title>Report</title>
            <article class="card"><p>Unrelated teaser repeated many times.</p></article>
            <main><h1>Report</h1><div class="article-body">
            <p>The actual source fact.</p><p>Its supporting detail.</p></div></main>''')
        self.assertEqual(text, "Report；The actual source fact.\n\nIts supporting detail.")

    def test_main_article_wins_over_longer_article_card_outside_main(self):
        _, text = self.extract('<title>Report</title><article><p>' + 'Teaser ' * 100 +
            '</p></article><main><article><p>Actual source.</p></article></main>')
        self.assertEqual(text, "Report；Actual source.")

    def test_article_card_body_does_not_override_main_story(self):
        _, text = self.extract('<title>Report</title><main><article><p>Actual source.</p></article>'
            '<article class="article-card"><div class="article-body">Unrelated teaser</div>'
            '</article></main>')
        self.assertEqual(text, "Report；Actual source.")

    def test_empty_main_does_not_hide_article_outside_it(self):
        _, text = self.extract('<title>Report</title><main></main><article><p>Actual source.</p></article>')
        self.assertEqual(text, "Report；Actual source.")

    def test_body_markers_support_common_publishers(self):
        for marker in ['itemprop="articleBody"', 'class="entry-content"', 'id="js_content"']:
            with self.subTest(marker=marker):
                _, text = self.extract(f'<title>Report</title><div>Outside</div>'
                    f'<div {marker}><p>Verified fact.</p></div>')
                self.assertEqual(text, "Report；Verified fact.")

    def test_inline_text_preserves_word_and_chinese_character_boundaries(self):
        _, text = self.extract('<title>Report</title><article><p>AI<strong>工具</strong>发布，'
            're<em>search</em> works &amp; helps.</p><p>Next<br>line.</p></article>')
        self.assertEqual(text, "Report；AI工具发布，research works & helps.\n\nNext\nline.")

    def test_plain_fallback_preserves_paragraphs_and_filters_div_noise(self):
        _, text = self.extract('''<title>Report</title><body><div class="navigation">Menu</div>
            <div><p>First fact.</p><p>Second fact.</p></div>
            <div id="recommendations">Other story</div></body>''')
        self.assertEqual(text, "Report；First fact.\n\nSecond fact.")

    def test_short_article_does_not_restore_filtered_noise(self):
        _, text = self.extract('<title>Report</title><nav>Menu</nav>'
            '<article><p>Fact.</p><aside>Related story</aside></article>')
        self.assertEqual(text, "Report；Fact.")

    def test_advertising_subject_is_retained(self):
        _, text = self.extract('<title>Advertising report</title><article>'
            '<p>Advertising revenue rose. Recommended practices changed.</p></article>')
        self.assertIn("Advertising revenue rose. Recommended practices changed.", text)

    def test_svg_title_does_not_contaminate_document_title(self):
        title, _ = self.extract('<head><title>Report</title></head><body>'
            '<svg><title>Icon description</title></svg><article>Actual source.</article></body>')
        self.assertEqual(title, 'Report')

    def test_omitted_head_end_tag_does_not_hide_body(self):
        title, text = self.extract('<html><head><title>Report</title><meta charset="utf-8">'
            '<body><article><p>Actual source.</p><p>Supporting fact.</p></article></body></html>')
        self.assertEqual(title, 'Report')
        self.assertEqual(text, 'Report；Actual source.\n\nSupporting fact.')

    def test_void_and_mismatched_tags_do_not_hide_later_body(self):
        _, text = self.extract('<title>Report</title><body><nav><img src="x"><input>Menu</nav>'
            '</aside><article><p>First<img src="x"> fact.<p>Second fact.'
            '<div class="ads"><br/>Buy</div><p>Last fact.</article></body>')
        self.assertEqual(text, "Report；First fact.\n\nSecond fact.\n\nLast fact.")

    def test_empty_filtered_html_fails_instead_of_returning_chrome(self):
        with self.assertRaisesRegex(RuntimeError, "页面正文为空"):
            self.extract('<title>Report</title><nav>Only navigation</nav><script>ignored</script>')

    def test_html_summary_is_still_capped_at_4000_characters(self):
        _, text = self.extract('<title>Report</title><article><p>' + 'a' * 3000 +
            '</p><p>' + 'b' * 3000 + '</p></article>')
        self.assertEqual(len(text), 4000)
        self.assertIn('\n\n', text)

    def test_markdown_and_github_readme_still_work(self):
        _, text = self.extract('# Project\n\nA useful project with documented source facts.')
        self.assertIn("documented source facts", text)
        title, text = _extract_title_and_text('# Project\n\nUseful README content.',
            'https://github.com/example/project',
            'https://raw.githubusercontent.com/example/project/main/README.md')
        self.assertIn('project', title.lower())
        self.assertIn('Useful README content.', text)


if __name__ == '__main__':
    unittest.main()
