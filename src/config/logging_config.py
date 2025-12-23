"""
Logging Configuration for ChronosProxy
Sets up colored console logging and JSON file logging
"""

import logging
import sys
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler, RotatingFileHandler
from typing import Optional
import colorlog
from pythonjsonlogger import jsonlogger


def setup_logging(
    log_dir: str = 'logs',
    level: str = 'INFO',
    log_file: str = 'chronosproxy.log',
    rotation: str = 'daily',
    retention_days: int = 30,
    max_file_size_mb: int = 100,
    console_colors: bool = True
) -> logging.Logger:
    """
    Setup logging with both console and file handlers

    Args:
        log_dir: Directory for log files
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Log file name
        rotation: Rotation strategy ('daily', 'weekly', or 'size')
        retention_days: Days to retain logs
        max_file_size_mb: Max file size for size-based rotation
        console_colors: Enable colored console output

    Returns:
        Configured logger instance
    """
    # Create log directory
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Get root logger
    logger = logging.getLogger('chronosproxy')
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers.clear()  # Clear any existing handlers

    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)

    if console_colors:
        console_formatter = colorlog.ColoredFormatter(
            fmt='%(log_color)s%(asctime)s [%(levelname)-8s]%(reset)s %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
    else:
        console_formatter = logging.Formatter(
            fmt='%(asctime)s [%(levelname)-8s] %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler with JSON formatting
    log_file_path = log_path / log_file

    if rotation == 'daily':
        file_handler = TimedRotatingFileHandler(
            filename=log_file_path,
            when='midnight',
            interval=1,
            backupCount=retention_days,
            encoding='utf-8'
        )
    elif rotation == 'weekly':
        file_handler = TimedRotatingFileHandler(
            filename=log_file_path,
            when='W0',  # Monday
            interval=1,
            backupCount=int(retention_days / 7),
            encoding='utf-8'
        )
    else:  # size-based rotation
        file_handler = RotatingFileHandler(
            filename=log_file_path,
            maxBytes=max_file_size_mb * 1024 * 1024,
            backupCount=10,
            encoding='utf-8'
        )

    file_handler.setLevel(logging.DEBUG)

    # JSON formatter for structured logging
    json_formatter = jsonlogger.JsonFormatter(
        fmt='%(asctime)s %(name)s %(levelname)s %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S'
    )
    file_handler.setFormatter(json_formatter)
    logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module

    Args:
        name: Logger name (usually __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(f'chronosproxy.{name}')


class QueryLogger:
    """
    Specialized logger for query processing
    Tracks query lifecycle and transformations
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize query logger

        Args:
            logger: Base logger instance (default: get chronosproxy logger)
        """
        self.logger = logger or logging.getLogger('chronosproxy.query')
        self.query_count = 0
        self.success_count = 0
        self.transformed_count = 0
        self.rejected_count = 0

    def log_received(self, query_id: str, query: str, connection_id: str, source_ip: str):
        """Log query received"""
        self.query_count += 1
        self.logger.info(
            "Query received",
            extra={
                'query_id': query_id,
                'connection_id': connection_id,
                'source_ip': source_ip,
                'status': 'RECEIVED',
                'query': query[:500]  # Truncate for logging
            }
        )

    def log_metadata_passthrough(self, query_id: str, query: str):
        """Log metadata query passthrough"""
        self.logger.debug(
            "Metadata query passthrough",
            extra={
                'query_id': query_id,
                'status': 'METADATA_PASSTHROUGH',
                'query': query
            }
        )

    def log_rejected(self, query_id: str, reason: str, query: str, details: dict = None):
        """Log query rejection"""
        self.rejected_count += 1
        log_data = {
            'query_id': query_id,
            'status': f'REJECTED_{reason.upper()}',
            'reason': reason,
            'query': query[:500]
        }
        if details:
            log_data.update(details)

        self.logger.warning("Query rejected", extra=log_data)

    def log_transformation(self, query_id: str, transformation_type: str,
                          before: str, after: str, details: dict = None):
        """Log query transformation"""
        self.transformed_count += 1
        log_data = {
            'query_id': query_id,
            'status': f'TRANSFORMED_{transformation_type.upper()}',
            'transformation_type': transformation_type,
            'before': before[:500],
            'after': after[:500]
        }
        if details:
            log_data.update(details)

        self.logger.info("Query transformed", extra=log_data)

    def log_success(self, query_id: str, query: str, execution_time_ms: float,
                   rows_returned: int, was_transformed: bool = False):
        """Log successful query execution"""
        self.success_count += 1
        status = 'TRANSFORMED_SUCCESS' if was_transformed else 'SUCCESS'

        self.logger.info(
            "Query executed successfully",
            extra={
                'query_id': query_id,
                'status': status,
                'query': query[:500],
                'execution_time_ms': execution_time_ms,
                'rows_returned': rows_returned,
                'was_transformed': was_transformed
            }
        )

    def log_error(self, query_id: str, error: str, query: str, details: dict = None):
        """Log query execution error"""
        log_data = {
            'query_id': query_id,
            'status': 'ERROR',
            'error': error,
            'query': query[:500]
        }
        if details:
            log_data.update(details)

        self.logger.error("Query execution failed", extra=log_data)

    def log_metrics(self):
        """Log aggregate metrics"""
        if self.query_count == 0:
            return

        total = self.query_count
        success_rate = self.success_count / total if total > 0 else 0
        transformation_rate = self.transformed_count / total if total > 0 else 0
        rejection_rate = self.rejected_count / total if total > 0 else 0

        self.logger.info(
            "Query metrics",
            extra={
                'metric_type': 'aggregate_summary',
                'total_queries': total,
                'success_count': self.success_count,
                'transformed_count': self.transformed_count,
                'rejected_count': self.rejected_count,
                'success_rate': round(success_rate, 3),
                'transformation_rate': round(transformation_rate, 3),
                'rejection_rate': round(rejection_rate, 3)
            }
        )


# Global query logger instance
_query_logger: Optional[QueryLogger] = None


def get_query_logger() -> QueryLogger:
    """Get global query logger instance"""
    global _query_logger
    if _query_logger is None:
        _query_logger = QueryLogger()
    return _query_logger
