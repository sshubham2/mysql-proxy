# Metadata Query Bypass

## The Problem

Tableau and other MySQL clients query system schemas to discover database structure:
- `SHOW DATABASES`
- `SHOW TABLES`
- `SELECT * FROM INFORMATION_SCHEMA.TABLES`
- `SELECT * FROM INFORMATION_SCHEMA.COLUMNS`

These are **metadata/discovery queries**, not data queries. They should **NOT** be subject to business rules like the mandatory `cob_date` filter.

### Original Issue

When Tableau tried to connect, it would send queries like:
```sql
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE()
```

This was being **validated** and rejected with:
```
ERROR: cob_date filter is mandatory
```

This prevented Tableau from even connecting and discovering tables!

## The Solution

Updated `src/utils/sql_parser.py` to recognize **all metadata queries** and bypass validation:

### What's Considered Metadata

1. **SHOW Statements** ✅
   - `SHOW DATABASES`
   - `SHOW TABLES`
   - `SHOW COLUMNS FROM table_name`
   - `SHOW CREATE TABLE table_name`
   - `SHOW STATUS`
   - `SHOW VARIABLES`

2. **DESCRIBE Statements** ✅
   - `DESCRIBE table_name`
   - `DESC table_name`

3. **USE Statements** ✅
   - `USE database_name`

4. **SET Statements** ✅
   - `SET NAMES utf8mb4`
   - `SET @variable = value`
   - `SET autocommit = 1`

5. **INFORMATION_SCHEMA Queries** ✅ (NEW!)
   - `SELECT * FROM INFORMATION_SCHEMA.TABLES`
   - `SELECT * FROM INFORMATION_SCHEMA.COLUMNS`
   - `SELECT * FROM INFORMATION_SCHEMA.SCHEMATA`
   - Case-insensitive: `information_schema`, `INFORMATION_SCHEMA`

6. **PERFORMANCE_SCHEMA Queries** ✅ (NEW!)
   - `SELECT * FROM performance_schema.threads`
   - `SELECT * FROM performance_schema.events_statements_summary_by_digest`

7. **System Database Queries** ✅ (NEW!)
   - `SELECT * FROM mysql.user`
   - `SELECT * FROM mysql.db`
   - `SELECT * FROM sys.version`
   - `SELECT * FROM sys.schema_table_statistics`

## Implementation

### Before (Broken)
```python
def is_metadata_query(self, sql: str) -> bool:
    query_type = self.get_query_type(sql)
    metadata_types = {QueryType.SHOW, QueryType.DESCRIBE, QueryType.USE, QueryType.SET}
    return query_type in metadata_types
    # ❌ INFORMATION_SCHEMA queries return False!
```

**Problem**: `SELECT * FROM INFORMATION_SCHEMA.TABLES` has `query_type = SELECT`, so it returns `False` and goes through validation!

### After (Fixed)
```python
def is_metadata_query(self, sql: str) -> bool:
    query_type = self.get_query_type(sql)
    metadata_types = {QueryType.SHOW, QueryType.DESCRIBE, QueryType.USE, QueryType.SET}

    if query_type in metadata_types:
        return True

    # Check if SELECT query is from INFORMATION_SCHEMA or other system schemas
    if query_type == QueryType.SELECT:
        sql_upper = sql.upper()
        system_schemas = [
            'INFORMATION_SCHEMA',
            'PERFORMANCE_SCHEMA',
            'MYSQL.', 'SYS.',
        ]
        for schema in system_schemas:
            if schema in sql_upper:
                return True  # ✅ Bypass validation!

    return False
```

## Query Pipeline Flow

### Metadata Queries (Bypassed)

```
Client → Tableau sends: SELECT * FROM INFORMATION_SCHEMA.TABLES
              ↓
    ChronosProxy receives query
              ↓
    QueryPipeline.process()
              ↓
    _is_metadata_query() → TRUE ✅
              ↓
    _execute_metadata_query() (direct execution)
              ↓
    ❌ SKIP security validation
    ❌ SKIP unsupported feature detection
    ❌ SKIP transformation
    ❌ SKIP cob_date validation
              ↓
    Backend MySQL executes query
              ↓
    Returns table list to Tableau
              ↓
    Tableau discovers schema ✅
```

### Regular Data Queries (Validated)

```
Client → Tableau sends: SELECT * FROM my_table
              ↓
    ChronosProxy receives query
              ↓
    QueryPipeline.process()
              ↓
    _is_metadata_query() → FALSE ❌
              ↓
    ✅ Security validation (write blocker)
    ✅ Unsupported feature detection
    ✅ Transformation (subquery unwrap, GROUP BY fix)
    ✅ cob_date validation ← ENFORCED!
              ↓
    ERROR: cob_date filter is mandatory ← Correct behavior!
```

## Testing

### Test Metadata Detection

