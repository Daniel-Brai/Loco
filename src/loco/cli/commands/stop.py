from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ...core.exceptions import TunnelNotFoundError
from ...network.manager import TunnelManager

console = Console()


async def stop_tunnel_async(tunnel_id: str) -> None:
    """Stop a tunnel."""
    try:
        manager = TunnelManager()
        await manager.load_from_storage()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
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
            full_tunnel_id = tunnel.config.tunnel_id

            if tunnel.status.value in ["stopped", "error"]:
                console.print(
                    f"[yellow]Tunnel {full_tunnel_id[:8]}... is already stopped"
                )
                return

            task = progress.add_task("Stopping tunnel...", total=None)

            try:
                await manager.stop_tunnel(full_tunnel_id)
                progress.update(task, description="Tunnel stopped")

                name_info = f" ({tunnel.config.name})" if tunnel.config.name else ""
                console.print(
                    f"[green]✓[/green] Tunnel stopped: {full_tunnel_id[:8]}...{name_info}"
                )

            except TunnelNotFoundError:
                console.print(f"[red]Error: Tunnel {tunnel_id} not found")
            except Exception as e:
                console.print(f"[red]Error stopping tunnel: {e}")

    except Exception as e:
        console.print(f"[red]Error: {e}")


async def stop_all_tunnels_async() -> None:
    """Stop all active tunnels."""
    try:
        manager = TunnelManager()
        await manager.load_from_storage()

        tunnels = await manager.list_tunnels()
        active_tunnels = [
            t for t in tunnels if t.status.value in ["active", "starting"]
        ]

        if not active_tunnels:
            console.print("[yellow]No active tunnels to stop")
            return

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"Stopping {len(active_tunnels)} tunnel(s)...", total=None
            )

            await manager.stop_all_tunnels()

            progress.update(task, description="All tunnels stopped")
            console.print(f"[green]✓[/green] Stopped {len(active_tunnels)} tunnel(s)")

    except Exception as e:
        console.print(f"[red]Error stopping tunnels: {e}")
