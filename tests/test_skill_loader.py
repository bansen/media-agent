import unittest

from content_agent.skill_loader import load_content_skill


class SkillLoaderTests(unittest.TestCase):
    def test_loads_project_content_skill(self):
        skill = load_content_skill("xiaohongshu_content")

        self.assertIn("name: xiaohongshu_content", skill)
        self.assertIn("Xiaohongshu Content Skill", skill)
        self.assertIn("Cover Card Plan", skill)

    def test_rejects_nested_skill_names(self):
        with self.assertRaisesRegex(ValueError, "invalid skill name"):
            load_content_skill("../secret")


if __name__ == "__main__":
    unittest.main()
