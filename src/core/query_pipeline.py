"""
Query Processing Pipeline
Main orchestrator for query validation, transformation, and execution
"""

import uuid
import time
from typing import Tuple, List, Any, Optional
from sqlglot import exp
from src.config.settings import Settings
from src.config.logging_config import get_query_logger
from src.utils.sql_parser import SQLParser, QueryType
from src.utils.error_formatter import ErrorFormatter
from src.utils.result_converter import ResultConverter
from src.security.write_blocker import WriteBlocker, WriteOperationBlocked
from src.detection.unsupported_detector import UnsupportedDetector, UnsupportedFeatureDetected
from src.validation.cob_date_validator import CobDateValidator, MissingCobDateError
from src.transformation.transformer import Transformer
from src.transformation.subquery_unwrapper import SubqueryTooComplex
from src.backend.executor import QueryExecutor, QueryExecutionResult
from src.utils.information_schema_converter import InformationSchemaConverter


class QueryPipelineResult:
    """Result from query pipeline"""

    def __init__(
        self,
        success: bool,
        columns: List[Tuple[str, str]],
        rows: List[Tuple[Any, ...]],
        error_message: Optional[str] = None,
        was_transformed: bool = False,
        execution_time_ms: float = 0.0
    ):
        """
        Initialize pipeline result

        Args:
            success: Whether pipeline succeeded
            columns: Column definitions
            rows: Result rows
            error_message: Error message (if failed)
            was_transformed: Whether query was transformed
            execution_time_ms: Total execution time
        """
        self.success = success
        self.columns = columns
        self.rows = rows
        self.error_message = error_message
        self.was_transformed = was_transformed
        self.execution_time_ms = execution_time_ms


