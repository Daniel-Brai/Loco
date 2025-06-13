import asyncio
import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from loco.network.proxy import TunnelProxy


@pytest.mark.unit
class TestTunnelProxy:
    def test_init(self, sample_tunnel_config_tcp):
        """Test proxy initialization."""
        proxy = TunnelProxy(config=sample_tunnel_config_tcp)

        assert proxy.config == sample_tunnel_config_tcp
        assert proxy._server_socket is None
        assert proxy.on_data_transfer is None
        assert proxy._connections == set()

    @pytest.mark.asyncio
    async def test_start(self, sample_tunnel_config_tcp):
        """Test starting the proxy server."""
        proxy = TunnelProxy(config=sample_tunnel_config_tcp)

        mock_socket = MagicMock(spec=socket.socket)
        mock_loop = AsyncMock(spec=asyncio.AbstractEventLoop)

        mock_client_socket = MagicMock(spec=socket.socket)
        mock_client_addr = ("192.168.1.1", 12345)

        mock_loop.sock_accept.side_effect = [
            (mock_client_socket, mock_client_addr),
            asyncio.CancelledError(),
        ]

        with (
            patch("socket.socket", return_value=mock_socket) as mock_socket_class,
            patch("asyncio.get_event_loop", return_value=mock_loop),
            patch.object(proxy, "_handle_tcp_connection") as mock_handle_conn,
        ):
            real_task = MagicMock()
            real_task.add_done_callback = MagicMock()

            def fake_create_task(coro):
                proxy._connections.add(real_task)
                return real_task

            mock_loop.create_task = fake_create_task

            mock_handle_conn.return_value = None

            with patch("contextlib.suppress"):
                await proxy.start()

            mock_socket_class.assert_called_once_with(
                socket.AF_INET, socket.SOCK_STREAM
            )
            mock_socket.setsockopt.assert_called_once_with(
                socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
            )
            mock_socket.bind.assert_called_once_with(
                (
                    sample_tunnel_config_tcp.remote_host,
                    sample_tunnel_config_tcp.remote_port,
                )
            )
            mock_socket.listen.assert_called_once()
            mock_socket.setblocking.assert_called_once_with(False)

            mock_loop.sock_accept.assert_called()
            assert len(proxy._connections) == 1

    @pytest.mark.asyncio
    async def test_stop(self, sample_tunnel_config_tcp):
        """Test stopping the proxy server."""
        proxy = TunnelProxy(config=sample_tunnel_config_tcp)

        proxy._server_socket = MagicMock(spec=socket.socket)

        async def dummy_task():
            return None

        task1 = asyncio.create_task(dummy_task())
        task1.done = MagicMock(return_value=False)
        task1.cancel = MagicMock()

        task2 = asyncio.create_task(dummy_task())
        task2.done = MagicMock(return_value=True)
        task2.cancel = MagicMock()

        proxy._connections = {task1, task2}
        proxy._running = True

        with patch("contextlib.suppress"):
            await proxy.stop()

        assert proxy._running == False

        task1.cancel.assert_called_once()
        task2.cancel.assert_not_called()

        assert proxy._server_socket is None

        assert proxy._connections == set()

    @pytest.mark.asyncio
    async def test_handle_tcp_connection(self, sample_tunnel_config_tcp):
        """Test TCP connection handling."""
        proxy = TunnelProxy(config=sample_tunnel_config_tcp)
        proxy._running = True

        mock_client_socket = MagicMock(spec=socket.socket)
        mock_local_socket = MagicMock(spec=socket.socket)
        mock_client_addr = ("192.168.1.1", 12345)

        mock_loop = AsyncMock(spec=asyncio.AbstractEventLoop)

        with (
            patch("socket.socket", return_value=mock_local_socket) as mock_socket_class,
            patch("asyncio.get_event_loop", return_value=mock_loop),
            patch("asyncio.create_task") as mock_create_task,
            patch("asyncio.wait") as mock_wait,
        ):
            task1 = AsyncMock(spec=asyncio.Task)
            task2 = AsyncMock(spec=asyncio.Task)
            mock_create_task.side_effect = [task1, task2]

            mock_wait.return_value = (set(), {task2})

            await proxy._handle_tcp_connection(mock_client_socket, mock_client_addr)

            mock_socket_class.assert_called_once_with(
                socket.AF_INET, socket.SOCK_STREAM
            )
            mock_loop.sock_connect.assert_called_once_with(
                mock_local_socket,
                (
                    sample_tunnel_config_tcp.local_host,
                    sample_tunnel_config_tcp.local_port,
                ),
            )

            assert mock_create_task.call_count == 2

            task2.cancel.assert_called_once()

            mock_client_socket.close.assert_called_once()
            mock_local_socket.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_forward_data(self, sample_tunnel_config_tcp):
        """Test data forwarding between sockets."""
        proxy = TunnelProxy(config=sample_tunnel_config_tcp)
        proxy._running = True

        mock_src_socket = MagicMock(spec=socket.socket)
        mock_dst_socket = MagicMock(spec=socket.socket)

        mock_loop = AsyncMock(spec=asyncio.AbstractEventLoop)

        proxy.on_data_transfer = AsyncMock()

        with patch("asyncio.get_event_loop", return_value=mock_loop):
            mock_loop.sock_recv.side_effect = [b"test data", b""]

            await proxy._forward_data(mock_src_socket, mock_dst_socket, "test->test")

            mock_loop.sock_recv.assert_called_with(
                mock_src_socket, sample_tunnel_config_tcp.buffer_size
            )
            mock_loop.sock_sendall.assert_called_once_with(
                mock_dst_socket, b"test data"
            )

            proxy.on_data_transfer.assert_called_once_with(len(b"test data"))

    def test_get_connection_count(self, sample_tunnel_config_tcp):
        """Test getting active connection count."""
        proxy = TunnelProxy(config=sample_tunnel_config_tcp)

        task1 = MagicMock(spec=asyncio.Task)
        task1.done.return_value = False

        task2 = MagicMock(spec=asyncio.Task)
        task2.done.return_value = True

        proxy._connections = {task1, task2}

        assert proxy.get_connection_count() == 1

    def test_is_running(self, sample_tunnel_config_tcp):
        """Test checking if proxy is running."""
        proxy = TunnelProxy(config=sample_tunnel_config_tcp)
        assert proxy.is_running() == False

        proxy._running = True
        assert proxy.is_running() == True
