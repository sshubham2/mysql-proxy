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
        if not self.enabled:
            return False, None, None

        if not isinstance(ast, exp.Select):
            return False, None, None

        # Check if this matches Tableau pattern: SELECT * FROM (SELECT ...) subquery_alias
        unwrapped_ast = self._unwrap_tableau_pattern(ast)

        if unwrapped_ast is None:
            return False, None, None

        # Check final depth
        final_depth = self.sql_parser.get_subquery_depth(unwrapped_ast)
        if final_depth > self.max_depth:
            error_msg = ErrorFormatter.format_complex_subquery_error(
                sql, final_depth, self.max_depth
            )
            raise SubqueryTooComplex(error_msg)

        # Convert back to SQL
        unwrapped_sql = self.sql_parser.to_sql(unwrapped_ast)

        return True, unwrapped_sql, unwrapped_ast

    def _unwrap_tableau_pattern(self, ast: exp.Select) -> Optional[exp.Select]:
        """
        Unwrap Tableau subquery pattern: SELECT * FROM (SELECT ...) alias

        Args:
            ast: Outer SELECT statement

        Returns:
            Unwrapped AST or None if pattern doesn't match
        """
        # Check if SELECT *
        if not self._is_select_star(ast):
            return None

        # Check if FROM clause has exactly one subquery
        from_clause = ast.find(exp.From)
        if not from_clause:
            return None

        # Get subquery from FROM
        subquery = None
        for table in from_clause.find_all(exp.Subquery):
            if subquery is not None:
                # Multiple subqueries, too complex
                return None
            subquery = table

        if subquery is None:
            return None

        # Get inner SELECT
        inner_select = subquery.this
        if not isinstance(inner_select, exp.Select):
            return None

        # Clone inner SELECT for modification
        unwrapped = inner_select.copy()

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
