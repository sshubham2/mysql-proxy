"""
Write Operation Blocker
Detects and blocks write operations (INSERT, UPDATE, DELETE, etc.)
"""

from src.config.settings import Settings
from src.utils.error_formatter import ErrorFormatter


class WriteOperationBlocked(Exception):
    """Exception raised when write operation is blocked"""

    def __init__(self, operation: str, message: str):
        """
        Initialize exception

        Args:
            operation: Blocked operation name
            message: Error message
        """
        self.operation = operation
        super().__init__(message)


class WriteBlocker:
    """Blocks write operations for security"""

    def __init__(self, settings: Settings):
        """
        Initialize write blocker

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.block_writes = settings.security.get('block_writes', True)

    def check_query(self, sql: str):
        """
        Check if query contains write operation

        Args:
            sql: SQL query

        Raises:
            WriteOperationBlocked: If write operation detected
        """
        if not self.block_writes:
            return

        # Get first keyword
        first_keyword = sql.strip().split()[0].upper() if sql.strip() else ""

        # Check if it's a write operation
        if self.settings.is_write_operation(first_keyword):
            error_msg = ErrorFormatter.format_write_operation_error(first_keyword)
            raise WriteOperationBlocked(first_keyword, error_msg)
