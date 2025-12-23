"""
Error Formatter
Formats clear, actionable error messages for users
"""

from typing import List, Optional, Dict, Any


class ErrorFormatter:
    """Formats user-friendly error messages"""

    @staticmethod
    def format_join_error(query: str, join_types: List[str]) -> str:
        """
        Format error message for JOIN rejection

        Args:
            query: Original SQL query
            join_types: List of detected join types

        Returns:
            Formatted error message
        """
        joins_str = ", ".join(join_types)

        return f"""MySQL Proxy Error: JOINs are not supported

Your query contains table joins which are not supported by the backend MySQL server.

Detected: {joins_str}

Suggestions:
  • Create a denormalized view or table that combines the required data
  • Use Tableau's data blending feature instead of SQL joins
  • Contact your database administrator about enabling JOIN support

Feature: JOINs (INNER, LEFT, RIGHT, OUTER, CROSS)
Status: Not Supported"""

    @staticmethod
    def format_union_error(query: str, union_count: int) -> str:
        """
        Format error message for UNION rejection

        Args:
            query: Original SQL query
            union_count: Number of UNIONs detected

        Returns:
            Formatted error message
        """
        return f"""MySQL Proxy Error: UNIONs are not supported

Your query contains {union_count} UNION operation(s) which are not supported by the backend.

Suggestions:
  • Split into separate queries and combine results in Tableau
  • Create a unified view in the database
  • Use separate data sources in Tableau

Feature: UNION, UNION ALL
Status: Not Supported"""

    @staticmethod
    def format_window_function_error(query: str, window_funcs: List[str]) -> str:
        """
        Format error message for window function rejection

        Args:
            query: Original SQL query
            window_funcs: List of detected window functions

        Returns:
            Formatted error message
        """
        funcs_str = ", ".join(set(window_funcs))

        return f"""MySQL Proxy Error: Window functions are not supported

Your query uses window functions which are not supported by the backend.

Detected functions: {funcs_str}

Suggestions:
  • Use Tableau's table calculations for ranking and windowing
  • Pre-calculate these values in a database view
  • Use Tableau's RANK(), ROW_NUMBER(), or similar functions

Feature: Window Functions (ROW_NUMBER, RANK, DENSE_RANK, OVER clause)
Status: Not Supported"""

    @staticmethod
    def format_unsupported_function_error(query: str, functions: List[str]) -> str:
        """
        Format error message for unsupported function rejection

        Args:
            query: Original SQL query
            functions: List of unsupported functions found

        Returns:
            Formatted error message
        """
        funcs_str = ", ".join(set(functions))

        # Special handling for COUNT
        if 'COUNT' in [f.upper() for f in functions]:
            return f"""MySQL Proxy Error: COUNT() function is not supported

Your query uses the COUNT() aggregation function which is not supported by the backend.

Alternative: Use SUM(1) instead of COUNT(*)
  Example: SELECT category, SUM(1) AS record_count
           FROM sales
           WHERE cob_date='2024-01-15'
           GROUP BY category

Alternative: Use SUM(CASE) instead of COUNT(column)
  Example: SELECT category, SUM(CASE WHEN customer_id IS NOT NULL THEN 1 ELSE 0 END)
           FROM sales
           WHERE cob_date='2024-01-15'
           GROUP BY category

Or let Tableau handle the counting:
  • Remove COUNT from Custom SQL
  • Drag the dimension to Rows
  • Tableau will count records automatically

Feature: COUNT() Aggregation
Status: Not Supported
Alternative: SUM(1) for counting rows"""

        return f"""MySQL Proxy Error: Unsupported function(s): {funcs_str}

Your query uses function(s) that are not supported by the backend MySQL server.

Detected: {funcs_str}

Suggestions:
  • Check documentation for supported functions
  • Use alternative functions if available
  • Perform calculations in Tableau instead of SQL

Status: Not Supported"""

    @staticmethod
    def format_missing_cob_date_error(query: str) -> str:
        """
        Format error message for missing cob_date

        Args:
            query: Original SQL query

        Returns:
            Formatted error message
        """
        return """MySQL Proxy Error: cob_date filter is mandatory

All queries must include a cob_date filter in the WHERE clause to ensure temporal consistency.

Required format:
  SELECT column1, column2
  FROM table_name
  WHERE cob_date = '2024-01-15' AND other_conditions...

The cob_date filter ensures your query operates on a specific date's data snapshot.

Business Rule: Mandatory cob_date Filter
Status: Rejected - Add cob_date filter and retry"""

    @staticmethod
    def format_complex_subquery_error(query: str, depth: int, max_depth: int) -> str:
        """
        Format error message for complex subquery rejection

        Args:
            query: Original SQL query
            depth: Detected subquery depth
            max_depth: Maximum allowed depth

        Returns:
            Formatted error message
        """
        return f"""MySQL Proxy Error: Query too complex (subquery depth: {depth})

Your query contains nested subqueries that are too complex to flatten.

Maximum allowed depth: {max_depth}
Your query depth: {depth}

Suggestions:
  • Simplify the query by creating intermediate views
  • Break down the query into multiple simpler queries
  • Remove unnecessary subquery nesting

Feature: Nested Subqueries
Status: Limited support (depth <= {max_depth})"""

    @staticmethod
    def format_write_operation_error(operation: str) -> str:
        """
        Format error message for write operation rejection

        Args:
            operation: Write operation keyword (INSERT, UPDATE, etc.)

        Returns:
            Formatted error message
        """
        return f"""MySQL Proxy Error: Write operations are not permitted

Your query attempts to perform a write operation ({operation}) which is not allowed.

This proxy provides read-only access to the database.

Blocked operations: INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, TRUNCATE, REPLACE, GRANT, REVOKE

Security Policy: Read-Only Access
Status: Rejected"""

    @staticmethod
    def format_parse_error(query: str, error: str) -> str:
        """
        Format error message for SQL parse errors

        Args:
            query: Original SQL query
            error: Parse error message

        Returns:
            Formatted error message
        """
        return f"""MySQL Proxy Error: Failed to parse SQL query

The query could not be parsed. Please check your SQL syntax.

Error: {error}

Suggestions:
  • Verify SQL syntax is valid
  • Check for missing or extra parentheses
  • Ensure proper quoting of strings and identifiers

Status: Parse Error"""

    @staticmethod
    def format_backend_error(query: str, error_code: Optional[int], error_message: str) -> str:
        """
        Format error message for backend execution errors

        Args:
            query: Executed SQL query
            error_code: Backend error code (if available)
            error_message: Backend error message

        Returns:
            Formatted error message
        """
        code_str = f" (Error {error_code})" if error_code else ""

        return f"""MySQL Backend Error{code_str}

The backend database returned an error while executing your query.

Error: {error_message}

This error originated from the backend MySQL server, not the proxy.

Suggestions:
  • Check that all referenced tables and columns exist
  • Verify data types are compatible
  • Ensure your query follows backend SQL limitations

Status: Backend Execution Error"""

    @staticmethod
    def format_database_blocked_error(database: str) -> str:
        """
        Format error message for blocked database access

        Args:
            database: Database name

        Returns:
            Formatted error message
        """
        return f"""MySQL Proxy Error: Access to database '{database}' is not permitted

The database you're trying to access is blocked by security policy.

Blocked databases: mysql, information_schema, performance_schema, sys

Suggestions:
  • Use an allowed application database
  • Contact your administrator for database access

Security Policy: Database Access Control
Status: Rejected"""
