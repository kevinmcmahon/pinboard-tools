# ABOUTME: Display utilities for formatting output
# ABOUTME: Provides consistent formatting for CLI output

from datetime import datetime
from typing import Any

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()


def print_bookmarks_table(
    bookmarks: list[dict[str, Any]], title: str = "Bookmarks"
) -> None:
    """Display bookmarks in a formatted table"""
    table = Table(title=title, show_lines=True)
    table.add_column("Time", style="cyan", width=20)
    table.add_column("Title", style="green", width=50)
    table.add_column("URL", style="blue", width=50)
    table.add_column("Tags", style="yellow", width=30)

    for bookmark in bookmarks:
        time_str = bookmark.get("time", "")
        if time_str:
            try:
                dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                time_str = dt.strftime("%Y-%m-%d %H:%M")
            except (ValueError, AttributeError):
                pass

        table.add_row(
            time_str,
            bookmark.get("description", "")[:50],
            bookmark.get("href", "")[:50],
            bookmark.get("tags", "")[:30],
        )

    console.print(table)


def print_tags_table(tags: list[dict[str, Any]], title: str = "Tags") -> None:
    """Display tags with counts in a formatted table"""
    table = Table(title=title)
    table.add_column("Tag", style="cyan", width=30)
    table.add_column("Count", style="green", justify="right", width=10)

    for tag in tags:
        table.add_row(tag["name"], str(tag["count"]))

    console.print(table)


def print_stats(stats: dict[str, Any], title: str = "Statistics") -> None:
    """Display statistics in a formatted table"""
    table = Table(title=title, show_header=False)
    table.add_column("Metric", style="cyan", width=30)
    table.add_column("Value", style="green", justify="right", width=20)

    for key, value in stats.items():
        # Format key nicely
        formatted_key = key.replace("_", " ").title()
        table.add_row(formatted_key, str(value))

    console.print(table)


def get_progress_spinner(description: str) -> Progress:
    """Create a progress spinner for long operations"""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    )


def confirm_action(prompt: str, default: bool = False) -> bool:
    """Ask user for confirmation"""
    default_str = "Y/n" if default else "y/N"
    response = console.input(f"{prompt} [{default_str}]: ").strip().lower()

    if not response:
        return default
    return response in ("y", "yes")


def print_error(message: str) -> None:
    """Print error message in red"""
    console.print(f"[red]Error:[/red] {message}")


def print_success(message: str) -> None:
    """Print success message in green"""
    console.print(f"[green]Success:[/green] {message}")


def print_warning(message: str) -> None:
    """Print warning message in yellow"""
    console.print(f"[yellow]Warning:[/yellow] {message}")


def print_info(message: str) -> None:
    """Print info message in blue"""
    console.print(f"[blue]Info:[/blue] {message}")
