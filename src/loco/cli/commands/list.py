from rich.console import Console
from rich.table import Table

from ...network.manager import TunnelManager

console = Console()


async def list_tunnels_async() -> None:
    """List all tunnels."""
    try:
        manager = TunnelManager()
        await manager.load_from_storage()

        tunnels = await manager.list_tunnels()

        if not tunnels:
            console.print("[yellow]No tunnels found[/yellow]")
            return

        table = Table(title="Tunnels")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="magenta")
        table.add_column("Status", style="green")
        table.add_column("Local", style="blue")
        table.add_column("Public URL", style="yellow")
        table.add_column("Protocol", style="red")

        for tunnel in tunnels:
            table.add_row(
                tunnel.config.tunnel_id[:8] + "...",
                tunnel.config.name or "—",
                tunnel.status.value,
                f"{tunnel.config.local_host}:{tunnel.config.local_port}",
                tunnel.public_url or "—",
                tunnel.config.protocol.value.upper(),
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error listing tunnels: {e}")
