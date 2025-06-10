import uuid

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text

from ... import get_ascii_banner
from ...core.models import TunnelConfig, TunnelProtocol
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
) -> None:
    """Create a tunnel asynchronously."""
    try:
        try:
            tunnel_protocol = TunnelProtocol(protocol.lower())
        except ValueError:
            console.print(
                f"[red]Error: Invalid protocol '{protocol}'. Valid options: http, https, tcp, websocket"
            )
            return

        manager = TunnelManager()
        await manager.load_from_storage()

        existing_tunnels = await manager.list_tunnels()
        is_first_tunnel = len(existing_tunnels) == 0

        # Show welcome banner for first tunnel
        if is_first_tunnel:
            console.print()
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
            console.print()
            console.print(
                "[bold green]Welcome to loco![/bold green] Let's create your first tunnel."
            )
            console.print()

        tunnel_id = str(uuid.uuid4())
        if remote_port is None:
            remote_port = 8080 + len(existing_tunnels)

        config = TunnelConfig(
            tunnel_id=tunnel_id,
            name=name or f"tunnel-{port}",
            local_host=host,
            local_port=port,
            remote_host="0.0.0.0",  # Default to localhost
            remote_port=remote_port,
            protocol=tunnel_protocol,
            subdomain=subdomain,
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Creating tunnel...", total=None)
            await manager.create_tunnel(config)
            progress.update(task, description="Tunnel created")

            if start:
                progress.update(task, description="Starting tunnel...")
                await manager.start_tunnel(tunnel_id)
                progress.update(task, description="Tunnel started")

        status = "started" if start else "created"
        console.print(f"[green]✓[/green] Tunnel {status} successfully!")
        console.print()

        console.print("[bold]Tunnel Details:[/bold]")
        console.print(f"  ID: {tunnel_id[:8]}...")
        console.print(f"  Name: {config.name}")
        console.print(f"  Local: {config.local_host}:{config.local_port}")
        console.print(f"  Remote: {config.remote_host}:{config.remote_port}")
        console.print(f"  Protocol: {config.protocol.value}")

        if start:
            public_url = (
                f"{config.protocol.value}://{config.remote_host}:{config.remote_port}"
            )
            console.print(f"  [bold green]Public URL: {public_url}[/bold green]")
            console.print()
            console.print(
                f"[dim]Your local service at {config.local_host}:{config.local_port} is now accessible via the public URL above.\n[/dim]"
            )
        else:
            console.print()
            console.print(
                f"[dim]Use 'loco status {tunnel_id[:8]}' to check tunnel status or 'loco start {tunnel_id[:8]}' to start it.[/dim]"
            )

    except Exception as e:
        console.print(f"[red]Error creating tunnel: {e}")
