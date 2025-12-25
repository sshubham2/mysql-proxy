"""
ODBC Connection Pool
Manages ODBC connections to the backend MySQL server
"""

import pyodbc
from typing import List, Tuple, Any, Optional
from queue import Queue, Empty
import threading
import time
from contextlib import contextmanager


class ODBCConnectionPool:
    """ODBC connection pool for backend MySQL server"""

    def __init__(
        self,
        connection_string: str,
        pool_size: int = 10,
        pool_recycle: int = 3600,
        pool_pre_ping: bool = True
    ):
        """
        Initialize ODBC connection pool

        Args:
            connection_string: ODBC connection string
            pool_size: Number of connections in pool
            pool_recycle: Recycle connections after N seconds
            pool_pre_ping: Test connection before use
        """
        self.connection_string = connection_string
        self.pool_size = pool_size
        self.pool_recycle = pool_recycle
        self.pool_pre_ping = pool_pre_ping

        self._pool: Queue = Queue(maxsize=pool_size)
        self._lock = threading.Lock()
        self._connection_times = {}  # Track connection creation times

        # Pre-populate pool
        for _ in range(pool_size):
            conn = self._create_connection()
            self._pool.put(conn)

    def _create_connection(self) -> pyodbc.Connection:
        """
        Create a new ODBC connection

        Returns:
            ODBC connection

        Raises:
            pyodbc.Error: If connection fails
        """
        conn = pyodbc.connect(self.connection_string, autocommit=True)
        self._connection_times[id(conn)] = time.time()
        return conn

    def _is_connection_stale(self, conn: pyodbc.Connection) -> bool:
        """
        Check if connection should be recycled

        Args:
            conn: Connection to check

        Returns:
            True if connection is stale
        """
        conn_id = id(conn)
        if conn_id not in self._connection_times:
            return True

        age = time.time() - self._connection_times[conn_id]
        return age > self.pool_recycle

    def _test_connection(self, conn: pyodbc.Connection) -> bool:
        """
        Test if connection is alive

        Args:
            conn: Connection to test

        Returns:
            True if connection is alive
        """
        try:
            cursor = conn.cursor()
            # Use SHOW TABLES to test connection (SHOW STATUS not supported by backend)
            cursor.execute("SHOW TABLES")
            cursor.fetchone()
            cursor.close()
            return True
        except:
            return False

    @contextmanager
    def get_connection(self):
        """
        Get a connection from the pool (context manager)

        Yields:
            ODBC connection

        Raises:
            Exception: If no connection available or connection fails
        """
        conn = None
        try:
            # Get connection from pool
            conn = self._pool.get(timeout=30)

            # Check if connection needs recycling
            if self._is_connection_stale(conn):
                try:
                    conn.close()
                except:
                    pass
                conn = self._create_connection()

            # Pre-ping if enabled
            if self.pool_pre_ping:
                if not self._test_connection(conn):
                    try:
                        conn.close()
                    except:
                        pass
                    conn = self._create_connection()

            yield conn

        finally:
            # Return connection to pool
            if conn is not None:
                try:
                    self._pool.put(conn, block=False)
                except:
                    # Pool is full, close connection
                    try:
                        conn.close()
                    except:
                        pass

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
            - column_definitions: List of (name, type) tuples
            - rows: List of row tuples

        Raises:
            pyodbc.Error: If query execution fails
        """
        # Debug logging - log exact SQL being sent to backend
        import logging
        logger = logging.getLogger('chronosproxy.backend')
        logger.debug(f"BACKEND EXECUTE: Full SQL string length={len(sql)}, SQL=>>>{sql}<<<")

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Execute query
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)

            # Get column information
            if cursor.description:
                columns = [
                    (col[0], self._map_odbc_type(col[1]))
                    for col in cursor.description
                ]

                # Fetch all rows
                rows = cursor.fetchall()

                # Convert pyodbc.Row to tuples
                rows = [tuple(row) for row in rows]
            else:
                # No results (e.g., SHOW commands sometimes)
                columns = []
                rows = []

            cursor.close()
            return columns, rows

    def _map_odbc_type(self, odbc_type) -> str:
        """
        Map ODBC type to MySQL type name

        Args:
            odbc_type: ODBC SQL type code

        Returns:
            MySQL type name
        """
        # Map common ODBC types to MySQL types
        type_map = {
            pyodbc.SQL_CHAR: 'CHAR',
            pyodbc.SQL_VARCHAR: 'VARCHAR',
            pyodbc.SQL_LONGVARCHAR: 'TEXT',
            pyodbc.SQL_WCHAR: 'CHAR',
            pyodbc.SQL_WVARCHAR: 'VARCHAR',
            pyodbc.SQL_WLONGVARCHAR: 'TEXT',
            pyodbc.SQL_DECIMAL: 'DECIMAL',
            pyodbc.SQL_NUMERIC: 'NUMERIC',
            pyodbc.SQL_SMALLINT: 'SMALLINT',
            pyodbc.SQL_INTEGER: 'INT',
            pyodbc.SQL_REAL: 'REAL',
            pyodbc.SQL_FLOAT: 'FLOAT',
            pyodbc.SQL_DOUBLE: 'DOUBLE',
            pyodbc.SQL_BIT: 'BIT',
            pyodbc.SQL_TINYINT: 'TINYINT',
            pyodbc.SQL_BIGINT: 'BIGINT',
            pyodbc.SQL_BINARY: 'BINARY',
            pyodbc.SQL_VARBINARY: 'VARBINARY',
            pyodbc.SQL_LONGVARBINARY: 'BLOB',
            pyodbc.SQL_TYPE_DATE: 'DATE',
            pyodbc.SQL_TYPE_TIME: 'TIME',
            pyodbc.SQL_TYPE_TIMESTAMP: 'DATETIME',
        }

        return type_map.get(odbc_type, 'VARCHAR')

    def close(self):
        """Close all connections in the pool"""
        with self._lock:
            while not self._pool.empty():
                try:
                    conn = self._pool.get_nowait()
                    conn.close()
                except Empty:
                    break
                except:
                    pass

            self._connection_times.clear()

    def __del__(self):
        """Cleanup on deletion"""
        try:
            self.close()
        except:
            pass
