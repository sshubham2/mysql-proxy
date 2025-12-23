"""
SQL Parser Utilities
Wrapper around sqlglot for SQL parsing and AST manipulation
"""

import sqlglot
from sqlglot import exp, parse_one
from typing import List, Optional, Set, Tuple
from enum import Enum


class QueryType(Enum):
    """SQL Query types"""
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    CREATE = "CREATE"
    DROP = "DROP"
    ALTER = "ALTER"
    TRUNCATE = "TRUNCATE"
    SHOW = "SHOW"
    DESCRIBE = "DESCRIBE"
    USE = "USE"
    SET = "SET"
    UNKNOWN = "UNKNOWN"


class SQLParser:
    """SQL Parser wrapper for sqlglot"""

    def __init__(self, dialect: str = 'mysql'):
        """
        Initialize SQL parser

        Args:
            dialect: SQL dialect (default: mysql)
        """
        self.dialect = dialect

    def parse(self, sql: str) -> exp.Expression:
        """
        Parse SQL query into AST

        Args:
            sql: SQL query string

        Returns:
            sqlglot Expression (AST root)

        Raises:
            sqlglot.errors.ParseError: If query is invalid
        """
        return parse_one(sql, dialect=self.dialect)

    def get_query_type(self, sql: str) -> QueryType:
        """
        Determine query type from SQL string

        Args:
            sql: SQL query string

        Returns:
            QueryType enum
        """
        # Simple keyword-based detection (fast)
        first_keyword = sql.strip().split()[0].upper() if sql.strip() else ""

        try:
            return QueryType(first_keyword)
        except ValueError:
            return QueryType.UNKNOWN

    def is_metadata_query(self, sql: str) -> bool:
        """
        Check if query is a metadata query (SHOW, DESCRIBE, USE, SET, etc.)

        Args:
            sql: SQL query string

        Returns:
            True if metadata query
        """
        query_type = self.get_query_type(sql)
        metadata_types = {QueryType.SHOW, QueryType.DESCRIBE, QueryType.USE, QueryType.SET}
        return query_type in metadata_types

    def has_joins(self, ast: exp.Expression) -> Tuple[bool, List[str]]:
        """
        Check if query contains JOINs

        Args:
            ast: Parsed SQL AST

        Returns:
            Tuple of (has_joins, list of join types found)
        """
        join_types = []

        for join in ast.find_all(exp.Join):
            # Determine join type
            if join.side:
                join_types.append(f"{join.side.upper()} JOIN")
            elif join.kind:
                join_types.append(f"{join.kind.upper()} JOIN")
            else:
                join_types.append("INNER JOIN")

        return len(join_types) > 0, join_types

    def has_unions(self, ast: exp.Expression) -> Tuple[bool, int]:
        """
        Check if query contains UNIONs

        Args:
            ast: Parsed SQL AST

        Returns:
            Tuple of (has_unions, count of unions)
        """
        unions = list(ast.find_all(exp.Union))
        return len(unions) > 0, len(unions)

    def has_window_functions(self, ast: exp.Expression) -> Tuple[bool, List[str]]:
        """
        Check if query contains window functions

        Args:
            ast: Parsed SQL AST

        Returns:
            Tuple of (has_window_functions, list of window function names)
        """
        window_funcs = []

        # Look for OVER clause (indicates window function)
        for node in ast.find_all(exp.Window):
            # Get the function name
            if isinstance(node.parent, exp.Func):
                window_funcs.append(node.parent.sql_name().upper())

        return len(window_funcs) > 0, window_funcs

    def has_function(self, ast: exp.Expression, function_names: List[str]) -> Tuple[bool, List[str]]:
        """
        Check if query contains specific functions

        Args:
            ast: Parsed SQL AST
            function_names: List of function names to check (e.g., ['COUNT'])

        Returns:
            Tuple of (has_function, list of found functions)
        """
        found_funcs = []
        function_names_upper = [f.upper() for f in function_names]

        for func in ast.find_all(exp.Func):
            func_name = func.sql_name().upper()
            if func_name in function_names_upper:
                found_funcs.append(func_name)

        return len(found_funcs) > 0, found_funcs

    def has_subqueries(self, ast: exp.Expression) -> Tuple[bool, int]:
        """
        Check if query contains subqueries

        Args:
            ast: Parsed SQL AST

        Returns:
            Tuple of (has_subqueries, count of subqueries)
        """
        subqueries = list(ast.find_all(exp.Subquery))
        return len(subqueries) > 0, len(subqueries)

    def get_subquery_depth(self, ast: exp.Expression) -> int:
        """
        Calculate maximum subquery nesting depth

        Args:
            ast: Parsed SQL AST

        Returns:
            Maximum nesting depth (0 = no subqueries)
        """
        max_depth = 0

        def count_depth(node: exp.Expression, current_depth: int = 0):
            nonlocal max_depth
            if isinstance(node, exp.Subquery):
                current_depth += 1
                max_depth = max(max_depth, current_depth)

            for child in node.iter_expressions():
                count_depth(child, current_depth)

        count_depth(ast)
        return max_depth

    def get_select_columns(self, ast: exp.Expression) -> List[str]:
        """
        Extract column names from SELECT clause

        Args:
            ast: Parsed SQL AST (must be SELECT)

        Returns:
            List of column names (or expressions)
        """
        if not isinstance(ast, exp.Select):
            return []

        columns = []
        for expression in ast.expressions:
            if isinstance(expression, exp.Alias):
                # Use alias name
                columns.append(expression.alias)
            elif isinstance(expression, exp.Column):
                # Use column name
                columns.append(expression.name)
            else:
                # For complex expressions, use SQL representation
                columns.append(expression.sql(dialect=self.dialect))

        return columns

    def get_aggregated_columns(self, ast: exp.Expression) -> Set[str]:
        """
        Get columns that are inside aggregate functions

        Args:
            ast: Parsed SQL AST

        Returns:
            Set of column names used in aggregates
        """
        aggregated = set()

        # Common aggregate functions
        agg_funcs = {exp.Sum, exp.Avg, exp.Max, exp.Min, exp.Count}

        for func in ast.find_all(exp.Func):
            if type(func) in agg_funcs:
                # Find all columns inside this aggregate
                for col in func.find_all(exp.Column):
                    aggregated.add(col.name)

        return aggregated

    def has_column_in_where(self, ast: exp.Expression, column_name: str) -> bool:
        """
        Check if a specific column is referenced in WHERE clause

        Args:
            ast: Parsed SQL AST
            column_name: Column name to search for

        Returns:
            True if column found in WHERE clause
        """
        if not isinstance(ast, exp.Select):
            return False

        where = ast.find(exp.Where)
        if not where:
            return False

        for col in where.find_all(exp.Column):
            if col.name.lower() == column_name.lower():
                return True

        return False

    def to_sql(self, ast: exp.Expression) -> str:
        """
        Convert AST back to SQL string

        Args:
            ast: Parsed SQL AST

        Returns:
            SQL string
        """
        return ast.sql(dialect=self.dialect, pretty=False)
