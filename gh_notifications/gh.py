"""Thin wrapper around the gh CLI for GitHub notifications."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


@dataclass
class Notification:
    id: str
    repo: str
    type: str
    title: str
    reason: str
    unread: bool
    updated_at: str
    url: str
    subject_url: str | None = None
    latest_comment_url: str | None = None

    @classmethod
    def from_json(cls, data: dict) -> Notification:
        return cls(
            id=data["id"],
            repo=data["repository"]["full_name"],
            type=data["subject"]["type"],
            title=data["subject"]["title"],
            reason=data["reason"],
            unread=data["unread"],
            updated_at=data["updated_at"],
            url=data.get("url", ""),
            subject_url=data["subject"].get("url"),
            latest_comment_url=data["subject"].get("latest_comment_url"),
        )

    @property
    def repo_short(self) -> str:
        return self.repo.split("/")[-1]

    @property
    def updated_date(self) -> str:
        return self.updated_at.split("T")[0]

    def html_url(self) -> str | None:
        """Convert API URL to browser URL."""
        url = self.latest_comment_url or self.subject_url
        if not url:
            return None
        return (
            url.replace("api.github.com/repos/", "github.com/")
            .replace("/pulls/", "/pull/")
            .replace("/commits/", "/commit/")
        )


def _run_gh(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gh", "api", *args],
        capture_output=True,
        text=True,
        check=check,
    )


def fetch_notifications() -> list[Notification]:
    result = _run_gh("notifications", "--paginate", check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to fetch notifications: {result.stderr.strip()}")
    raw = result.stdout.strip()
    if not raw:
        return []
    data = json.loads(raw)
    return [Notification.from_json(n) for n in data]


def mark_as_read(thread_id: str) -> None:
    result = _run_gh(
        "--method",
        "PATCH",
        f"notifications/threads/{thread_id}",
        "--silent",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to mark {thread_id} as read: {result.stderr.strip()}"
        )


def unsubscribe(thread_id: str) -> None:
    result = _run_gh(
        "--method",
        "PUT",
        f"notifications/threads/{thread_id}/subscription",
        "-f",
        "ignored=true",
        "--silent",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to unsubscribe {thread_id}: {result.stderr.strip()}"
        )


def mark_all_read(last_read_at: str | None = None) -> None:
    args = ["--method", "PUT", "notifications", "--silent"]
    if last_read_at:
        args.extend(["-f", f"last_read_at={last_read_at}"])
    result = _run_gh(*args, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to mark all as read: {result.stderr.strip()}")


def open_in_browser(notification: Notification) -> None:
    url = notification.html_url()
    if url:
        subprocess.run(["open", url], check=False)
