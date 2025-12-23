"""
Result Converter
Converts backend database results to MySQL protocol format
"""

from typing import List, Tuple, Any, Optional
import decimal
import datetime


class ResultConverter:
    """Converts backend results to MySQL protocol format"""

    @staticmethod
    def convert_row_value(value: Any) -> Any:
        """
        Convert a single value to MySQL-compatible format

        Args:
            value: Value from backend database

        Returns:
            MySQL-compatible value
        """
        if value is None:
            return None

        # Convert decimal to float (MySQL protocol uses double)
        if isinstance(value, decimal.Decimal):
            return float(value)

        # Convert date/time to string (MySQL protocol format)
        if isinstance(value, datetime.datetime):
            return value.strftime('%Y-%m-%d %H:%M:%S')

        if isinstance(value, datetime.date):
            return value.strftime('%Y-%m-%d')

        if isinstance(value, datetime.time):
            return value.strftime('%H:%M:%S')

        # Convert bytes to string (for CHAR/VARCHAR)
        if isinstance(value, bytes):
            return value.decode('utf-8', errors='replace')

        # Everything else passes through
        return value

    @staticmethod
    def convert_rows(rows: List[Tuple[Any, ...]]) -> List[Tuple[Any, ...]]:
        """
        Convert all rows to MySQL-compatible format

        Args:
            rows: List of row tuples from backend

        Returns:
            List of converted row tuples
        """
        return [
            tuple(ResultConverter.convert_row_value(val) for val in row)
            for row in rows
        ]

    @staticmethod
    def infer_column_type(value: Any) -> str:
        """
        Infer MySQL column type from value

        Args:
            value: Sample value

        Returns:
            MySQL type name
        """
        if value is None:
            return 'VARCHAR'

        if isinstance(value, bool):
            return 'TINYINT'

        if isinstance(value, int):
            return 'BIGINT'

        if isinstance(value, float) or isinstance(value, decimal.Decimal):
            return 'DOUBLE'

        if isinstance(value, datetime.datetime):
            return 'DATETIME'

        if isinstance(value, datetime.date):
            return 'DATE'

        if isinstance(value, datetime.time):
            return 'TIME'

        if isinstance(value, bytes):
            return 'BLOB'

        # Default to VARCHAR for strings and unknown types
        return 'VARCHAR'

    @staticmethod
    def create_column_definitions(
        column_names: List[str],
        sample_row: Optional[Tuple[Any, ...]] = None
    ) -> List[Tuple[str, str]]:
        """
        Create column definitions for MySQL protocol

        Args:
            column_names: List of column names
            sample_row: Sample row for type inference (optional)

        Returns:
            List of (column_name, column_type) tuples
        """
        if sample_row:
            return [
                (name, ResultConverter.infer_column_type(value))
                for name, value in zip(column_names, sample_row)
            ]
        else:
            # Default to VARCHAR if no sample
            return [(name, 'VARCHAR') for name in column_names]
