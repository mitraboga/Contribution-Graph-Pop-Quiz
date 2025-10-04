from __future__ import annotations
import base64
import datetime as dt
import os
import random
import string
from typing import Optional

# Graceful import for requests
try:
    import requests  # type: ignore
except Exception:  # ImportError or anything odd in the env
    requests = None

__all__ = ["GitHubCommitter", "make_daily_commits_if_configured", "diagnose_config"]

GITHUB_API = "https://api.github.com"


def _need_requests_msg() -> str:
    return (
        "Dependency missing: the 'requests' package is not installed.\n"
        "Fix: activate your venv and run:\n"
        "    pip install requests\n"
        "Then retry your command."
    )


def diagnose_config() -> str:
    """Return a human-readable diagnostics string about env + deps."""
    lines = []
    lines.append(f"requests available: {requests is not None}")
    for key in ("GITHUB_TOKEN", "GITHUB_REPO", "GH_USER_NAME", "GH_USER_EMAIL"):
        val = os.environ.get(key)
        show = (val[:6] + "…" + val[-4:]) if (val and key == "GITHUB_TOKEN" and len(val) > 12) else val
        lines.append(f"{key}: {'SET' if val else 'MISSING'}{(' ('+show+')') if show else ''}")
    return "\n".join(lines)


class GitHubCommitter:
    def __init__(
        self,
        token: str,
        repo: str,
        author_name: str,
        author_email: str,
        session: Optional["requests.Session"] = None,  # type: ignore[name-defined]
    ):
        if requests is None:
            raise RuntimeError(_need_requests_msg())

        self.token = token
        self.repo = repo
        self.author_name = author_name
        self.author_email = author_email
        self.sess = session or requests.Session()
        self.sess.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "Commit-Quiz-Bot",
            }
        )

    def _put_file(self, path: str, content_str: str, message: str):
        """
        Create or update a file by path on the default branch (usually main).
        We create unique paths each time so we don't need an existing SHA.
        """
        url = f"{GITHUB_API}/repos/{self.repo}/contents/{path}"
        body = {
            "message": message,
            "content": base64.b64encode(content_str.encode("utf-8")).decode("ascii"),
             # Let GitHub infer author/committer from the token owner
        }

        r = self.sess.put(url, json=body, timeout=30)
        if r.status_code not in (200, 201):
            raise RuntimeError(f"GitHub API error {r.status_code}: {r.text}")
        return r.json()

    def commit_n(self, n: int = 5, tag: Optional[str] = None):
        """
        Make `n` commits by creating n small text files under logs/YYYY/MM/DD/.
        """
        today = dt.date.today()
        prefix = f"logs/{today.year:04d}/{today.month:02d}/{today.day:02d}"
        tag = tag or "quiz"
        for i in range(1, n + 1):
            salt = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
            path = f"{prefix}/{tag}-{i}-{salt}.txt"
            content = f"Quiz commit #{i} for {today.isoformat()} tag:{tag}\n"
            msg = f"quiz: daily commit {today.isoformat()} [{tag}] #{i}"
            self._put_file(path, content, msg)


def make_daily_commits_if_configured(n: int = 5, tag: Optional[str] = None) -> Optional[str]:
    """
    Reads env vars and fires commits if configured. Returns a friendly string
    on success or a human-readable reason if it can’t run (no exceptions).
    Required env: GITHUB_TOKEN, GITHUB_REPO, GH_USER_NAME, GH_USER_EMAIL
    """
    if requests is None:
        return _need_requests_msg()

    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPO")
    name = os.environ.get("GH_USER_NAME")
    email = os.environ.get("GH_USER_EMAIL")
    missing = [k for k, v in {
        "GITHUB_TOKEN": token,
        "GITHUB_REPO": repo,
        "GH_USER_NAME": name,
        "GH_USER_EMAIL": email,
    }.items() if not v]
    if missing:
        return "GitHub committer not configured (missing env vars): " + ", ".join(missing)

    try:
        committer = GitHubCommitter(token, repo, name, email)
        committer.commit_n(n=n, tag=tag)
        return f"Committed {n} files to {repo}."
    except Exception as e:
        # Return a short message rather than raising, so callers/logs stay clean
        return f"Commit failed: {e}"


if __name__ == "__main__":
    # Self-diagnose & attempt a single commit
    print("Diagnostics:")
    print(diagnose_config())
    print("Test commit result:")
    print(make_daily_commits_if_configured(n=1, tag="self-test"))
