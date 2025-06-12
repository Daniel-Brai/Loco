from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from loco.core.exceptions import TunnelError, TunnelNotFoundError
from loco.core.models import TunnelConfig, TunnelProtocol, TunnelState, TunnelStatus


@pytest.mark.unit
class TestTunnelManager:
    @pytest.mark.asyncio
    async def test_init(self, tunnel_manager, mock_storage):
        assert tunnel_manager.storage == mock_storage
        assert tunnel_manager._tunnels == {}

    @pytest.mark.asyncio
    async def test_load_from_storage(
        self, tunnel_manager, mock_storage, sample_tunnel_config, sample_tunnel_state
    ):
        """Test loading tunnels from storage."""
        mock_storage.list_tunnel_configs.return_value = [sample_tunnel_config]
        mock_storage.load_tunnel_state.return_value = sample_tunnel_state

        await tunnel_manager.load_from_storage()

        mock_storage.list_tunnel_configs.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_tunnel(self, tunnel_manager):
        """Test creating a new tunnel."""
        with patch("loco.network.manager.Tunnel") as mock_tunnel_class:
            config = TunnelConfig(
                tunnel_id="new-tunnel",
                name="New Test Tunnel",
                local_host="127.0.0.1",
                local_port=8000,
                remote_host="0.0.0.0",
                remote_port=9000,
                protocol=TunnelProtocol.HTTP,
                subdomain=None,
                ssl_cert_path=None,
                ssl_key_path=None,
            )

            tunnel_instance = MagicMock()
            mock_tunnel_class.return_value = tunnel_instance

            await tunnel_manager.create_tunnel(config)

            mock_tunnel_class.assert_called_once_with(config)
            assert config.tunnel_id in tunnel_manager._tunnels
            tunnel_manager.storage.save_tunnel_config.assert_called_once_with(config)
            tunnel_manager.storage.save_tunnel_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_tunnel_already_exists(self, tunnel_manager):
        """Test creating a tunnel that already exists."""
        config = TunnelConfig(
            tunnel_id="existing-tunnel",
            name="Existing Tunnel",
            local_host="127.0.0.1",
            local_port=8000,
            remote_host="0.0.0.0",
            remote_port=9000,
            protocol=TunnelProtocol.HTTP,
            subdomain=None,
            ssl_cert_path=None,
            ssl_key_path=None,
        )
        tunnel_manager._tunnels = {"existing-tunnel": MagicMock()}

        with pytest.raises(TunnelError):
            await tunnel_manager.create_tunnel(config)

    def test_get_tunnel(self, tunnel_manager):
        """Test getting a tunnel by ID."""
        mock_tunnel = MagicMock()
        tunnel_manager._tunnels = {"test-id": mock_tunnel}

        result = tunnel_manager.get_tunnel("test-id")
        assert result == mock_tunnel

        with pytest.raises(TunnelNotFoundError):
            tunnel_manager.get_tunnel("non-existent-id")

    @pytest.mark.asyncio
    async def test_list_tunnels(self, tunnel_manager):
        """Test listing all tunnels."""
        mock_tunnel1 = MagicMock()
        mock_tunnel2 = MagicMock()

        config1 = TunnelConfig(
            tunnel_id="test-id-1",
            name="Test1",
            local_port=8000,
            local_host="localhost",
            remote_port=9000,
            remote_host="0.0.0.0",
            protocol=TunnelProtocol.HTTP,
            subdomain=None,
            ssl_cert_path=None,
            ssl_key_path=None,
        )

        config2 = TunnelConfig(
            tunnel_id="test-id-2",
            name="Test2",
            local_port=8001,
            local_host="localhost",
            remote_port=9001,
            remote_host="0.0.0.0",
            protocol=TunnelProtocol.HTTP,
            subdomain=None,
            ssl_cert_path=None,
            ssl_key_path=None,
        )

        # Create states
        state1 = TunnelState(
            config=config1,
            status=TunnelStatus.ACTIVE,
            active_connections=5,
            bytes_transferred=1024,
            public_url="http://localhost:9000",
            created_at=datetime.now(UTC),
            error_message=None,
            last_activity=datetime.now(UTC),
            started_at=datetime.now(UTC),
            stopped_at=None,
            total_connections=1,
        )

        state2 = TunnelState(
            config=config2,
            status=TunnelStatus.STOPPED,
            active_connections=5,
            bytes_transferred=1024,
            public_url="http://localhost:9001",
            created_at=datetime.now(UTC),
            error_message=None,
            last_activity=datetime.now(UTC),
            started_at=datetime.now(UTC),
            stopped_at=None,
            total_connections=1,
        )

        mock_tunnel1.state = state1
        mock_tunnel1.is_active.return_value = True
        mock_tunnel1.config = config1

        mock_tunnel2.state = state2
        mock_tunnel2.is_active.return_value = False
        mock_tunnel2.config = config2

        tunnel_manager._tunnels = {
            "test-id-1": mock_tunnel1,
            "test-id-2": mock_tunnel2,
        }

        with patch.object(tunnel_manager, "sync_tunnel_state"):
            result = await tunnel_manager.list_tunnels()

            assert len(result) == 2
            tunnel_ids_and_statuses = [
                {"tunnel_id": r.config.tunnel_id, "status": r.status} for r in result
            ]
            assert {
                "tunnel_id": "test-id-1",
                "status": TunnelStatus.ACTIVE,
            } in tunnel_ids_and_statuses
            assert {
                "tunnel_id": "test-id-2",
                "status": TunnelStatus.STOPPED,
            } in tunnel_ids_and_statuses

    @pytest.mark.asyncio
    async def test_start_tunnel(self, tunnel_manager):
        """Test starting a tunnel."""
        mock_tunnel = AsyncMock()
        mock_config = MagicMock()
        mock_config.tunnel_id = "test-id"
        mock_tunnel.config = mock_config

        tunnel_manager._tunnels = {"test-id": mock_tunnel}

        with patch.object(tunnel_manager, "sync_tunnel_state"):
            await tunnel_manager.start_tunnel("test-id")
            mock_tunnel.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_tunnel(self, tunnel_manager):
        """Test stopping a tunnel."""
        mock_tunnel = AsyncMock()
        mock_config = MagicMock()
        mock_config.tunnel_id = "test-id"
        mock_tunnel.config = mock_config

        tunnel_manager._tunnels = {"test-id": mock_tunnel}

        with patch.object(tunnel_manager, "sync_tunnel_state"):
            await tunnel_manager.stop_tunnel("test-id")
            mock_tunnel.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_tunnel(self, tunnel_manager):
        """Test removing a tunnel."""
        mock_tunnel = AsyncMock()
        mock_config = MagicMock()
        mock_config.tunnel_id = "test-id"
        mock_tunnel.config = mock_config
        mock_tunnel.is_active = MagicMock(return_value=False)

        tunnel_manager._tunnels = {"test-id": mock_tunnel}

        await tunnel_manager.remove_tunnel("test-id")

        tunnel_manager.storage.delete_tunnel.assert_called_once_with("test-id")
        assert "test-id" not in tunnel_manager._tunnels

    @pytest.mark.asyncio
    async def test_get_tunnel_status(self, tunnel_manager):
        """Test getting tunnel status."""
        mock_tunnel = MagicMock()
        mock_tunnel.state = MagicMock()
        mock_tunnel.state.status = TunnelStatus.ACTIVE
        mock_config = MagicMock()
        mock_config.tunnel_id = "test-id"
        mock_tunnel.config = mock_config

        tunnel_manager._tunnels = {"test-id": mock_tunnel}

        with patch.object(
            tunnel_manager, "_get_tunnel_by_partial_id", return_value=mock_tunnel
        ):
            status = await tunnel_manager.get_tunnel_status("test-id")
            assert status == TunnelStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_get_tunnel_stats(self, tunnel_manager):
        """Test getting tunnel stats."""
        expected_stats = {"connections": 5, "bytes_transferred": 1024}
        mock_tunnel = MagicMock()
        mock_tunnel.get_stats.return_value = expected_stats
        mock_config = MagicMock()
        mock_config.tunnel_id = "test-id"
        mock_tunnel.config = mock_config

        tunnel_manager._tunnels = {"test-id": mock_tunnel}

        with patch.object(
            tunnel_manager, "_get_tunnel_by_partial_id", return_value=mock_tunnel
        ):
            stats = await tunnel_manager.get_tunnel_stats("test-id")
            assert stats == expected_stats
            mock_tunnel.get_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_stopped_tunnels(self, tunnel_manager):
        """Test cleaning up stopped tunnels."""
        mock_tunnel1 = MagicMock()
        mock_config1 = MagicMock()
        mock_config1.tunnel_id = "test-id-1"
        mock_tunnel1.config = mock_config1
        mock_tunnel1.is_active.return_value = False
        mock_tunnel1.state.status = TunnelStatus.STOPPED

        mock_tunnel2 = MagicMock()
        mock_config2 = MagicMock()
        mock_config2.tunnel_id = "test-id-2"
        mock_tunnel2.config = mock_config2
        mock_tunnel2.is_active.return_value = True
        mock_tunnel2.state.status = TunnelStatus.ACTIVE

        tunnel_manager._tunnels = {
            "test-id-1": mock_tunnel1,
            "test-id-2": mock_tunnel2,
        }

        with patch.object(tunnel_manager, "remove_tunnel") as mock_remove:
            stopped_count = await tunnel_manager.cleanup_stopped_tunnels()

            assert stopped_count == 1
            mock_remove.assert_called_once_with("test-id-1")

    @pytest.mark.asyncio
    async def test_stop_all_tunnels(self, tunnel_manager):
        """Test stopping all tunnels."""
        mock_tunnel1 = AsyncMock()
        mock_config1 = MagicMock()
        mock_tunnel1.config = mock_config1
        mock_tunnel1.is_active = MagicMock(return_value=True)

        mock_tunnel2 = AsyncMock()
        mock_config2 = MagicMock()
        mock_config2.tunnel_id = "test-id-2"
        mock_tunnel2.config = mock_config2
        mock_tunnel2.is_active = MagicMock(return_value=True)

        tunnel_manager._tunnels = {
            "test-id-1": mock_tunnel1,
            "test-id-2": mock_tunnel2,
        }

        await tunnel_manager.stop_all_tunnels()

        mock_tunnel1.stop.assert_called_once()
        mock_tunnel2.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_tunnel_state(self, tunnel_manager):
        """Test synchronizing tunnel state."""
        mock_tunnel = MagicMock()
        mock_config = MagicMock()
        mock_config.tunnel_id = "test-id"
        mock_tunnel.config = mock_config
        mock_tunnel.is_active.return_value = True
        mock_tunnel.state.status = TunnelStatus.STARTING

        tunnel_manager._tunnels = {"test-id": mock_tunnel}

        await tunnel_manager.sync_tunnel_state("test-id")

        assert mock_tunnel.state.status == TunnelStatus.ACTIVE
        tunnel_manager.storage.save_tunnel_state.assert_called_once_with(
            mock_tunnel.state
        )
