"""
Data models for tunnel management.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, PositiveInt


class TunnelStatus(StrEnum):
    """
    Eumeration of possible tunnel states.
    Attributes:
        STARTING: Tunnel is being initialized.
        ACTIVE: Tunnel is running and accepting connections.
        STOPPED: Tunnel has been stopped.
        ERROR: Tunnel encountered an error and is not operational.
        STOPPING: Tunnel is in the process of shutting down.
    """

    STARTING = "starting"
    ACTIVE = "active"
    STOPPED = "stopped"
    ERROR = "error"
    STOPPING = "stopping"


class TunnelProtocol(StrEnum):
    """
    Enumeration of supported tunnel protocols.
    Attributes:
        HTTP: Standard HTTP protocol.
        HTTPS: Secure HTTP protocol.
        TCP: Generic TCP protocol for raw data transfer.
        WEBSOCKET: WebSocket protocol for real-time communication.
    """

    HTTP = "http"
    HTTPS = "https"
    TCP = "tcp"
    WEBSOCKET = "websocket"


class TunnelConfig(BaseModel):
    """
    Configuration for a tunnel.
    Attributes:
        tunnel_id (str): Unique identifier for the tunnel.
        name (Optional[str]): Optional name for the tunnel.
        local_port (PositiveInt): Local port to bind the tunnel.
        local_host (str): Local host address to bind the tunnel.
        remote_port (Optional[PositiveInt]): Remote port to forward traffic to.
        remote_host (str): Remote host address to forward traffic to.
        protocol (TunnelProtocol): Protocol to use for the tunnel.
        subdomain (Optional[str]): Optional subdomain for the tunnel.
        custom_domain (Optional[str]): Optional custom domain for the tunnel.
        auth_token (Optional[str]): Optional authentication token for the tunnel.
        ssl_cert_path (Optional[str]): Path to SSL certificate for HTTPS tunnels.
        ssl_key_path (Optional[str]): Path to SSL key for HTTPS tunnels.
        max_connections (PositiveInt): Maximum number of concurrent connections allowed.
        connection_timeout (PositiveFloat): Timeout for connections in seconds.
        buffer_size (PositiveInt): Size of the buffer for data transfer in bytes.
        enable_compression (bool): Whether to enable compression for data transfer.
        enable_logging (bool): Whether to enable logging for the tunnel.
        metadata (Dict[str, Any]): Additional metadata for the tunnel configuration.
    """

    tunnel_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str | None = Field(default=None, max_length=100, min_length=1)
    local_port: PositiveInt = Field(ge=1, le=65535)
    local_host: str = Field(default="127.0.0.1")
    remote_port: PositiveInt | None = Field(default=None, ge=1, le=65535)
    remote_host: str = Field(default="0.0.0.0")
    protocol: TunnelProtocol = TunnelProtocol.HTTP
    subdomain: str | None = Field(default=None, pattern=r"^[a-z0-9-]{1,63}$")
    custom_domain: str | None = None
    auth_token: str | None = None
    ssl_cert_path: str | None = None
    ssl_key_path: str | None = None
    max_connections: PositiveInt = Field(default=100, ge=1)
    connection_timeout: PositiveFloat = Field(default=30.0, ge=1.0)
    buffer_size: PositiveInt = Field(default=8192, ge=1024)
    enable_compression: bool = True
    enable_logging: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class TunnelState(BaseModel):
    """
    State of a tunnel.
    Attributes:
        config (TunnelConfig): Configuration of the tunnel.
        status (TunnelStatus): Current status of the tunnel.
        public_url (Optional[str]): Public URL for accessing the tunnel.
        server_pid (Optional[PositiveInt]): Process ID of the server handling the tunnel.
        client_pid (Optional[PositiveInt]): Process ID of the client handling the tunnel.
        created_at (datetime): Timestamp when the tunnel was created.
        started_at (Optional[datetime]): Timestamp when the tunnel was started.
        stopped_at (Optional[datetime]): Timestamp when the tunnel was stopped.
        last_activity (Optional[datetime]): Timestamp of the last activity on the tunnel.
        active_connections (int): Number of currently active connections.
        total_connections (int): Total number of connections made to the tunnel.
        bytes_transferred (int): Total bytes transferred through the tunnel.
        error_message (Optional[str]): Error message if any error occurred in the tunnel.
    """

    model_config = ConfigDict(json_encoders={datetime: lambda dt: dt.isoformat()})

    config: TunnelConfig
    status: TunnelStatus = TunnelStatus.STOPPED
    public_url: str | None = None
    server_pid: PositiveInt | None = None
    client_pid: PositiveInt | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    last_activity: datetime | None = None
    active_connections: int = Field(default=0, ge=0)
    total_connections: int = Field(default=0, ge=0)
    bytes_transferred: int = Field(default=0, ge=0)
    error_message: str | None = None


class ConnectionInfo(BaseModel):
    """
    Information about an active connection.
    Attributes:
        connection_id (str): Unique identifier for the connection.
        tunnel_id (str): Identifier of the tunnel this connection belongs to.
        remote_addr (str): Remote address of the client.
        local_addr (str): Local address of the server.
        protocol (TunnelProtocol): Protocol used for this connection.
        connected_at (datetime): Timestamp when the connection was established.
        last_activity (datetime): Timestamp of the last activity on this connection.
        bytes_sent (int): Total bytes sent through this connection.
        bytes_received (int): Total bytes received through this connection.
        is_active (bool): Whether the connection is currently active.
    """

    connection_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tunnel_id: str
    remote_addr: str
    local_addr: str
    protocol: TunnelProtocol
    connected_at: datetime = Field(default_factory=datetime.now)
    last_activity: datetime = Field(default_factory=datetime.now)
    bytes_sent: int = Field(default=0, ge=0)
    bytes_received: int = Field(default=0, ge=0)
    is_active: bool = True


class TunnelStats(BaseModel):
    """
    Statistics for a tunnel.
    Attributes:
        tunnel_id (str): Identifier of the tunnel.
        total_connections (int): Total number of connections made to the tunnel.
        active_connections (int): Number of currently active connections.
        bytes_transferred (int): Total bytes transferred through the tunnel.
        uptime_seconds (float): Uptime of the tunnel in seconds.
        error_count (int): Number of errors encountered by the tunnel.
        last_error (Optional[str]): Last error message if any error occurred.
        performance_metrics (Dict[str, PositiveFloat]): Performance metrics for the tunnel.
    """

    tunnel_id: str
    total_connections: int = Field(default=0, ge=0)
    active_connections: int = Field(default=0, ge=0)
    bytes_transferred: int = Field(default=0, ge=0)
    uptime_seconds: float = Field(default=0.0, ge=0.0)
    error_count: PositiveInt = 0
    last_error: str | None = None
    performance_metrics: dict[str, PositiveFloat] = Field(default_factory=dict)
