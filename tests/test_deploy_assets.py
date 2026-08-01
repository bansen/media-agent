import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DeployAssetTests(unittest.TestCase):
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

    def test_deploy_script_bootstraps_env_file_for_first_run(self):
        script = (PROJECT_ROOT / "scripts" / "deploy.sh").read_text(encoding="utf-8")

        self.assertIn("cp .env.example \"$ENV_FILE\"", script)
        self.assertIn("Created $APP_DIR/$ENV_FILE", script)
        self.assertIn("compose up -d", script)


if __name__ == "__main__":
    unittest.main()