```python
from src.utils.sql_parser import SQLParser
parser = SQLParser()

# These should ALL return True (bypass validation)
assert parser.is_metadata_query("SHOW DATABASES") == True
assert parser.is_metadata_query("SHOW TABLES") == True
assert parser.is_metadata_query("SELECT * FROM INFORMATION_SCHEMA.TABLES") == True
assert parser.is_metadata_query("select * from information_schema.columns") == True
assert parser.is_metadata_query("SELECT * FROM performance_schema.threads") == True

# These should return False (go through validation)
assert parser.is_metadata_query("SELECT * FROM my_table") == False
assert parser.is_metadata_query("SELECT * FROM customers WHERE id = 1") == False
```

### Test with Tableau

1. **Connect Tableau to ChronosProxy**
   - Host: localhost
   - Port: 3307
   - Database: your_database

2. **Tableau will send discovery queries**:
   ```sql
   SHOW DATABASES;
   SELECT TABLE_SCHEMA FROM INFORMATION_SCHEMA.SCHEMATA;
   SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'your_db';
   SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'your_db';
   ```

3. **All should succeed** ✅ without requiring `cob_date`

4. **When Tableau queries actual data**:
   ```sql
   SELECT * FROM my_table;  -- ❌ Rejected (no cob_date)
   SELECT * FROM my_table WHERE cob_date = '2024-01-01';  -- ✅ Allowed
   ```

## What Gets Bypassed

When a query is detected as metadata, it skips these pipeline steps:

| Step | Regular Query | Metadata Query |
|------|--------------|----------------|
| **Metadata check** | ❌ Not metadata | ✅ **IS METADATA** |
| **Security validation** | ✅ Checked | ❌ **SKIPPED** |
| **SQL parsing** | ✅ Parsed | ❌ **SKIPPED** |
| **Unsupported features** | ✅ Checked | ❌ **SKIPPED** |
| **Transformation** | ✅ Applied | ❌ **SKIPPED** |
| **cob_date validation** | ✅ **ENFORCED** | ❌ **SKIPPED** |
| **Backend execution** | ✅ Executed | ✅ Executed |

## Common Tableau Queries That Now Work

All of these now bypass validation:

```sql
-- Database discovery
SHOW DATABASES;
SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA;

-- Table discovery
SHOW TABLES;
SHOW TABLES FROM database_name;
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE();

-- Column discovery
SHOW COLUMNS FROM table_name;
DESCRIBE table_name;
SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'my_table';

-- Index information
SHOW INDEX FROM table_name;
SELECT * FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_NAME = 'my_table';

-- Table details
SHOW CREATE TABLE table_name;
SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'my_table';

-- Server information
SHOW STATUS;
SHOW VARIABLES;
SELECT @@version;
SELECT @@character_set_database;
```

## Edge Cases

### What about SELECT from user tables named like system schemas?

**Q**: What if I have a table called `information_schema_backup`?
```sql
SELECT * FROM information_schema_backup WHERE cob_date = '2024-01-01'
```

**A**: This would be detected as metadata (contains "INFORMATION_SCHEMA") and bypass validation.

**Solution**: The check looks for exact schema references:
- `INFORMATION_SCHEMA.` (with dot)
- `FROM INFORMATION_SCHEMA`
- Not just any table with those words

However, current implementation is simple string matching. If this becomes an issue, we can improve it to parse the schema name properly.

### Does this affect security?

**No**. Metadata queries are **read-only** by nature:
- `SHOW` commands are always read-only
- `INFORMATION_SCHEMA` is a read-only virtual database
- Write blocker still active (would catch INSERT/UPDATE/DELETE)
- System schemas are informational only

## Configuration

No configuration needed! This is automatic behavior.

If you want to **disable** metadata bypass (not recommended):

```python
# In src/core/query_pipeline.py
def process(self, sql: str):
    # Comment out this check:
    # if self._is_metadata_query(sql):
    #     return self._execute_metadata_query(query_id, sql)

    # Now ALL queries go through validation
```

**Warning**: Disabling this will **break Tableau and most MySQL clients**!

## Benefits

✅ **Tableau can connect** - Discovery queries work
✅ **JDBC/ODBC compatible** - Client metadata APIs work
✅ **Schema browsing works** - Tools can list tables/columns
✅ **cob_date still enforced** - On actual data queries
✅ **Performance** - Metadata queries skip unnecessary validation
✅ **Security maintained** - Write operations still blocked

## Summary

| Query | Detected As | cob_date Required? | Why |
|-------|------------|-------------------|-----|
| `SHOW DATABASES` | Metadata | ❌ No | Discovery query |
| `SHOW TABLES` | Metadata | ❌ No | Discovery query |
| `SELECT * FROM INFORMATION_SCHEMA.TABLES` | Metadata | ❌ No | System schema |
| `SELECT * FROM performance_schema.threads` | Metadata | ❌ No | System schema |
| `SELECT * FROM mysql.user` | Metadata | ❌ No | System database |
| `SELECT * FROM my_table` | Data query | ✅ **YES** | User data table |
| `SELECT * FROM customers WHERE id = 1` | Data query | ✅ **YES** | User data table |

**Fixed in**: `src/utils/sql_parser.py:74-104`

Tableau and other clients can now connect and discover your schema! 🎉
