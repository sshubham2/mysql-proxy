"""
ChronosProxy - MySQL Protocol Proxy Server
Main entry point for the application
"""

import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import get_settings, ConfigError
from src.config.logging_config import setup_logging, get_logger
from src.backend.connection_factory import ConnectionFactory
from src.backend.executor import QueryExecutor
from src.core.server import ChronosServer


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='ChronosProxy - Intelligent MySQL Protocol Proxy Server',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start server with default config
  python src/main.py

  # Start with custom config file
  python src/main.py --config config/production.yaml

  # Start with debug logging
  python src/main.py --log-level DEBUG

For more information, see the documentation.
        """
    )

    parser.add_argument(
        '--config',
        '-c',
        type=str,
        default=None,
        help='Path to configuration file (default: config/config.yaml)'
    )

    parser.add_argument(
        '--log-level',
        '-l',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default=None,
        help='Override log level from config'
    )

    parser.add_argument(
        '--version',
        '-v',
        action='version',
        version='ChronosProxy 1.0.0'
    )

    return parser.parse_args()


def main():
    """Main entry point"""
    # Parse arguments
    args = parse_args()

    try:
        # Load configuration
        print("Loading configuration...")
        settings = get_settings(args.config)

        # Setup logging
        log_level = args.log_level or settings.logging.get('level', 'INFO')
        log_dir = settings.logging.get('log_dir', 'logs')
        rotation = settings.logging.get('rotation', 'daily')
        retention_days = settings.logging.get('retention_days', 30)
        max_file_size_mb = settings.logging.get('max_file_size_mb', 100)

        setup_logging(
            log_dir=log_dir,
            level=log_level,
            rotation=rotation,
            retention_days=retention_days,
            max_file_size_mb=max_file_size_mb
        )

        logger = get_logger(__name__)

        logger.info("="*60)
        logger.info("ChronosProxy - MySQL Protocol Proxy Server")
        logger.info("="*60)
        logger.info(f"Configuration: {settings.config_file}")
        logger.info(f"Log level: {log_level}")
        logger.info(f"Log directory: {log_dir}")

        # Create backend connection pool
        logger.info("Initializing backend connection pool...")
        connection_type = settings.backend.get('connection_type', 'odbc')
        logger.info(f"Connection type: {connection_type}")

        connection_pool = ConnectionFactory.create_connection_pool(settings)

        # Test connection
        logger.info("Testing backend connection...")
        executor = QueryExecutor(connection_pool)
        # Use SHOW query instead of SELECT 1 to avoid validation issues
        test_result = executor.execute("SHOW TABLES")

        if not test_result.success:
            logger.error(f"Backend connection test failed: {test_result.error}")
            sys.exit(1)

        logger.info("Backend connection successful")

        # Log configuration summary
        logger.info("-" * 60)
        logger.info("Configuration Summary:")
        logger.info(f"  Proxy Host: {settings.proxy.get('host', '0.0.0.0')}")
        logger.info(f"  Proxy Port: {settings.proxy.get('port', 3307)}")
        logger.info(f"  Connection Pool Size: {settings.backend.get('pool_size', 10)}")
        logger.info(f"  Write Operations Blocked: {settings.security.get('block_writes', True)}")
        logger.info(f"  Require cob_date: {settings.business_rules.get('require_cob_date', True)}")
        logger.info(f"  Auto-unwrap Subqueries: {settings.transformations.get('unwrap_subqueries', True)}")
        logger.info(f"  Auto-fix GROUP BY: {settings.transformations.get('auto_fix_group_by', True)}")
        logger.info("-" * 60)

        # Create and start server
        server = ChronosServer(settings, executor)

        logger.info("Starting server...")
        logger.info(f"Listening on {server.host}:{server.port}")
        logger.info("Press Ctrl+C to stop")
        logger.info("="*60)

        # Start server (blocks here)
        server.start()

    except ConfigError as e:
        print(f"Configuration Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
