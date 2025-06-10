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
            # Find tunnel (support partial ID matching)
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

            # Check if tunnel is already running
            if tunnel.status.value in ["active", "starting"]:
                console.print(
                    f"[yellow]Tunnel {full_tunnel_id[:8]}... is already running"
                )
                return

            # Start the tunnel
            task = progress.add_task("Starting tunnel...", total=None)

            try:
                await manager.start_tunnel(full_tunnel_id)
                progress.update(task, description="Tunnel started")

                name_info = f" ({tunnel.config.name})" if tunnel.config.name else ""
                console.print(
                    f"[green]✓[/green] Tunnel started: {full_tunnel_id[:8]}...{name_info}"
                )

                # Show tunnel details
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

            except TunnelNotFoundError:
                console.print(f"[red]Error: Tunnel {tunnel_id} not found")
            except Exception as e:
                console.print(f"[red]Error starting tunnel: {e}")

    except Exception as e:
        console.print(f"[red]Error: {e}")


async def start_all_tunnels_async() -> None:
    """Start all stopped tunnels."""
    try:
        manager = TunnelManager()
        await manager.load_from_storage()

        tunnels = await manager.list_tunnels()
        stopped_tunnels = [t for t in tunnels if t.status.value in ["stopped", "error"]]

        if not stopped_tunnels:
            console.print("[yellow]No stopped tunnels to start")
            return

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"Starting {len(stopped_tunnels)} tunnel(s)...", total=None
            )

            started_count = 0
            failed_count = 0

            for tunnel in stopped_tunnels:
                try:
                    await manager.start_tunnel(tunnel.config.tunnel_id)
                    started_count += 1
                except Exception as e:
                    console.print(
                        f"[red]Failed to start {tunnel.config.tunnel_id[:8]}...: {e}"
                    )
                    failed_count += 1

            progress.update(task, description=f"Started {started_count} tunnel(s)")

            if started_count > 0:
                console.print(f"[green]✓[/green] Started {started_count} tunnel(s)")
            if failed_count > 0:
                console.print(f"[red]✗[/red] Failed to start {failed_count} tunnel(s)")

    except Exception as e:
        console.print(f"[red]Error starting tunnels: {e}")
