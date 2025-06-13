from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from loco.core.exceptions import TunnelStartupError
from loco.core.models import TunnelConfig, TunnelProtocol, TunnelStatus
from loco.network.tunnel import Tunnel


@pytest.mark.unit
class TestTunnel:
    @pytest.mark.asyncio
    async def test_init(self, sample_tunnel_config):
        """Test tunnel initialization."""
        tunnel = Tunnel(config=sample_tunnel_config)

        assert tunnel.config == sample_tunnel_config
        assert tunnel.state is not None
        assert tunnel.state.status == TunnelStatus.STOPPED
        assert tunnel._server is None
        assert tunnel._proxy is None

    @pytest.mark.asyncio
    async def test_start_http_tunnel(self, sample_tunnel_config):
        """Test starting an HTTP tunnel."""
        tunnel = Tunnel(config=sample_tunnel_config)

        with patch("loco.network.tunnel.TunnelServer") as mock_server_class:
            mock_server = AsyncMock()
            mock_server_class.return_value = mock_server

            await tunnel.start()

            mock_server_class.assert_called_once()
            mock_server.start.assert_called_once()
            assert tunnel.state.status == TunnelStatus.ACTIVE
            assert tunnel.state.public_url == "http://localhost:9000"
            assert tunnel._server == mock_server

    @pytest.mark.asyncio
    async def test_start_tcp_tunnel(self):
        """Test starting a TCP tunnel."""
        config = TunnelConfig(
            tunnel_id="test-tcp-tunnel",
            name="Test TCP Tunnel",
            local_host="127.0.0.1",
            local_port=8000,
            remote_host="0.0.0.0",
            remote_port=9000,
            protocol=TunnelProtocol.TCP,
            subdomain=None,
            ssl_cert_path=None,
            ssl_key_path=None,
        )
        tunnel = Tunnel(config=config)

        with patch("loco.network.tunnel.TunnelProxy") as mock_proxy_class:
            mock_proxy = AsyncMock()
            mock_proxy_class.return_value = mock_proxy

            await tunnel.start()

            mock_proxy_class.assert_called_once()
            mock_proxy.start.assert_called_once()
            assert tunnel.state.status == TunnelStatus.ACTIVE
            assert tunnel._proxy == mock_proxy

    @pytest.mark.asyncio
    async def test_start_error(self, sample_tunnel_config):
        """Test error handling when starting a tunnel."""
        tunnel = Tunnel(config=sample_tunnel_config)

        with patch("loco.network.tunnel.TunnelServer") as mock_server_class:
            mock_server = AsyncMock()
            mock_server_class.return_value = mock_server
            mock_server.start.side_effect = Exception("Test error")

            with pytest.raises(TunnelStartupError):
                await tunnel.start()

            assert tunnel.state.status == TunnelStatus.ERROR
            assert "Test error" == tunnel.state.error_message

    @pytest.mark.asyncio
    async def test_stop(self, sample_tunnel_config):
        """Test stopping a tunnel."""
        tunnel = Tunnel(config=sample_tunnel_config)
        tunnel.state.status = TunnelStatus.ACTIVE

        with patch("loco.network.tunnel.TunnelServer") as mock_server_class:
            mock_server = AsyncMock()
            mock_server_class.return_value = mock_server

        await tunnel.stop()

        assert tunnel.state.status == TunnelStatus.STOPPED
        assert tunnel._server is None

    @pytest.mark.asyncio
    async def test_on_client_connected(self, sample_tunnel_config):
        """Test client connection callback."""
        tunnel = Tunnel(config=sample_tunnel_config)

        tunnel.state = MagicMock()

        assert tunnel.state.last_activity is not None

    @pytest.mark.asyncio
    async def test_on_data_transfer(self, sample_tunnel_config):
        """Test data transfer callback."""
        tunnel = Tunnel(config=sample_tunnel_config)

        tunnel.state = MagicMock()

        await tunnel._on_data_transfer(1024)

        assert tunnel.state.last_activity is not None
