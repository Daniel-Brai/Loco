"""
Network server for handling HTTP/WebSocket tunnels.
"""

from __future__ import annotations

import asyncio
import contextlib
import socket
import ssl
from datetime import datetime
from typing import TYPE_CHECKING, Any

from aiohttp import ClientSession, ClientTimeout, TCPConnector, WSMsgType, web
from aiohttp.web_ws import WebSocketResponse

from ..core.exceptions import TunnelError
from ..core.models import TunnelConfig, TunnelProtocol
from ..utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from aiohttp.web_request import Request
    from aiohttp.web_response import Response, StreamResponse


logger = get_logger("loco.network.server")


class TunnelServer:
    """
    Async HTTP/WebSocket tunnel server.\n
    This server listens for incoming connections and proxies them
    to a specified local service.
    Attributes:
        config (TunnelConfig): Configuration for the tunnel server.
        on_connection (Optional[Callable[[Dict[str, Any]], Any]]): Callback for new connections.
        on_disconnection (Optional[Callable[[Dict[str, Any]], Any]]): Callback for disconnections.
    """

    def __init__(
        self,
        config: TunnelConfig,
        on_connection: Callable[[dict[str, Any]], Any] | None = None,
        on_disconnection: Callable[[dict[str, Any]], Any] | None = None,
        on_log_request: Callable[[dict[str, Any]], Any] | None = None,
    ) -> None:
        """Initialize tunnel server."""
        self.config = config
        self.on_connection = on_connection
        self.on_disconnection = on_disconnection
        self.on_log_request = on_log_request
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._client_session: ClientSession | None = None

        self._app = web.Application()
        self._setup_routes()

    async def start(self) -> None:
        """Start the server."""
        try:
            logger.info(
                f"Starting tunnel server on {self.config.remote_host}:{self.config.remote_port}"
            )
            logger.info(
                f"Forwarding to local service: {self.config.local_host}:{self.config.local_port}"
            )

            if await self._is_port_in_use(
                self.config.remote_host, self.config.remote_port
            ):
                raise TunnelError(f"Port {self.config.remote_port} is already in use")

            timeout = ClientTimeout(
                total=self.config.connection_timeout,
                connect=10,
                sock_read=30,
                sock_connect=10,
            )

            self._client_session = ClientSession(
                timeout=timeout,
                connector=TCPConnector(
                    limit=100,
                    limit_per_host=30,
                    enable_cleanup_closed=True,
                    keepalive_timeout=30,
                ),
            )

            self._runner = web.AppRunner(self._app, access_log=None)
            await self._runner.setup()

            ssl_context = None
            if self.config.protocol == TunnelProtocol.HTTPS:
                ssl_context = await self._setup_ssl()

            bind_host = self.config.remote_host
            if bind_host == "0.0.0.0":
                bind_host = "0.0.0.0"

            logger.info(f"Binding server to {bind_host}:{self.config.remote_port}")

            for attempt in range(3):
                try:
                    self._site = web.TCPSite(
                        self._runner,
                        host=bind_host,
                        port=self.config.remote_port,
                        ssl_context=ssl_context,
                        reuse_address=True,
                        reuse_port=False,
                    )

                    await self._site.start()
                    logger.info(f"Site started successfully on attempt {attempt + 1}")
                    break
                except Exception as e:
                    logger.warning(
                        f"Failed to start site on attempt {attempt + 1}: {e}"
                    )
                    if attempt == 2:
                        raise
                    await asyncio.sleep(1)

            await asyncio.sleep(1)

            if not await self._verify_server_running():
                raise TunnelError("Server failed to start - port may not be accessible")

            try:
                local_check = await self._test_local_service_connectivity()
                if not local_check:
                    logger.warning(
                        f"Local service at {self.config.local_host}:{self.config.local_port} may not be accessible"
                    )
            except Exception as e:
                logger.warning(f"Local service check failed: {e}")

            logger.info("Tunnel server started successfully!")
            logger.info(
                f"Public URL: {self.config.protocol.value}://localhost:{self.config.remote_port}"
            )
            logger.info(
                f"Local Service: {self.config.local_host}:{self.config.local_port}"
            )

        except Exception as e:
            logger.error(f"Server startup failed: {e}")
            await self.stop()
            raise TunnelError(f"Server startup failed: {e}") from e

    async def stop(self) -> None:
        """Stop the server."""
        try:
            logger.info("Stopping tunnel server...")

            if self._client_session:
                await self._client_session.close()
                self._client_session = None

            if self._site:
                await self._site.stop()
                self._site = None

            if self._runner:
                await self._runner.cleanup()
                self._runner = None

            logger.info("Tunnel server stopped")
        except Exception as e:
            logger.error(f"Error stopping server: {e}")
            raise

    def is_serving(self) -> bool:
        """Check if the server is running."""
        return self._runner is not None and self._site is not None

    async def serve_forever(self) -> None:
        """Keep the server running."""
        while self.is_serving():
            await asyncio.sleep(1)

    async def _is_port_in_use(self, host: str, port: int) -> bool:
        """Check if a port is already in use."""
        try:
            test_hosts = []
            if host == "0.0.0.0":
                test_hosts = ["127.0.0.1", "localhost"]
            else:
                test_hosts = [host if host != "0.0.0.0" else "127.0.0.1"]

            for test_host in test_hosts:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1)
                    result = sock.connect_ex((test_host, port))
                    sock.close()
                    if result == 0:
                        logger.warning(f"Port {port} is already in use on {test_host}")
                        return True
                except Exception:
                    continue
            return False
        except Exception:
            return False

    async def _verify_server_running(self) -> bool:
        """Verify the server is actually running."""
        test_hosts = ["127.0.0.1", "localhost"]

        for host_to_check in test_hosts:
            for attempt in range(5):
                try:
                    logger.debug(
                        f"Verifying server connection to {host_to_check}:{self.config.remote_port} (attempt {attempt + 1}/5)"
                    )

                    try:
                        reader, writer = await asyncio.wait_for(
                            asyncio.open_connection(
                                host_to_check, self.config.remote_port
                            ),
                            timeout=3.0,
                        )

                        request = f"GET / HTTP/1.1\r\nHost: {host_to_check}:{self.config.remote_port}\r\nConnection: close\r\n\r\n"
                        writer.write(request.encode())
                        await writer.drain()

                        try:
                            response = await asyncio.wait_for(
                                reader.read(1024), timeout=2.0
                            )
                            logger.debug(
                                f"Received response: {response.decode()[:100]}..."
                            )
                        except TimeoutError:
                            logger.debug("Response read timeout (this might be normal)")

                        writer.close()
                        await writer.wait_closed()

                        logger.info(
                            f"Successfully verified server running at {host_to_check}:{self.config.remote_port}"
                        )
                        return True

                    except Exception as e:
                        logger.debug(f"HTTP verification failed: {e}")

                        reader, writer = await asyncio.wait_for(
                            asyncio.open_connection(
                                host_to_check, self.config.remote_port
                            ),
                            timeout=2.0,
                        )
                        writer.close()
                        await writer.wait_closed()
                        logger.info(
                            f"Successfully verified server running at {host_to_check}:{self.config.remote_port} (socket test)"
                        )
                        return True

                except Exception as e:
                    logger.debug(
                        f"Attempt {attempt + 1}/5: Failed to verify server running at {host_to_check}:{self.config.remote_port}. Error: {e}"
                    )
                    await asyncio.sleep(0.5)

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex(("127.0.0.1", self.config.remote_port))
            sock.close()
            if result == 0:
                logger.info(
                    f"Socket check: Server is running at 127.0.0.1:{self.config.remote_port}"
                )
                return True
            else:
                logger.error(
                    f"Socket check: Server is not running. Connection result: {result}"
                )
        except Exception as e:
            logger.error(f"Socket check failed: {e}")

        logger.error("Server verification failed. The tunnel may not be accessible.")
        return False

    async def _setup_ssl(self) -> ssl.SSLContext:
        """Setup SSL context if certificates are provided."""
        if not self.config.ssl_cert_path or not self.config.ssl_key_path:
            raise TunnelError("SSL certificate and key paths are required for HTTPS")

        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(self.config.ssl_cert_path, self.config.ssl_key_path)
        return ssl_context

    def _setup_routes(self) -> None:
        """Set up HTTP routes"""
        self._app.router.add_route("*", "/{path:.*}", self._handle_request)

    async def _handle_request(self, request: Request) -> Response | StreamResponse:
        """Handle HTTP request and proxy it to the local service"""

        if self._client_session is None:
            return web.Response(
                status=503,
                text="Tunnel server not properly initialized",
                content_type="text/plain",
            )

        if self.on_connection:
            await self.on_connection(
                {
                    "remote_addr": request.remote,
                    "method": request.method,
                    "path": request.path,
                    "headers": dict(request.headers),
                }
            )

        if request.method == "GET" and request.path == "/_tunnel/health":
            return await self._handle_health_check()
        elif request.method == "GET" and request.path == "/_tunnel/stats":
            return await self._handle_stats()

        start_time = asyncio.get_event_loop().time()
        response = None

        try:
            if request.headers.get("Upgrade", "").lower() == "websocket":
                return await self._handle_websocket_proxy(request)

            target_url = self._build_target_url(request)
            headers = self._prepare_proxy_headers(request)

            body_data = None
            if request.can_read_body:
                body_data = await request.read()

            logger.debug(f"Proxying {request.method} {request.path} to {target_url}")

            async with self._client_session.request(
                method=request.method,
                url=target_url,
                headers=headers,
                data=body_data,
                allow_redirects=False,
                raise_for_status=False,
            ) as local_response:
                response_headers = dict(local_response.headers)

                for header in [
                    "connection",
                    "keep-alive",
                    "proxy-authenticate",
                    "proxy-authorization",
                    "te",
                    "trailers",
                    "transfer-encoding",
                    "upgrade",
                ]:
                    response_headers.pop(header, None)

                response = web.StreamResponse(
                    status=local_response.status,
                    reason=local_response.reason,
                    headers=response_headers,
                )

                await response.prepare(request)

                async for chunk in local_response.content.iter_chunked(8192):
                    await response.write(chunk)

                await response.write_eof()

                if self.on_disconnection:
                    await self.on_disconnection({"remote_addr": request.remote})

                end_time = asyncio.get_event_loop().time()
                duration_ms = (end_time - start_time) * 1000

                log_entry: dict[str, Any] = {
                    "timestamp": datetime.now().isoformat(),
                    "method": request.method,
                    "path": request.path,
                    "status": response.status,
                    "ip": request.remote,
                    "duration": duration_ms,
                    "headers": dict(request.headers),
                    "query_string": request.query_string,
                }

                if hasattr(self, "on_log_request") and callable(self.on_log_request):
                    await self.on_log_request(log_entry)

                return response

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(
                f"Error proxying request to {self.config.local_host}:{self.config.local_port}: {e}"
            )

            error_msg = f"Failed to connect to local service at {self.config.local_host}:{self.config.local_port}"
            if "Connection refused" in str(e) or "ConnectionRefusedError" in str(e):
                error_msg += f"\n\nMake sure your local service is running and accessible at {self.config.local_host}:{self.config.local_port}."

            return web.Response(
                status=502,
                text=error_msg,
                content_type="text/plain",
            )

    def _build_target_url(self, request: Request) -> str:
        """Build the target URL for the local service."""
        # Use http for local connections even if tunnel uses https for now
        # TODO(daniel): Support https for local connections later
        scheme = "http"
        target_url = f"{scheme}://{self.config.local_host}:{self.config.local_port}{request.path}"

        if request.query_string:
            target_url += f"?{request.query_string}"

        return target_url

    def _prepare_proxy_headers(self, request: Request) -> dict[str, str]:
        """Prepare headers for proxying to local service."""
        headers = dict(request.headers)

        headers["Host"] = f"{self.config.local_host}:{self.config.local_port}"

        headers["X-Forwarded-For"] = request.remote or "unknown"
        headers["X-Forwarded-Proto"] = self.config.protocol.value
        headers["X-Forwarded-Host"] = (
            request.host or f"localhost:{self.config.remote_port}"
        )
        headers["X-Forwarded-Port"] = str(self.config.remote_port)

        for header in [
            "connection",
            "keep-alive",
            "proxy-authenticate",
            "proxy-authorization",
            "te",
            "trailers",
            "upgrade",
        ]:
            headers.pop(header, None)

        return headers

    async def _handle_websocket_proxy(self, request: Request) -> WebSocketResponse:
        """Handle WebSocket connections by proxying to local service."""
        if self._client_session is None:
            raise TunnelError("Client session not initialized")

        ws_server = WebSocketResponse()
        await ws_server.prepare(request)

        if self.on_connection:
            await self.on_connection(
                {"remote_addr": request.remote, "type": "websocket"}
            )

        try:
            # Use ws for local connections even if tunnel uses ws for now
            # TODO(Daniel): Support wss for local connections later
            ws_scheme = "ws"  # Use ws even if tunnel is wss
            local_ws_url = f"{ws_scheme}://{self.config.local_host}:{self.config.local_port}{request.path}"
            if request.query_string:
                local_ws_url += f"?{request.query_string}"

            headers = self._prepare_proxy_headers(request)

            ws_client = await self._client_session.ws_connect(
                local_ws_url,
                headers=headers,
            )

            async def forward_messages(
                source: Any, target: Any, direction: str
            ) -> None:
                """Forward WebSocket messages in one direction."""
                try:
                    async for msg in source:
                        if msg.type == WSMsgType.TEXT:
                            await target.send_str(msg.data)
                        elif msg.type == WSMsgType.BINARY:
                            await target.send_bytes(msg.data)
                        elif msg.type == WSMsgType.CLOSE:
                            await target.close(code=msg.data, message=msg.extra)
                            break
                        elif msg.type == WSMsgType.ERROR:
                            logger.error(f"WebSocket error in {direction}: {msg.data}")
                            break
                except Exception as e:
                    logger.error(
                        f"Error forwarding WebSocket messages ({direction}): {e}"
                    )
                finally:
                    with contextlib.suppress(Exception):
                        await target.close()

            client_to_server = asyncio.create_task(
                forward_messages(ws_server, ws_client, "client->server")
            )
            server_to_client = asyncio.create_task(
                forward_messages(ws_client, ws_server, "server->client")
            )

            _, pending = await asyncio.wait(
                [client_to_server, server_to_client],
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

            with contextlib.suppress(Exception):
                await ws_client.close()

        except Exception as e:
            logger.error(f"Error handling WebSocket proxy: {e}")
            await ws_server.close(code=1011, message=str(e).encode())

        if self.on_disconnection:
            await self.on_disconnection({"remote_addr": request.remote})

        return ws_server

    async def _test_local_service_connectivity(self) -> bool:
        """Test if the local service is accessible."""
        try:
            logger.debug(
                f"Testing connectivity to local service at {self.config.local_host}:{self.config.local_port}"
            )
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(self.config.local_host, self.config.local_port),
                timeout=2.0,
            )
            writer.close()
            await writer.wait_closed()
            logger.info(
                f"Local service at {self.config.local_host}:{self.config.local_port} is accessible"
            )
            return True
        except Exception as e:
            logger.warning(
                f"Local service at {self.config.local_host}:{self.config.local_port} might not be accessible: {e}"
            )
            return False

    async def _handle_health_check(self) -> Response:
        """Handle health check requests."""
        return web.json_response(
            {
                "status": "healthy",
                "tunnel_id": self.config.tunnel_id,
                "local_service": f"{self.config.local_host}:{self.config.local_port}",
            }
        )

    async def _handle_stats(self) -> Response:
        """Handle stats requests."""
        return web.json_response(
            {
                "config": self.config.model_dump(exclude_unset=True),
                "server_info": {
                    "host": self.config.remote_host,
                    "port": self.config.remote_port,
                    "protocol": self.config.protocol.value,
                    "is_serving": self.is_serving(),
                },
            }
        )
