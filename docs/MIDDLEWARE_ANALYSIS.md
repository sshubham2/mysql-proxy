# mysql-mimic Middleware Analysis for Proxy Use Case

## The Problem

The mysql-mimic `Session` class has built-in middlewares that intercept certain queries and handle them automatically. This is great for building a standalone MySQL server, but **problematic for a proxy** where we want queries to pass through to the real backend MySQL server.

## Default Session Middlewares

When you inherit from `Session`, you get these middlewares by default:

```python
self.middlewares: list[Middleware] = [
    self._set_var_middleware,        # SET statements
    self._set_middleware,            # SET commands (legacy)
    self._static_query_middleware,   # Static queries (SELECT 1, etc.)
    self._use_middleware,            # USE database
    self._kill_middleware,           # KILL connection
    self._show_middleware,           # SHOW statements
    self._describe_middleware,       # DESCRIBE/EXPLAIN statements
    self._begin_middleware,          # BEGIN transaction
    self._commit_middleware,         # COMMIT transaction
    self._rollback_middleware,       # ROLLBACK transaction
    self._info_schema_middleware,    # INFORMATION_SCHEMA queries
]
```

## What Each Middleware Does

### Metadata Middlewares (⚠️ Problematic for Proxy)

These intercept queries and return synthetic results:

- **`_show_middleware`**: Intercepts `SHOW TABLES`, `SHOW COLUMNS`, etc.
  - Calls `self._show()` which generates results from `self.schema()`
  - **Problem**: Returns proxy's schema, not backend's schema!

- **`_describe_middleware`**: Intercepts `DESCRIBE table_name`
  - Converts to `SHOW COLUMNS FROM table_name`
  - **Problem**: Returns proxy's schema, not backend's schema!

- **`_info_schema_middleware`**: Intercepts queries to `INFORMATION_SCHEMA`
  - Calls `self._query_info_schema()` to generate synthetic results
  - **Problem**: Returns proxy's schema, not backend's schema!

### Connection Management Middlewares (✅ Keep These)

These handle session-level state:

- **`_set_var_middleware`**: Handles `SET @variable = value`
  - Stores user-defined variables in session
  - **Keep**: Session variables should be local to the connection

- **`_use_middleware`**: Handles `USE database_name`
  - Updates `self.database` to track current database
  - **Keep**: Current database is session state

### Transaction Middlewares (❓ Decision Needed)

These handle transaction control:

- **`_begin_middleware`**: Handles `BEGIN` / `START TRANSACTION`
- **`_commit_middleware`**: Handles `COMMIT`
- **`_rollback_middleware`**: Handles `ROLLBACK`

**For a proxy, we want these to pass through to the backend!**
- The backend MySQL server manages the actual transaction
- Proxy should not intercept these

### Other Middlewares

- **`_set_middleware`**: Legacy SET command handler
  - Might conflict with `_set_var_middleware`
  - **Decision**: Remove to avoid conflicts

- **`_static_query_middleware`**: Handles static queries like `SELECT 1`
  - **Decision**: Let backend handle these for consistency

- **`_kill_middleware`**: Handles `KILL connection_id`
  - **Decision**: Remove - we can't kill backend connections from proxy

## Our Proxy Requirements

For **ChronosProxy**, we need:

1. **Metadata queries → Backend**: Tableau needs to see the real backend schema
   - `SHOW TABLES` should show backend tables
   - `SHOW COLUMNS` should show backend columns
   - `INFORMATION_SCHEMA` queries should return backend metadata

2. **Session state → Local**: Track client session state
   - `SET @var = value` should be stored locally
   - `USE database` should update local state

3. **Transactions → Backend**: Backend manages transactions
   - `BEGIN`, `COMMIT`, `ROLLBACK` should pass through

## Solution: Override Middlewares

In `src/core/session.py`, we override the middlewares list:

```python
class ChronosSession(Session):
    def __init__(self, settings, executor, connection_id):
        super().__init__()

        # Override middlewares to pass everything to backend
        # Only keep essential session state management
        self.middlewares = [
            self._set_var_middleware,    # Handle SET @var (session variables)
            self._set_middleware,         # Handle SET NAMES, SET CHARACTER SET, etc.
            self._static_query_middleware, # Handle SELECT CONNECTION_ID(), etc.
            self._use_middleware,         # Handle USE database (current db)
        ]
```

### What This Does

