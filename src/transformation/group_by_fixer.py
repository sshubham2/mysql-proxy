"""
GROUP BY Auto-Fixer
Automatically adds or completes GROUP BY clauses for aggregations
"""

from sqlglot import exp
from typing import List, Set, Tuple, Optional
from src.config.settings import Settings
from src.utils.sql_parser import SQLParser


class GroupByFixer:
    """Auto-fixes GROUP BY clauses"""

    def __init__(self, settings: Settings, sql_parser: SQLParser):
        """
        Initialize GROUP BY fixer

        Args:
            settings: Application settings
            sql_parser: SQL parser instance
        """
        self.settings = settings
        self.sql_parser = sql_parser
        self.enabled = settings.transformations.get('auto_fix_group_by', True)

    def fix(self, sql: str, ast: exp.Expression) -> Tuple[bool, Optional[str], Optional[exp.Expression], List[str]]:
        """
        Fix GROUP BY clause

        Args:
            sql: SQL query
            ast: Parsed SQL AST

        Returns:
            Tuple of (was_fixed, fixed_sql, fixed_ast, added_columns)
        """
        if not self.enabled:
            return False, None, None, []

        if not isinstance(ast, exp.Select):
            return False, None, None, []

        # Analyze SELECT clause
        select_columns = self._get_select_column_names(ast)
        aggregated_columns = self.sql_parser.get_aggregated_columns(ast)

        # Check if query has aggregations
        if not self._has_aggregations(ast):
            return False, None, None, []

        # Determine non-aggregated columns
        non_aggregated = []
        for col in select_columns:
            if col not in aggregated_columns and col != '*':
                non_aggregated.append(col)

        if not non_aggregated:
            # All columns are aggregated, no GROUP BY needed
            return False, None, None, []

        # Check existing GROUP BY
        group_by = ast.find(exp.Group)

        if group_by is None:
            # Add GROUP BY with all non-aggregated columns
            fixed_ast = self._add_group_by(ast, non_aggregated)
            fixed_sql = self.sql_parser.to_sql(fixed_ast)
            return True, fixed_sql, fixed_ast, non_aggregated
        else:
            # Check if GROUP BY is complete
            existing_cols = self._get_group_by_columns(group_by)
            missing_cols = [col for col in non_aggregated if col not in existing_cols]

            if missing_cols:
                # Add missing columns to GROUP BY
                fixed_ast = self._append_to_group_by(ast, group_by, missing_cols)
                fixed_sql = self.sql_parser.to_sql(fixed_ast)
                return True, fixed_sql, fixed_ast, missing_cols
            else:
                # GROUP BY is already complete
                return False, None, None, []

    def _has_aggregations(self, ast: exp.Select) -> bool:
        """
        Check if SELECT has aggregate functions

        Args:
            ast: SELECT statement

        Returns:
            True if has aggregations
        """
        agg_funcs = {exp.Sum, exp.Avg, exp.Max, exp.Min, exp.Count}

        for func in ast.find_all(exp.Func):
            if type(func) in agg_funcs:
                return True

        return False

    def _get_select_column_names(self, ast: exp.Select) -> List[str]:
        """
        Get column names (or expression strings) from SELECT

        Args:
            ast: SELECT statement

        Returns:
            List of column identifiers
        """
        columns = []

        for expression in ast.expressions:
            if isinstance(expression, exp.Star):
                columns.append('*')
            elif isinstance(expression, exp.Column):
                columns.append(expression.name)
            elif isinstance(expression, exp.Alias):
                # For aliases, use the original expression if it's a column
                if isinstance(expression.this, exp.Column):
                    columns.append(expression.this.name)
                else:
                    # For complex expressions, use full SQL
                    columns.append(expression.this.sql(dialect='mysql'))
            else:
                # For other expressions, use SQL representation
                columns.append(expression.sql(dialect='mysql'))

        return columns

    def _get_group_by_columns(self, group_by: exp.Group) -> Set[str]:
        """
        Get columns from existing GROUP BY clause

        Args:
            group_by: GROUP BY expression

        Returns:
            Set of column names
        """
        columns = set()

        for expression in group_by.expressions:
            if isinstance(expression, exp.Column):
                columns.add(expression.name)
            else:
                # For expressions, use full SQL
                columns.add(expression.sql(dialect='mysql'))

        return columns

    def _add_group_by(self, ast: exp.Select, columns: List[str]) -> exp.Select:
        """
        Add GROUP BY clause to SELECT

        Args:
            ast: SELECT statement
            columns: Columns to group by

        Returns:
            Modified AST
        """
        # Clone AST
        fixed = ast.copy()

        # Create GROUP BY expressions
        group_by_exprs = [exp.Column(this=col) for col in columns]

        # Add GROUP BY
        fixed = fixed.group_by(*group_by_exprs, copy=False)

        return fixed

    def _append_to_group_by(
        self,
        ast: exp.Select,
        group_by: exp.Group,
        columns: List[str]
    ) -> exp.Select:
        """
        Append columns to existing GROUP BY

        Args:
            ast: SELECT statement
            group_by: Existing GROUP BY expression
            columns: Columns to append

        Returns:
            Modified AST
        """
        # Clone AST
        fixed = ast.copy()

        # Get existing GROUP BY expressions
        existing_exprs = list(group_by.expressions)

        # Add new columns
        for col in columns:
            existing_exprs.append(exp.Column(this=col))

        # Replace GROUP BY
        fixed = fixed.group_by(*existing_exprs, copy=False)

        return fixed
