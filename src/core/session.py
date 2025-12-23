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
            self._set_var_middleware,  # Handle SET @var (session variables)
            self._use_middleware,       # Handle USE database (current db tracking)
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
        result = pipeline.process(sql)

        if result.success:
            # Extract column names from column definitions
            column_names = [col[0] for col in result.columns]

            # Return rows and column names
            return result.rows, column_names
        else:
            # Raise error to send to client
            raise Exception(result.error_message)

    async def schema(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        """
        Return database schema (optional)

        Returns empty dict - we don't provide schema info since we're proxying
        to a real MySQL server.

        Returns:
            Empty dictionary (schema provided by backend MySQL server)
        """
        return {}
