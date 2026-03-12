"""
BIM2GRAPH - Convert IFC models to an integrated Neo4j property graph.

Main entry point:

Package structure:
"""

from .graph_builder import bim2graph
from .query_manager import QueryManager
from .persistence import Neo4jOperations

__version__ = "0.1.0"

__all__ = [
    'bim2graph',
    "QueryManager",
    "Neo4jOperations",
]
