"""
MySQL Protocol Server
Main server using mysql-mimic to accept Tableau connections
"""

import uuid
from mysql_mimic import MysqlServer
from src.config.settings import Settings
from src.config.logging_config import get_logger
from src.core.session import ChronosSession
from src.backend.executor import QueryExecutor


class ChronosServer:
    """ChronosProxy MySQL protocol server"""

    def __init__(
        self,
        settings: Settings,
        executor: QueryExecutor
    ):
        """
        Initialize ChronosProxy server

        Args:
            settings: Application settings
            executor: Query executor for backend
        """
        self.settings = settings
        self.executor = executor
        self.logger = get_logger(__name__)

        # Server configuration
        self.host = settings.proxy.get('host', '0.0.0.0')
        self.port = settings.proxy.get('port', 3307)

    def create_session(self) -> ChronosSession:
        """
        Create a new session for incoming connection

        Returns:
            ChronosSession instance
        """
        connection_id = f"conn-{uuid.uuid4().hex[:8]}"

        self.logger.info(f"New connection: {connection_id}")

        return ChronosSession(
            settings=self.settings,
            executor=self.executor,
            connection_id=connection_id
        )

    def start(self):
        """
        Start the MySQL protocol server

        This will block until server is stopped
        """
        self.logger.info(f"Starting ChronosProxy on {self.host}:{self.port}")

        # Create mysql-mimic server
        server = MysqlServer(
            session_factory=self.create_session,
            host=self.host,
            port=self.port
        )

        try:
            # Start server (blocking)
            server.serve_forever()
        except KeyboardInterrupt:
            self.logger.info("Server stopped by user")
        except Exception as e:
            self.logger.error(f"Server error: {e}", exc_info=True)
            raise
        finally:
            self.logger.info("ChronosProxy server shutdown")

    def __repr__(self) -> str:
        return f"ChronosServer(host={self.host}, port={self.port})"
