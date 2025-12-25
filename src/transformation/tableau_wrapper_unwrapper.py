"""
Tableau Wrapper Unwrapper
Unwraps Tableau's custom SQL query wrapper: SELECT * FROM (query) `alias`
"""

from sqlglot import exp, parse_one
from typing import Optional, Tuple


class TableauWrapperUnwrapper:
    """Unwrap Tableau custom SQL query wrappers"""

    @staticmethod
    def needs_unwrapping(sql: str) -> bool:
        """
        Check if query is a Tableau custom SQL wrapper

        Pattern: SELECT * FROM (<subquery>) `Custom SQL Query`
        Or: SELECT * FROM (<subquery>) alias_name

        Args:
            sql: SQL query

        Returns:
            True if this is a Tableau wrapper
        """
        try:
            ast = parse_one(sql, dialect='mysql')

            if not isinstance(ast, exp.Select):
                return False

            # Check if SELECT *
            select_expressions = ast.expressions
            if len(select_expressions) != 1:
                return False

            if not isinstance(select_expressions[0], exp.Star):
                return False

            # Check if FROM has only one subquery
            from_clause = ast.find(exp.From)
            if not from_clause:
                return False

            # Check if it's a subquery
            subquery = from_clause.find(exp.Subquery)
            if not subquery:
                return False

            # This is SELECT * FROM (subquery)
            return True

        except Exception:
            return False

    @staticmethod
    def unwrap(sql: str) -> Optional[str]:
        """
        Unwrap Tableau custom SQL query

        Transforms: SELECT * FROM (<inner_query>) `alias`
        To: <inner_query>

        Args:
            sql: Tableau wrapped query

        Returns:
            Unwrapped inner query, or None if can't unwrap
        """
        try:
            ast = parse_one(sql, dialect='mysql')

            if not isinstance(ast, exp.Select):
                return None

            # Get the subquery
            from_clause = ast.find(exp.From)
            if not from_clause:
                return None

            subquery = from_clause.find(exp.Subquery)
            if not subquery:
                return None

            # Get the inner query
            inner_ast = subquery.this

            # Convert back to SQL
            return inner_ast.sql(dialect='mysql')

        except Exception:
            return None
