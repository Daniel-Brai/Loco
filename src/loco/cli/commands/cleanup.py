from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm

from ...network.manager import TunnelManager

console = Console()


async def cleanup_tunnels_async(force: bool = False) -> None:
    """Clean up stopped tunnels."""
    try:
        manager = TunnelManager()
        await manager.load_from_storage()

        tunnels = await manager.list_tunnels()
        stopped_tunnels = [t for t in tunnels if t.status.value in ["stopped", "error"]]

        if not stopped_tunnels:
            console.print("[green]No stopped tunnels to clean up\n")
            return

        console.print(f"[yellow]Found {len(stopped_tunnels)} stopped tunnel(s):\n")

        for tunnel in stopped_tunnels:
            name_info = f" ({tunnel.config.name})" if tunnel.config.name else ""
            status_color = "red" if tunnel.status.value == "error" else "yellow"
            console.print(
                f"  • {tunnel.config.tunnel_id[:8]}...{name_info} "
                f"[{status_color}]({tunnel.status.value})[/{status_color}]"
            )

        if not force and not Confirm.ask(
            "\n[bold]Remove these tunnels?[/bold]", default=False
        ):
            console.print("[yellow]Cleanup cancelled")
            return

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("\nCleaning up tunnels...", total=None)

            cleaned_count = await manager.cleanup_stopped_tunnels()

            progress.update(task, description="Cleanup complete\n")

            if cleaned_count > 0:
                console.print(f"[green]✓[/green] Cleaned up {cleaned_count} tunnel(s)")
            else:
                console.print("[yellow]No tunnels were cleaned up")

    except Exception as e:
        console.print(f"[red]Error during cleanup: {e}")


async def cleanup_all_async(force: bool = False) -> None:
    """Clean up all tunnels (including active ones)."""
    try:
        manager = TunnelManager()
        await manager.load_from_storage()

        tunnels = await manager.list_tunnels()

        if not tunnels:
            console.print("[green]No tunnels to clean up")
            return

        console.print(f"[red]This will remove ALL {len(tunnels)} tunnel(s):")

        for tunnel in tunnels:
            name_info = f" ({tunnel.config.name})" if tunnel.config.name else ""
            status_color = {
                "active": "green",
                "starting": "yellow",
                "stopping": "yellow",
                "stopped": "red",
                "error": "bright_red",
            }.get(tunnel.status.value, "white")

            console.print(
                f"  • {tunnel.config.tunnel_id[:8]}...{name_info} "
                f"[{status_color}]({tunnel.status.value})[/{status_color}]"
            )

        if not force:
            console.print(
                "\n[bold red]⚠ WARNING: This will stop and remove all tunnels![/bold red]"
            )
            if not Confirm.ask("[bold]Are you sure?[/bold]", default=False):
                console.print("[yellow]Cleanup cancelled")
                return

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            active_count = len(
                [t for t in tunnels if t.status.value in ["active", "starting"]]
            )
            if active_count > 0:
                task = progress.add_task(
                    f"Stopping {active_count} active tunnel(s)...", total=None
                )
                await manager.stop_all_tunnels()
                progress.update(task, description="Active tunnels stopped")

            task = progress.add_task("Removing all tunnels...", total=None)

            for tunnel in tunnels:
                await manager.remove_tunnel(tunnel.config.tunnel_id)

            progress.update(task, description="All tunnels removed")

            console.print(f"[green]✓[/green] Removed all {len(tunnels)} tunnel(s)")

    except Exception as e:
        console.print(f"[red]Error during cleanup: {e}")
