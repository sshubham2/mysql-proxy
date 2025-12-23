"""
Native MySQL Connection Pool
Alternative backend connection using mysql-connector-python
"""

import mysql.connector
from mysql.connector import pooling
from typing import List, Tuple, Any, Optional, Dict


class NativeConnectionPool:
    """Native MySQL connection pool"""

    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
        charset: str = 'utf8mb4',
        pool_size: int = 10,
        pool_name: str = 'chronos_pool'
    ):
        """
        Initialize native MySQL connection pool

        Args:
            host: MySQL server host
            port: MySQL server port
            database: Database name
            user: Username
            password: Password
            charset: Character set
            pool_size: Number of connections in pool
            pool_name: Pool name
        """
        self.pool_config = {
            'host': host,
            'port': port,
            'database': database,
            'user': user,
            'password': password,
            'charset': charset,
            'autocommit': True,
        }

        self.pool = pooling.MySQLConnectionPool(
            pool_name=pool_name,
            pool_size=pool_size,
            **self.pool_config
        )

    def execute_query(
        self,
        sql: str,
        params: Optional[Tuple[Any, ...]] = None
    ) -> Tuple[List[Tuple[str, str]], List[Tuple[Any, ...]]]:
        """
        Execute query and return results

        Args:
            sql: SQL query
            params: Query parameters (optional)

        Returns:
            Tuple of (column_definitions, rows)

        Raises:
            mysql.connector.Error: If query execution fails
        """
        conn = self.pool.get_connection()

        try:
            cursor = conn.cursor()

            # Execute query
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)

            # Get column information
            if cursor.description:
                columns = [
                    (col[0], self._map_mysql_type(col[1]))
                    for col in cursor.description
                ]

                # Fetch all rows
                rows = cursor.fetchall()
            else:
                columns = []
                rows = []

            cursor.close()
            return columns, rows

        finally:
            conn.close()

    def _map_mysql_type(self, field_type: int) -> str:
        """
        Map MySQL field type code to type name

        Args:
            field_type: MySQL field type code

        Returns:
            MySQL type name
        """
        from mysql.connector import FieldType

        # Map field type codes to names
        type_map = {
            FieldType.DECIMAL: 'DECIMAL',
            FieldType.TINY: 'TINYINT',
            FieldType.SHORT: 'SMALLINT',
            FieldType.LONG: 'INT',
            FieldType.FLOAT: 'FLOAT',
            FieldType.DOUBLE: 'DOUBLE',
            FieldType.NULL: 'NULL',
            FieldType.TIMESTAMP: 'TIMESTAMP',
            FieldType.LONGLONG: 'BIGINT',
            FieldType.INT24: 'MEDIUMINT',
            FieldType.DATE: 'DATE',
            FieldType.TIME: 'TIME',
            FieldType.DATETIME: 'DATETIME',
            FieldType.YEAR: 'YEAR',
            FieldType.NEWDATE: 'DATE',
            FieldType.VARCHAR: 'VARCHAR',
            FieldType.BIT: 'BIT',
            FieldType.JSON: 'JSON',
            FieldType.NEWDECIMAL: 'DECIMAL',
            FieldType.ENUM: 'ENUM',
            FieldType.SET: 'SET',
            FieldType.TINY_BLOB: 'TINYBLOB',
            FieldType.MEDIUM_BLOB: 'MEDIUMBLOB',
            FieldType.LONG_BLOB: 'LONGBLOB',
            FieldType.BLOB: 'BLOB',
            FieldType.VAR_STRING: 'VARCHAR',
            FieldType.STRING: 'CHAR',
        }

        return type_map.get(field_type, 'VARCHAR')

    def close(self):
        """Close connection pool (not directly supported, connections auto-close)"""
        pass
