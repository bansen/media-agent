import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image

from content_agent.skill_loader import load_content_skill
from content_agent.xhs_layout import parse_xhs_note, render_xhs_package


NOTE = """标题：秋天养元气，先做这4件小事

正文：
最近早晚一凉，人就容易犯懒。下面这些习惯，我自己坚持起来没有压力。

1. 早上先喝温水
醒来先补水，再慢慢开始一天。

2. 午休出去走10分钟
绕着楼下走一圈，让身体换个状态。

3. 下午换成温润饮品
少一点刺激，也不影响工作节奏。

4. 睡前泡脚15分钟
用舒服的温度就好，不必追求出汗。

封面图组：
1. 首图：标题文字“秋天养元气，先做这4件小事”
2. 图2：温水和晨光
3. 图3：午间散步
4. 图4：下午饮品
5. 图5：睡前泡脚
6. 尾图：少消耗，多收着点

标签：
#职场女性 #健康养生 #生活习惯 #低成本养生
"""


class XiaohongshuLayoutTests(unittest.TestCase):
    def test_layout_skill_is_project_owned_and_loadable(self):
        skill = load_content_skill("xiaohongshu_layout")

        self.assertIn("name: xiaohongshu_layout", skill)
        self.assertIn("3:4", skill)

    def test_parses_publishable_note_without_cover_plan(self):
        note = parse_xhs_note(NOTE)

        self.assertEqual(note.title, "秋天养元气，先做这4件小事")
        self.assertEqual(len(note.points), 4)
        self.assertEqual(note.tags, ["#职场女性", "#健康养生", "#生活习惯", "#低成本养生"])
        self.assertNotIn("封面图组", note.publish_text)
        self.assertNotIn("标题文字", note.publish_text)
        self.assertIn("睡前泡脚15分钟", note.publish_text)

    def test_parses_inline_body_and_tags_without_repeating_section_labels(self):
        note = parse_xhs_note(
            "标题：打工人秋天养元气的4个习惯\n\n"
            "正文：这是适合忙碌上班族的开场。\n\n"
            "1. 先喝温水\n慢慢喝就好。\n\n"
            "标签：#职场女性 #健康养生"
        )

        self.assertTrue(note.body.startswith("这是适合忙碌上班族的开场。"))
        self.assertEqual(note.tags, ["#职场女性", "#健康养生"])
        self.assertNotIn("正文：", note.publish_text)
        self.assertNotIn("标签：", note.publish_text)
        self.assertEqual(note.publish_text.count("#职场女性"), 1)

    def test_renders_cover_points_and_tail_as_three_to_four_images(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            background = Path(tmpdir) / "background.jpg"
            Image.new("RGB", (1200, 900), color=(196, 183, 145)).save(background)

            package = render_xhs_package(
                NOTE,
                output_dir=Path(tmpdir),
                basename="秋季养生",
                background_path=background,
                theme="fresh-green",
            )

            self.assertEqual(len(package.cards), 6)
            self.assertEqual([card.kind for card in package.cards], ["cover", "point", "point", "point", "point", "tail"])
            for card in package.cards:
                with Image.open(card.path) as image:
                    self.assertEqual(image.size, (1080, 1440))
            self.assertTrue(package.zip_path.exists())
            with zipfile.ZipFile(package.zip_path) as archive:
                names = archive.namelist()
                self.assertIn("发布文案.txt", names)
                self.assertEqual(len([name for name in names if name.endswith(".jpg")]), 6)
                publish_text = archive.read("发布文案.txt").decode("utf-8")
            self.assertNotIn("封面图组", publish_text)

    def test_package_id_isolates_same_named_layouts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            first = render_xhs_package(
                NOTE,
                output_dir=Path(tmpdir),
                basename="秋季养生",
                package_id="job-one",
            )
            second = render_xhs_package(
                NOTE.replace("秋天养元气", "入秋少疲惫"),
                output_dir=Path(tmpdir),
                basename="秋季养生",
                package_id="job-two",
            )

            self.assertNotEqual(first.zip_path, second.zip_path)
            self.assertIn("job-one", first.zip_path.parts)
            self.assertIn("job-two", second.zip_path.parts)


if __name__ == "__main__":
    unittest.main()
