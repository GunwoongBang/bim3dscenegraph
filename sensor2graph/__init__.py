"""
SENSOR2GRAPH - Merge point cloud data with BIM graph to create a 3D scene graph.

Main entry point:

Package structure:
- graph_builder.py: Main orchestrator for SENSOR2GRAPH pipeline
- worker/: Contains point cloud processing functions
- query_manager.py: Manages Neo4j queries for graph persistence
"""

from .graph_builder import sensor2graph
from .query_manager import QueryManager
from .persistence import Neo4jOperations


__version__ = "0.1.0"

__all__ = [
    "sensor2graph",
    "QueryManager",
    "Neo4jOperations",
]
