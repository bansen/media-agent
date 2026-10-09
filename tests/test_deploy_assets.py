import unittest
import os
import subprocess
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DeployAssetTests(unittest.TestCase):
    def run_deploy(self, failure=""):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env.production").write_text("WEBSEARCH_MCP_ENABLED=false\n")
            docker = root / "docker"
            docker.write_text(
                '#!/bin/sh\nprintf "%s\\n" "$*" >> "$DOCKER_LOG"\n'
                'if [ -n "$FAIL_COMMAND" ]; then\n'
                '  case "$*" in *"$FAIL_COMMAND"*) exit 17;; esac\nfi\n'
            )
            docker.chmod(0o755)
            log = root / "docker.log"
            result = subprocess.run(
                ["sh", str(PROJECT_ROOT / "scripts/deploy.sh")],
                env={**os.environ, "PATH": str(root) + os.pathsep + os.environ["PATH"],
                     "APP_DIR": str(root), "ENV_FILE": ".env.production",
                     "DOCKER_LOG": str(log), "FAIL_COMMAND": failure},
                capture_output=True, text=True,
            )
            return result, log.read_text().splitlines()

    def test_successful_deployment_prunes_unused_images_after_startup(self):
        result, commands = self.run_deploy()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(commands[-1], "image prune --all --force")
        self.assertIn("up -d --wait --wait-timeout 120", commands[-2])
        self.assertFalse(any("volume" in command or "system prune" in command for command in commands))

    def test_failed_pull_or_startup_keeps_old_images(self):
        for failure in ("pull", "up -d"):
            with self.subTest(failure=failure):
                result, commands = self.run_deploy(failure)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(any("prune" in command for command in commands))

    def test_cleanup_failure_is_reported_as_deployment_failure(self):
        result, commands = self.run_deploy("image prune")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(commands[-1], "image prune --all --force")

    def test_private_repo_script_documents_safe_git_publish_flow(self):
        script = (PROJECT_ROOT / "scripts" / "publish_private_repo.sh").read_text(encoding="utf-8")

        self.assertIn("gh repo create", script)
        self.assertIn("--private", script)
        self.assertIn("GIT_REMOTE_URL", script)
        self.assertIn("media-agent", script)
        self.assertIn("git add -A", script)
        self.assertIn("git push", script)

    def test_deploy_docs_keep_env_file_out_of_git(self):
        docs = (PROJECT_ROOT / "deploy" / "README.md").read_text(encoding="utf-8")
        gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")

        self.assertIn(".env", gitignore)
        self.assertIn("不要提交 .env", docs)
        self.assertIn("Cloudflare", docs)
        self.assertIn("二级域名", docs)
        self.assertIn("media-agent.createbeauty.top", docs)

    def test_github_actions_matches_putiyuan_style_docker_deploy(self):
        workflow = (PROJECT_ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
        compose = (PROJECT_ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
        dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")

        self.assertIn("ghcr.io", workflow)
        self.assertIn("ALIYUN_HOST", workflow)
        self.assertIn("ALIYUN_SSH_PASSPHRASE", workflow)
        self.assertIn("/opt/media-agent", workflow)
        self.assertIn("deploy/nginx.media-agent.conf", workflow)
        self.assertIn("/etc/nginx/conf.d/media-agent.conf", workflow)
        self.assertIn("media-agent-app", compose)
        self.assertIn("media-agent-db", compose)
        self.assertIn("postgres:16-alpine", compose)
        self.assertIn("DATABASE_URL", compose)
        self.assertIn("content_agent.web", dockerfile)
        self.assertIn("COPY .env.example ./.env.example", dockerfile)
        self.assertIn("--host\", \"0.0.0.0", dockerfile)

    def test_docker_image_installs_npx_for_websearch_mcp(self):
        dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")

        self.assertIn("nodejs", dockerfile)
        self.assertIn("npm", dockerfile)

    def test_deploy_script_bootstraps_env_file_for_first_run(self):
        script = (PROJECT_ROOT / "scripts" / "deploy.sh").read_text(encoding="utf-8")

        self.assertIn("cp .env.example \"$ENV_FILE\"", script)
        self.assertIn("Created $APP_DIR/$ENV_FILE", script)
        self.assertIn("compose up -d", script)

    def test_deploy_script_checks_tavily_key_when_websearch_mcp_is_enabled(self):
        script = (PROJECT_ROOT / "scripts" / "deploy.sh").read_text(encoding="utf-8")

        self.assertIn("WEBSEARCH_MCP_ENABLED", script)
        self.assertIn("TAVILY_API_KEY", script)
        self.assertIn("Missing TAVILY_API_KEY", script)


if __name__ == "__main__":
    unittest.main()
