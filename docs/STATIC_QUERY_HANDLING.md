# Static Query Handling

## The Problem

MySQL clients frequently send "static queries" - queries with no FROM clause that return session/connection information:

- `SELECT CONNECTION_ID()` - Get current connection ID
- `SELECT DATABASE()` - Get current database
- `SELECT USER()` - Get current user
- `SELECT VERSION()` - Get MySQL version
- `SELECT @@version` - Get system variable
- `SELECT 1` - Connection test

### Issues with Backend Driver

1. **Backend may not support these queries**: Your driver may reject `SELECT CONNECTION_ID()`
2. **Validation blocks them**: These are SELECT queries that would require `cob_date` filter
3. **Unnecessary backend load**: These queries don't need to reach the backend

## The Solution

Added `_static_query_middleware` to handle static queries **locally** in the proxy using mysql-mimic's built-in execution engine.

### What's a Static Query?

A static query is a SELECT with:
- ✅ SELECT expression(s)
- ❌ No FROM clause
- ❌ No WHERE clause
- ❌ No GROUP BY
- ❌ No HAVING
- ❌ No ORDER BY
- ✅ Optional LIMIT/HINT

**Examples**:
```sql
-- Static queries (handled locally)
SELECT CONNECTION_ID()
SELECT DATABASE()
SELECT USER()
SELECT VERSION()
SELECT 1
SELECT 'hello world'
SELECT @@version
SELECT @@character_set_database
SELECT 1 + 2 AS result
SELECT NOW()

-- NOT static (sent to backend)
SELECT * FROM my_table
SELECT CONNECTION_ID() FROM DUAL
SELECT 1 WHERE 1=1
```

## How It Works

### Middleware Chain

