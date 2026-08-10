import tempfile
import unittest
import os
from io import BytesIO
from pathlib import Path

from PIL import Image

from content_agent.cover_generation import ReplicateHttpRunner, generate_cover_image


class FakeReplicateOutput:
    url = "https://replicate.delivery/mock/output.jpg"

    def read(self):
        return b"generated-image"


class FakeImageReplicateOutput:
    url = "https://replicate.delivery/mock/output.jpg"

    def read(self):
        stream = BytesIO()
        Image.new("RGB", (1024, 1024), color=(28, 92, 78)).save(stream, format="JPEG")
        return stream.getvalue()


class FakeReplicateRunner:
    def __init__(self):
        self.calls = []

    def run(self, model, input):
        self.calls.append((model, input))
        return FakeReplicateOutput()


class FakeImageReplicateRunner(FakeReplicateRunner):
    def run(self, model, input):
        self.calls.append((model, input))
        return FakeImageReplicateOutput()


class CoverGenerationTests(unittest.TestCase):
    def test_http_runner_builds_official_model_prediction_request(self):
        runner = ReplicateHttpRunner(api_token="secret-token")

        endpoint, headers, body = runner.build_prediction_request(
            "black-forest-labs/flux-1.1-pro",
            {"prompt": "cover"},
        )

        self.assertEqual(endpoint, "https://api.replicate.com/v1/models/black-forest-labs/flux-1.1-pro/predictions")
        self.assertEqual(headers["Authorization"], "Bearer secret-token")
        self.assertEqual(headers["Prefer"], "wait=60")
        self.assertEqual(body["input"]["prompt"], "cover")

    def test_generates_cover_image_to_disk_with_replicate_runner(self):
        runner = FakeReplicateRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            cover = generate_cover_image(
                prompt="clean knowledge-card cover",
                output_dir=Path(tmpdir),
                basename="AI副业",
                model="black-forest-labs/flux-1.1-pro",
                runner=runner,
            )

            self.assertTrue(cover.path.exists())
            self.assertEqual(cover.path.read_bytes(), b"generated-image")
            self.assertEqual(cover.url, "https://replicate.delivery/mock/output.jpg")
            self.assertEqual(runner.calls[0][0], "black-forest-labs/flux-1.1-pro")
            self.assertTrue(runner.calls[0][1]["prompt_upsampling"])
            self.assertEqual(runner.calls[0][1]["aspect_ratio"], "16:9")

    def test_normalizes_generated_cover_file_to_sixteen_to_nine(self):
        runner = FakeImageReplicateRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            cover = generate_cover_image(
                prompt="clean knowledge-card cover",
                output_dir=Path(tmpdir),
                basename="AI副业",
                model="black-forest-labs/flux-1.1-pro",
                runner=runner,
            )

            with Image.open(cover.path) as image:
                width, height = image.size

        self.assertAlmostEqual(width / height, 16 / 9, places=2)

    def test_generates_xiaohongshu_cover_as_three_to_four(self):
        runner = FakeImageReplicateRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            cover = generate_cover_image(
                prompt="bright lifestyle cover",
                output_dir=Path(tmpdir),
                basename="秋季养生",
                model="black-forest-labs/flux-1.1-pro",
                runner=runner,
                aspect_ratio="3:4",
            )

            with Image.open(cover.path) as image:
                size = image.size

        self.assertEqual(runner.calls[0][1]["aspect_ratio"], "3:4")
        self.assertEqual(size, (1080, 1440))

    def test_sets_replicate_token_for_sdk_without_printing_it(self):
        runner = FakeReplicateRunner()
        old_token = os.environ.get("REPLICATE_API_TOKEN")

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                generate_cover_image(
                    prompt="clean knowledge-card cover",
                    output_dir=Path(tmpdir),
                    basename="AI副业",
                    model="black-forest-labs/flux-1.1-pro",
                    runner=runner,
                    api_token="secret-token",
                )

                self.assertEqual(os.environ["REPLICATE_API_TOKEN"], "secret-token")
        finally:
            if old_token is None:
                os.environ.pop("REPLICATE_API_TOKEN", None)
            else:
                os.environ["REPLICATE_API_TOKEN"] = old_token
