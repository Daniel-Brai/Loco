"""
Data models for tunnel management.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

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
        name (str | None): Human-readable name for the tunnel.
        local_host (str): Local host to forward to (default: "127.0.0.1").
        local_port (PositiveInt): Local port to forward to.
        remote_host (str): Remote host to bind to (default: "0.0.0.0").
        remote_port (PositiveInt): Remote port to bind to.
        protocol (TunnelProtocol): Tunnel protocol (default: HTTP).
        subdomain (str | None): Custom subdomain for the tunnel.
        ssl_cert_path (str | None): Path to SSL certificate (optional).
        ssl_key_path (str | None): Path to SSL private key (optional).
        connection_timeout (PositiveFloat): Connection timeout in seconds (default: 30.0).
        max_connections (PositiveInt): Maximum concurrent connections (default: 100).
        buffer_size (PositiveInt): Buffer size for data transfer (default: 8192).
        created_at (datetime | None): Creation timestamp (default: current time).
        tags (list[str]): Tags for organization (default: empty list).
    """

    model_config = ConfigDict(
        str_strip_whitespace=True, validate_assignment=True, extra="forbid"
    )

    tunnel_id: str = Field(..., description="Unique identifier for the tunnel")
    name: str | None = Field(None, description="Human-readable name for the tunnel")
    local_host: str = Field(default="127.0.0.1", description="Local host to forward to")
    local_port: PositiveInt = Field(..., description="Local port to forward to")
    remote_host: str = Field(default="0.0.0.0", description="Remote host to bind to")
    remote_port: PositiveInt = Field(..., description="Remote port to bind to")
    protocol: TunnelProtocol = Field(
        default=TunnelProtocol.HTTP, description="Tunnel protocol"
    )
    subdomain: str | None = Field(None, description="Custom subdomain")
    ssl_cert_path: str | None = Field(None, description="Path to SSL certificate")
    ssl_key_path: str | None = Field(None, description="Path to SSL private key")
    connection_timeout: PositiveFloat = Field(
        default=30.0, description="Connection timeout in seconds"
    )
    max_connections: PositiveInt = Field(
        default=100, description="Maximum concurrent connections"
    )
    buffer_size: PositiveInt = Field(
        default=8192, description="Buffer size for data transfer"
    )
    created_at: datetime | None = Field(
        default_factory=lambda: datetime.now(), description="Creation timestamp"
    )
    tags: list[str] = Field(default_factory=list, description="Tags for organization")


class TunnelState(BaseModel):
    """
    Current state of a tunnel.
    Attributes:
        config (TunnelConfig): Configuration of the tunnel.
        status (TunnelStatus): Current status of the tunnel.
        created_at (datetime | None): Timestamp when the tunnel was created.
        started_at (datetime | None): Timestamp when the tunnel was started.
        stopped_at (datetime | None): Timestamp when the tunnel was stopped.
        last_activity (datetime | None): Timestamp of the last activity on the tunnel.
        public_url (str | None): Public URL for accessing the tunnel.
        error_message (str | None): Last error message if any.
        active_connections (int): Current number of active connections.
        total_connections (int): Total number of connections served by the tunnel.
        bytes_transferred (int): Total bytes transferred through the tunnel.
    """

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    config: TunnelConfig = Field(..., description="Tunnel configuration")
    status: TunnelStatus = Field(
        default=TunnelStatus.STOPPED, description="Current tunnel status"
    )
    created_at: datetime | None = Field(
        default_factory=lambda: datetime.now(), description="Creation timestamp"
    )
    started_at: datetime | None = Field(None, description="Start timestamp")
    stopped_at: datetime | None = Field(None, description="Stop timestamp")
    last_activity: datetime | None = Field(None, description="Last activity timestamp")
    public_url: str | None = Field(
        None, description="Public URL for accessing the tunnel"
    )
    error_message: str | None = Field(None, description="Last error message")
    active_connections: int = Field(default=0, description="Current active connections")
    total_connections: int = Field(default=0, description="Total connections served")
    bytes_transferred: int = Field(default=0, description="Total bytes transferred")


class ConnectionInfo(BaseModel):
    """
    Information about a connection.
    Attributes:
        remote_addr (str): Remote address of the connection.
        timestamp (datetime): Timestamp when the connection was established.
        method (str | None): HTTP method used in the request (if applicable).
        path (str | None): Request path (if applicable).
        user_agent (str | None): User agent string of the client.
    """

    remote_addr: str = Field(..., description="Remote address")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(), description="Connection timestamp"
    )
    method: str | None = Field(None, description="HTTP method")
    path: str | None = Field(None, description="Request path")
    user_agent: str | None = Field(None, description="User agent")


class TunnelStats(BaseModel):
    """
    Statistics for a tunnel.
    Attributes:
        tunnel_id (str): Unique identifier for the tunnel.
        uptime_seconds (float): Uptime in seconds.
        requests_per_minute (float): Average requests per minute.
        average_response_time (float): Average response time in milliseconds.
        error_rate (float): Error rate percentage.
        bandwidth_usage (int): Bandwidth usage in bytes.
    """

    tunnel_id: str = Field(..., description="Tunnel identifier")
    uptime_seconds: float = Field(default=0.0, description="Uptime in seconds")
    requests_per_minute: float = Field(default=0.0, description="Requests per minute")
    average_response_time: float = Field(
        default=0.0, description="Average response time"
    )
    error_rate: float = Field(default=0.0, description="Error rate percentage")
    bandwidth_usage: int = Field(default=0, description="Bandwidth usage in bytes")
