"""Tunnel implementation for managing individual tunnel instances."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime
from typing import Any

from ..core.exceptions import TunnelError, TunnelStartupError
from ..core.models import TunnelConfig, TunnelState, TunnelStatus
from ..utils.logging import get_logger
from .proxy import TunnelProxy
from .server import TunnelServer

logger = get_logger("loco.network.tunnel")


class Tunnel:
    """
    A Tunnel instance.\n
    This class manages the lifecycle of a tunnel, including starting,
    stopping, and monitoring its state.
    It handles the underlying server and proxy components,
    and provides methods to interact with the tunnel.
    Attributes:\n
        config (TunnelConfig): Tunnel configuration settings.
        state (TunnelState): Current state of the tunnel.
    """

    def __init__(self, config: TunnelConfig) -> None:
        """Initialize tunnel with configuration."""
        self.config = config
        self.state = TunnelState(config=config)
        self._server: TunnelServer | None = None
        self._proxy: TunnelProxy | None = None
        self._server_task: asyncio.Task[Any] | None = None
        self._proxy_task: asyncio.Task[Any] | None = None

    async def start(self) -> None:
        """Start the tunnel."""
        if self.is_active():
            raise TunnelError(f"Tunnel {self.config.tunnel_id} is already active")

        try:
            self.state.status = TunnelStatus.STARTING
            self.state.started_at = datetime.now(UTC)

            logger.info(f"Starting tunnel {self.config.tunnel_id}")

            self._server = TunnelServer(
                config=self.config,
                on_connection=self._on_connection,
                on_disconnection=self._on_disconnection,
            )

            await self._server.start()

            self._proxy = TunnelProxy(
                config=self.config,
                server=self._server,
                on_data_transfer=self._on_data_transfer,
            )

            self._server_task = asyncio.create_task(self._server.serve_forever())
            self._proxy_task = asyncio.create_task(self._proxy.start())

            protocol = "https" if self.config.protocol.value == "https" else "http"
            self.state.public_url = (
                f"{protocol}://{self.config.remote_host}:{self.config.remote_port}"
            )

            self.state.status = TunnelStatus.ACTIVE
            self.state.last_activity = datetime.now(UTC)

            logger.info(
                f"Tunnel {self.config.tunnel_id} started successfully at {self.state.public_url}"
            )

        except Exception as e:
            self.state.status = TunnelStatus.ERROR
            self.state.error_message = str(e)
            await self._cleanup()
            raise TunnelStartupError(
                f"Failed to start tunnel {self.config.tunnel_id}: {e}"
            ) from e

    async def stop(self) -> None:
        """Stop the tunnel."""
        if not self.is_active():
            logger.warning(f"Tunnel {self.config.tunnel_id} is not active")
            return

        try:
            self.state.status = TunnelStatus.STOPPING
            logger.info(f"Stopping tunnel {self.config.tunnel_id}")

            await self._cleanup()

            self.state.status = TunnelStatus.STOPPED
            self.state.stopped_at = datetime.now(UTC)

            logger.info(f"Tunnel {self.config.tunnel_id} stopped successfully")

        except Exception as e:
            self.state.status = TunnelStatus.ERROR
            self.state.error_message = str(e)
            logger.error(f"Error stopping tunnel {self.config.tunnel_id}: {e}")
            raise TunnelError(
                f"Failed to stop tunnel {self.config.tunnel_id}: {e}"
            ) from e

    def is_active(self) -> bool:
        """Check if tunnel is active."""
        return self.state.status in (TunnelStatus.STARTING, TunnelStatus.ACTIVE)

    def get_stats(self) -> dict[str, Any]:
        """Get tunnel statistics."""
        uptime_seconds = 0.0
        if self.state.started_at and self.state.status == TunnelStatus.ACTIVE:
            uptime_seconds = (datetime.now(UTC) - self.state.started_at).total_seconds()

        return {
            "tunnel_id": self.config.tunnel_id,
            "status": self.state.status.value,
            "uptime_seconds": uptime_seconds,
            "active_connections": self.state.active_connections,
            "total_connections": self.state.total_connections,
            "bytes_transferred": self.state.bytes_transferred,
            "public_url": self.state.public_url,
            "local_service": f"{self.config.local_host}:{self.config.local_port}",
            "created_at": self.state.created_at.isoformat(),
            "started_at": (
                self.state.started_at.isoformat() if self.state.started_at else None
            ),
            "last_activity": (
                self.state.last_activity.isoformat()
                if self.state.last_activity
                else None
            ),
            "error_message": self.state.error_message,
        }

    async def _cleanup(self) -> None:
        """Clean up tunnel resources."""
        if self._server_task and not self._server_task.done():
            self._server_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._server_task

        if self._proxy_task and not self._proxy_task.done():
            self._proxy_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._proxy_task

        if self._proxy:
            await self._proxy.stop()
            self._proxy = None

        if self._server:
            await self._server.stop()
            self._server = None

        self._server_task = None
        self._proxy_task = None

    async def _on_connection(self, connection_info: dict[str, Any]) -> None:
        """Handle new connection."""
        self.state.active_connections += 1
        self.state.total_connections += 1
        self.state.last_activity = datetime.now(UTC)

        logger.debug(
            f"New connection to tunnel {self.config.tunnel_id}: {connection_info}"
        )

    async def _on_disconnection(self, connection_info: dict[str, Any]) -> None:
        """Handle connection closure."""
        self.state.active_connections = max(0, self.state.active_connections - 1)
        self.state.last_activity = datetime.now(UTC)

        logger.debug(
            f"Connection closed for tunnel {self.config.tunnel_id}: {connection_info}"
        )

    async def _on_data_transfer(self, bytes_count: int) -> None:
        """Handle data transfer tracking."""
        self.state.bytes_transferred += bytes_count
        self.state.last_activity = datetime.now(UTC)

    def __str__(self) -> str:
        """String representation of tunnel."""
        return f"Tunnel({self.config.tunnel_id}, {self.state.status.value})"

    def __repr__(self) -> str:
        """Detailed string representation of tunnel."""
        return (
            f"Tunnel(id={self.config.tunnel_id}, "
            f"status={self.state.status.value}, "
            f"local={self.config.local_host}:{self.config.local_port}, "
            f"remote={self.config.remote_host}:{self.config.remote_port})"
        )
