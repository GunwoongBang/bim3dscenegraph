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

    # tx: Transaction object passed from the session context
    #
    def reset_database(self, tx):
        """Delete all nodes and relationships from the database."""
        q = self.qm.get("RESET_DATABASE")
        if q:
            tx.run(q)
        self._log("Database reset")

    def ensure_schema(self, tx):
        """Create unique constraints for all node types."""
        schema_queries = [
            "ENSURE_SCHEMA_SPACES",
            "ENSURE_SCHEMA_WALLS",
            "ENSURE_SCHEMA_LAYERS",
            "ENSURE_SCHEMA_OPENINGS",
            "ENSURE_SCHEMA_MEP_SYSTEM",
            "ENSURE_SCHEMA_MEP_ELEMENT",
        ]
        for query_name in schema_queries:
            q = self.qm.get(query_name)
            if q:
                tx.run(q)
        self._log("Schema constraints created")

    def upsert_spaces(self, tx, spaces):
        """Create or update Space nodes in Neo4j."""
        q = self.qm.get("UPSERT_SPACES")
        if q:
            tx.run(q, spaces=spaces)
        self._log(f"Upserted {len(spaces)} Space nodes")

    def upsert_walls(self, tx, walls):
        """Create or update Wall nodes in Neo4j."""
        q = self.qm.get("UPSERT_WALLS")
        if q:
            tx.run(q, walls=walls)
        self._log(f"Upserted {len(walls)} Wall nodes")

    def upsert_layers(self, tx, layers):
        """Create or update Layer nodes in Neo4j."""
        q = self.qm.get("UPSERT_LAYERS")
        if q:
            tx.run(q, layers=layers)
        self._log(f"Upserted {len(layers)} Layer nodes")

    def upsert_openings(self, tx, openings):
        """Create or update Opening nodes in Neo4j."""
        q = self.qm.get("UPSERT_OPENINGS")
        if q:
            tx.run(q, openings=openings)
        self._log(f"Upserted {len(openings)} Opening nodes")

    def create_wall_layer_edges(self, tx, layers):
        """Create relationships between walls and their layers."""
        q = self.qm.get("CREATE_WALL_LAYER_EDGES")
        if q:
            tx.run(q, layers=layers)
        self._log(f"Created {len(layers)} Wall-Layer relationships")

    def create_wall_opening_edges(self, tx, edges):
        """Create relationships between walls and openings."""
        q = self.qm.get("CREATE_WALL_OPENING_EDGES")
        if q:
            tx.run(q, edges=edges)
        self._log(f"Created {len(edges)} Wall-Opening relationships")

    def create_space_wall_edges(self, tx, edges):
        """Create space-wall boundary relationships."""
        q = self.qm.get("CREATE_SPACE_WALL_EDGES")
        if q:
            tx.run(q, edges=edges)
        self._log(f"Created {len(edges)} Space-Wall relationships")

    def upsert_mep_elements(self, tx, mep_elements):
        """Create or update MEP element nodes in Neo4j."""
        q = self.qm.get("UPSERT_MEP_ELEMENTS")
        if q:
            tx.run(q, elements=mep_elements)
        self._log(f"Upserted {len(mep_elements)} MEPElement nodes")

    def upsert_mep_systems(self, tx, systems):
        """Create or update MEP system nodes in Neo4j."""
        q = self.qm.get("UPSERT_MEP_SYSTEMS")
        if q:
            tx.run(q, systems=systems)
        self._log(f"Upserted {len(systems)} MEP system nodes")

    def create_mep_wall_edges(self, tx, edges):
        """Create MEPElement-Wall relationships."""
        q = self.qm.get("CREATE_MEP_WALL_EDGES")
        if q:
            tx.run(q, edges=edges)
        self._log(f"Created {len(edges)} MEPElement-Wall relationships")

    def create_mep_system_mep_edges(self, tx, edges):
        """Create MEPSystem-MEPElement relationships."""
        q = self.qm.get("CREATE_MEP_SYSTEM_MEP_EDGES")
        if q:
            tx.run(q, edges=edges)
        self._log(f"Created {len(edges)} MEPSystem-MEPElement relationships")

    def create_mep_system_space_edges(self, tx, edges):
        """Create MEPSystem-Space relationships."""
        q = self.qm.get("CREATE_MEP_SYSTEM_SPACE_EDGES")
        if q:
            tx.run(q, edges=edges)
        self._log(f"Created {len(edges)} MEPSystem-Space relationships")
