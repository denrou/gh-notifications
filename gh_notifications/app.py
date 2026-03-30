"""GitHub Notifications TUI."""

from __future__ import annotations

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, Input, Label, Static

from gh_notifications.gh import (
    Notification,
    fetch_notifications,
    mark_all_read,
    mark_as_read,
    open_in_browser,
    unsubscribe,
)

REASON_LABELS = {
    "assign": "Assigned",
    "author": "Author",
    "ci_activity": "CI",
    "comment": "Comment",
    "manual": "Manual",
    "mention": "Mention",
    "push": "Push",
    "review_requested": "Review req",
    "state_change": "State change",
    "subscribed": "Subscribed",
    "team_mention": "Team mention",
}


class FilterInput(ModalScreen[str | None]):
    """Modal for entering a filter string."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, current_filter: str = "") -> None:
        super().__init__()
        self._current = current_filter

    def compose(self) -> ComposeResult:
        with Vertical(id="filter-dialog"):
            yield Label("Filter notifications (regex on repo, title, type, reason):")
            yield Input(
                value=self._current,
                placeholder="e.g. centreon|review",
                id="filter-input",
            )

    def on_mount(self) -> None:
        self.query_one("#filter-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def action_cancel(self) -> None:
        self.dismiss(None)


class DetailScreen(ModalScreen[None]):
    """Shows full details of a notification."""

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("q", "close", "Close"),
    ]

    def __init__(self, notification: Notification) -> None:
        super().__init__()
        self._notif = notification

    def compose(self) -> ComposeResult:
        n = self._notif
        browser_url = n.html_url() or "N/A"
        text = (
            f"[b]Title:[/b]   {n.title}\n"
            f"[b]Repo:[/b]    {n.repo}\n"
            f"[b]Type:[/b]    {n.type}\n"
            f"[b]Reason:[/b]  {REASON_LABELS.get(n.reason, n.reason)}\n"
            f"[b]Unread:[/b]  {'Yes' if n.unread else 'No'}\n"
            f"[b]Updated:[/b] {n.updated_at}\n"
            f"[b]ID:[/b]      {n.id}\n"
            f"[b]URL:[/b]     {browser_url}\n"
        )
        with Vertical(id="detail-dialog"):
            yield Static(text, markup=True)
            yield Label("[dim]Press Escape or q to close[/dim]")

    def action_close(self) -> None:
        self.dismiss(None)


class NotificationsApp(App[None]):
    """GitHub Notifications TUI."""

    TITLE = "GitHub Notifications"

    CSS = """
    Screen {
        background: $surface;
    }
    #status-bar {
        height: 1;
        dock: bottom;
        margin-bottom: 1;
        padding: 0 1;
        background: $primary-background;
        color: $text;
    }
    #filter-dialog {
        align: center middle;
        width: 60;
        height: auto;
        max-height: 8;
        border: thick $accent;
        padding: 1 2;
        background: $surface;
    }
    #detail-dialog {
        align: center middle;
        width: 80;
        height: auto;
        max-height: 20;
        border: thick $accent;
        padding: 1 2;
        background: $surface;
    }
    """

    BINDINGS = [
        Binding("r", "mark_read", "Mark read"),
        Binding("R", "mark_all_read", "Mark all read"),
        Binding("u", "unsubscribe", "Unsubscribe"),
        Binding("o", "open_browser", "Open in browser"),
        Binding("enter", "show_detail", "Details"),
        Binding("/", "filter", "Filter"),
        Binding("c", "clear_filter", "Clear filter"),
        Binding("g", "refresh_list", "Refresh"),
        Binding("s", "toggle_select", "Select"),
        Binding("a", "select_all", "Select all"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._notifications: list[Notification] = []
        self._filtered: list[Notification] = []
        self._selected: set[str] = set()
        self._filter_text: str = ""

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id="notifications-table")
        yield Static("Loading...", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#notifications-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns(" ", "ID", "Repo", "Type", "Reason", "Title", "Updated")
        self._load_notifications()

    @work(thread=True)
    def _load_notifications(self) -> None:
        self._update_status("Fetching notifications...")
        try:
            self._notifications = fetch_notifications()
        except RuntimeError as e:
            self._update_status(str(e))
            return
        self.call_from_thread(self._apply_filter_and_render)

    def _update_status(self, text: str) -> None:
        def _set() -> None:
            self.query_one("#status-bar", Static).update(text)

        self.call_from_thread(_set)

    def _apply_filter_and_render(self) -> None:
        import re

        if self._filter_text:
            try:
                pat = re.compile(self._filter_text, re.IGNORECASE)
            except re.error:
                self.query_one("#status-bar", Static).update(
                    f"Invalid regex: {self._filter_text}"
                )
                return
            self._filtered = [
                n
                for n in self._notifications
                if pat.search(n.repo)
                or pat.search(n.title)
                or pat.search(n.type)
                or pat.search(n.reason)
            ]
        else:
            self._filtered = list(self._notifications)

        table = self.query_one("#notifications-table", DataTable)
        table.clear()
        for n in self._filtered:
            sel = "*" if n.id in self._selected else " "
            table.add_row(
                sel,
                n.id,
                n.repo_short,
                n.type,
                REASON_LABELS.get(n.reason, n.reason),
                n.title,
                n.updated_date,
                key=n.id,
            )

        total = len(self._notifications)
        shown = len(self._filtered)
        selected = len(self._selected)
        filter_info = f"  filter: '{self._filter_text}'" if self._filter_text else ""
        sel_info = f"  selected: {selected}" if selected else ""
        self.query_one("#status-bar", Static).update(
            f"{shown}/{total} notifications{filter_info}{sel_info}"
        )

    def action_cursor_down(self) -> None:
        table = self.query_one("#notifications-table", DataTable)
        table.action_cursor_down()

    def action_cursor_up(self) -> None:
        table = self.query_one("#notifications-table", DataTable)
        table.action_cursor_up()

    def _get_current_notification(self) -> Notification | None:
        table = self.query_one("#notifications-table", DataTable)
        if table.row_count == 0:
            return None
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        for n in self._filtered:
            if n.id == str(row_key):
                return n
        return None

    def _get_target_ids(self) -> list[str]:
        """Return selected IDs if any, otherwise the current row's ID."""
        if self._selected:
            return list(self._selected)
        n = self._get_current_notification()
        return [n.id] if n else []

    def action_toggle_select(self) -> None:
        n = self._get_current_notification()
        if not n:
            return
        if n.id in self._selected:
            self._selected.discard(n.id)
        else:
            self._selected.add(n.id)
        self._apply_filter_and_render()

    def action_select_all(self) -> None:
        if len(self._selected) == len(self._filtered):
            self._selected.clear()
        else:
            self._selected = {n.id for n in self._filtered}
        self._apply_filter_and_render()

    def action_mark_read(self) -> None:
        ids = self._get_target_ids()
        if ids:
            self._do_mark_read(ids)

    @work(thread=True)
    def _do_mark_read(self, ids: list[str]) -> None:
        self._update_status(f"Marking {len(ids)} notification(s) as read...")
        errors = []
        for tid in ids:
            try:
                mark_as_read(tid)
            except RuntimeError as e:
                errors.append(str(e))

        # Remove from local state
        read_set = set(ids) - {e.split()[2] for e in errors}  # rough, but ok
        self._notifications = [n for n in self._notifications if n.id not in read_set]
        self._selected -= read_set

        if errors:
            self._update_status(f"Errors: {'; '.join(errors)}")
        else:
            self.call_from_thread(self._apply_filter_and_render)

    def action_mark_all_read(self) -> None:
        self._do_mark_all_read()

    @work(thread=True)
    def _do_mark_all_read(self) -> None:
        self._update_status("Marking all notifications as read...")
        try:
            mark_all_read()
            self._notifications.clear()
            self._selected.clear()
            self.call_from_thread(self._apply_filter_and_render)
        except RuntimeError as e:
            self._update_status(str(e))

    def action_unsubscribe(self) -> None:
        ids = self._get_target_ids()
        if ids:
            self._do_unsubscribe(ids)

    @work(thread=True)
    def _do_unsubscribe(self, ids: list[str]) -> None:
        self._update_status(f"Unsubscribing from {len(ids)} thread(s)...")
        errors = []
        for tid in ids:
            try:
                unsubscribe(tid)
                mark_as_read(tid)
            except RuntimeError as e:
                errors.append(str(e))

        done_set = set(ids)
        self._notifications = [n for n in self._notifications if n.id not in done_set]
        self._selected -= done_set

        if errors:
            self._update_status(f"Errors: {'; '.join(errors)}")
        else:
            self.call_from_thread(self._apply_filter_and_render)

    def action_open_browser(self) -> None:
        n = self._get_current_notification()
        if n:
            open_in_browser(n)

    def action_show_detail(self) -> None:
        n = self._get_current_notification()
        if n:
            self.push_screen(DetailScreen(n))

    def action_filter(self) -> None:
        def on_dismiss(value: str | None) -> None:
            if value is not None:
                self._filter_text = value
                self._apply_filter_and_render()

        self.push_screen(FilterInput(self._filter_text), callback=on_dismiss)

    def action_clear_filter(self) -> None:
        self._filter_text = ""
        self._apply_filter_and_render()

    def action_refresh_list(self) -> None:
        self._selected.clear()
        self._load_notifications()


def main() -> None:
    app = NotificationsApp()
    app.run()


if __name__ == "__main__":
    main()
