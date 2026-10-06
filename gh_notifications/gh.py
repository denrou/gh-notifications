"""Thin wrapper around the gh CLI for GitHub notifications."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass

_PR_URL_RE = re.compile(r"/repos/([^/]+)/([^/]+)/pulls/(\d+)$")

# GraphQL field selection shared by every pull request in a batched query.
_PR_FRAGMENT = """
fragment PR on PullRequest {
  state
  isDraft
  reviewDecision
  reviews(last: 1) { nodes { state submittedAt author { login } } }
  comments(last: 1) { nodes { createdAt author { login } } }
  commits(last: 1) { nodes { commit { statusCheckRollup { state } } } }
}
"""

# Maximum number of pull requests queried in one GraphQL request.
_GRAPHQL_BATCH_SIZE = 50

REVIEW_DECISION_LABELS = {
    "APPROVED": "approved",
    "CHANGES_REQUESTED": "changes",
    "REVIEW_REQUIRED": "pending",
}

REVIEW_STATE_LABELS = {
    "APPROVED": "approved",
    "CHANGES_REQUESTED": "requested changes",
    "COMMENTED": "commented",
    "DISMISSED": "dismissed",
    "PENDING": "pending",
}


@dataclass
class PullRequestInfo:
    """State of a pull request, fetched separately from the notification."""

    state: str  # OPEN, CLOSED or MERGED
    is_draft: bool
    review_decision: str | None  # APPROVED, CHANGES_REQUESTED, REVIEW_REQUIRED
    ci_state: str | None  # SUCCESS, FAILURE, PENDING, ERROR, EXPECTED
    last_review_state: str | None = None
    last_review_author: str | None = None
    last_review_at: str | None = None
    last_comment_author: str | None = None
    last_comment_at: str | None = None

    @classmethod
    def from_graphql(cls, data: dict) -> PullRequestInfo:
        reviews = data["reviews"]["nodes"]
        comments = data["comments"]["nodes"]
        commits = data["commits"]["nodes"]
        review = reviews[0] if reviews else {}
        comment = comments[0] if comments else {}
        rollup = commits[0]["commit"]["statusCheckRollup"] if commits else None
        return cls(
            state=data["state"],
            is_draft=data["isDraft"],
            review_decision=data["reviewDecision"],
            ci_state=rollup["state"] if rollup else None,
            last_review_state=review.get("state"),
            last_review_author=(review.get("author") or {}).get("login"),
            last_review_at=review.get("submittedAt"),
            last_comment_author=(comment.get("author") or {}).get("login"),
            last_comment_at=comment.get("createdAt"),
        )

    @property
    def state_label(self) -> str:
        if self.state == "OPEN" and self.is_draft:
            return "draft"
        return self.state.lower()

    @property
    def ci_failed(self) -> bool:
        return self.ci_state in ("FAILURE", "ERROR")

    @property
    def review_label(self) -> str:
        label = REVIEW_DECISION_LABELS.get(self.review_decision or "", "")
        if self.ci_failed:
            label = f"{label} CI!".strip()
        return label


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
    last_read_at: str | None = None
    pr: PullRequestInfo | None = None

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
            last_read_at=data.get("last_read_at"),
        )

    def pr_ref(self) -> tuple[str, str, int] | None:
        """Return (owner, repo, number) when the subject is a pull request."""
        if self.type != "PullRequest" or not self.subject_url:
            return None
        m = _PR_URL_RE.search(self.subject_url)
        if not m:
            return None
        return m.group(1), m.group(2), int(m.group(3))

    def _is_new(self, timestamp: str | None) -> bool:
        """True when timestamp is later than the last time the thread was read."""
        if not timestamp:
            return False
        if not self.last_read_at:
            return True
        # ISO-8601 UTC timestamps from the API compare correctly as strings.
        return timestamp > self.last_read_at

    @property
    def has_new_review(self) -> bool:
        return self.pr is not None and self._is_new(self.pr.last_review_at)

    @property
    def has_new_comment(self) -> bool:
        return self.pr is not None and self._is_new(self.pr.last_comment_at)

    @property
    def state_label(self) -> str:
        """Pull request state, or the subject type for other notifications."""
        if self.pr:
            return self.pr.state_label
        return self.type

    @property
    def review_label(self) -> str:
        return self.pr.review_label if self.pr else ""

    @property
    def activity_label(self) -> str:
        """What happened on the thread since it was last read."""
        parts = []
        if self.has_new_review:
            parts.append("review")
        if self.has_new_comment:
            parts.append("comment")
        return "+".join(parts)

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


def _graphql_alias(index: int) -> str:
    return f"pr{index}"


def _build_pr_query(refs: list[tuple[str, str, int]]) -> str:
    parts = []
    for i, (owner, repo, number) in enumerate(refs):
        parts.append(
            f"{_graphql_alias(i)}: repository(owner: {json.dumps(owner)}, name: {json.dumps(repo)}) "
            f"{{ pullRequest(number: {number}) {{ ...PR }} }}"
        )
    return _PR_FRAGMENT + "query {\n" + "\n".join(parts) + "\n}"


def fetch_pull_request_info(
    notifications: list[Notification],
) -> dict[str, PullRequestInfo]:
    """Fetch pull request state for every PR notification, in batched GraphQL queries.

    Returns a mapping from notification id to PullRequestInfo. Notifications
    whose pull request could not be fetched are left out of the result.
    """
    targets = [(n, n.pr_ref()) for n in notifications]
    targets = [(n, ref) for n, ref in targets if ref is not None]
    result: dict[str, PullRequestInfo] = {}
    for start in range(0, len(targets), _GRAPHQL_BATCH_SIZE):
        batch = targets[start : start + _GRAPHQL_BATCH_SIZE]
        query = _build_pr_query([ref for _, ref in batch])
        proc = _run_gh("graphql", "-f", f"query={query}", check=False)
        raw = proc.stdout.strip()
        if not raw:
            raise RuntimeError(
                f"Failed to fetch pull request details: {proc.stderr.strip()}"
            )
        # gh exits non-zero when the response carries partial errors but still
        # prints the payload, so parse whatever came back.
        data = json.loads(raw).get("data") or {}
        for i, (notification, _) in enumerate(batch):
            repo_data = data.get(_graphql_alias(i)) or {}
            pr_data = repo_data.get("pullRequest")
            if pr_data:
                result[notification.id] = PullRequestInfo.from_graphql(pr_data)
    return result


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
