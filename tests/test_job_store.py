import tempfile
import unittest
from pathlib import Path

from content_agent.web import JobStore, WebRunOptions


class JobStorePersistenceTests(unittest.TestCase):
    def test_job_store_persists_completed_job_and_events(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            database_url = f"sqlite:///{Path(tmpdir) / 'content-agent.db'}"
            store = JobStore(database_url=database_url, auto_start=False)
            job = store.create(WebRunOptions(keyword="AI副业", channel="wechat", collector="mock"))

            store._update(job.id, status="running", event="Job started")
            store._update(
                job.id,
                status="preview_ready",
                event="Job completed",
                result={
                    "keyword": "AI副业",
                    "gzh_formatting": {
                        "clean_html": "output/AI副业_排版_摸鱼绿(moyu-green).html",
                        "preview_html": "output/AI副业_排版_摸鱼绿(moyu-green)_预览.html",
                    },
                    "cover_image": {"path": "output/AI副业_cover.jpg"},
                },
            )

            reloaded = JobStore(database_url=database_url, auto_start=False)
            loaded = reloaded.get(job.id)

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.status, "preview_ready")
        self.assertEqual(loaded.result["keyword"], "AI副业")
        self.assertEqual(loaded.events, ["Job started", "Job completed"])
        self.assertEqual(loaded.options.keyword, "AI副业")

    def test_job_store_lists_persisted_jobs_newest_first(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            database_url = f"sqlite:///{Path(tmpdir) / 'content-agent.db'}"
            store = JobStore(database_url=database_url, auto_start=False)
            first = store.create(WebRunOptions(keyword="AI副业", channel="wechat", collector="mock"))
            second = store.create(WebRunOptions(keyword="健康养生", channel="xiaohongshu", collector="mock"))

            jobs = JobStore(database_url=database_url, auto_start=False).list()

        self.assertEqual([job.id for job in jobs], [second.id, first.id])
        self.assertEqual(jobs[0].options.keyword, "健康养生")

    def test_job_store_persists_publish_attempt_and_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            database_url = f"sqlite:///{Path(tmpdir) / 'content-agent.db'}"
            store = JobStore(database_url=database_url, auto_start=False)
            job = store.create(WebRunOptions(keyword="AI副业", channel="wechat", collector="mock"))

            store.record_publish_attempt(
                job.id,
                platform="wechat",
                status="published_draft",
                response={"errcode": 0, "media_id": "DRAFT_ID"},
                error="",
            )

            reloaded = JobStore(database_url=database_url, auto_start=False)
            loaded = reloaded.get(job.id)

        self.assertEqual(loaded.status, "published_draft")
        self.assertEqual(loaded.publish_attempts[0]["platform"], "wechat")
        self.assertEqual(loaded.publish_attempts[0]["response"]["media_id"], "DRAFT_ID")


if __name__ == "__main__":
    unittest.main()
