"""Tunnel implementation for managing individual tunnel instances."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from ..core.exceptions import TunnelError, TunnelStartupError
from ..core.models import TunnelConfig, TunnelProtocol, TunnelState, TunnelStatus
from ..utils.logging import get_logger
from .proxy import TunnelProxy
from .server import TunnelServer

logger = get_logger("loco.network.tunnel")

if TYPE_CHECKING:
    from collections.abc import Callable


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
        self.state = TunnelState(
            config=config,
            started_at=None,
            stopped_at=None,
            last_activity=None,
            public_url=None,
            error_message=None,
        )
        self._server: TunnelServer | None = None
        self._proxy: TunnelProxy | None = None
        self._server_task: asyncio.Task[Any] | None = None
        self._proxy_task: asyncio.Task[Any] | None = None

    async def start(self) -> None:
        """Start the tunnel."""
        if self.is_active():
            return

        try:
            logger.info(f"Starting tunnel {self.config.tunnel_id}")
            self.state.status = TunnelStatus.STARTING
            self.state.started_at = datetime.now(UTC)
            self.state.stopped_at = None

            if self.config.protocol in [
                TunnelProtocol.HTTP,
                TunnelProtocol.HTTPS,
                TunnelProtocol.WEBSOCKET,
            ]:
                self._server = TunnelServer(
                    config=self.config,
                    on_connection=self._on_connection,
                    on_disconnection=self._on_disconnection,
                    on_log_request=self._log_request,
                )
                await self._server.start()
                self._server_task = asyncio.create_task(self._server.serve_forever())
            else:
                self._proxy = TunnelProxy(
                    config=self.config,
                    on_data_transfer=self._on_data_transfer,
                )
                self._proxy_task = asyncio.create_task(self._proxy.start())

            self.state.status = TunnelStatus.ACTIVE
            self.state.last_activity = datetime.now(UTC)

            if not self.state.public_url:
                protocol = self.config.protocol.value
                host = "localhost"
                port = self.config.remote_port
                self.state.public_url = f"{protocol}://{host}:{port}"

            logger.info(f"Tunnel {self.config.tunnel_id} started successfully")

        except Exception as e:
            self.state.status = TunnelStatus.ERROR
            self.state.error_message = str(e)
            logger.error(f"Failed to start tunnel {self.config.tunnel_id}: {e}")
            await self._cleanup()
            raise TunnelStartupError(f"Failed to start tunnel: {e}") from e

    async def stop(self) -> None:
        """Stop the tunnel."""
        if not self.is_active():
            logger.warning(f"Tunnel {self.config.tunnel_id} is not active")
            return

        try:
            logger.info(f"Stopping tunnel {self.config.tunnel_id}")
            self.state.status = TunnelStatus.STOPPING

            await self._cleanup()

            self.state.status = TunnelStatus.STOPPED
            self.state.stopped_at = datetime.now(UTC)
            self.state.last_activity = datetime.now(UTC)
            logger.info(f"Tunnel {self.config.tunnel_id} stopped")

        except Exception as e:
            self.state.status = TunnelStatus.ERROR
            self.state.error_message = str(e)
            logger.error(f"Error stopping tunnel {self.config.tunnel_id}: {e}")
            raise TunnelError(f"Failed to stop tunnel: {e}") from e

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
            "protocol": self.config.protocol.value,
            "status": self.state.status.value,
            "uptime_seconds": uptime_seconds,
            "created_at": (
                self.state.created_at.isoformat() if self.state.created_at else None
            ),
            "started_at": (
                self.state.started_at.isoformat() if self.state.started_at else None
            ),
            "stopped_at": (
                self.state.stopped_at.isoformat() if self.state.stopped_at else None
            ),
            "public_url": self.state.public_url,
            "local_service": f"{self.config.local_host}:{self.config.local_port}",
            "active_connections": self.state.active_connections,
            "total_connections": self.state.total_connections,
            "bytes_transferred": self.state.bytes_transferred,
            "last_activity": (
                self.state.last_activity.isoformat()
                if self.state.last_activity
                else None
            ),
            "error_message": self.state.error_message,
        }

    async def _cleanup(self) -> None:
        """Clean up resources."""
        if self._server_task:
            self._server_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._server_task
            self._server_task = None

        if self._proxy_task:
            self._proxy_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._proxy_task
            self._proxy_task = None

        if self._server:
            await self._server.stop()
            self._server = None

        if self._proxy:
            await self._proxy.stop()
            self._proxy = None

    async def _on_connection(self, _connection_info: dict[str, Any]) -> None:
        """Handle new connection."""
        self.state.active_connections += 1
        self.state.total_connections += 1
        self.state.last_activity = datetime.now(UTC)

    async def _on_disconnection(self, _connection_info: dict[str, Any]) -> None:
        """Handle connection disconnection."""
        if self.state.active_connections > 0:
            self.state.active_connections -= 1
        self.state.last_activity = datetime.now(UTC)

    async def _on_data_transfer(self, bytes_count: int) -> None:
        """Handle data transfer."""
        self.state.bytes_transferred += bytes_count
        self.state.last_activity = datetime.now(UTC)

    def register_log_handler(self, handler: Callable[[dict[str, Any]], None]) -> None:
        """Register a log handler function."""
        self._log_handlers = getattr(self, "_log_handlers", [])
        self._log_handlers.append(handler)

    def unregister_log_handler(self, handler: Callable[[dict[str, Any]], None]) -> None:
        """Unregister a log handler function."""
        self._log_handlers = getattr(self, "_log_handlers", [])
        if handler in self._log_handlers:
            self._log_handlers.remove(handler)

    async def _log_request(self, request_info: dict[str, Any]) -> None:
        """Log a request."""
        if hasattr(self, "_log_handlers"):
            for handler in self._log_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(request_info)
                    else:
                        handler(request_info)
                except Exception as e:
                    logger.error(f"Error in log handler: {e}")

    def __str__(self) -> str:
        return f"Tunnel({self.config.tunnel_id[:8]}...)"

    def __repr__(self) -> str:
        return f"Tunnel(id={self.config.tunnel_id}, status={self.state.status})"
