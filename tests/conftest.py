"""
Pytest configuration and shared fixtures
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import Settings
from src.utils.sql_parser import SQLParser


@pytest.fixture
def test_settings():
    """Create test settings with minimal configuration"""
    import tempfile
    import yaml

    # Create minimal test config
    config = {
        'proxy': {
            'host': '127.0.0.1',
            'port': 3307,
        },
        'backend': {
            'connection_type': 'odbc',
            'odbc': {
                'connection_string': 'DRIVER={MySQL};SERVER=localhost;DATABASE=test'
            },
            'pool_size': 5
        },
        'capabilities': {
            'unsupported_features': ['joins', 'unions', 'window_functions'],
            'unsupported_functions': ['COUNT']
        },
        'transformations': {
            'unwrap_subqueries': True,
            'max_subquery_depth': 2,
            'auto_fix_group_by': True
        },
        'business_rules': {
            'require_cob_date': True,
            'require_complete_group_by': True,
            'allowed_databases': [],
            'blocked_databases': ['mysql', 'information_schema']
        },
        'security': {
            'block_writes': True,
            'write_operations': ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE']
        },
        'logging': {
            'level': 'INFO',
            'log_dir': 'logs'
        }
    }

    # Create temporary config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config, f)
        config_file = f.name

    settings = Settings(config_file)

    yield settings

    # Cleanup
    import os
    os.unlink(config_file)


@pytest.fixture
def sql_parser():
    """Create SQL parser instance"""
    return SQLParser()


@pytest.fixture
def sample_queries():
    """Sample SQL queries for testing"""
    return {
        'simple_select': "SELECT id, name FROM users WHERE cob_date='2024-01-15'",

        'tableau_subquery': """
            SELECT * FROM (
                SELECT category, SUM(amount) AS total
                FROM sales
                WHERE cob_date='2024-01-15'
            ) sub
            WHERE category='Electronics'
        """,

        'missing_group_by': """
            SELECT category, SUM(amount)
            FROM sales
            WHERE cob_date='2024-01-15'
        """,

        'with_join': """
            SELECT a.id, b.name
            FROM sales a
            JOIN products b ON a.product_id = b.id
            WHERE a.cob_date='2024-01-15'
        """,

        'with_union': """
            SELECT id FROM sales WHERE cob_date='2024-01-15'
            UNION
            SELECT id FROM archive WHERE cob_date='2024-01-15'
        """,

        'with_window_function': """
            SELECT id, ROW_NUMBER() OVER (ORDER BY amount DESC) AS rank
            FROM sales
            WHERE cob_date='2024-01-15'
        """,

        'with_count': """
            SELECT category, COUNT(*)
            FROM sales
            WHERE cob_date='2024-01-15'
            GROUP BY category
        """,

        'missing_cob_date': """
            SELECT category, SUM(amount)
            FROM sales
            GROUP BY category
        """,

        'write_operation': "INSERT INTO sales (id, amount) VALUES (1, 100)"
    }
