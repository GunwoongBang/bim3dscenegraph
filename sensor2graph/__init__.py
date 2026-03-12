"""
SENSOR2GRAPH - Convert IFC models to 3D scene graph.

This package provides tools for extracting sensor-derived information from IFC files.

Main entry point:


Package structure:
"""

from .graph_builder import sensor2graph
# from .query_manager import QueryManager
# from .persistence import Neo4jOperations

__version__ = "0.1.0"

__all__ = [
    "sensor2graph",
    "QueryManager",
    "Neo4jOperations",
]
