"""
Cypher query manager for loading and accessing queries from external files.
"""

import os


class QueryManager:
    """Loads and manages Cypher queries from external files."""

    def __init__(self, query_file=None):
        """
        Initialize the query manager by loading queries from a file.

        Args:
            query_file: Path to .cypher file. If None, uses default location.
        """
        if query_file is None:
            query_file = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "query_handler",
                "cypher4sensor.cypher"
            )
        self.query_file = query_file
        self.queries = self._load_queries(query_file)

    def _load_queries(self, path):
        """
        Parse a Cypher query file with -- name: labels.

        File format:
            -- name: QUERY_NAME
            CYPHER QUERY HERE;

            -- name: ANOTHER_QUERY
            ANOTHER CYPHER QUERY;

        Args:
            path: Path to the .cypher file

        Returns:
            Dictionary mapping query names to query strings
        """
        queries = {}
