"""
Unit tests for Subquery Unwrapper
"""

import pytest
from src.transformation.subquery_unwrapper import SubqueryUnwrapper, SubqueryTooComplex
from src.utils.sql_parser import SQLParser


class TestSubqueryUnwrapper:
    """Test subquery unwrapping functionality"""

    @pytest.fixture
    def unwrapper(self, test_settings):
        """Create subquery unwrapper instance"""
        sql_parser = SQLParser()
        return SubqueryUnwrapper(test_settings, sql_parser)

    def test_simple_tableau_pattern_unwrap(self, unwrapper, sql_parser):
        """Test unwrapping simple Tableau subquery pattern"""
        sql = """
            SELECT * FROM (
                SELECT id, name
                FROM users
                WHERE cob_date='2024-01-15'
            ) sub
        """

        ast = sql_parser.parse(sql)
        was_unwrapped, unwrapped_sql, unwrapped_ast = unwrapper.unwrap(sql, ast)

        assert was_unwrapped is True
        assert "FROM (SELECT" not in unwrapped_sql.upper()
        assert "cob_date" in unwrapped_sql.lower()

    def test_tableau_pattern_with_outer_where(self, unwrapper, sql_parser):
        """Test unwrapping with outer WHERE clause"""
        sql = """
            SELECT * FROM (
                SELECT category, SUM(amount) AS total
                FROM sales
                WHERE cob_date='2024-01-15'
            ) sub
            WHERE category='Electronics'
        """

        ast = sql_parser.parse(sql)
        was_unwrapped, unwrapped_sql, unwrapped_ast = unwrapper.unwrap(sql, ast)

        assert was_unwrapped is True
        assert "Electronics" in unwrapped_sql
        assert "cob_date" in unwrapped_sql.lower()
        assert "FROM (SELECT" not in unwrapped_sql.upper()

    def test_non_select_star_not_unwrapped(self, unwrapper, sql_parser):
        """Test that non-SELECT * patterns are not unwrapped"""
        sql = """
            SELECT id FROM (
                SELECT id, name
                FROM users
                WHERE cob_date='2024-01-15'
            ) sub
        """

        ast = sql_parser.parse(sql)
        was_unwrapped, unwrapped_sql, unwrapped_ast = unwrapper.unwrap(sql, ast)

        assert was_unwrapped is False

    def test_simple_query_not_unwrapped(self, unwrapper, sql_parser):
        """Test that simple queries without subqueries are not unwrapped"""
        sql = "SELECT id, name FROM users WHERE cob_date='2024-01-15'"

        ast = sql_parser.parse(sql)
        was_unwrapped, unwrapped_sql, unwrapped_ast = unwrapper.unwrap(sql, ast)

        assert was_unwrapped is False

    def test_disabled_unwrapper(self, test_settings, sql_parser):
        """Test unwrapper when disabled"""
        test_settings.transformations['unwrap_subqueries'] = False
        unwrapper = SubqueryUnwrapper(test_settings, sql_parser)

        sql = """
            SELECT * FROM (
                SELECT id, name
                FROM users
                WHERE cob_date='2024-01-15'
            ) sub
        """

        ast = sql_parser.parse(sql)
        was_unwrapped, unwrapped_sql, unwrapped_ast = unwrapper.unwrap(sql, ast)

        assert was_unwrapped is False
