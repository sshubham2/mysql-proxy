"""
COB Date Validator
Validates that queries include mandatory cob_date filter
"""

from sqlglot import exp
from src.config.settings import Settings
from src.utils.sql_parser import SQLParser
from src.utils.error_formatter import ErrorFormatter


class MissingCobDateError(Exception):
    """Exception raised when cob_date filter is missing"""

    def __init__(self, message: str):
        """
        Initialize exception

        Args:
            message: Error message
        """
        super().__init__(message)


class CobDateValidator:
    """Validates cob_date filter presence"""

    def __init__(self, settings: Settings, sql_parser: SQLParser):
        """
        Initialize validator

        Args:
            settings: Application settings
            sql_parser: SQL parser instance
        """
        self.settings = settings
        self.sql_parser = sql_parser
        self.require_cob_date = settings.business_rules.get('require_cob_date', True)

    def validate(self, sql: str, ast: exp.Expression):
        """
        Validate that query includes cob_date OR date_index filter

        Args:
            sql: SQL query
            ast: Parsed SQL AST

        Raises:
            MissingCobDateError: If neither cob_date nor date_index filter is present
        """
        if not self.require_cob_date:
            return

        # Only check SELECT queries
        if not isinstance(ast, exp.Select):
            return

        # Check if cob_date OR date_index is in WHERE clause
        has_cob_date = self.sql_parser.has_column_in_where(ast, 'cob_date')
        has_date_index = self.sql_parser.has_column_in_where(ast, 'date_index')

        if not has_cob_date and not has_date_index:
            error_msg = ErrorFormatter.format_missing_cob_date_error(sql)
            raise MissingCobDateError(error_msg)