In [src/core/session.py:46](src/core/session.py#L46), we include `_static_query_middleware`:

```python
self.middlewares = [
    self._set_var_middleware,    # Handle SET @var
    self._set_middleware,         # Handle SET NAMES, etc.
    self._static_query_middleware, # Handle SELECT CONNECTION_ID(), etc. ✅
    self._use_middleware,         # Handle USE database
]
```

### Execution Flow

```
Client sends: SELECT CONNECTION_ID()
         ↓
   mysql-mimic server
         ↓
   Session.query()
         ↓
   Middleware chain
         ↓
   _static_query_middleware checks:
     - Is it a SELECT? ✅
     - Has no FROM/WHERE/GROUP BY? ✅
         ↓
   Execute locally using sqlglot
         ↓
   Return result (e.g., connection_id: 42)
         ↓
   Client receives result

   ❌ Never reaches backend!
   ❌ Never goes through query pipeline!
   ❌ Never validated for cob_date!
```

### What Gets Executed Locally

The middleware uses **sqlglot's execution engine** to evaluate expressions:

```python
# mysql-mimic source
async def _static_query_middleware(self, q: Query) -> AllowedResult:
    if isinstance(q.expression, exp.Select) and not has_from_where_etc:
        result = execute(q.expression)  # Execute with sqlglot
        return result.rows, result.columns
    return await q.next()
```

**Supported functions** (executed by sqlglot):
- `CONNECTION_ID()` - Returns session connection ID
- `DATABASE()` - Returns current database
- `USER()` - Returns current user
- `VERSION()` - Returns MySQL version
- `NOW()`, `CURDATE()`, `CURTIME()` - Date/time functions
- Math: `1 + 2`, `RAND()`, `FLOOR()`, etc.
- String: `CONCAT()`, `UPPER()`, `LOWER()`, etc.
- System variables: `@@version`, `@@character_set_database`

## Common Client Queries

### JDBC Driver
```sql
SELECT @@session.auto_increment_increment AS auto_increment_increment
SELECT @@character_set_database
SELECT DATABASE()
SELECT CONNECTION_ID()
```

### ODBC Driver
```sql
SELECT USER()
SELECT DATABASE()
SELECT VERSION()
```

### Tableau
```sql
SELECT DATABASE()
SELECT CONNECTION_ID()
SELECT @@version_comment
```

### MySQL Workbench
```sql
SELECT CONNECTION_ID()
SELECT USER()
SELECT DATABASE()
SELECT VERSION()
```

**All of these now work** without reaching your backend!

## Benefits

### 1. Backend Compatibility
- Backend doesn't need to support `CONNECTION_ID()` or other session functions
- Driver limitations completely bypassed
- No modifications needed to backend server

### 2. No Validation Required
- Static queries skip cob_date validation
- Skip unsupported feature detection
- Skip transformation pipeline

### 3. Performance
- No network round-trip to backend
- Instant response from proxy
- Reduced backend load

### 4. Accurate Session Info
- `CONNECTION_ID()` returns the proxy's connection ID
- `DATABASE()` returns the current database tracked by proxy
- `USER()` returns the authenticated user

## Testing

### Test Static Query Detection

```python
from sqlglot import parse_one, exp

sql = "SELECT CONNECTION_ID()"
ast = parse_one(sql, dialect='mysql')

# Check if static (no FROM, WHERE, etc.)
is_static = isinstance(ast, exp.Select) and not any(
    ast.args.get(a)
    for a in set(exp.Select.arg_types) - {'expressions', 'limit', 'hint'}
)

assert is_static == True  # ✅ Will be handled locally
```

### Test with MySQL Client

```sql
-- Connect to ChronosProxy
mysql -h localhost -P 3307 -u root

-- These should all work instantly
SELECT CONNECTION_ID();
-- Returns: (e.g., 42)

SELECT DATABASE();
-- Returns: your_database (if USE was called)

SELECT USER();
-- Returns: root@localhost

SELECT VERSION();
-- Returns: MySQL version

SELECT 1;
-- Returns: 1

SELECT @@version;
-- Returns: MySQL version

-- This should go to backend and require cob_date
SELECT * FROM my_table;
-- ERROR: cob_date filter is mandatory
```

## What Still Goes to Backend

Not all SELECT queries are static:

```sql
-- These have FROM clause → go to backend
SELECT * FROM my_table
SELECT CONNECTION_ID() FROM DUAL
SELECT DATABASE() FROM information_schema.tables LIMIT 1

-- These have WHERE/GROUP BY → go to backend
SELECT 1 WHERE 1=1
SELECT COUNT(*) GROUP BY status
```

## Architecture Comparison

### Before (Broken)

```
Client: SELECT CONNECTION_ID()
    ↓
Proxy: Treat as regular SELECT
    ↓
QueryPipeline.process()
    ↓
Validation: ❌ Requires cob_date filter
    ↓
ERROR: cob_date filter is mandatory
```

### After (Fixed)

```
Client: SELECT CONNECTION_ID()
    ↓
Proxy: Intercept via _static_query_middleware
    ↓
Execute locally with sqlglot
    ↓
Return: connection_id = 42
    ↓
Client: ✅ Success
```

## Edge Cases

### What about SELECT 1 for connection testing?

**Before this fix**: We changed connection tests to use `SHOW STATUS` because `SELECT 1` would be validated.

**Now**: `SELECT 1` works again! But we'll **keep** `SHOW STATUS` for connection tests because:
- It's more descriptive (actually checks server status)
- Consistent with the pattern of using metadata queries
- No need to change back

### What if backend needs these queries?

Some backends may need to see certain static queries. If needed, you can:

1. **Remove the middleware**:
```python
# Don't include _static_query_middleware
self.middlewares = [
    self._set_var_middleware,
    self._set_middleware,
    # self._static_query_middleware,  # ← Commented out
    self._use_middleware,
]
```

2. **Mark them as metadata** in `sql_parser.py`:
```python
# Add to is_metadata_query()
if "CONNECTION_ID()" in sql_upper:
    return True
```

## Middleware Order

The order matters! Static query middleware should come **before** other interceptors:

```python
self.middlewares = [
    self._set_var_middleware,    # 1. Handle SET @var
    self._set_middleware,         # 2. Handle SET NAMES, etc.
    self._static_query_middleware, # 3. Handle SELECT 1, CONNECTION_ID()
    self._use_middleware,         # 4. Handle USE database
    # Other queries continue to query() method
]
```

If a query matches multiple middlewares, the **first one** handles it.

## Summary

| Query | Type | Handler | Backend Needed? |
|-------|------|---------|-----------------|
| `SELECT CONNECTION_ID()` | Static | `_static_query_middleware` | ❌ No |
| `SELECT DATABASE()` | Static | `_static_query_middleware` | ❌ No |
| `SELECT USER()` | Static | `_static_query_middleware` | ❌ No |
| `SELECT VERSION()` | Static | `_static_query_middleware` | ❌ No |
| `SELECT 1` | Static | `_static_query_middleware` | ❌ No |
| `SELECT @@version` | Static | `_static_query_middleware` | ❌ No |
| `SELECT * FROM table` | Regular | Backend execution | ✅ Yes |

## Implementation Status

✅ **Fixed**: `SELECT CONNECTION_ID()` now works locally
✅ **Location**: [src/core/session.py:46](src/core/session.py#L46)
✅ **Backend impact**: None - completely handled by proxy
✅ **Client compatibility**: JDBC, ODBC, Tableau all work

Your backend driver will **never see** static queries like `SELECT CONNECTION_ID()` - they're completely handled by the proxy's middleware!
