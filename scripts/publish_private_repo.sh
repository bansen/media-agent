#!/usr/bin/env bash
set -euo pipefail

REPO_NAME="${REPO_NAME:-media-agent}"
BRANCH="${BRANCH:-main}"
COMMIT_MESSAGE="${COMMIT_MESSAGE:-Update content agent}"
GIT_REMOTE_URL="${GIT_REMOTE_URL:-}"

cd "$(dirname "$0")/.."

if [ ! -d ".git" ]; then
  git init
  git branch -M "$BRANCH"
fi

if [ -f ".env" ] && ! grep -qx ".env" .gitignore; then
  echo ".env must stay in .gitignore before publishing." >&2
  exit 1
fi

git add -A
if git diff --cached --quiet; then
  echo "No staged changes to commit."
else
  git commit -m "$COMMIT_MESSAGE"
fi

if git remote get-url origin >/dev/null 2>&1; then
  git push -u origin "$BRANCH"
  exit 0
fi

if [ -n "$GIT_REMOTE_URL" ]; then
  git remote add origin "$GIT_REMOTE_URL"
  git push -u origin "$BRANCH"
  exit 0
fi

if command -v gh >/dev/null 2>&1; then
  gh repo create "$REPO_NAME" --private --source . --remote origin --push
  exit 0
fi

cat >&2 <<'EOF'
No git remote is configured, and GitHub CLI was not found.

Choose one:
1. Install and login GitHub CLI, then rerun:
   gh auth login
   REPO_NAME=media-agent ./scripts/publish_private_repo.sh

2. Create a private repo manually, then rerun:
   GIT_REMOTE_URL=git@github.com:<owner>/media-agent.git ./scripts/publish_private_repo.sh
EOF
exit 2
