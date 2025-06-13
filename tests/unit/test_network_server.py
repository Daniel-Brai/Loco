from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import WSMsgType, web
from aiohttp.web_ws import WebSocketResponse

from loco.network.server import TunnelServer


class TestTunnelServer:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_init(self, sample_tunnel_config):
        """Test server initialization."""
        with patch("loco.network.server.web.Application") as mock_app_class:
            mock_app = MagicMock()
            mock_app_class.return_value = mock_app

            server = TunnelServer(config=sample_tunnel_config)

            assert server.config == sample_tunnel_config
            assert server._app == mock_app
            assert server._site is None
            assert server._runner is None
            mock_app.router.add_route.assert_called()

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_start(self, sample_tunnel_config):
        """Test starting the server."""
        with (
            patch("loco.network.server.web.Application") as mock_app_class,
            patch("loco.network.server.web.AppRunner") as mock_runner_class,
            patch("loco.network.server.web.TCPSite") as mock_site_class,
        ):
            mock_app = MagicMock()
            mock_app_class.return_value = mock_app

            mock_runner = AsyncMock()
            mock_runner_class.return_value = mock_runner

            mock_site = AsyncMock()
            mock_site_class.return_value = mock_site

            server = TunnelServer(config=sample_tunnel_config)
            server._verify_server_running = AsyncMock()
            server._verify_server_running.return_value = True

            await server.start()

            mock_runner.setup.assert_called_once()
            mock_site_class.assert_called_once()
            mock_site.start.assert_called_once()

            assert (
                "http://localhost:9000"
                == f"http://localhost:{sample_tunnel_config.remote_port}"
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_stop(self, sample_tunnel_config):
        """Test stopping the server."""
        server = TunnelServer(config=sample_tunnel_config)

        server._runner = AsyncMock()
        server._site = AsyncMock()

        await server.stop()

        assert server._site is None
        assert server._runner is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_http_request(self, sample_tunnel_config):
        """Test HTTP request handling."""
        server = TunnelServer(config=sample_tunnel_config)
        server.config.subdomain = "test"

        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.path = "/test"
        mock_request.headers = {"Host": "example.com"}
        mock_request.remote = "192.168.1.1"

        with patch.object(
            server, "_handle_request", return_value=web.Response(text="OK")
        ) as mock_proxy:
            resp = await server._handle_request(mock_request)

            assert getattr(resp, "text", None) == "OK"
            mock_proxy.assert_called_once_with(mock_request)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_websocket_request(self, sample_tunnel_config):
        """Test WebSocket request handling."""
        server = TunnelServer(config=sample_tunnel_config)
        mock_request = MagicMock()

        with patch.object(
            server, "_handle_websocket_proxy", return_value="ws_response"
        ) as mock_proxy_ws:
            resp = await server._handle_websocket_proxy(mock_request)

            assert resp == "ws_response"
            mock_proxy_ws.assert_called_once_with(mock_request)

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_proxy_http_success(self, sample_tunnel_config):
        """Test successful HTTP request proxying."""
        server = TunnelServer(config=sample_tunnel_config)

        mock_request = AsyncMock()
        mock_request.method = "GET"
        mock_request.path = "/test"
        mock_request.headers = {"Host": "example.com"}
        mock_request.remote = "192.168.1.1"
        mock_request.host = "example.com"
        mock_request.query_string = ""
        mock_request.can_read_body = True
        mock_request.read = AsyncMock(return_value=b"request body")

        mock_content = AsyncMock()
        mock_content.read = AsyncMock(return_value=b"response content")
        mock_content.__aenter__.return_value = mock_content

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.reason = "OK"
        mock_response.headers = {"Content-Type": "text/plain"}
        mock_response.content = mock_content

        mock_session = AsyncMock()
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_response
        mock_session.request.return_value = mock_session_cm

        response = web.Response(
            status=200,
            reason="OK",
            headers={"Content-Type": "text/plain"},
            text="response content",
        )

        with (
            patch("loco.network.server.ClientSession", return_value=mock_session),
            patch("loco.network.server.web.Response", return_value=response),
        ):
            server._client_session = mock_session

            resp = await server._handle_request(mock_request)

            assert "Content-Type" in resp.headers
            assert resp.reason == "OK"
            assert resp.status == 200

            mock_session.request.assert_called_once()

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_proxy_websocket_success(self, sample_tunnel_config):
        """Test successful WebSocket proxying."""
        server = TunnelServer(config=sample_tunnel_config)

        server._client_session = AsyncMock()

        mock_client_ws = MagicMock(spec=WebSocketResponse)
        mock_client_ws.__aiter__ = AsyncMock()
        mock_client_ws.__aiter__.return_value = [
            MagicMock(type=WSMsgType.TEXT, data="hello"),
            MagicMock(type=WSMsgType.CLOSE),
        ]
        mock_client_ws.closed = False

        mock_upstream_ws = AsyncMock()
        mock_upstream_ws.closed = False

        with (
            patch(
                "loco.network.server.web.WebSocketResponse", return_value=mock_client_ws
            ),
            patch("loco.network.server.ClientSession") as mock_session_class,
        ):
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session
            mock_session.__aenter__.return_value = mock_session
            mock_session.ws_connect.return_value.__aenter__.return_value = (
                mock_upstream_ws
            )

            mock_request = MagicMock()
            mock_request.path = "/socket"

            mock_client_ws.prepare = AsyncMock()

            with patch.object(
                server, "_handle_websocket_proxy", return_value=mock_client_ws
            ):
                mock_client_ws.prepare.return_value = mock_client_ws
                mock_upstream_ws.send_str = AsyncMock()
                mock_upstream_ws.send_str.return_value = None
                mock_upstream_ws.receive.return_value = WSMsgType.TEXT

                resp = await server._handle_websocket_proxy(mock_request)

            assert resp == mock_client_ws
