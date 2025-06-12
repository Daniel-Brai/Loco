"""
Create a new tunnel with the specified configuration.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid

from rich.console import Console
from rich.text import Text

from ... import get_ascii_banner
from ...core.constants import DEFAULT_TUNNEL_NAME, DEFAULT_TUNNEL_PORT
from ...core.models import TunnelConfig, TunnelProtocol, TunnelStatus
from ...network.manager import TunnelManager

console = Console()


async def create_tunnel_async(
    port: int,
    name: str | None = None,
    protocol: str = "http",
    subdomain: str | None = None,
    remote_port: int | None = None,
    host: str = "127.0.0.1",
    start: bool = True,
    logs: bool = True,
) -> None:
    """Create and manage a tunnel."""
    manager = TunnelManager()
    tunnel_id = None

    try:
        try:
            tunnel_protocol = TunnelProtocol(protocol.lower())
        except ValueError:
            console.print(
                f"[red]Error: Invalid protocol '{protocol}'. Valid options: http, https, tcp, websocket"
            )
            return

        await manager.load_from_storage()
        existing_tunnels = await manager.list_tunnels()

        is_first_tunnel = len(existing_tunnels) == 0

        if is_first_tunnel:
            console.print()
            banner_lines = get_ascii_banner().split("\n")
            for i, line in enumerate(banner_lines):
                if i < 6:
                    console.print(Text(line, style="bold cyan"))
                elif "Lightning-fast" in line:
                    console.print(Text(line, style="bold white"))
                elif "that's anything but crazy" in line:
                    console.print(Text(line, style="italic white"))
                elif "VERSION" in line:
                    console.print(Text(line, style="bold green"))
                else:
                    console.print(line)
            console.print()
            console.print(
                "[bold green]Welcome to loco![/bold green] Let's create your first tunnel."
            )
            console.print()

        tunnel_id = str(uuid.uuid4())

        if remote_port is None:
            remote_port = DEFAULT_TUNNEL_PORT + len(existing_tunnels)

        if host == "localhost":
            host = "127.0.0.1"

        config = TunnelConfig(
            tunnel_id=tunnel_id,
            name=name or DEFAULT_TUNNEL_NAME.format(port=remote_port),
            local_host=host,
            local_port=port,
            remote_host="127.0.0.1",
            remote_port=remote_port,
            protocol=tunnel_protocol,
            subdomain=subdomain,
            ssl_cert_path=None,
            ssl_key_path=None,
        )

        with console.status("[bold green]Creating tunnel...") as status:
            tunnel_id = await manager.create_tunnel(config)

            if start:
                status.update("[bold green]Starting tunnel...")
                await manager.start_tunnel(tunnel_id)

                tunnel_status = await manager.get_tunnel_status(tunnel_id)
                if tunnel_status != TunnelStatus.ACTIVE:
                    console.print(
                        f"[yellow]Warning: Tunnel created but status is {tunnel_status.value}[/yellow]"
                    )

        public_url = f"{config.protocol.value}://localhost:{config.remote_port}"

        console.print("\n[bold green]✓ Tunnel created successfully!")
        console.print(f"\n[bold]Tunnel ID:[/bold] [cyan]{tunnel_id[:8]}...")
        console.print(f"[bold]Tunnel Name:[/bold] [cyan]{config.name}")
        console.print(f"[bold]Public URL:[/bold] [cyan]{public_url}")
        console.print(f"[bold]Local Service:[/bold] [cyan]{host}:{port}")

        console.print()
        console.print(
            f"[dim]Your local service at {config.local_host}:{config.local_port} is now accessible via the public URL above.[/dim]"
        )
        console.print()
        console.print("[bold yellow]Testing Instructions:[/bold yellow]")
        console.print(
            f"1. Make sure your service is running on [cyan]{config.local_host}:{config.local_port}[/cyan]"
        )
        console.print(
            f"2. Test with: [cyan]curl http://localhost:{config.remote_port}[/cyan]"
        )
        console.print(
            f"3. Or open [cyan]http://localhost:{config.remote_port}[/cyan] in your browser"
        )
        console.print()
        console.print(
            f"[yellow bold]IMPORTANT:[/yellow bold] [yellow]Make sure you have a service running on {config.local_host}:{config.local_port} or connections will be refused![/yellow]"
        )
        console.print()

        if start and logs:
            console.print("\n[dim]Press Ctrl+C to stop the tunnel[/dim]")
            console.print("[dim]" + "=" * 86 + "[/dim]")

            try:
                from .logs import stream_logs_async

                await stream_logs_async(tunnel_id, follow=True, header=False)
            except KeyboardInterrupt:
                console.print("\n[bold yellow]Stopping tunnel...")
                await manager.stop_tunnel(tunnel_id)
                console.print("[bold green]Tunnel stopped")
        elif start:
            console.print("\n[dim]Press Ctrl+C to stop the tunnel[/dim]")
            try:
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                pass
            except KeyboardInterrupt:
                console.print("\n[bold yellow]Stopping tunnel...")
                await manager.stop_tunnel(tunnel_id)
                console.print("[bold green]Tunnel stopped")

    except Exception as e:
        console.print(f"\n[red]Error creating tunnel - {e}")
        if tunnel_id:
            with contextlib.suppress(Exception):
                await manager.stop_tunnel(tunnel_id)
