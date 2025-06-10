"""Loco - Lightning-fast localhost tunneling."""

__version__ = "0.1.0"
__author__ = "Daniel Brai"
__email__ = "danielbrai.dev@gmail.com"
__description__ = "Lightning-fast localhost tunneling that's anything but crazy"
__package_name__ = "loco"
__package__ = "loco.cli"

LOCO_ASCII_ART = r"""
     _
    | |
    | | ___   ___ ___
    | |/ _ \ / __/ _ \
    | | (_) | (_| (_) |
    |_|\___/ \___\___/

Lightning-fast localhost tunneling
that's anything but crazy.

    VERSION {version}
"""


def get_version() -> str:
    """Get the current version of loco."""
    return __version__


def get_ascii_banner() -> str:
    """Get the ASCII art banner with version."""
    return LOCO_ASCII_ART.format(version=__version__)
