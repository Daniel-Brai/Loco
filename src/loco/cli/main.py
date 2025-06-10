"""Loco CLI"""

import asyncio
import logging

import typer
from rich.console import Console
from rich.text import Text

from .. import get_ascii_banner
from ..utils.logging import setup_logging
from .commands import cleanup, create, list, start, status, stop

app = typer.Typer(
    name="loco",
    help="Lightning-fast localhost tunneling that's anything but crazy",
    add_completion=True,
    rich_markup_mode="rich",
)

console = Console()


@app.command("create")
def create_tunnel(
    port: int = typer.Argument(..., help="Local port to tunnel"),
    name: str | None = typer.Option(None, "--name", "-n", help="Tunnel name"),
    protocol: str = typer.Option(
        "http", "--protocol", "-p", help="Protocol (http/https/tcp/websocket)"
    ),
    subdomain: str | None = typer.Option(
        None, "--subdomain", "-s", help="Custom subdomain"
    ),
    remote_port: int | None = typer.Option(
        None, "--remote-port", "-r", help="Remote port"
    ),
    host: str = typer.Option("localhost", "--host", help="Local host"),
    start: bool = typer.Option(
        True, "--start/--no-start", help="Start tunnel immediately"
    ),
) -> None:
    """Create a new tunnel."""
    asyncio.run(
        create.create_tunnel_async(
            port=port,
            name=name,
            protocol=protocol,
            subdomain=subdomain,
            remote_port=remote_port,
            host=host,
            start=start,
        )
    )


@app.command("list")
def list_tunnels() -> None:
    """List all tunnels."""
    asyncio.run(list.list_tunnels_async())


@app.command("start")
def start_tunnel(
    tunnel_id: str = typer.Argument(..., help="Tunnel ID to start"),
) -> None:
    """Start a stopped tunnel."""
    asyncio.run(start.start_tunnel_async(tunnel_id))


@app.command("start-all")
def start_all_tunnels() -> None:
    """Start all stopped tunnels."""
    asyncio.run(start.start_all_tunnels_async())


@app.command("stop")
def stop_tunnel(tunnel_id: str = typer.Argument(..., help="Tunnel ID to stop")) -> None:
    """Stop a tunnel."""
    asyncio.run(stop.stop_tunnel_async(tunnel_id))


@app.command("stop-all")
def stop_all_tunnels() -> None:
    """Stop all active tunnels."""
    asyncio.run(stop.stop_all_tunnels_async())


@app.command("status")
def status_tunnel(
    tunnel_id: str | None = typer.Argument(None, help="Tunnel ID (optional)"),
) -> None:
    """Show tunnel status."""
    asyncio.run(status.status_tunnel_async(tunnel_id))


@app.command("cleanup")
def cleanup_tunnels(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Clean up stopped tunnels."""
    asyncio.run(cleanup.cleanup_tunnels_async(force))


@app.command("cleanup-all")
def cleanup_all_tunnels(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Clean up all tunnels (including active ones)."""
    asyncio.run(cleanup.cleanup_all_async(force))


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-v", help="Show version and exit"
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
) -> None:
    """Lightning-fast localhost tunneling that's anything but crazy."""

    if debug:
        setup_logging(logging.DEBUG)
    elif verbose:
        setup_logging(logging.INFO)
    else:
        setup_logging(
            logging.CRITICAL + 1
        )  # Higher than CRITICAL to suppress everything

    if version:
        banner_lines = get_ascii_banner().split("\n")

        for i, line in enumerate(banner_lines):
            if i < 6:  # ASCII art lines
                console.print(Text(line, style="bold cyan"))
            elif "Lightning-fast" in line:
                console.print(Text(line, style="bold white"))
            elif "that's anything but crazy" in line:
                console.print(Text(line, style="italic white"))
            elif "VERSION" in line:
                console.print(Text(line, style="bold green"))
            else:
                console.print(line)

        raise typer.Exit()

    if ctx.invoked_subcommand is None:
        console.print(Text(get_ascii_banner(), style="bold cyan"))
        console.print("\n[bold]Available commands:[/bold]")
        console.print("  [cyan]create[/cyan]        Create a new tunnel")
        console.print("  [cyan]list[/cyan]          List all tunnels")
        console.print("  [cyan]start[/cyan]         Start a stopped tunnel")
        console.print("  [cyan]start-all[/cyan]     Start all stopped tunnels")
        console.print("  [cyan]stop[/cyan]          Stop a tunnel")
        console.print("  [cyan]stop-all[/cyan]      Stop all active tunnels")
        console.print("  [cyan]status[/cyan]        Show tunnel status")
        console.print("  [cyan]cleanup[/cyan]       Clean up stopped tunnels")
        console.print(
            "  [cyan]cleanup-all[/cyan]   Clean up all tunnels (active and stopped)"
        )
        console.print(
            "\n[dim]Use 'loco --help' for detailed help or 'loco <command> --help' for command-specific help.[/dim]"
        )


if __name__ == "__main__":
    app()
