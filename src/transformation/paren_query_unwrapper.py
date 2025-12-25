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
        import logging
        logger = logging.getLogger('chronosproxy.transform')

        # Strip all leading/trailing whitespace
        sql_stripped = sql.strip()

        # Normalize internal whitespace (collapse multiple spaces/newlines to single space)
        sql_normalized = ' '.join(sql_stripped.split())

        logger.debug(f"ParenthesizedQueryUnwrapper.needs_unwrapping: Original length={len(sql)}")
        logger.debug(f"ParenthesizedQueryUnwrapper.needs_unwrapping: Normalized length={len(sql_normalized)}")
        logger.debug(f"ParenthesizedQueryUnwrapper.needs_unwrapping: Normalized first 100 chars: {sql_normalized[:100]}")
        logger.debug(f"ParenthesizedQueryUnwrapper.needs_unwrapping: Starts with '(': {sql_normalized.startswith('(')}")

        # Simple check: starts with ( and contains SELECT
        if not sql_normalized.startswith('('):
            logger.debug("ParenthesizedQueryUnwrapper: Does not start with '(', skipping")
            return False

        if 'SELECT' not in sql_normalized.upper():
            logger.debug("ParenthesizedQueryUnwrapper: Does not contain SELECT, skipping")
            return False

        # Pattern 1: (SELECT ...) LIMIT N
        pattern1_match = re.match(r'^\(SELECT\s+.*\)\s+LIMIT\s+\d+$', sql_normalized, re.IGNORECASE)
        if pattern1_match:
            logger.debug("ParenthesizedQueryUnwrapper: Matched pattern 1 (SELECT ...) LIMIT N")
            return True

        # Pattern 2: Just parentheses around SELECT
        pattern2_match = re.match(r'^\(SELECT\s+.*\)$', sql_normalized, re.IGNORECASE)
        if pattern2_match:
            logger.debug("ParenthesizedQueryUnwrapper: Matched pattern 2 (SELECT ...)")
            return True

        logger.debug("ParenthesizedQueryUnwrapper: No pattern matched")
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
        import logging
        logger = logging.getLogger('chronosproxy.transform')

        # Strip and normalize whitespace
        sql_stripped = sql.strip()
        sql_normalized = ' '.join(sql_stripped.split())

        logger.debug(f"ParenthesizedQueryUnwrapper.unwrap: Attempting to unwrap SQL")
        logger.debug(f"ParenthesizedQueryUnwrapper.unwrap: Normalized SQL: {sql_normalized[:200]}")

        # Pattern 1: (SELECT ...) LIMIT N
        match = re.match(
            r'^\((SELECT\s+.+)\)\s+(LIMIT\s+\d+)$',
            sql_normalized,
            re.IGNORECASE
        )
        if match:
            inner_query = match.group(1).strip()
            limit_clause = match.group(2).strip()
            unwrapped = f"{inner_query} {limit_clause}"
            logger.debug(f"ParenthesizedQueryUnwrapper.unwrap: Pattern 1 matched, unwrapped length={len(unwrapped)}")
            logger.debug(f"ParenthesizedQueryUnwrapper.unwrap: Result=>>>{unwrapped}<<<")
            return unwrapped

        # Pattern 2: Just (SELECT ...)
        match = re.match(
            r'^\((SELECT\s+.+)\)$',
            sql_normalized,
            re.IGNORECASE
        )
        if match:
            inner_query = match.group(1).strip()
            logger.debug(f"ParenthesizedQueryUnwrapper.unwrap: Pattern 2 matched, unwrapped length={len(inner_query)}")
            logger.debug(f"ParenthesizedQueryUnwrapper.unwrap: Result=>>>{inner_query}<<<")
            return inner_query

        logger.debug("ParenthesizedQueryUnwrapper.unwrap: No pattern matched, returning None")
        return None
