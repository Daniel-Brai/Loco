import json
from unittest.mock import patch

import aiofiles
import pytest

from loco.core.exceptions import StorageError
from loco.storage.file_storage import FileStorage


@pytest.mark.unit
class TestFileStorage:
    @pytest.mark.asyncio
    async def test_init_creates_directories(self, temp_dir):
        """Test that init creates the necessary directories."""
        storage = FileStorage(base_dir=temp_dir)

        assert storage.config_dir.exists()
        assert storage.state_dir.exists()

    @pytest.mark.asyncio
    async def test_save_tunnel_config(self, file_storage, sample_tunnel_config):
        """Test saving a tunnel configuration."""
        await file_storage.save_tunnel_config(sample_tunnel_config)

        config_path = file_storage.config_dir / f"{sample_tunnel_config.tunnel_id}.json"
        assert config_path.exists()

        async with aiofiles.open(config_path, "r") as f:
            content = await f.read()
            saved_config = json.loads(content)
            assert saved_config["tunnel_id"] == sample_tunnel_config.tunnel_id
            assert saved_config["name"] == sample_tunnel_config.name

    @pytest.mark.asyncio
    async def test_load_tunnel_config(self, file_storage, sample_tunnel_config):
        """Test loading a tunnel configuration."""
        await file_storage.save_tunnel_config(sample_tunnel_config)

        loaded_config = await file_storage.load_tunnel_config(
            sample_tunnel_config.tunnel_id
        )

        assert loaded_config is not None
        assert loaded_config.tunnel_id == sample_tunnel_config.tunnel_id
        assert loaded_config.name == sample_tunnel_config.name
        assert loaded_config.local_port == sample_tunnel_config.local_port

    @pytest.mark.asyncio
    async def test_load_nonexistent_tunnel_config(self, file_storage):
        """Test loading a tunnel configuration that doesn't exist."""
        loaded_config = await file_storage.load_tunnel_config("nonexistent-id")
        assert loaded_config is None

    @pytest.mark.asyncio
    async def test_list_tunnel_configs(self, file_storage, sample_tunnel_config):
        """Test listing tunnel configurations."""
        config1 = sample_tunnel_config
        config2 = sample_tunnel_config.model_copy(
            update={"tunnel_id": "test-tunnel-id-2", "name": "Test Tunnel 2"}
        )

        await file_storage.save_tunnel_config(config1)
        await file_storage.save_tunnel_config(config2)

        configs = await file_storage.list_tunnel_configs()

        assert len(configs) == 2
        assert any(c.tunnel_id == config1.tunnel_id for c in configs)
        assert any(c.tunnel_id == config2.tunnel_id for c in configs)

    @pytest.mark.asyncio
    async def test_save_tunnel_state(self, file_storage, sample_tunnel_state):
        """Test saving a tunnel state."""
        await file_storage.save_tunnel_state(sample_tunnel_state)

        state_path = (
            file_storage.state_dir / f"{sample_tunnel_state.config.tunnel_id}.json"
        )
        assert state_path.exists()

        async with aiofiles.open(state_path, "r") as f:
            content = await f.read()
            saved_state = json.loads(content)
            assert saved_state["status"] == sample_tunnel_state.status.value
            assert saved_state["public_url"] == sample_tunnel_state.public_url

    @pytest.mark.asyncio
    async def test_load_tunnel_state(self, file_storage, sample_tunnel_state):
        """Test loading a tunnel state."""
        await file_storage.save_tunnel_config(sample_tunnel_state.config)
        await file_storage.save_tunnel_state(sample_tunnel_state)

        loaded_state = await file_storage.load_tunnel_state(
            sample_tunnel_state.config.tunnel_id
        )

        assert loaded_state is not None
        assert loaded_state.status == sample_tunnel_state.status
        assert loaded_state.public_url == sample_tunnel_state.public_url
        assert loaded_state.config.tunnel_id == sample_tunnel_state.config.tunnel_id

    @pytest.mark.asyncio
    async def test_load_nonexistent_tunnel_state(self, file_storage):
        """Test loading a tunnel state that doesn't exist."""
        loaded_state = await file_storage.load_tunnel_state("nonexistent-id")
        assert loaded_state is None

    @pytest.mark.asyncio
    async def test_delete_tunnel(
        self, file_storage, sample_tunnel_config, sample_tunnel_state
    ):
        """Test deleting a tunnel completely."""
        await file_storage.save_tunnel_config(sample_tunnel_config)
        await file_storage.save_tunnel_state(sample_tunnel_state)

        config_path = file_storage.config_dir / f"{sample_tunnel_config.tunnel_id}.json"
        state_path = file_storage.state_dir / f"{sample_tunnel_config.tunnel_id}.json"
        assert config_path.exists()
        assert state_path.exists()

        await file_storage.delete_tunnel(sample_tunnel_config.tunnel_id)

        assert not config_path.exists()
        assert not state_path.exists()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_tunnel(self, file_storage):
        """Test deleting a tunnel that doesn't exist."""
        await file_storage.delete_tunnel("nonexistent-id")

    @pytest.mark.asyncio
    async def test_save_config_storage_error(self, file_storage, sample_tunnel_config):
        """Test storage error during config save."""
        with patch("aiofiles.open", side_effect=Exception("Mocked error")):
            with pytest.raises(StorageError) as exc_info:
                await file_storage.save_tunnel_config(sample_tunnel_config)

            assert "Failed to save tunnel config" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_load_config_storage_error(self, file_storage, sample_tunnel_config):
        """Test storage error during config load."""
        await file_storage.save_tunnel_config(sample_tunnel_config)

        with patch("aiofiles.open", side_effect=Exception("Mocked error")):
            with pytest.raises(StorageError) as exc_info:
                await file_storage.load_tunnel_config(sample_tunnel_config.tunnel_id)

            assert "Failed to load config" in str(exc_info.value)
