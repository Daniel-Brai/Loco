from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from loco.core.models import TunnelConfig, TunnelProtocol, TunnelState, TunnelStatus
from loco.network.manager import TunnelManager
from loco.storage.file_storage import FileStorage


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for storage tests."""
    return tmp_path


@pytest.fixture
def file_storage(temp_dir) -> FileStorage:
    """Create a FileStorage instance using the temporary directory."""
    from loco.storage.file_storage import FileStorage

    return FileStorage(base_dir=temp_dir)


@pytest.fixture
def sample_tunnel_config() -> TunnelConfig:
    """Create a sample TunnelConfig for testing."""
    return TunnelConfig(
        tunnel_id="test-tunnel-id",
        name="Test Tunnel",
        local_host="127.0.0.1",
        local_port=8000,
        remote_host="0.0.0.0",
        remote_port=9000,
        protocol=TunnelProtocol.HTTP,
        subdomain=None,
        ssl_cert_path=None,
        ssl_key_path=None,
        connection_timeout=30.0,
        max_connections=100,
        buffer_size=8192,
    )


@pytest.fixture
def sample_tunnel_state(sample_tunnel_config) -> TunnelState:
    return TunnelState(
        config=sample_tunnel_config,
        status=TunnelStatus.ACTIVE,
        started_at=datetime.fromisoformat("2023-01-01T12:00:00"),
        stopped_at=None,
        last_activity=datetime.fromisoformat("2023-01-01T12:05:00"),
        public_url="http://localhost:9000",
        error_message=None,
    )


@pytest.fixture
def mock_storage():
    storage = AsyncMock(spec=FileStorage)
    storage.list_tunnel_configs.return_value = []
    return storage


@pytest.fixture
def tunnel_manager(mock_storage):
    with patch("loco.network.manager.FileStorage", return_value=mock_storage):
        manager = TunnelManager()
        return manager


@pytest.fixture
def mock_tunnel():
    tunnel = AsyncMock()
    config = MagicMock()
    config.tunnel_id = "test-id"
    tunnel.state = MagicMock()
    return tunnel
