"""File-based storage implementation."""

from __future__ import annotations

from pathlib import Path

import aiofiles

from ..core.exceptions import StorageError
from ..core.models import TunnelConfig, TunnelState
from .base import StorageBackend


class FileStorage(StorageBackend):
    """
    File-based storage backend for tunnel configurations and states.\n
    This backend stores tunnel configurations and states in JSON files
    within a specified directory structure.
    Attributes:
        base_dir (Path): Base directory for storage.
        config_dir (Path): Directory for tunnel configurations.
        state_dir (Path): Directory for tunnel states.
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        """Initialize file storage."""
        self.base_dir = base_dir or Path.home() / ".loco"
        self.config_dir = self.base_dir / "configs"
        self.state_dir = self.base_dir / "states"

        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)

    async def save_tunnel_config(self, config: TunnelConfig) -> None:
        """Save tunnel configuration."""
        try:
            config_path = self.config_dir / f"{config.tunnel_id}.json"

            async with aiofiles.open(config_path, "w") as f:
                await f.write(config.model_dump_json(indent=2))

        except Exception as e:
            raise StorageError(f"Failed to save tunnel config: {e}") from e

    async def load_tunnel_config(self, tunnel_id: str) -> TunnelConfig | None:
        """Load tunnel configuration."""
        try:
            config_path = self.config_dir / f"{tunnel_id}.json"

            if not config_path.exists():
                return None

            async with aiofiles.open(config_path) as f:
                data = await f.read()
                return TunnelConfig.model_validate(data)

        except Exception as e:
            raise StorageError(f"Failed to load config: {e}") from e

    async def list_tunnel_configs(self) -> list[TunnelConfig]:
        """List all tunnel configurations."""
        configs = []

        try:
            for config_file in self.config_dir.glob("*.json"):
                async with aiofiles.open(config_file) as f:
                    data = await f.read()
                    config = TunnelConfig.model_validate_json(data)
                    configs.append(config)

        except Exception as e:
            raise StorageError(f"Failed to list configs: {e}") from e

        return configs

    async def save_tunnel_state(self, state: TunnelState) -> None:
        """Save tunnel state."""
        try:
            state_path = self.state_dir / f"{state.config.tunnel_id}.json"

            async with aiofiles.open(state_path, "w") as f:
                await f.write(state.model_dump_json(indent=2))

        except Exception as e:
            raise StorageError(f"Failed to save state: {e}") from e

    async def load_tunnel_state(self, tunnel_id: str) -> TunnelState | None:
        """Load tunnel state."""
        try:
            state_path = self.state_dir / f"{tunnel_id}.json"

            if not state_path.exists():
                return None

            async with aiofiles.open(state_path) as f:
                data = await f.read()
                return TunnelState.model_validate_json(data)

        except Exception as e:
            raise StorageError(f"Failed to load state: {e}") from e

    async def delete_tunnel(self, tunnel_id: str) -> None:
        """Delete tunnel data."""
        try:
            config_path = self.config_dir / f"{tunnel_id}.json"
            state_path = self.state_dir / f"{tunnel_id}.json"

            if config_path.exists():
                config_path.unlink()

            if state_path.exists():
                state_path.unlink()

        except Exception as e:
            raise StorageError(f"Failed to delete tunnel: {e}") from e
