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

        Pattern 1: SELECT * FROM (<subquery>) `Custom SQL Query`
        Pattern 2: SELECT alias.col1, alias.col2 FROM (<subquery>) alias

        Args:
            sql: SQL query

        Returns:
            True if this is a Tableau wrapper
        """
        import logging
        logger = logging.getLogger('chronosproxy.transform')

        try:
            ast = parse_one(sql, dialect='mysql')

            logger.debug(f"TableauWrapperUnwrapper.needs_unwrapping: AST type={type(ast).__name__}")

            if not isinstance(ast, exp.Select):
                logger.debug("TableauWrapperUnwrapper: Not a Select, skipping")
                return False

            # Check if FROM has only one subquery
            from_clause = ast.find(exp.From)
            if not from_clause:
                logger.debug("TableauWrapperUnwrapper: No FROM clause")
                return False

            # Check if it's a subquery
            subquery = from_clause.find(exp.Subquery)
            if not subquery:
                logger.debug("TableauWrapperUnwrapper: No subquery in FROM")
                return False

            # Check select expressions
            select_expressions = ast.expressions
            logger.debug(f"TableauWrapperUnwrapper: {len(select_expressions)} select expressions")

            # Pattern 1: SELECT *
            if len(select_expressions) == 1 and isinstance(select_expressions[0], exp.Star):
                logger.debug("TableauWrapperUnwrapper: Matched pattern 1 (SELECT *)")
                return True

            # Pattern 2: SELECT alias.col1, alias.col2, ... FROM (subquery) alias
            # All selected columns reference the subquery alias
            if subquery.alias:
                logger.debug(f"TableauWrapperUnwrapper: Subquery has alias '{subquery.alias}'")
                # This is SELECT cols FROM (subquery) alias - let SubqueryUnwrapper handle it
                logger.debug("TableauWrapperUnwrapper: Has subquery with alias, will let SubqueryUnwrapper handle it")
                return False

            logger.debug("TableauWrapperUnwrapper: No pattern matched")
            return False

        except Exception as e:
            logger.debug(f"TableauWrapperUnwrapper: Exception during parsing: {e}")
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
