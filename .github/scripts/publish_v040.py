"""Fail-closed, manual-only publisher for the reviewed v0.4.0 commit."""
from __future__ import annotations
import json
import os
import re
import urllib.request
from pathlib import Path

VERSION = "v0.4.0"
REPO = "SergejDAGDA/agent-maintain-server-containers"
ROOT = Path(__file__).resolve().parents[2]


class ReleaseRefused(RuntimeError):
    pass


def verify_source(root):
    for p in ("plugin.json", ".claude-plugin/plugin.json"):
        if json.loads((root / p).read_text(encoding="utf-8"))["version"] != "0.4.0":
            raise ReleaseRefused("Manifest version mismatch")
    if (root / "skills/maintain-server-containers/VERSION").read_text(encoding="utf-8").strip() != "0.4.0":
        raise ReleaseRefused("Skill VERSION mismatch")
    if "## 0.4.0 - 2026-10-14" not in (root / "CHANGELOG.md").read_text(encoding="utf-8"):
        raise ReleaseRefused("Changelog date mismatch")
    for p in ("README.md", "README.ru.md"):
        if VERSION not in (root / p).read_text(encoding="utf-8"):
            raise ReleaseRefused("README version mismatch")
    for p in ("skills/maintain-server-containers/SKILL.md", "docs/releases/v0.4.0.md"):
        if not (root / p).is_file():
            raise ReleaseRefused("Missing release or canonical skill file")


class Github:
    def __init__(self, token):
        self.token = token

    def _api(self, method, path, payload=None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request("https://api.github.com/repos/" + REPO + "/" + path,
            data=data, method=method, headers={
                "Authorization": "Bearer " + self.token,
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
            })
        try:
            with urllib.request.urlopen(req, timeout=20) as res:
                return json.load(res)
        except Exception as exc:
            raise ReleaseRefused("GitHub API failed; investigate before retrying") from exc

    def get(self, path):
        return self._api("GET", path)

    def post(self, path, payload):
        return self._api("POST", path, payload)


def tag(api):
    rows = api.get("git/matching-refs/tags/" + VERSION)
    if not isinstance(rows, list):
        raise ReleaseRefused("Tag inventory unavailable")
    return [r for r in rows if isinstance(r, dict) and r.get("ref") == "refs/tags/" + VERSION]


def releases(api):
    found = []
    for page in range(1, 51):
        rows = api.get(f"releases?per_page=100&page={page}")
        if not isinstance(rows, list):
            raise ReleaseRefused("Release inventory unavailable")
        found += [r for r in rows if isinstance(r, dict) and r.get("tag_name") == VERSION]
        if len(rows) < 100:
            return found
    raise ReleaseRefused("Release inventory bound exceeded")


def ci_passed(api, file, sha):
    data = api.get(f"actions/workflows/{file}/runs?head_sha={sha}&branch=main&per_page=100")
    if not isinstance(data, dict) or not isinstance(data.get("workflow_runs"), list):
        raise ReleaseRefused("CI evidence unavailable")
    return any(isinstance(r, dict) and r.get("head_sha") == sha and
               r.get("head_branch") == "main" and r.get("event") == "push" and
               r.get("status") == "completed" and r.get("conclusion") == "success"
               for r in data["workflow_runs"])


def tag_pins(api, sha):
    obj = api.get("git/ref/tags/" + VERSION)
    actual = obj.get("object") if isinstance(obj, dict) else None
    return isinstance(actual, dict) and actual.get("type") == "commit" and actual.get("sha") == sha


def publish(api, sha, root):
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ReleaseRefused("Full approved commit SHA required")
    verify_source(root)
    main = api.get("branches/main")
    if not isinstance(main, dict) or main.get("commit", {}).get("sha") != sha:
        raise ReleaseRefused("Approved commit is not main at dispatch time")
    if tag(api) or releases(api):
        raise ReleaseRefused("Tag or Release already exists; manual investigation required")
    for workflow in ("tests.yml", "integration.yml"):
        if not ci_passed(api, workflow, sha):
            raise ReleaseRefused("Push-to-main CI gate not verified: " + workflow)
    # The human approved this exact SHA. No implicit retargeting if main moves.
    api.post("git/refs", {"ref": "refs/tags/" + VERSION, "sha": sha})
    if not tag_pins(api, sha) or releases(api):
        raise ReleaseRefused("Post-tag identity failed or concurrent Release appeared")
    created = api.post("releases", {
        "tag_name": VERSION, "target_commitish": sha,
        "name": "Maintain Server Containers " + VERSION,
        "body": (root / "docs/releases/v0.4.0.md").read_text(encoding="utf-8"),
        "draft": False, "prerelease": False,
    })
    verified = api.get("releases/tags/" + VERSION)
    if (not isinstance(created, dict) or not isinstance(verified, dict) or
            verified.get("id") != created.get("id") or
            verified.get("tag_name") != VERSION or
            verified.get("draft") is not False or
            verified.get("prerelease") is not False or
            not verified.get("published_at") or not tag_pins(api, sha)):
        raise ReleaseRefused("Release publication postconditions failed")
    return verified


def main():
    if (os.environ.get("GITHUB_REPOSITORY") != REPO or
            os.environ.get("GITHUB_REF") != "refs/heads/main" or
            os.environ.get("RELEASE_CONFIRMATION") != "PUBLISH-v0.4.0"):
        raise ReleaseRefused("Explicit manual main-branch confirmation required")
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise ReleaseRefused("GitHub token missing")
    sha = os.environ.get("RELEASE_SHA", "")
    released = publish(Github(token), sha, ROOT)
    print(f"Published {VERSION} for exact approved commit {sha}; release ID {released['id']}")


if __name__ == "__main__":
    try:
        main()
    except ReleaseRefused as exc:
        print("RELEASE BLOCKED: " + str(exc))
        raise SystemExit(2)