class QueryPipeline:
    """Main query processing pipeline"""

    def __init__(
        self,
        settings: Settings,
        executor: QueryExecutor,
        connection_id: str = "unknown",
        source_ip: str = "0.0.0.0"
    ):
        """
        Initialize query pipeline

        Args:
            settings: Application settings
            executor: Query executor
            connection_id: Connection identifier
            source_ip: Source IP address
        """
        self.settings = settings
        self.executor = executor
        self.connection_id = connection_id
        self.source_ip = source_ip

        # Initialize components
        self.sql_parser = SQLParser()
        self.write_blocker = WriteBlocker(settings)
        self.unsupported_detector = UnsupportedDetector(settings, self.sql_parser)
        self.cob_date_validator = CobDateValidator(settings, self.sql_parser)
        self.transformer = Transformer(settings)

        # Logger
        self.query_logger = get_query_logger()

    def process(self, sql: str) -> QueryPipelineResult:
        """
        Process a SQL query through the complete pipeline

        Args:
            sql: SQL query string

        Returns:
            QueryPipelineResult
        """
        query_id = str(uuid.uuid4())
        start_time = time.time()

        # Log received
        self.query_logger.log_received(query_id, sql, self.connection_id, self.source_ip)

        try:
            # Step 1: Metadata query check
            if self._is_metadata_query(sql):
                return self._execute_metadata_query(query_id, sql)

            # Step 2: Security validation (write blocker)
            try:
                self.write_blocker.check_query(sql)
            except WriteOperationBlocked as e:
                self.query_logger.log_rejected(
                    query_id, 'write_operation', sql,
                    {'operation': e.operation}
                )
                return QueryPipelineResult(
                    success=False,
                    columns=[],
                    rows=[],
                    error_message=str(e)
                )

            # Step 3: SQL Parsing
            try:
                ast = self.sql_parser.parse(sql)
            except Exception as e:
                error_msg = ErrorFormatter.format_parse_error(sql, str(e))
                self.query_logger.log_rejected(query_id, 'parse_error', sql)
                return QueryPipelineResult(
                    success=False,
                    columns=[],
                    rows=[],
                    error_message=error_msg
                )

            # Step 4: Capability Detection (unsupported features)
            try:
                self.unsupported_detector.check_query(sql, ast)
            except UnsupportedFeatureDetected as e:
                self.query_logger.log_rejected(
                    query_id, e.feature, sql,
                    {'feature': e.feature}
                )
                return QueryPipelineResult(
                    success=False,
                    columns=[],
                    rows=[],
                    error_message=str(e)
                )

            # Step 5: Transformation Phase
            try:
                transform_result = self.transformer.transform(sql, ast)
            except SubqueryTooComplex as e:
                self.query_logger.log_rejected(query_id, 'complex_subquery', sql)
                return QueryPipelineResult(
                    success=False,
                    columns=[],
                    rows=[],
                    error_message=str(e)
                )

            # Log transformations
            for trans in transform_result.transformations:
                self.query_logger.log_transformation(
                    query_id,
                    trans.transformation_type,
                    trans.before,
                    trans.after,
                    trans.details
                )

            # Use final query for remaining steps
            final_sql = transform_result.final_query
            final_ast = transform_result.final_ast

            # Step 6: Business Rule Validation (cob_date)
            try:
                self.cob_date_validator.validate(final_sql, final_ast)
            except MissingCobDateError as e:
                self.query_logger.log_rejected(query_id, 'missing_cob_date', final_sql)
                return QueryPipelineResult(
                    success=False,
                    columns=[],
                    rows=[],
                    error_message=str(e),
                    was_transformed=transform_result.was_transformed
                )

            # Step 7: Backend Execution
            exec_result = self.executor.execute(final_sql)

            if exec_result.success:
                # Success
                execution_time_ms = (time.time() - start_time) * 1000

                self.query_logger.log_success(
                    query_id,
                    final_sql,
                    exec_result.execution_time_ms,
                    exec_result.row_count,
                    was_transformed=transform_result.was_transformed
                )

                # Convert results
                converted_rows = ResultConverter.convert_rows(exec_result.rows)

                return QueryPipelineResult(
                    success=True,
                    columns=exec_result.columns,
                    rows=converted_rows,
                    was_transformed=transform_result.was_transformed,
                    execution_time_ms=execution_time_ms
                )
            else:
                # Backend error
                error_msg = ErrorFormatter.format_backend_error(
                    final_sql,
                    exec_result.error_code,
                    exec_result.error
                )

                self.query_logger.log_error(
                    query_id,
                    exec_result.error,
                    final_sql,
                    {'error_code': exec_result.error_code}
                )

                return QueryPipelineResult(
                    success=False,
                    columns=[],
                    rows=[],
                    error_message=error_msg,
                    was_transformed=transform_result.was_transformed
                )

        except Exception as e:
            # Unexpected error
            self.query_logger.log_error(query_id, str(e), sql)
            return QueryPipelineResult(
                success=False,
                columns=[],
                rows=[],
                error_message=f"Internal Error: {str(e)}"
            )

    def _is_metadata_query(self, sql: str) -> bool:
        """Check if query is metadata query"""
        return self.sql_parser.is_metadata_query(sql)

    def _execute_metadata_query(
        self,
        query_id: str,
        sql: str
    ) -> QueryPipelineResult:
        """Execute metadata query directly without transformation"""
        # Check if this is an INFORMATION_SCHEMA query that needs conversion
        final_sql = sql
        was_converted = False
        return_empty = False

        if InformationSchemaConverter.can_convert(sql):
            converted_sql = InformationSchemaConverter.convert_to_show(sql)
            if converted_sql:
                self.query_logger.info(
                    f"Converting INFORMATION_SCHEMA query to SHOW command",
                    extra={
                        'query_id': query_id,
                        'original': sql,
                        'converted': converted_sql
                    }
                )
                final_sql = converted_sql
                was_converted = True
            else:
                # Can't convert (too complex) - return empty result instead of failing
                self.query_logger.info(
                    f"INFORMATION_SCHEMA query too complex to convert, returning empty result",
                    extra={
                        'query_id': query_id,
                        'original': sql
                    }
                )
                return_empty = True

        # If we need to return empty result, do so without executing
        if return_empty:
            return QueryPipelineResult(
                success=True,
                columns=[],
                rows=[],
                was_transformed=False,
                execution_time_ms=0.0
            )

        self.query_logger.log_metadata_passthrough(query_id, final_sql)

        exec_result = self.executor.execute(final_sql)

        if exec_result.success:
            converted_rows = ResultConverter.convert_rows(exec_result.rows)

            return QueryPipelineResult(
                success=True,
                columns=exec_result.columns,
                rows=converted_rows,
                was_transformed=was_converted,
                execution_time_ms=exec_result.execution_time_ms
            )
        else:
            error_msg = ErrorFormatter.format_backend_error(
                final_sql,
                exec_result.error_code,
                exec_result.error
            )

            return QueryPipelineResult(
                success=False,
                columns=[],
                rows=[],
                error_message=error_msg
            )
