from abc import ABC, abstractmethod

from ..core.models import TunnelConfig, TunnelState


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    async def save_tunnel_config(self, config: TunnelConfig) -> None:
        """Save tunnel configuration."""
        pass

    @abstractmethod
    async def load_tunnel_config(self, tunnel_id: str) -> TunnelConfig | None:
        """Load tunnel configuration."""
        pass

    @abstractmethod
    async def list_tunnel_configs(self) -> list[TunnelConfig]:
        """List all tunnel configurations."""
        pass

    @abstractmethod
    async def save_tunnel_state(self, state: TunnelState) -> None:
        """Save tunnel state."""
        pass

    @abstractmethod
    async def load_tunnel_state(self, tunnel_id: str) -> TunnelState | None:
        """Load tunnel state."""
        pass

    @abstractmethod
    async def delete_tunnel(self, tunnel_id: str) -> None:
        """Delete tunnel data."""
        pass
