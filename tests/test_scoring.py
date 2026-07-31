import unittest

from content_agent.models import CandidateContent
from content_agent.scoring import score_candidate


class ScoringTests(unittest.TestCase):
    def test_scores_candidate_with_explainable_weighted_formula(self):
        candidate = CandidateContent(
            title="普通人用 AI 做副业，最容易踩的 5 个坑",
            source="manual",
            url="https://example.com/topic",
            heat=80,
            interaction=70,
            hook=90,
            pain=85,
            reuse=75,
            material=65,
        )

        score = score_candidate(candidate)

        self.assertAlmostEqual(score.total, 78.25)
        self.assertEqual(score.level, "A")
        self.assertIn("热度", score.reasons[0])
        self.assertIn("标题钩子", " ".join(score.reasons))

    def test_rejects_metric_values_outside_0_to_100(self):
        candidate = CandidateContent(
            title="bad",
            source="manual",
            url=None,
            heat=101,
            interaction=70,
            hook=90,
            pain=85,
            reuse=75,
            material=65,
        )

        with self.assertRaises(ValueError):
            score_candidate(candidate)


if __name__ == "__main__":
    unittest.main()
