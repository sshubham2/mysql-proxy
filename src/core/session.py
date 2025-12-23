"""
MySQL Session Handler
Handles individual client sessions using mysql-mimic
"""

from typing import Sequence, List, Tuple, Any
from mysql_mimic import MysqlSession, ResultSet, ColumnDefinition
from mysql_mimic.types import MysqlType
from src.config.settings import Settings
from src.config.logging_config import get_logger
from src.core.query_pipeline import QueryPipeline
from src.backend.executor import QueryExecutor


class ChronosSession(MysqlSession):
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

    def query(self, expression: str) -> ResultSet:
        """
        Handle SQL query from client

        Args:
            expression: SQL query string

        Returns:
            ResultSet with query results
        """
        # Get client info
        source_ip = getattr(self, '_client_address', ('unknown', 0))[0]

        # Create pipeline for this query
        pipeline = QueryPipeline(
            settings=self.settings,
            executor=self.executor,
            connection_id=self.connection_id,
            source_ip=source_ip
        )

        # Process query
        result = pipeline.process(expression)

        if result.success:
            # Convert columns to mysql-mimic format
            column_defs = self._convert_columns(result.columns)

            # Return successful result
            return ResultSet(
                columns=column_defs,
                rows=result.rows
            )
        else:
            # Raise error to send to client
            raise Exception(result.error_message)

    def use_database(self, database: str) -> None:
        """
        Handle USE database command

        Args:
            database: Database name

        Raises:
            Exception: If database is blocked
        """
        # Check if database is allowed
        if not self.settings.is_database_allowed(database):
            from src.utils.error_formatter import ErrorFormatter
            error_msg = ErrorFormatter.format_database_blocked_error(database)
            raise Exception(error_msg)

        self.current_database = database
        self.logger.info(f"Connection {self.connection_id} switched to database: {database}")

    def _convert_columns(
        self,
        columns: List[Tuple[str, str]]
    ) -> Sequence[ColumnDefinition]:
        """
        Convert column definitions to mysql-mimic format

        Args:
            columns: List of (name, type) tuples

        Returns:
            List of ColumnDefinition objects
        """
        column_defs = []

        for name, mysql_type in columns:
            # Map MySQL type name to MysqlType
            mimic_type = self._map_to_mimic_type(mysql_type)

            column_defs.append(
                ColumnDefinition(
                    name=name,
                    type=mimic_type
                )
            )

        return column_defs

    def _map_to_mimic_type(self, mysql_type: str) -> MysqlType:
        """
        Map MySQL type name to mysql-mimic MysqlType

        Args:
            mysql_type: MySQL type name (e.g., 'VARCHAR', 'INT')

        Returns:
            MysqlType enum value
        """
        # Map common types
        type_map = {
            'CHAR': MysqlType.VAR_STRING,
            'VARCHAR': MysqlType.VAR_STRING,
            'TEXT': MysqlType.BLOB,
            'TINYTEXT': MysqlType.BLOB,
            'MEDIUMTEXT': MysqlType.BLOB,
            'LONGTEXT': MysqlType.BLOB,
            'TINYINT': MysqlType.TINY,
            'SMALLINT': MysqlType.SHORT,
            'MEDIUMINT': MysqlType.INT24,
            'INT': MysqlType.LONG,
            'INTEGER': MysqlType.LONG,
            'BIGINT': MysqlType.LONGLONG,
            'FLOAT': MysqlType.FLOAT,
            'DOUBLE': MysqlType.DOUBLE,
            'REAL': MysqlType.DOUBLE,
            'DECIMAL': MysqlType.NEWDECIMAL,
            'NUMERIC': MysqlType.NEWDECIMAL,
            'DATE': MysqlType.DATE,
            'TIME': MysqlType.TIME,
            'DATETIME': MysqlType.DATETIME,
            'TIMESTAMP': MysqlType.TIMESTAMP,
            'YEAR': MysqlType.YEAR,
            'BLOB': MysqlType.BLOB,
            'TINYBLOB': MysqlType.TINY_BLOB,
            'MEDIUMBLOB': MysqlType.MEDIUM_BLOB,
            'LONGBLOB': MysqlType.LONG_BLOB,
            'BIT': MysqlType.BIT,
            'ENUM': MysqlType.ENUM,
            'SET': MysqlType.SET,
            'JSON': MysqlType.JSON,
            'NULL': MysqlType.NULL,
        }

        return type_map.get(mysql_type.upper(), MysqlType.VAR_STRING)
