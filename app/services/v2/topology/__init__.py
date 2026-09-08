"""
app/services/v2/topology/__init__.py
-----------------------------------
Cadastral topology validation subsystem.
"""

from app.services.v2.topology.cleanup import (
    TopologyReport,
    enforce_cadastral_topology,
    inspect_topology,
)
from app.services.v2.topology.engine import CadastralTopologyEngine

__all__ = [
    "CadastralTopologyEngine",
    "TopologyReport",
    "enforce_cadastral_topology",
    "inspect_topology",
]
