"""
Neo4j database operations for SENSOR graph persistence.
"""


class Neo4jOperations:
    """Handles all Neo4j CRUD operations for SENSOR data."""

    def __init__(self, query_manager, logger=None):
        """
        Initialize with a query manager.

        Args:
            query_manager: QueryManager instance for loading Cypher queries
            logger: Optional logger for output messages
        """
        self.qm = query_manager
        self.logger = logger

    def _log(self, message):
        """Log a message if logger is available."""
        if self.logger:
            self.logger.logText("SENSOR2GRAPH", message)
