"""
Parenthesized Query Unwrapper
Handles queries like: (SELECT ...) LIMIT 0
Tableau sends these to discover schema without fetching data
"""

import re
from typing import Optional


class ParenthesizedQueryUnwrapper:
    """Unwrap parenthesized queries with LIMIT clause"""

    @staticmethod
    def needs_unwrapping(sql: str) -> bool:
        """
        Check if query is a parenthesized SELECT with outer LIMIT

        Pattern: (SELECT ...) LIMIT N
        Or: (SELECT ...) (whitespace/newline)

        Args:
            sql: SQL query

        Returns:
            True if this pattern matches
        """
        sql_stripped = sql.strip()

        # Pattern 1: (SELECT ...) LIMIT N
        if re.match(r'^\(SELECT\s+.*\)\s+LIMIT\s+\d+$', sql_stripped, re.IGNORECASE | re.DOTALL):
            return True

        # Pattern 2: Just parentheses around SELECT
        if re.match(r'^\(SELECT\s+.*\)$', sql_stripped, re.IGNORECASE | re.DOTALL):
            return True

        return False

    @staticmethod
    def unwrap(sql: str) -> Optional[str]:
        """
        Unwrap parenthesized query

        Transforms: (SELECT col1 FROM table WHERE ...) LIMIT 0
        To: SELECT col1 FROM table WHERE ... LIMIT 0

        Args:
            sql: Parenthesized query

        Returns:
            Unwrapped query, or None if can't unwrap
        """
        sql_stripped = sql.strip()

        # Pattern 1: (SELECT ...) LIMIT N
        match = re.match(
            r'^\((SELECT\s+.+)\)\s+(LIMIT\s+\d+)$',
            sql_stripped,
            re.IGNORECASE | re.DOTALL
        )
        if match:
            inner_query = match.group(1).strip()
            limit_clause = match.group(2).strip()
            return f"{inner_query} {limit_clause}"

        # Pattern 2: Just (SELECT ...)
        match = re.match(
            r'^\((SELECT\s+.+)\)$',
            sql_stripped,
            re.IGNORECASE | re.DOTALL
        )
        if match:
            inner_query = match.group(1).strip()
            return inner_query

        return None
