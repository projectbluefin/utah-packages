"""Reject dispatches which do not name this repository's current bot PR head."""
import argparse
import json
import re
from pathlib import Path


def verify(pr: dict, repository: str, sha: str, branch: str) -> None:
    if not re.fullmatch(r"(?:chore/buildroot-mirror|import/rawhide-[A-Za-z0-9][A-Za-z0-9_.+-]*)", branch):
        raise ValueError("dispatch ref is not an allowed bot branch")
    expected = (pr.get("state") == "OPEN" and pr.get("baseRefName") == "main"
                and pr.get("headRefName") == branch and pr.get("headRefOid") == sha
                and pr.get("headRepository", {}).get("nameWithOwner") == repository
                and pr.get("author", {}).get("login") == "app/github-actions")
    if not expected:
        raise ValueError("pull request is not the open same-repository bot PR at this dispatch ref/SHA")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("repository")
    parser.add_argument("sha")
    parser.add_argument("branch")
    args = parser.parse_args()
    verify(json.loads(args.metadata.read_text()), args.repository, args.sha, args.branch)
