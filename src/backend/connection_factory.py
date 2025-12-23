"""
Connection Factory
Creates appropriate backend connection based on configuration
"""

from typing import Union
from src.config.settings import Settings
from src.backend.odbc_connection import ODBCConnectionPool
from src.backend.native_connection import NativeConnectionPool


class ConnectionFactory:
    """Factory for creating backend connections"""

    @staticmethod
    def create_connection_pool(
        settings: Settings
    ) -> Union[ODBCConnectionPool, NativeConnectionPool]:
        """
        Create backend connection pool based on configuration

        Args:
            settings: Application settings

        Returns:
            Connection pool instance (ODBC or Native)

        Raises:
            ValueError: If connection_type is invalid
        """
        connection_type = settings.backend.get('connection_type', 'odbc')

        if connection_type == 'odbc':
            return ConnectionFactory._create_odbc_pool(settings)
        elif connection_type == 'native':
            return ConnectionFactory._create_native_pool(settings)
        else:
            raise ValueError(
                f"Invalid connection_type: {connection_type}. "
                f"Must be 'odbc' or 'native'"
            )

    @staticmethod
    def _create_odbc_pool(settings: Settings) -> ODBCConnectionPool:
        """
        Create ODBC connection pool

        Args:
            settings: Application settings

        Returns:
            ODBCConnectionPool instance
        """
        connection_string = settings.get_odbc_connection_string()
        pool_size = settings.backend.get('pool_size', 10)
        pool_recycle = settings.backend.get('pool_recycle', 3600)
        pool_pre_ping = settings.backend.get('pool_pre_ping', True)

        return ODBCConnectionPool(
            connection_string=connection_string,
            pool_size=pool_size,
            pool_recycle=pool_recycle,
            pool_pre_ping=pool_pre_ping
        )

    @staticmethod
    def _create_native_pool(settings: Settings) -> NativeConnectionPool:
        """
        Create native MySQL connection pool

        Args:
            settings: Application settings

        Returns:
            NativeConnectionPool instance
        """
        params = settings.get_native_connection_params()
        pool_size = settings.backend.get('pool_size', 10)

        return NativeConnectionPool(
            host=params['host'],
            port=params['port'],
            database=params['database'],
            user=params['user'],
            password=params['password'],
            charset=params['charset'],
            pool_size=pool_size
        )
