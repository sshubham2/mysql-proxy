"""
INFORMATION_SCHEMA to SHOW Command Converter
Converts INFORMATION_SCHEMA queries to equivalent SHOW commands
for backends that don't support INFORMATION_SCHEMA
"""

from typing import Optional, Tuple, List
from sqlglot import parse_one, exp


class InformationSchemaConverter:
    """Convert INFORMATION_SCHEMA queries to SHOW commands"""

    @staticmethod
    def can_convert(sql: str) -> bool:
        """
        Check if query can be converted to SHOW command

        Args:
            sql: SQL query string

        Returns:
            True if convertible to SHOW
        """
        sql_upper = sql.upper()

        # Check for common INFORMATION_SCHEMA patterns
        convertible_patterns = [
            'INFORMATION_SCHEMA.TABLES',
            'INFORMATION_SCHEMA.COLUMNS',
            'INFORMATION_SCHEMA.SCHEMATA',
            'INFORMATION_SCHEMA.TABLE_CONSTRAINTS',
        ]

        return any(pattern in sql_upper for pattern in convertible_patterns)

    @staticmethod
    def convert_to_show(sql: str) -> Optional[str]:
        """
        Convert INFORMATION_SCHEMA query to equivalent SHOW command

        Args:
            sql: INFORMATION_SCHEMA query

        Returns:
            SHOW command string, or None if can't convert
        """
        try:
            ast = parse_one(sql, dialect='mysql')

            if not isinstance(ast, exp.Select):
                return None

            # Get the table being queried
            from_clause = ast.find(exp.From)
            if not from_clause:
                return None

            table = from_clause.find(exp.Table)
            if not table:
                return None

            table_name = table.name.upper()

            # Convert based on INFORMATION_SCHEMA table
            # Backend quirk: Supports INFORMATION_SCHEMA.SCHEMATA but NOT SHOW DATABASES
            # Backend quirk: Supports SHOW TABLES but NOT INFORMATION_SCHEMA.TABLES
            if 'TABLES' in table_name:
                # Convert INFORMATION_SCHEMA.TABLES → SHOW TABLES
                return InformationSchemaConverter._convert_tables_query(ast)
            elif 'COLUMNS' in table_name:
                # Convert INFORMATION_SCHEMA.COLUMNS → SHOW COLUMNS
                return InformationSchemaConverter._convert_columns_query(ast)
            elif 'SCHEMATA' in table_name:
                # DON'T convert - backend supports INFORMATION_SCHEMA.SCHEMATA natively
                # But doesn't support SHOW DATABASES
                # Return original SQL to send as-is
                return sql

            return None

        except Exception:
            return None

    @staticmethod
    def _convert_tables_query(ast: exp.Select) -> str:
        """
        Convert INFORMATION_SCHEMA.TABLES query to SHOW TABLES

        Examples:
            SELECT * FROM INFORMATION_SCHEMA.TABLES
            -> SHOW TABLES

            SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'mydb'
            -> SHOW TABLES FROM mydb
        """
        # Try to extract database from WHERE clause
        database = InformationSchemaConverter._extract_schema_from_where(ast)

        if database:
            return f"SHOW TABLES FROM {database}"
        else:
            return "SHOW TABLES"

    @staticmethod
    def _convert_columns_query(ast: exp.Select) -> Optional[str]:
        """
        Convert INFORMATION_SCHEMA.COLUMNS query to SHOW COLUMNS

        Examples:
            SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'users'
            -> SHOW COLUMNS FROM users

            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'mydb' AND TABLE_NAME = 'users'
            -> SHOW COLUMNS FROM mydb.users
        """
        # Check if WHERE clause has complex conditions we can't convert
        if InformationSchemaConverter._has_complex_where(ast):
            # Can't convert - will return empty result later
            return None

        # Extract table name from WHERE clause
        table_name = InformationSchemaConverter._extract_table_from_where(ast)
        database = InformationSchemaConverter._extract_schema_from_where(ast)

        if table_name:
            if database and database != '':
                return f"SHOW COLUMNS FROM {database}.{table_name}"
            else:
                return f"SHOW COLUMNS FROM {table_name}"
        else:
            # Can't determine table - can't convert
            return None

    @staticmethod
    def _has_complex_where(ast: exp.Select) -> bool:
        """
        Check if WHERE clause contains conditions we can't convert to SHOW

        Complex conditions include:
        - Filtering by DATA_TYPE (e.g., data_type='enum')
        - Filtering by COLUMN_NAME
        - Filtering by other metadata columns
        - Complex expressions

        Allowed:
        - TABLE_NAME, TABLE_SCHEMA filters
        - TABLE_TYPE filters (for TABLES queries only)
        """
        where = ast.find(exp.Where)
        if not where:
            return False

        # Get table being queried
        from_clause = ast.find(exp.From)
        if from_clause:
            table = from_clause.find(exp.Table)
            table_name = table.name.upper() if table else ""
        else:
            table_name = ""

        # Check for conditions on columns
        for node in where.find_all(exp.Column):
            col_name = node.name.upper()

            # For TABLES queries, TABLE_TYPE is allowed (BASE TABLE, VIEW)
            if 'TABLES' in table_name and col_name == 'TABLE_TYPE':
                continue

            # Only TABLE_NAME and TABLE_SCHEMA are convertible
            if col_name not in ('TABLE_NAME', 'TABLE_SCHEMA'):
                return True  # Has filter on other columns

        return False

    @staticmethod
    def _extract_schema_from_where(ast: exp.Select) -> Optional[str]:
        """Extract database/schema name from WHERE clause"""
        where = ast.find(exp.Where)
        if not where:
            return None

        # Look for TABLE_SCHEMA = 'database_name' or DATABASE() comparison
        for node in where.find_all(exp.EQ):
            left = node.left
            right = node.right

            # Check for TABLE_SCHEMA = 'value'
            if isinstance(left, exp.Column) and left.name.upper() == 'TABLE_SCHEMA':
                if isinstance(right, exp.Literal):
                    return right.this

            # Also check reversed: 'value' = TABLE_SCHEMA
            if isinstance(right, exp.Column) and right.name.upper() == 'TABLE_SCHEMA':
                if isinstance(left, exp.Literal):
                    return left.this

            # Check for TABLE_SCHEMA = DATABASE()
            if isinstance(right, exp.Anonymous) and right.name.upper() == 'DATABASE':
                # Use current database (proxy will track this)
                return None

        return None

    @staticmethod
    def _extract_table_from_where(ast: exp.Select) -> Optional[str]:
        """Extract table name from WHERE clause"""
        where = ast.find(exp.Where)
        if not where:
            return None

        # Look for TABLE_NAME = 'table_name'
        for node in where.find_all(exp.EQ):
            left = node.left
            right = node.right

            # Check for TABLE_NAME = 'value'
            if isinstance(left, exp.Column) and left.name.upper() == 'TABLE_NAME':
                if isinstance(right, exp.Literal):
                    return right.this

            # Also check reversed: 'value' = TABLE_NAME
            if isinstance(right, exp.Column) and right.name.upper() == 'TABLE_NAME':
                if isinstance(left, exp.Literal):
                    return left.this

        return None

    @staticmethod
    def convert_show_result_to_information_schema(
        show_command: str,
        rows: List[Tuple],
        columns: List[Tuple[str, str]]
    ) -> Tuple[List[Tuple], List[Tuple[str, str]]]:
        """
        Convert SHOW command result to INFORMATION_SCHEMA format

        Args:
            show_command: The SHOW command that was executed
            rows: Result rows from SHOW command
            columns: Column definitions from SHOW command

        Returns:
            Tuple of (converted_rows, converted_columns) matching INFORMATION_SCHEMA format
        """
        # For now, return as-is
        # TODO: Map SHOW TABLES columns to TABLE_NAME, TABLE_SCHEMA, etc.
        # TODO: Map SHOW COLUMNS columns to COLUMN_NAME, DATA_TYPE, etc.
        return rows, columns
