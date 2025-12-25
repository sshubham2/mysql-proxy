"""
Subquery Unwrapper
Flattens Tableau's subquery wrapper patterns into simple SELECT statements
"""

from sqlglot import exp
from typing import Optional, Tuple
from src.config.settings import Settings
from src.utils.sql_parser import SQLParser
from src.utils.error_formatter import ErrorFormatter


class SubqueryTooComplex(Exception):
    """Exception raised when subquery cannot be unwrapped"""

    def __init__(self, message: str):
        """
        Initialize exception

        Args:
            message: Error message
        """
        super().__init__(message)


class SubqueryUnwrapper:
    """Unwraps and flattens subquery patterns"""

    def __init__(self, settings: Settings, sql_parser: SQLParser):
        """
        Initialize unwrapper

        Args:
            settings: Application settings
            sql_parser: SQL parser instance
        """
        self.settings = settings
        self.sql_parser = sql_parser
        self.enabled = settings.transformations.get('unwrap_subqueries', True)
        self.max_depth = settings.transformations.get('max_subquery_depth', 2)

    def unwrap(self, sql: str, ast: exp.Expression) -> Tuple[bool, Optional[str], Optional[exp.Expression]]:
        """
        Attempt to unwrap subquery

        Args:
            sql: Original SQL query
            ast: Parsed SQL AST

        Returns:
            Tuple of (was_unwrapped, unwrapped_sql, unwrapped_ast)

        Raises:
            SubqueryTooComplex: If query is too complex to unwrap
        """
        # Debug logging
        import logging
        logger = logging.getLogger('chronosproxy.transform')
        logger.debug(f"SubqueryUnwrapper.unwrap() called, enabled={self.enabled}, AST type={type(ast).__name__}")

        if not self.enabled:
            return False, None, None

        if not isinstance(ast, exp.Select):
            return False, None, None

        # Check if this matches Tableau pattern: SELECT * FROM (SELECT ...) subquery_alias
        unwrapped_ast = self._unwrap_tableau_pattern(ast)

        if unwrapped_ast is None:
            logger.debug("SubqueryUnwrapper: Pattern doesn't match Tableau pattern, not unwrapping")
            return False, None, None

        logger.debug("SubqueryUnwrapper: Matched Tableau pattern, unwrapping...")

        # Check final depth
        final_depth = self.sql_parser.get_subquery_depth(unwrapped_ast)
        if final_depth > self.max_depth:
            error_msg = ErrorFormatter.format_complex_subquery_error(
                sql, final_depth, self.max_depth
            )
            raise SubqueryTooComplex(error_msg)

        # Convert back to SQL
        unwrapped_sql = self.sql_parser.to_sql(unwrapped_ast)
        logger.debug(f"SubqueryUnwrapper: Unwrapped SQL length={len(unwrapped_sql)}, SQL=>>>{unwrapped_sql}<<<")

        return True, unwrapped_sql, unwrapped_ast

    def _unwrap_tableau_pattern(self, ast: exp.Select) -> Optional[exp.Select]:
        """
        Unwrap Tableau subquery pattern:
        - SELECT * FROM (SELECT ...) alias
        - SELECT alias.col1, alias.col2 FROM (SELECT ...) alias

        Args:
            ast: Outer SELECT statement

        Returns:
            Unwrapped AST or None if pattern doesn't match
        """
        import logging
        logger = logging.getLogger('chronosproxy.transform')

        # Check if FROM clause has exactly one subquery
        from_clause = ast.find(exp.From)
        if not from_clause:
            logger.debug("_unwrap_tableau_pattern: No FROM clause")
            return None

        # Get subquery from FROM
        subquery = None
        for table in from_clause.find_all(exp.Subquery):
            if subquery is not None:
                # Multiple subqueries, too complex
                logger.debug("_unwrap_tableau_pattern: Multiple subqueries, too complex")
                return None
            subquery = table

        if subquery is None:
            logger.debug("_unwrap_tableau_pattern: No subquery found")
            return None

        # Get inner SELECT
        inner_select = subquery.this
        if not isinstance(inner_select, exp.Select):
            logger.debug("_unwrap_tableau_pattern: Subquery is not a SELECT")
            return None

        # Pattern 1: SELECT * FROM (subquery)
        if self._is_select_star(ast):
            logger.debug("_unwrap_tableau_pattern: Pattern 1 (SELECT *) matched")
            # Clone inner SELECT for modification
            unwrapped = inner_select.copy()
        # Pattern 2: SELECT alias.col1, alias.col2 FROM (subquery) alias
        # Check if all selected columns reference the subquery alias
        elif subquery.alias and self._all_columns_from_alias(ast, subquery.alias):
            logger.debug(f"_unwrap_tableau_pattern: Pattern 2 (SELECT alias.cols) matched, alias='{subquery.alias}'")
            # Clone inner SELECT for modification
            unwrapped = inner_select.copy()
        else:
            logger.debug("_unwrap_tableau_pattern: No pattern matched")
            return None

        # Merge outer WHERE into inner WHERE (if exists)
        outer_where = ast.find(exp.Where)
        if outer_where:
            inner_where = unwrapped.find(exp.Where)
            if inner_where:
                # Combine with AND
                combined = exp.And(
                    this=inner_where.this,
                    expression=outer_where.this
                )
                unwrapped = unwrapped.where(combined, copy=False)
            else:
                # Add outer WHERE
                unwrapped = unwrapped.where(outer_where.this, copy=False)

        # Merge outer ORDER BY into inner ORDER BY
        outer_order = ast.find(exp.Order)
        if outer_order and not unwrapped.find(exp.Order):
            unwrapped.set('order', outer_order)

        # Merge outer LIMIT into inner LIMIT (use minimum if both exist)
        outer_limit = ast.find(exp.Limit)
        if outer_limit:
            inner_limit = unwrapped.find(exp.Limit)
            if inner_limit:
                # Use minimum
                outer_val = self._get_limit_value(outer_limit)
                inner_val = self._get_limit_value(inner_limit)
                if outer_val is not None and inner_val is not None:
                    min_val = min(outer_val, inner_val)
                    unwrapped.set('limit', exp.Limit(expression=exp.Literal.number(min_val)))
            else:
                # Add outer LIMIT
                unwrapped.set('limit', outer_limit)

        return unwrapped

    def _is_select_star(self, ast: exp.Select) -> bool:
        """
        Check if SELECT clause is SELECT *

        Args:
            ast: SELECT statement

        Returns:
            True if SELECT *
        """
        if not ast.expressions:
            return False

        # Check if single expression and it's a Star
        if len(ast.expressions) == 1:
            expr = ast.expressions[0]
            if isinstance(expr, exp.Star):
                return True

        return False

    def _all_columns_from_alias(self, ast: exp.Select, alias_name: str) -> bool:
        """
        Check if all selected columns reference a specific table alias

        Args:
            ast: SELECT statement
            alias_name: Table alias to check

        Returns:
            True if all columns are from the specified alias
        """
        import logging
        logger = logging.getLogger('chronosproxy.transform')

        if not ast.expressions:
            logger.debug("_all_columns_from_alias: No expressions")
            return False

        # Check each selected expression
        for expr in ast.expressions:
            # Handle aliased columns: col AS alias
            actual_expr = expr.this if isinstance(expr, exp.Alias) else expr

            # Check if it's a column reference
            if isinstance(actual_expr, exp.Column):
                # Check if column has a table reference
                if actual_expr.table:
                    # Compare table name (case-insensitive)
                    if actual_expr.table.lower() != alias_name.lower():
                        logger.debug(f"_all_columns_from_alias: Column {actual_expr} references different table '{actual_expr.table}'")
                        return False
                else:
                    # Column without table reference - could be from anywhere
                    logger.debug(f"_all_columns_from_alias: Column {actual_expr} has no table reference")
                    # For now, be lenient and allow it
                    pass
            else:
                # Not a simple column reference (could be expression)
                logger.debug(f"_all_columns_from_alias: Expression is not a Column: {type(actual_expr).__name__}")
                # For now, be lenient and allow it
                pass

        logger.debug(f"_all_columns_from_alias: All columns reference alias '{alias_name}'")
        return True

    def _get_limit_value(self, limit: exp.Limit) -> Optional[int]:
        """
        Extract numeric value from LIMIT clause

        Args:
            limit: LIMIT expression

        Returns:
            Limit value or None
        """
        if limit.expression:
            if isinstance(limit.expression, exp.Literal):
                try:
                    return int(limit.expression.this)
                except:
                    pass

        return None
