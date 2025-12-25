"""
MySQL Session Handler
Handles individual client sessions using mysql-mimic
"""

from typing import Tuple, List, Any, Dict
from mysql_mimic import Session
from sqlglot import exp
from src.config.settings import Settings
from src.config.logging_config import get_logger
from src.core.query_pipeline import QueryPipeline
from src.backend.executor import QueryExecutor


class ChronosSession(Session):
    """Custom MySQL session for ChronosProxy"""

    def __init__(
        self,
        settings: Settings,
        executor: QueryExecutor,
        connection_id: str
    ):
        """
        Initialize session

        Args:
            settings: Application settings
            executor: Query executor
            connection_id: Unique connection identifier
        """
        super().__init__()
        self.settings = settings
        self.executor = executor
        self.connection_id = connection_id
        self.logger = get_logger(__name__)
        self.current_database = None

        # Override middlewares to pass metadata queries to backend
        # By default, Session intercepts SHOW, DESCRIBE, and INFORMATION_SCHEMA
        # queries and returns synthetic results. For a proxy, we need the real
        # backend's metadata. Only keep essential session state management:
        self.middlewares = [
            self._set_var_middleware,    # Handle SET @var (session variables)
            self._set_middleware,         # Handle SET NAMES, SET CHARACTER SET, etc.
            self._static_query_middleware, # Handle SELECT CONNECTION_ID(), SELECT 1, etc.
            self._use_middleware,         # Handle USE database (current db tracking)
        ]
        # All other queries (SHOW, DESCRIBE, INFORMATION_SCHEMA, SELECT, etc.)
        # will pass through to query() method and reach the backend server.

    async def query(
        self,
        expression: exp.Expression,
        sql: str,
        attrs: Dict[str, str]
    ) -> Tuple[List[Tuple[Any, ...]], List[str]]:
        """
        Handle SQL query from client

        Args:
            expression: Parsed SQL expression (sqlglot AST)
            sql: Original SQL query string
            attrs: Query attributes

        Returns:
            Tuple of (rows, column_names)
            - rows: List of row tuples
            - column_names: List of column names
        """
        # Get client info (if available)
        source_ip = "unknown"
        if hasattr(self, 'connection') and hasattr(self.connection, 'peername'):
            source_ip = self.connection.peername[0] if self.connection.peername else "unknown"

        # Create pipeline for this query
        pipeline = QueryPipeline(
            settings=self.settings,
            executor=self.executor,
            connection_id=self.connection_id,
            source_ip=source_ip
        )

        # Process query
        try:
            result = pipeline.process(sql)

            if result.success:
                # Extract column names from column definitions
                # Handle empty or malformed column definitions gracefully
                try:
                    if result.columns:
                        column_names = [col[0] if isinstance(col, (tuple, list)) else str(col) for col in result.columns]
                    else:
                        # No columns defined - return empty
                        column_names = []

                    # Debug logging for INFORMATION_SCHEMA queries
                    if 'INFORMATION_SCHEMA' in sql.upper():
                        self.logger.debug(
                            f"INFORMATION_SCHEMA result",
                            extra={
                                'connection_id': self.connection_id,
                                'columns': column_names,
                                'row_count': len(result.rows),
                                'sample_row': str(result.rows[0]) if result.rows else 'empty'
                            }
                        )
                except (IndexError, TypeError) as e:
                    self.logger.warning(
                        f"Malformed column definitions: {e}",
                        extra={'connection_id': self.connection_id, 'columns': str(result.columns)[:100]}
                    )
                    column_names = []

                # Validate result format before returning to mysql-mimic
                # mysql-mimic has assertions that column count must match row value count
                if result.rows and column_names:
                    # Check first row to ensure column count matches
                    first_row = result.rows[0]
                    if len(first_row) != len(column_names):
                        self.logger.warning(
                            f"Column count mismatch: {len(column_names)} columns but row has {len(first_row)} values",
                            extra={
                                'connection_id': self.connection_id,
                                'columns': column_names,
                                'first_row': str(first_row)[:200]
                            }
                        )
                        # Fix the mismatch by padding column names
                        if len(first_row) > len(column_names):
                            # More values than columns - add generic column names
                            for i in range(len(column_names), len(first_row)):
                                column_names.append(f'column_{i+1}')
                        elif len(first_row) < len(column_names):
                            # Fewer values than columns - truncate column names
                            column_names = column_names[:len(first_row)]

                # Return rows and column names
                return result.rows, column_names
            else:
                # Query failed - send error to client gracefully
                # Log the error but don't print full traceback
                self.logger.warning(
                    f"Query failed: {result.error_message}",
                    extra={'connection_id': self.connection_id, 'query': sql[:100]}
                )
                # Raise error to send to client (mysql-mimic handles this)
                raise Exception(result.error_message)
        except Exception as e:
            # Log error without traceback (exc_info=False suppresses traceback)
            self.logger.error(
                f"Query execution error: {str(e)}",
                extra={'connection_id': self.connection_id, 'query': sql[:100]},
                exc_info=False  # Don't print traceback
            )
            # Re-raise to send error to client (mysql-mimic will handle this)
            raise

    async def schema(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        """
        Return database schema (optional)

        Returns empty dict - we don't provide schema info since we're proxying
        to a real MySQL server.

        Returns:
            Empty dictionary (schema provided by backend MySQL server)
        """
        return {}
