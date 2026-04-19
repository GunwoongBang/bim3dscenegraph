"""
Neo4j database operations for BIM graph persistence.
"""


class Neo4jOperations:
    """Handles all Neo4j CRUD operations for BIM data."""

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
            self.logger.logText("BIM2GRAPH", message)

    # tx: A transaction object passed from the session context
    # A transaction ensures that a group of operations is executed as a single unit
    # If all operations succeed, changes are commited
    # If any operation fails, everything is rolled back to maintain data integrity
    def reset_database(self, tx):
        """Delete all nodes and relationships from the database."""
        q = self.qm.get("RESET_DATABASE")
        if q:
            tx.run(q)
        self._log("Database reset")

    def retrieve_wall_attr(self, tx, wall_id):
        """Retrieve attributes of a wall by its ID."""
        q = self.qm.get("RETRIEVE_WALL_ATTRIBUTES")
        if q:
            result = tx.run(q, element_id=wall_id)
            return result.single()
        self._log(f"Retrieved attributes for Wall with ID: {wall_id}")
        return None
