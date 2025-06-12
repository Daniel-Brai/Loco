import asyncio

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ...core.exceptions import TunnelNotFoundError
from ...network.manager import TunnelManager

console = Console()


async def start_tunnel_async(tunnel_id: str) -> None:
    """Start a tunnel."""
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

            if tunnel.status.value in ["active", "starting"]:
                console.print(
                    f"[yellow]Tunnel {full_tunnel_id[:8]}... is already running"
                )
                return

            task = progress.add_task("Starting tunnel...", total=None)

            await manager.start_tunnel(full_tunnel_id)
        progress.update(task, description="Tunnel started")

        try:
            name_info = f" ({tunnel.config.name})" if tunnel.config.name else ""
            console.print(
                f"[green]✓[/green] Tunnel started: {full_tunnel_id[:8]}...{name_info}"
            )

            stats = await manager.get_tunnel_stats(full_tunnel_id)
            console.print()
            console.print("[bold]Tunnel Details:[/bold]")
            console.print(f"  Local: {stats['local_service']}")
            console.print(
                f"  Public URL: [bold green]{stats['public_url']}[/bold green]"
            )
            console.print()
            console.print(
                "[dim]Your local service is now accessible via the public URL above.[/dim]"
            )
            console.print()
            console.print("[dim]Press Ctrl+C to stop the tunnel[/dim]")
            console.print("[dim]" + "=" * 80 + "[/dim]")

            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                console.print("\n[bold yellow]Stopping tunnel...")
                await manager.stop_tunnel(full_tunnel_id)

                tunnel_instance = manager.get_tunnel(full_tunnel_id)
                await manager.storage.save_tunnel_state(tunnel_instance.state)
                console.print("[bold green]Tunnel stopped")

        except TunnelNotFoundError:
            console.print(f"[red]Error: Tunnel {tunnel_id} not found")
        except Exception as e:
            console.print(f"[red]Error starting tunnel: {e}")

    except Exception as e:
        console.print(f"[red]Error: {e}")
