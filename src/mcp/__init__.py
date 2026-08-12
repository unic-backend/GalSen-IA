"""
MCP : serveur d'abord, client ensuite (VOLET 34, ch. 09 ; ADR-017 §6).

Être appelé garde le risque de notre côté — nous authentifions, nous autorisons,
nous journalisons. Être client charge les descriptions d'outils d'autrui dans
notre invite, ce qui est la vulnérabilité MCP la plus documentée.
"""

from .client import (
    PinnedServer,
    ServerNotPinned,
    ToolDescription,
    inspect_description,
    pinned_servers,
    require_pinned,
)
from .exposure import OUTILS_EXPOSES, expose, refusal_reason
from .server import MCPServer

__all__ = [
    "OUTILS_EXPOSES",
    "MCPServer",
    "PinnedServer",
    "ServerNotPinned",
    "ToolDescription",
    "expose",
    "inspect_description",
    "pinned_servers",
    "refusal_reason",
    "require_pinned",
]
