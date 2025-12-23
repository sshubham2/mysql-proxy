"""
Unsupported Feature Detector
Detects unsupported SQL features (JOINs, UNIONs, window functions, etc.)
"""

from sqlglot import exp
from typing import Optional
from src.config.settings import Settings
from src.utils.sql_parser import SQLParser
from src.utils.error_formatter import ErrorFormatter


class UnsupportedFeatureDetected(Exception):
    """Exception raised when unsupported feature is detected"""

    def __init__(self, feature: str, message: str):
        """
        Initialize exception

        Args:
            feature: Unsupported feature name
            message: Error message
        """
        self.feature = feature
        super().__init__(message)


class UnsupportedDetector:
    """Detects unsupported SQL features"""

    def __init__(self, settings: Settings, sql_parser: SQLParser):
        """
        Initialize detector

        Args:
            settings: Application settings
            sql_parser: SQL parser instance
        """
        self.settings = settings
        self.sql_parser = sql_parser

    def check_query(self, sql: str, ast: exp.Expression):
        """
        Check query for unsupported features

        Args:
            sql: Original SQL query
            ast: Parsed SQL AST

        Raises:
            UnsupportedFeatureDetected: If unsupported feature found
        """
        # Check for JOINs
        if self.settings.is_unsupported_feature('joins'):
            self._check_joins(sql, ast)

        # Check for UNIONs
        if self.settings.is_unsupported_feature('unions'):
            self._check_unions(sql, ast)

        # Check for window functions
        if self.settings.is_unsupported_feature('window_functions'):
            self._check_window_functions(sql, ast)

        # Check for unsupported functions
        self._check_unsupported_functions(sql, ast)

    def _check_joins(self, sql: str, ast: exp.Expression):
        """Check for JOINs"""
        has_joins, join_types = self.sql_parser.has_joins(ast)

        if has_joins:
            error_msg = ErrorFormatter.format_join_error(sql, join_types)
            raise UnsupportedFeatureDetected('joins', error_msg)

    def _check_unions(self, sql: str, ast: exp.Expression):
        """Check for UNIONs"""
        has_unions, union_count = self.sql_parser.has_unions(ast)

        if has_unions:
            error_msg = ErrorFormatter.format_union_error(sql, union_count)
            raise UnsupportedFeatureDetected('unions', error_msg)

    def _check_window_functions(self, sql: str, ast: exp.Expression):
        """Check for window functions"""
        has_window, window_funcs = self.sql_parser.has_window_functions(ast)

        if has_window:
            error_msg = ErrorFormatter.format_window_function_error(sql, window_funcs)
            raise UnsupportedFeatureDetected('window_functions', error_msg)

    def _check_unsupported_functions(self, sql: str, ast: exp.Expression):
        """Check for unsupported functions"""
        unsupported_funcs = self.settings.capabilities.get('unsupported_functions', [])

        if unsupported_funcs:
            has_func, found_funcs = self.sql_parser.has_function(ast, unsupported_funcs)

            if has_func:
                error_msg = ErrorFormatter.format_unsupported_function_error(sql, found_funcs)
                raise UnsupportedFeatureDetected('unsupported_function', error_msg)
