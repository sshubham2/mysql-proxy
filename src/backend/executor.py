"""
Query Executor
Executes queries on the backend database
"""

import time
from typing import List, Tuple, Any, Optional, Union
from src.backend.odbc_connection import ODBCConnectionPool
from src.backend.native_connection import NativeConnectionPool


class QueryExecutionResult:
    """Result of query execution"""

    def __init__(
        self,
        success: bool,
        columns: List[Tuple[str, str]],
        rows: List[Tuple[Any, ...]],
        execution_time_ms: float,
        error: Optional[str] = None,
        error_code: Optional[int] = None
    ):
        """
        Initialize execution result

        Args:
            success: Whether execution succeeded
            columns: Column definitions [(name, type), ...]
            rows: Result rows
            execution_time_ms: Execution time in milliseconds
            error: Error message (if failed)
            error_code: Error code (if failed)
        """
        self.success = success
        self.columns = columns
        self.rows = rows
        self.execution_time_ms = execution_time_ms
        self.error = error
        self.error_code = error_code

    @property
    def row_count(self) -> int:
        """Number of rows returned"""
        return len(self.rows)


class QueryExecutor:
    """Executes queries on backend database"""

    def __init__(self, connection_pool: Union[ODBCConnectionPool, NativeConnectionPool]):
        """
        Initialize query executor

        Args:
            connection_pool: Backend connection pool
        """
        self.connection_pool = connection_pool

    def execute(
        self,
        sql: str,
        params: Optional[Tuple[Any, ...]] = None
    ) -> QueryExecutionResult:
        """
        Execute query on backend

        Args:
            sql: SQL query
            params: Query parameters (optional)

        Returns:
            QueryExecutionResult
        """
        start_time = time.time()

        try:
            # Execute query
            columns, rows = self.connection_pool.execute_query(sql, params)

            # Calculate execution time
            execution_time_ms = (time.time() - start_time) * 1000

            return QueryExecutionResult(
                success=True,
                columns=columns,
                rows=rows,
                execution_time_ms=execution_time_ms
            )

        except Exception as e:
            # Calculate execution time
            execution_time_ms = (time.time() - start_time) * 1000

            # Extract error code if available
            error_code = None
            if hasattr(e, 'args') and len(e.args) > 0:
                if isinstance(e.args[0], int):
                    error_code = e.args[0]

            return QueryExecutionResult(
                success=False,
                columns=[],
                rows=[],
                execution_time_ms=execution_time_ms,
                error=str(e),
                error_code=error_code
            )
