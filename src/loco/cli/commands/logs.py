"""Log streaming for tunnels."""

import asyncio
from datetime import datetime
from typing import Any

from rich.console import Console

from ...core.exceptions import TunnelNotFoundError
from ...network.manager import TunnelManager

console = Console()


async def stream_logs_async(
    tunnel_id: str,
    follow: bool = True,
    header: bool = True,
    manager: TunnelManager | None = None,
) -> None:
    """Stream logs for a tunnel."""
    try:
        if manager is None:
            manager = TunnelManager()
            await manager.load_from_storage()

        tunnel = manager.get_tunnel(tunnel_id)
        tunnel_name = tunnel.config.name or tunnel.config.tunnel_id[:8]

        console.print(
            f"[bold]Streaming logs for tunnel: [cyan]{tunnel_name}[/cyan][/bold]"
        )

        if header:
            console.print(
                f"[dim]Local: {tunnel.config.local_host}:{tunnel.config.local_port} • "
                f"Public: {tunnel.state.public_url or f'localhost:{tunnel.config.remote_port}'}"
            )
            console.print("[dim]Press Ctrl+C to stop viewing logs[/dim]")

        console.print("[dim]" + "=" * 86 + "[/dim]\n")

        console.print(
            f"[bold dim]{'TIME':8}  {'METHOD':6}  {'PATH':40}  {'CODE':3}  {'LATENCY':9}  {'IP ADDRESS'}[/bold dim]"
        )
        console.print("[dim]" + "-" * 86 + "[/dim]")

        log_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        if hasattr(tunnel, "register_log_handler"):
            tunnel.register_log_handler(lambda log: log_queue.put_nowait(log))

        try:
            while follow:
                log_entry = await log_queue.get()
                _print_log_entry(log_entry)
        except asyncio.CancelledError:
            pass
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopped log streaming")

    except TunnelNotFoundError:
        console.print(f"[red]Error: No tunnel found matching '{tunnel_id}'")
    except Exception as e:
        console.print(f"[red]Error streaming logs: {e}")


def _print_log_entry(entry: dict[Any, Any]) -> None:
    """Print a formatted log entry."""
    timestamp = entry.get("timestamp", datetime.now().isoformat())
    method = entry.get("method", "GET")
    path = entry.get("path", "/")
    status = entry.get("status", 200)
    ip = entry.get("ip", "127.0.0.1")
    duration = entry.get("duration", 0)

    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        time_str = dt.strftime("%H:%M:%S")
    except (ValueError, TypeError):
        time_str = _get_timestamp()

    if status < 300:
        status_color = "green"
    elif status < 400:
        status_color = "yellow"
    elif status < 500:
        status_color = "orange_red1"
    else:
        status_color = "red"

    method_colors = {
        "GET": "green",
        "POST": "yellow",
        "PUT": "blue",
        "DELETE": "red",
        "PATCH": "magenta",
        "OPTIONS": "cyan",
        "HEAD": "dim",
    }
    method_color = method_colors.get(method, "white")

    console.print(
        f"[dim]{time_str}[/dim]  "
        f"[{method_color}]{method:6}[/{method_color}]  "
        f"[white]{path:40.40}[/white]  "
        f"[{status_color}]{status:3}[/{status_color}]  "
        f"[dim]{duration:7.2f}ms[/dim]  "
        f"[blue]{ip}[/blue]"
    )


def _get_timestamp() -> str:
    """Get current timestamp for logs."""
    return datetime.now().strftime("%H:%M:%S")
