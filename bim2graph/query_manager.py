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
                "cypher4bim.cypher"
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

        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"Warning: Could not load queries from {path}: {e}")
            return queries

        current = None
        buf = []

        for line in content.splitlines():
            if line.strip().startswith('-- name:'):
                if current:
                    queries[current] = '\n'.join(buf).strip()
                current = line.split(':', 1)[1].strip()
                buf = []
            else:
                buf.append(line)

        if current:
            queries[current] = '\n'.join(buf).strip()

        return queries

    def get(self, name):
        """
        Get a query by name.

        Args:
            name: Query name as defined in the .cypher file

        Returns:
            Query string, or None if not found
        """
        return self.queries.get(name)

    def list_queries(self):
        """
        List all available query names.

        Returns:
            List of query names
        """
        return list(self.queries.keys())
