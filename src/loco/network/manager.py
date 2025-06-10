"""Tunnel manager for handling multiple tunnels"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from ..core.exceptions import TunnelError, TunnelNotFoundError
from ..core.models import TunnelConfig, TunnelState, TunnelStatus
from ..storage.file_storage import FileStorage
from ..utils.logging import get_logger
from .tunnel import Tunnel

logger = get_logger("loco.network.manager")

if TYPE_CHECKING:
    from ..storage.base import StorageBackend


class TunnelManager:
    """
    Manager for handling multiple tunnels.\n
    This class provides methods to create, start, stop, and remove tunnels,
    as well as to list and get the status of existing tunnels.
    It uses a storage backend to persist tunnel configurations and states.
    Attributes:\n
        storage (StorageBackend): Storage backend for tunnel configurations.
    """

    def __init__(self, storage: StorageBackend | None = None) -> None:
        """Initialize tunnel manager."""
        self.storage = storage or FileStorage()
        self._tunnels: dict[str, Tunnel] = {}

    async def create_tunnel(self, config: TunnelConfig) -> str:
        """Create a new tunnel."""
        if config.tunnel_id in self._tunnels:
            raise TunnelError(f"Tunnel {config.tunnel_id} already exists")

        tunnel = Tunnel(config)
        self._tunnels[config.tunnel_id] = tunnel

        await self.storage.save_tunnel_config(config)

        logger.info(f"Created tunnel {config.tunnel_id}")
        return config.tunnel_id

    async def start_tunnel(self, tunnel_id: str) -> None:
        """Start a tunnel."""
        tunnel = self._get_tunnel(tunnel_id)
        await tunnel.start()

        await self.storage.save_tunnel_state(tunnel.state)

    async def stop_tunnel(self, tunnel_id: str) -> None:
        """Stop a tunnel."""
        tunnel = self._get_tunnel(tunnel_id)
        await tunnel.stop()

        await self.storage.save_tunnel_state(tunnel.state)

    async def remove_tunnel(self, tunnel_id: str) -> None:
        """Remove a tunnel."""
        if tunnel_id in self._tunnels:
            tunnel = self._tunnels[tunnel_id]
            if tunnel.is_active():
                await tunnel.stop()
            del self._tunnels[tunnel_id]

        await self.storage.delete_tunnel(tunnel_id)

        logger.info(f"Removed tunnel {tunnel_id}")

    async def list_tunnels(self) -> list[TunnelState]:
        """List all tunnels."""
        return [tunnel.state for tunnel in self._tunnels.values()]

    async def get_tunnel_status(self, tunnel_id: str) -> TunnelStatus:
        """Get tunnel status."""
        tunnel = self._get_tunnel(tunnel_id)
        return tunnel.state.status

    async def get_tunnel_stats(self, tunnel_id: str) -> dict[str, Any]:
        """Get tunnel statistics."""
        tunnel = self._get_tunnel(tunnel_id)
        return tunnel.get_stats()

    async def cleanup_stopped_tunnels(self) -> int:
        """Clean up stopped tunnels."""
        stopped_count = 0
        tunnel_ids_to_remove = []

        for tunnel_id, tunnel in self._tunnels.items():
            if tunnel.state.status == TunnelStatus.STOPPED:
                tunnel_ids_to_remove.append(tunnel_id)

        for tunnel_id in tunnel_ids_to_remove:
            await self.remove_tunnel(tunnel_id)
            stopped_count += 1

        return stopped_count

    async def stop_all_tunnels(self) -> None:
        """Stop all active tunnels."""
        tasks = []
        for tunnel in self._tunnels.values():
            if tunnel.is_active():
                tasks.append(tunnel.stop())

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def load_from_storage(self) -> None:
        """Load tunnels from storage."""
        configs = await self.storage.list_tunnel_configs()

        for config in configs:
            if config.tunnel_id not in self._tunnels:
                tunnel = Tunnel(config)
                self._tunnels[config.tunnel_id] = tunnel

                try:
                    state = await self.storage.load_tunnel_state(config.tunnel_id)
                    if state:
                        tunnel.state = state
                except Exception as e:
                    logger.warning(
                        f"Could not load state for tunnel {config.tunnel_id}: {e}"
                    )

    def _get_tunnel(self, tunnel_id: str) -> Tunnel:
        """Get tunnel by ID or raise exception."""
        if tunnel_id not in self._tunnels:
            raise TunnelNotFoundError(f"Tunnel {tunnel_id} not found")
        return self._tunnels[tunnel_id]
