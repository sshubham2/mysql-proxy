# Connection Testing Strategy

## The Problem with `SELECT 1`

Initially, the code used `SELECT 1` for connection health checks:

```python
# ❌ WRONG - Gets rejected by validation
cursor.execute("SELECT 1")
test_result = executor.execute("SELECT 1 AS test")
```

### Why This Fails

1. **Not a metadata query**: `SELECT 1` is a regular SELECT query, not a metadata query like SHOW/DESCRIBE
2. **Goes through full validation pipeline**:
   - Security validation
   - Unsupported feature detection
   - Business rule validation (cob_date requirement)
3. **May be blocked**: Depending on validation rules, static SELECT queries might be rejected

## The Solution: Use SHOW Queries

Metadata queries (SHOW, DESCRIBE, USE, SET) **bypass validation** and execute directly:

```python
# ✅ CORRECT - Bypasses validation
cursor.execute("SHOW STATUS LIKE 'Threads_connected'")
test_result = executor.execute("SHOW STATUS LIKE 'Threads_connected'")
```

### Why This Works

From `src/core/query_pipeline.py`:

```python
def process(self, sql: str) -> QueryPipelineResult:
    # Step 1: Metadata query check
    if self._is_metadata_query(sql):
        return self._execute_metadata_query(query_id, sql)

    # All other queries go through validation...
```

Metadata queries identified by `src/utils/sql_parser.py`:

```python
def is_metadata_query(self, sql: str) -> bool:
    query_type = self.get_query_type(sql)
    metadata_types = {QueryType.SHOW, QueryType.DESCRIBE, QueryType.USE, QueryType.SET}
    return query_type in metadata_types
```

## Best Queries for Connection Testing

### Option 1: `SHOW STATUS LIKE 'Threads_connected'` ✅ (Recommended)

**Pros**:
- Fast and lightweight
- Returns actual data (number of connected threads)
- Works on all MySQL versions
- Bypasses validation pipeline

**Example**:
```python
cursor.execute("SHOW STATUS LIKE 'Threads_connected'")
result = cursor.fetchone()
# Returns: ('Threads_connected', '42')
```

### Option 2: `SHOW VARIABLES LIKE 'version'` ✅

**Pros**:
- Fast
- Returns MySQL version
- Useful diagnostic information

**Example**:
```python
cursor.execute("SHOW VARIABLES LIKE 'version'")
result = cursor.fetchone()
# Returns: ('version', '8.0.35')
```

### Option 3: `SHOW DATABASES` ✅

**Pros**:
- Very simple
- Lists available databases

**Cons**:
- Returns potentially large result set
- May expose database names

### ❌ NOT Recommended

- `SELECT 1` - Gets validated, may be blocked
- `SELECT VERSION()` - Still a SELECT query, goes through validation
- `SELECT NOW()` - Same issue
- `SHOW TABLES` - Requires active database context

## Implementation

### In Connection Health Checks

**File**: `src/backend/odbc_connection.py`

```python
def _is_connection_alive(self, conn) -> bool:
    """Test if connection is alive"""
    try:
        cursor = conn.cursor()
        # Use SHOW query instead of SELECT 1 to avoid validation issues
        cursor.execute("SHOW STATUS LIKE 'Threads_connected'")
        cursor.fetchone()
        cursor.close()
        return True
    except:
        return False
```

### In Startup Connection Test

**File**: `src/main.py`

```python
# Test connection
logger.info("Testing backend connection...")
executor = QueryExecutor(connection_pool)
# Use SHOW query instead of SELECT 1 to avoid validation issues
test_result = executor.execute("SHOW STATUS LIKE 'Threads_connected'")

if not test_result.success:
    logger.error(f"Backend connection test failed: {test_result.error}")
    sys.exit(1)

logger.info("Backend connection successful")
```

## Query Pipeline Flow

### Metadata Query Path (Fast, No Validation)

```
Client → mysql-mimic → Session.query()
                            ↓
                     QueryPipeline.process()
                            ↓
                  is_metadata_query() → YES
                            ↓
              _execute_metadata_query()
                            ↓
                  Backend (direct execution)
                            ↓
                         Response
```

### Regular Query Path (Full Validation)

```
Client → mysql-mimic → Session.query()
                            ↓
                     QueryPipeline.process()
                            ↓
                  is_metadata_query() → NO
                            ↓
           ┌─────────────────────────────────┐
           │ 1. Security validation         │
           │ 2. SQL parsing                 │
           │ 3. Unsupported feature check   │
           │ 4. Transformation              │
           │ 5. Business rule validation    │
           └─────────────────────────────────┘
                            ↓
                  Backend execution
                            ↓
                         Response
```

## Other Metadata Queries (Reference)

All these bypass validation:

- `SHOW TABLES`
- `SHOW COLUMNS FROM table_name`
- `SHOW CREATE TABLE table_name`
- `SHOW STATUS`
- `SHOW VARIABLES`
- `SHOW PROCESSLIST`
- `DESCRIBE table_name`
- `DESC table_name`
- `USE database_name`
- `SET @variable = value`
- `SET NAMES utf8mb4`

## Testing

To verify metadata queries bypass validation:

```sql
-- Connect to ChronosProxy
mysql -h localhost -P 3307 -u root

-- These should work immediately (no validation)
SHOW STATUS LIKE 'Threads_connected';
SHOW VARIABLES LIKE 'version';
SHOW DATABASES;

-- This might get validated/rejected
SELECT 1;  -- Depends on validation rules
```

## Summary

| Query | Type | Validated? | Recommended for Health Check? |
|-------|------|------------|-------------------------------|
| `SELECT 1` | Regular SELECT | ✅ Yes | ❌ No |
| `SELECT VERSION()` | Regular SELECT | ✅ Yes | ❌ No |
| `SHOW STATUS LIKE '...'` | Metadata | ❌ No | ✅ **YES** |
| `SHOW VARIABLES LIKE '...'` | Metadata | ❌ No | ✅ Yes |
| `SHOW DATABASES` | Metadata | ❌ No | ⚠️ Maybe |
| `DESCRIBE table` | Metadata | ❌ No | ⚠️ Requires table |

**Best Choice**: `SHOW STATUS LIKE 'Threads_connected'`
- Fast
- Lightweight
- Always works
- Returns meaningful data
- Bypasses all validation

## Code Changes Made

1. **`src/backend/odbc_connection.py:91`**
   - Changed from: `cursor.execute("SELECT 1")`
   - Changed to: `cursor.execute("SHOW STATUS LIKE 'Threads_connected'")`

2. **`src/main.py:112`**
   - Changed from: `executor.execute("SELECT 1 AS test")`
   - Changed to: `executor.execute("SHOW STATUS LIKE 'Threads_connected'")`

These changes ensure connection testing doesn't trigger validation rules and works reliably.