**Intercepted locally** (handled by middlewares):
- `SET @variable = value` - Session variables (user-defined variables)
- `SET NAMES utf8mb4` - Character set configuration
- `SET CHARACTER SET utf8` - Character set configuration
- `SET TRANSACTION ISOLATION LEVEL READ COMMITTED` - Transaction characteristics
- `SELECT CONNECTION_ID()` - Static queries (no FROM clause)
- `SELECT DATABASE()` - Static queries (no FROM clause)
- `SELECT USER()`, `SELECT VERSION()` - Static queries
- `SELECT 1`, `SELECT @@version` - Static queries
- `USE database_name` - Current database

**Passed to backend** (go to `query()` method → backend):
- `SHOW TABLES` - Backend's tables
- `SHOW COLUMNS FROM table` - Backend's columns
- `DESCRIBE table` - Backend's table structure
- `SELECT * FROM INFORMATION_SCHEMA.TABLES` - Backend's metadata
- `BEGIN` / `COMMIT` / `ROLLBACK` - Backend's transaction control
- `SELECT ...` - All regular queries
- `SELECT 1` - Static queries

## Alternative: Use BaseSession

The mysql-mimic documentation mentions:

> Using sqlglot, the abstract Session class handles queries to metadata, variables, etc. that many MySQL clients expect. To bypass this default behavior, you can implement the mysql_mimic.session.BaseSession interface.

### What is BaseSession?

`BaseSession` is a minimal interface with **no middlewares**. All queries go directly to `query()`.

### Why We Don't Use It

1. **Session variables are useful**: Tableau/MySQL clients expect `SET @var` to work
2. **Current database tracking**: Many clients rely on `USE database`
3. **Minimal overhead**: Only 2 middlewares have negligible performance impact
4. **Better compatibility**: Matches normal MySQL behavior for session state

### When to Use BaseSession

Use `BaseSession` if:
- Building a minimal proxy with no state
- Want complete control over every query
- Don't need session variable support
- Don't need current database tracking

## Verification

To verify the correct middlewares are active:

```python
# In ChronosSession.__init__, add logging:
self.logger.info(f"Active middlewares: {[m.__name__ for m in self.middlewares]}")

# Expected output:
# Active middlewares: ['_set_var_middleware', '_use_middleware']
```

## Testing Metadata Queries

Test that metadata queries reach the backend:

```sql
-- Connect to ChronosProxy (port 3307)
USE test_database;

-- These should return backend's actual data, not proxy's synthetic data
SHOW TABLES;
SHOW COLUMNS FROM my_table;
SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'test_database';
DESCRIBE my_table;

-- These should work locally (session state)
SET @my_var = 123;
SELECT @my_var;  -- Should return 123
USE other_database;
```

## Summary

| Query Type | Handler | Reason |
|------------|---------|--------|
| **SET @var** | `_set_var_middleware` | Session variables are local state |
| **SET NAMES** | `_set_middleware` | Character set is session state |
| **SET CHARACTER SET** | `_set_middleware` | Character set is session state |
| **SET TRANSACTION** | `_set_middleware` | Transaction options are session state |
| **SELECT CONNECTION_ID()** | `_static_query_middleware` | Session info, no backend needed |
| **SELECT DATABASE()** | `_static_query_middleware` | Session info, no backend needed |
| **SELECT 1** | `_static_query_middleware` | Static query, no backend needed |
| **USE database** | `_use_middleware` | Current database is local state |
| **SHOW statements** | **Backend** (via `query()`) | Need real backend schema |
| **DESCRIBE** | **Backend** (via `query()`) | Need real backend schema |
| **INFORMATION_SCHEMA** | **Backend** (via `query()`) | Need real backend metadata |
| **BEGIN/COMMIT/ROLLBACK** | **Backend** (via `query()`) | Backend manages transactions |
| **SELECT * FROM table** | **Backend** (via `query()`) | Data queries to backend |

## Implementation Status

✅ **CORRECT**: Current implementation in `src/core/session.py` properly overrides middlewares

```python
# Override middlewares to pass everything to backend
# Only keep essential session state management
self.middlewares = [
    self._set_var_middleware,    # Handle SET @var (session variables)
    self._set_middleware,         # Handle SET NAMES, SET CHARACTER SET, etc.
    self._static_query_middleware, # Handle SELECT CONNECTION_ID(), etc.
    self._use_middleware,         # Handle USE database (current db tracking)
]
```

This ensures:
- Tableau sees the real backend schema
- Metadata queries return accurate backend information
- Session state (variables, current database) is tracked locally
- Transactions are managed by the backend
- No unexpected query interception

**No changes needed** - the middleware configuration is correct for a proxy server!
