"""Network proxy for tunneling."""

from __future__ import annotations

import asyncio
import contextlib
import socket
from typing import TYPE_CHECKING, Any

from ..core.exceptions import TunnelError
from ..utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..core.models import TunnelConfig


logger = get_logger("loco.network.proxy")


class TunnelProxy:
    """
    Tunnel proxy for handling raw TCP connections.\n
    This class manages the proxying of raw TCP connections between
    remote and local hosts.
    Attributes:\n
        config (TunnelConfig): Configuration for the tunnel.
        on_data_transfer (Callable[[int], Any] | None): Optional callback for data transfer events.
    """

    def __init__(
        self,
        config: TunnelConfig,
        on_data_transfer: Callable[[int], Any] | None = None,
    ) -> None:
        """Initialize tunnel proxy."""
        self.config = config
        self.on_data_transfer = on_data_transfer
        self._running = False
        self._connections: set[asyncio.Task[Any]] = set()
        self._server_socket: socket.socket | None = None

    async def start(self) -> None:
        """Start the TCP proxy."""
        self._running = True
        logger.info(f"Starting TCP proxy for tunnel {self.config.tunnel_id}")

        try:
            self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_socket.bind((self.config.remote_host, self.config.remote_port))
            self._server_socket.listen(int(self.config.max_connections))
            self._server_socket.setblocking(False)

            logger.info(
                f"TCP proxy listening on {self.config.remote_host}:{self.config.remote_port}"
            )

            while self._running:
                try:
                    (
                        client_socket,
                        client_addr,
                    ) = await asyncio.get_event_loop().sock_accept(self._server_socket)

                    task = asyncio.create_task(
                        self._handle_tcp_connection(client_socket, client_addr)
                    )
                    self._connections.add(task)
                    task.add_done_callback(self._connections.discard)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    if self._running:
                        logger.error(f"Error accepting TCP connection: {e}")
                        await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Failed to start TCP proxy: {e}")
            raise TunnelError(f"TCP proxy startup failed: {e}") from e

    async def stop(self) -> None:
        """Stop the proxy."""
        self._running = False

        for task in list(self._connections):
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

        self._connections.clear()

        if self._server_socket:
            self._server_socket.close()
            self._server_socket = None

        logger.info(f"TCP proxy stopped for tunnel {self.config.tunnel_id}")

    async def _handle_tcp_connection(
        self, client_socket: socket.socket, client_addr: tuple[Any, Any]
    ) -> None:
        """Handle individual TCP connection."""
        logger.debug(f"New TCP connection from {client_addr!s}")

        local_socket = None
        try:
            local_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            await asyncio.get_event_loop().sock_connect(
                local_socket, (self.config.local_host, self.config.local_port)
            )

            client_to_local = asyncio.create_task(
                self._forward_data(client_socket, local_socket, "client->local")
            )
            local_to_client = asyncio.create_task(
                self._forward_data(local_socket, client_socket, "local->client")
            )

            _, pending = await asyncio.wait(
                [client_to_local, local_to_client],
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

        except Exception as e:
            logger.error(f"Error handling TCP connection from {client_addr}: {e}")
        finally:
            with contextlib.suppress(Exception):
                client_socket.close()
            with contextlib.suppress(Exception):
                if local_socket is not None:
                    local_socket.close()
            logger.debug(f"TCP connection from {client_addr} closed")

    async def _forward_data(
        self, src_socket: socket.socket, dst_socket: socket.socket, direction: str
    ) -> None:
        """Forward data between sockets."""
        try:
            while self._running:
                data = await asyncio.get_event_loop().sock_recv(
                    src_socket, self.config.buffer_size
                )

                if not data:
                    break

                await asyncio.get_event_loop().sock_sendall(dst_socket, data)

                if self.on_data_transfer:
                    await self.on_data_transfer(len(data))

                logger.debug(f"Forwarded {len(data)} bytes ({direction})")

        except Exception as e:
            logger.debug(f"Data forwarding stopped ({direction}): {e}")

    def get_connection_count(self) -> int:
        """Get current number of active connections."""
        return len([task for task in self._connections if not task.done()])

    def is_running(self) -> bool:
        """Check if proxy is running."""
        return self._running
