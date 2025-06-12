from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ...core.models import TunnelStatus
from ...network.manager import TunnelManager

console = Console()


async def status_tunnel_async(tunnel_id: str | None = None) -> None:
    """Show tunnel status."""
    try:
        manager = TunnelManager()
        await manager.load_from_storage()

        if tunnel_id:
            await _show_tunnel_details(manager, tunnel_id)
        else:
            await _show_tunnels_overview(manager)

    except Exception as e:
        console.print(f"[red]Error getting tunnel status: {e}")


async def _show_tunnel_details(manager: TunnelManager, tunnel_id: str) -> None:
    """Show detailed status for a specific tunnel."""
    try:
        tunnels = await manager.list_tunnels()
        matching_tunnels = [
            t
            for t in tunnels
            if t.config.tunnel_id.startswith(tunnel_id)
            or (t.config.name and tunnel_id.lower() in t.config.name.lower())
        ]

        if not matching_tunnels:
            console.print(f"[red]Error: No tunnel found matching '{tunnel_id}'")
            return

        if len(matching_tunnels) > 1:
            console.print(f"[yellow]Multiple tunnels match '{tunnel_id}':")
            for tunnel in matching_tunnels:
                name_info = f" ({tunnel.config.name})" if tunnel.config.name else ""
                console.print(f"  • {tunnel.config.tunnel_id[:8]}...{name_info}")
            console.print("[yellow]Please be more specific.")
            return

        tunnel = matching_tunnels[0]
        stats = await manager.get_tunnel_stats(tunnel.config.tunnel_id)

        status_color = _get_status_color(stats["status"])
        status_text = Text(stats["status"], style=status_color)

        info_table = Table(show_header=False, box=None, padding=(0, 1))
        info_table.add_column("Property", style="bold")
        info_table.add_column("Value")

        info_table.add_row("Tunnel ID", stats["tunnel_id"])
        info_table.add_row("Status", status_text)
        info_table.add_row("Local Service", stats["local_service"])
        info_table.add_row("Public URL", stats["public_url"] or "—")
        info_table.add_row("Uptime", _format_uptime(stats["uptime_seconds"]))
        info_table.add_row("Created", _format_timestamp(stats["created_at"]))

        if stats["started_at"]:
            info_table.add_row("Started", _format_timestamp(stats["started_at"]))

        if stats["last_activity"]:
            info_table.add_row(
                "Last Activity", _format_timestamp(stats["last_activity"])
            )

        if stats["error_message"]:
            info_table.add_row("Error", Text(stats["error_message"], style="red"))

        stats_table = Table(show_header=False, box=None, padding=(0, 1))
        stats_table.add_column("Metric", style="bold")
        stats_table.add_column("Value", style="cyan")

        stats_table.add_row("Active Connections", str(stats["active_connections"]))
        stats_table.add_row("Total Connections", str(stats["total_connections"]))
        stats_table.add_row(
            "Bytes Transferred", _format_bytes(stats["bytes_transferred"])
        )

        console.print(
            Panel(info_table, title="Tunnel Status", border_style=status_color)
        )
        console.print(Panel(stats_table, title="Statistics", border_style="blue"))

    except Exception as e:
        console.print(f"[red]Error getting tunnel details: {e}")


async def _show_tunnels_overview(manager: TunnelManager) -> None:
    """Show overview of all tunnels."""
    tunnels = await manager.list_tunnels()

    if not tunnels:
        console.print("[yellow]No tunnels found[/yellow]")
        return

    status_counts: dict[str, int] = {}
    for tunnel in tunnels:
        status = tunnel.status.value
        status_counts[status] = status_counts.get(status, 0) + 1

    table = Table(title="Tunnel Overview")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Local", style="blue")
    table.add_column("Public URL", style="yellow")
    table.add_column("Uptime", style="white")
    table.add_column("Connections", style="cyan")

    for tunnel in tunnels:
        uptime = "—"
        connections = "—"

        if tunnel.status == TunnelStatus.ACTIVE:
            try:
                stats = await manager.get_tunnel_stats(tunnel.config.tunnel_id)
                uptime = _format_uptime(stats["uptime_seconds"])
                connections = str(stats["active_connections"])
            except Exception:
                pass

        status_color = _get_status_color(tunnel.status.value)
        status_text = Text(tunnel.status.value, style=status_color)

        table.add_row(
            tunnel.config.tunnel_id[:8] + "...",
            tunnel.config.name or "—",
            status_text,
            f"{tunnel.config.local_host}:{tunnel.config.local_port}",
            tunnel.public_url or "—",
            uptime,
            connections,
        )

    console.print(table)

    summary_text = []
    for status, count in status_counts.items():
        color = _get_status_color(status)
        summary_text.append(f"[{color}]{count} {status}[/{color}]")

    console.print(f"\n[bold]Summary:[/bold] {' | '.join(summary_text)}")


def _get_status_color(status: str) -> str:
    """Get color for tunnel status."""
    colors = {
        "active": "green",
        "starting": "yellow",
        "stopping": "yellow",
        "stopped": "red",
        "error": "bright_red",
    }
    return colors.get(status.lower(), "white")


def _format_uptime(seconds: float) -> str:
    """Format uptime in human readable format."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def _format_bytes(bytes_count: int) -> str:
    """Format bytes in human readable format."""
    if bytes_count < 1024:
        return f"{bytes_count} B"
    elif bytes_count < 1024 * 1024:
        return f"{bytes_count / 1024:.1f} KB"
    elif bytes_count < 1024 * 1024 * 1024:
        return f"{bytes_count / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_count / (1024 * 1024 * 1024):.1f} GB"


def _format_timestamp(timestamp_str: str) -> str:
    """Format timestamp for display."""
    from datetime import datetime

    try:
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return timestamp_str
