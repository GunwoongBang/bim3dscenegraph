"""
BIM2GRAPH - Convert IFC models to an integrated Neo4j property graph.
"""

from query_manager import QueryManager
from .graph_builder import bim2graph
from .persistence import Neo4jOperations

__all__ = [
    'bim2graph',
    "QueryManager",
    "Neo4jOperations",
]
