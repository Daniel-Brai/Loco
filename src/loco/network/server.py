from __future__ import annotations

import asyncio
import ssl
from typing import TYPE_CHECKING, Any

from aiohttp import ClientSession, ClientTimeout, WSMsgType, web
from aiohttp.web_response import StreamResponse
from aiohttp.web_ws import WebSocketResponse

from ..core.exceptions import TunnelError
from ..core.models import TunnelConfig, TunnelProtocol
from ..utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from aiohttp import ClientWebSocketResponse
    from aiohttp.web_request import Request
    from aiohttp.web_response import Response


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
    ) -> None:
        """Initialize tunnel server."""
        self.config = config
        self.on_connection = on_connection
        self.on_disconnection = on_disconnection

        self._app = web.Application()
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._ssl_context: ssl.SSLContext | None = None
        self._client_session: ClientSession | None = None
        self._setup_routes()

    async def start(self) -> None:
        """Start the server."""
        try:
            if self.config.protocol == TunnelProtocol.HTTPS:
                await self._setup_ssl()

            timeout = ClientTimeout(total=self.config.connection_timeout)
            self._client_session = ClientSession(timeout=timeout)

            self._runner = web.AppRunner(self._app)
            await self._runner.setup()

            self._site = web.TCPSite(
                self._runner,
                host=self.config.remote_host,
                port=self.config.remote_port,
                ssl_context=self._ssl_context,
            )

            await self._site.start()

            logger.info(
                f"Tunnel server listening on "
                f"{self.config.remote_host}:{self.config.remote_port}"
            )

        except Exception as e:
            raise TunnelError(f"Failed to start server: {e}") from e

    async def stop(self) -> None:
        """Stop the server."""
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

    def is_serving(self) -> bool:
        """Check if server is currently serving."""
        return self._site is not None

    async def serve_forever(self) -> None:
        """Serve forever (until stopped)."""
        if not self.is_serving():
            raise TunnelError("Server is not started")

        try:
            while self.is_serving():
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Server serve_forever cancelled")
            raise

    def _setup_routes(self) -> None:
        """Setup server routes."""
        for method in ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]:
            self._app.router.add_route(method, "/{path:.*}", self._handle_http_request)

        self._app.router.add_get("/ws/{path:.*}", self._handle_websocket)

        self._app.router.add_get("/_tunnel/health", self._handle_health_check)

        self._app.router.add_get("/_tunnel/stats", self._handle_stats)

    async def _setup_ssl(self) -> None:
        """Setup SSL context."""
        if not self.config.ssl_cert_path or not self.config.ssl_key_path:
            raise TunnelError("SSL certificate and key paths required for HTTPS")

        self._ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self._ssl_context.load_cert_chain(
            self.config.ssl_cert_path, self.config.ssl_key_path
        )

    async def _handle_http_request(self, request: Request) -> Response | StreamResponse:
        """Handle HTTP requests by proxying to local service."""
        connection_info = {
            "type": "http",
            "remote_addr": request.remote,
            "method": request.method,
            "path": request.path_qs,
            "headers": dict(request.headers),
        }

        if self.on_connection:
            await self.on_connection(connection_info)

        try:
            response = await self._proxy_http_request(request)
            return response
        except Exception as e:
            logger.error(f"Error proxying HTTP request: {e}")
            return web.Response(
                text=f"Tunnel Error: {e}",
                status=502,
                headers={"Content-Type": "text/plain"},
            )
        finally:
            if self.on_disconnection:
                await self.on_disconnection(connection_info)

    async def _handle_websocket(self, request: Request) -> WebSocketResponse:
        """Handle WebSocket connections."""
        ws = WebSocketResponse()
        await ws.prepare(request)

        connection_info = {
            "type": "websocket",
            "remote_addr": request.remote,
            "path": request.path_qs,
        }

        if self.on_connection:
            await self.on_connection(connection_info)

        try:
            await self._proxy_websocket_messages(ws, request)
        except Exception as e:
            logger.error(f"Error handling WebSocket: {e}")
        finally:
            if self.on_disconnection:
                await self.on_disconnection(connection_info)

        return ws

    async def _proxy_http_request(self, request: Request) -> Response | StreamResponse:
        """Proxy HTTP request to local service."""
        if not self._client_session:
            raise TunnelError("Client session is not initialized")

        url = (
            f"http://{self.config.local_host}:{self.config.local_port}{request.path_qs}"
        )
        headers = dict(request.headers)

        hop_by_hop = {
            "connection",
            "keep-alive",
            "proxy-authenticate",
            "proxy-authorization",
            "te",
            "trailers",
            "transfer-encoding",
            "upgrade",
            "host",
        }
        headers = {k: v for k, v in headers.items() if k.lower() not in hop_by_hop}

        headers["Host"] = f"{self.config.local_host}:{self.config.local_port}"

        body = None
        if request.can_read_body:
            body = await request.read()

        async with self._client_session.request(
            method=request.method,
            url=url,
            headers=headers,
            data=body,
            allow_redirects=False,
        ) as resp:
            response_headers = dict(resp.headers)

            response_headers = {
                k: v for k, v in response_headers.items() if k.lower() not in hop_by_hop
            }

            if resp.content_type and "stream" in resp.content_type:
                return await self._create_streaming_response(
                    resp, response_headers, request=request
                )

            body = await resp.read()
            return web.Response(body=body, status=resp.status, headers=response_headers)

    async def _create_streaming_response(
        self, resp: Any, headers: dict[str, Any], *, request: Request
    ) -> StreamResponse:
        """Create streaming response for large content."""
        response = StreamResponse(status=resp.status, headers=headers)

        await response.prepare(request)

        async for chunk in resp.content.iter_chunked(self.config.buffer_size):
            await response.write(chunk)

        await response.write_eof()
        return response

    async def _proxy_websocket_messages(
        self, ws: WebSocketResponse, request: Request
    ) -> None:
        """Proxy WebSocket messages bidirectionally."""
        local_url = (
            f"ws://{self.config.local_host}:{self.config.local_port}{request.path_qs}"
        )

        try:
            if not self._client_session:
                raise TunnelError("Client session was not initialized")

            async with self._client_session.ws_connect(
                local_url, receive_timeout=self.config.connection_timeout
            ) as local_ws:
                tasks = [
                    asyncio.create_task(
                        self._forward_ws_messages(ws, local_ws, "client->local")
                    ),
                    asyncio.create_task(
                        self._forward_ws_messages(local_ws, ws, "local->client")
                    ),
                ]

                _, pending = await asyncio.wait(
                    tasks, return_when=asyncio.FIRST_COMPLETED
                )

                for task in pending:
                    task.cancel()

        except Exception as e:
            logger.error(f"WebSocket proxy error: {e}")
            await ws.close(code=1011, message=b"Upstream connection failed")

    async def _forward_ws_messages(
        self,
        src_ws: WebSocketResponse | ClientWebSocketResponse,
        dst_ws: WebSocketResponse | ClientWebSocketResponse,
        direction: str,
    ) -> None:
        """Forward WebSocket messages from source to destination."""
        try:
            async for msg in src_ws:
                if msg.type == WSMsgType.TEXT:
                    await dst_ws.send_str(msg.data)
                elif msg.type == WSMsgType.BINARY:
                    await dst_ws.send_bytes(msg.data)
                elif msg.type == WSMsgType.CLOSE:
                    await dst_ws.close()
                    break
                elif msg.type == WSMsgType.ERROR:
                    logger.error(
                        f"WebSocket error ({direction}): {src_ws.exception() or 'Unknown error'}"
                    )
                    break
        except Exception as e:
            logger.error(f"Error forwarding WebSocket messages ({direction}): {e}")

    async def _handle_health_check(self, _request: Request) -> Response:
        """Handle health check requests."""
        return web.json_response(
            {
                "status": "healthy",
                "tunnel_id": self.config.tunnel_id,
                "local_service": f"{self.config.local_host}:{self.config.local_port}",
            }
        )

    async def _handle_stats(self, _request: Request) -> Response:
        """Handle stats requests."""
        return web.json_response(
            {
                "tunnel_id": self.config.tunnel_id,
                "config": self.config.model_dump(exclude_unset=True),
                "server_info": {
                    "host": self.config.remote_host,
                    "port": self.config.remote_port,
                    "protocol": self.config.protocol.value,
                    "is_serving": self.is_serving(),
                },
            }
        )
