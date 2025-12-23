"""
Unit tests for GROUP BY Fixer
"""

import pytest
from src.transformation.group_by_fixer import GroupByFixer
from src.utils.sql_parser import SQLParser


class TestGroupByFixer:
    """Test GROUP BY auto-fix functionality"""

    @pytest.fixture
    def fixer(self, test_settings):
        """Create GROUP BY fixer instance"""
        sql_parser = SQLParser()
        return GroupByFixer(test_settings, sql_parser)

    def test_add_missing_group_by(self, fixer, sql_parser):
        """Test adding missing GROUP BY clause"""
        sql = """
            SELECT category, SUM(amount)
            FROM sales
            WHERE cob_date='2024-01-15'
        """

        ast = sql_parser.parse(sql)
        was_fixed, fixed_sql, fixed_ast, added_cols = fixer.fix(sql, ast)

        assert was_fixed is True
        assert "GROUP BY" in fixed_sql.upper()
        assert "category" in added_cols

    def test_complete_incomplete_group_by(self, fixer, sql_parser):
        """Test completing incomplete GROUP BY clause"""
        sql = """
            SELECT category, region, SUM(amount)
            FROM sales
            WHERE cob_date='2024-01-15'
            GROUP BY category
        """

        ast = sql_parser.parse(sql)
        was_fixed, fixed_sql, fixed_ast, added_cols = fixer.fix(sql, ast)

        assert was_fixed is True
        assert "region" in added_cols

    def test_complete_group_by_not_fixed(self, fixer, sql_parser):
        """Test that complete GROUP BY is not modified"""
        sql = """
            SELECT category, SUM(amount)
            FROM sales
            WHERE cob_date='2024-01-15'
            GROUP BY category
        """

        ast = sql_parser.parse(sql)
        was_fixed, fixed_sql, fixed_ast, added_cols = fixer.fix(sql, ast)

        assert was_fixed is False

    def test_no_aggregations_not_fixed(self, fixer, sql_parser):
        """Test that queries without aggregations are not modified"""
        sql = """
            SELECT category, region
            FROM sales
            WHERE cob_date='2024-01-15'
        """

        ast = sql_parser.parse(sql)
        was_fixed, fixed_sql, fixed_ast, added_cols = fixer.fix(sql, ast)

        assert was_fixed is False

    def test_all_aggregated_not_fixed(self, fixer, sql_parser):
        """Test that queries with all columns aggregated don't need GROUP BY"""
        sql = """
            SELECT SUM(amount), AVG(price)
            FROM sales
            WHERE cob_date='2024-01-15'
        """

        ast = sql_parser.parse(sql)
        was_fixed, fixed_sql, fixed_ast, added_cols = fixer.fix(sql, ast)

        assert was_fixed is False
