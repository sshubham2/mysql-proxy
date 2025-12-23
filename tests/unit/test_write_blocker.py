"""
Unit tests for Write Blocker
"""

import pytest
from src.security.write_blocker import WriteBlocker, WriteOperationBlocked


class TestWriteBlocker:
    """Test write operation blocking"""

    @pytest.fixture
    def blocker(self, test_settings):
        """Create write blocker instance"""
        return WriteBlocker(test_settings)

    def test_block_insert(self, blocker):
        """Test blocking INSERT operation"""
        sql = "INSERT INTO users (id, name) VALUES (1, 'test')"

        with pytest.raises(WriteOperationBlocked) as exc_info:
            blocker.check_query(sql)

        assert exc_info.value.operation == "INSERT"

    def test_block_update(self, blocker):
        """Test blocking UPDATE operation"""
        sql = "UPDATE users SET name='test' WHERE id=1"

        with pytest.raises(WriteOperationBlocked) as exc_info:
            blocker.check_query(sql)

        assert exc_info.value.operation == "UPDATE"

    def test_block_delete(self, blocker):
        """Test blocking DELETE operation"""
        sql = "DELETE FROM users WHERE id=1"

        with pytest.raises(WriteOperationBlocked) as exc_info:
            blocker.check_query(sql)

        assert exc_info.value.operation == "DELETE"

    def test_block_drop(self, blocker):
        """Test blocking DROP operation"""
        sql = "DROP TABLE users"

        with pytest.raises(WriteOperationBlocked) as exc_info:
            blocker.check_query(sql)

        assert exc_info.value.operation == "DROP"

    def test_allow_select(self, blocker):
        """Test allowing SELECT operation"""
        sql = "SELECT id, name FROM users WHERE cob_date='2024-01-15'"

        # Should not raise
        blocker.check_query(sql)

    def test_disabled_blocker(self, test_settings):
        """Test blocker when disabled"""
        test_settings.security['block_writes'] = False
        blocker = WriteBlocker(test_settings)

        sql = "INSERT INTO users (id, name) VALUES (1, 'test')"

        # Should not raise when disabled
        blocker.check_query(sql)
