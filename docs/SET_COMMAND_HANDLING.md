# SET Command Handling in ChronosProxy

## The Problem

MySQL clients frequently send `SET` commands to configure the session:
- `SET NAMES utf8mb4` - Configure character encoding
- `SET CHARACTER SET utf8` - Set character set
- `SET AUTOCOMMIT = 1` - Configure transaction behavior
- `SET @my_var = 123` - User-defined variables

If your backend driver doesn't support these commands (error: "SET NAMES not allowed by driver"), the proxy needs to handle them locally.

## The Solution

ChronosProxy intercepts and handles SET commands **locally** using mysql-mimic's `_set_middleware`. This means:
- The commands never reach the backend
- Session state is tracked in the proxy
- Backend driver limitations don't matter
- Client compatibility is maintained

## How It Works

### Middleware Configuration

In `src/core/session.py`, we enable the `_set_middleware`:

```python
self.middlewares = [
    self._set_var_middleware,  # Handle SET @var (session variables)
    self._set_middleware,       # Handle SET NAMES, SET CHARACTER SET, etc.
    self._use_middleware,       # Handle USE database (current db tracking)
]
```

### What Each Middleware Handles

#### 1. `_set_var_middleware` - User Variables
Handles: `SET @variable_name = value`

**Examples**:
```sql
SET @user_id = 123;
SET @start_date = '2024-01-01';
SELECT @user_id;  -- Returns 123
```

**Behavior**:
- Stores variables in `session.variables`
- Variables persist for the session
- Can be referenced in subsequent queries

#### 2. `_set_middleware` - Session Configuration
Handles multiple SET commands:

##### a) SET NAMES
**Syntax**: `SET NAMES charset_name [COLLATE collation_name]`

**Examples**:
```sql
SET NAMES utf8mb4;
SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;
SET NAMES DEFAULT;
```

**What it does**:
```python
# Sets these session variables:
self.variables.set("character_set_client", "utf8mb4")
self.variables.set("character_set_connection", "utf8mb4")
self.variables.set("character_set_results", "utf8mb4")
self.variables.set("collation_connection", "utf8mb4_unicode_ci")
```

##### b) SET CHARACTER SET
**Syntax**: `SET CHARACTER SET charset_name`

**Examples**:
```sql
SET CHARACTER SET utf8;
SET CHARACTER SET latin1;
SET CHARACTER SET DEFAULT;
```

**What it does**:
```python
# Sets these session variables:
self.variables.set("character_set_client", "utf8")
self.variables.set("character_set_results", "utf8")
# connection uses database charset
self.variables.set("character_set_connection", database_charset)
```

##### c) SET TRANSACTION
**Syntax**: `SET TRANSACTION characteristic [, characteristic]...`

**Examples**:
```sql
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;
SET TRANSACTION READ ONLY;
SET TRANSACTION READ WRITE;
```

**What it does**:
```python
# Maps characteristics to session variables:
"READ UNCOMMITTED" -> ("tx_isolation", "READ-UNCOMMITTED")
"READ COMMITTED" -> ("tx_isolation", "READ-COMMITTED")
"REPEATABLE READ" -> ("tx_isolation", "REPEATABLE-READ")
"SERIALIZABLE" -> ("tx_isolation", "SERIALIZABLE")
"READ ONLY" -> ("tx_read_only", 1)
"READ WRITE" -> ("tx_read_only", 0)
```

##### d) SET SESSION/GLOBAL Variables
**Syntax**: `SET [SESSION|GLOBAL] variable_name = value`

**Examples**:
```sql
SET SESSION autocommit = 1;
SET GLOBAL max_connections = 1000;
SET sql_mode = 'STRICT_TRANS_TABLES';
```

**What it does**:
- Stores the variable in session state
- Tracks session vs global scope
- Values can be queried via `SELECT @@variable_name`

#### 3. `_use_middleware` - Database Selection
Handles: `USE database_name`

**Example**:
```sql
USE my_database;
```

**Behavior**:
- Updates `session.database` to track current database
- Affects subsequent queries that don't specify database

## Why Handle SET Commands Locally?

### 1. Backend Compatibility
Some backend drivers/servers have limitations:
- Custom MySQL implementations may not support all SET commands
- Simplified backends may only support SELECT queries
- **Your case**: "SET NAMES not allowed by driver"

### 2. Session State Isolation
- Each client connection has its own session state
- Variables set by one client don't affect others
- Proxy maintains proper isolation

### 3. Performance
- No need to send SET commands to backend
- Reduces backend load
- Faster response (no network round-trip)

### 4. Client Compatibility
- MySQL clients expect SET commands to work
- JDBC, ODBC, Tableau all send SET NAMES on connect
- Without handling, connections would fail

## Common Client Initialization

When MySQL clients connect, they typically send:

```sql
-- MySQL Connector/J (JDBC)
SET NAMES utf8mb4;
SET autocommit=1;
SET sql_mode = concat(@@sql_mode,',STRICT_TRANS_TABLES');

-- MySQL ODBC Driver
SET NAMES utf8;
SET CHARACTER SET utf8;

-- Tableau
SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;
SET SESSION sql_mode='ANSI_QUOTES';
```

**All of these are now handled locally** by the proxy, even if your backend doesn't support them!

## What Still Goes to Backend

Not all commands are intercepted. These pass through to backend:

```sql
-- Transaction control (should be managed by backend)
BEGIN;
COMMIT;
ROLLBACK;
START TRANSACTION;

-- Data queries
SELECT * FROM table WHERE id = 1;
INSERT INTO table VALUES (1, 'test');
UPDATE table SET name = 'new' WHERE id = 1;
DELETE FROM table WHERE id = 1;

-- Metadata queries
SHOW TABLES;
SHOW COLUMNS FROM table_name;
DESCRIBE table_name;
SELECT * FROM INFORMATION_SCHEMA.TABLES;
```

## Testing SET Commands

You can test that SET commands work properly:

```sql
-- Connect to ChronosProxy
mysql -h localhost -P 3307 -u root

-- Test character set configuration
SET NAMES utf8mb4;
SELECT @@character_set_client, @@character_set_connection;
-- Should return: utf8mb4, utf8mb4

-- Test user variables
SET @my_var = 'Hello World';
SELECT @my_var;
-- Should return: Hello World

-- Test transaction isolation
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
SELECT @@tx_isolation;
-- Should return: READ-COMMITTED

-- Test database selection
USE test_database;
SELECT DATABASE();
-- Should return: test_database
```

## Error Handling

If a SET command isn't supported, the middleware will raise an error:

```python
raise MysqlError(
    f"Unsupported SET statement: {kind}",
    code=ErrorCode.NOT_SUPPORTED_YET,
)
```

**Currently supported SET commands**:
- ✅ SET @variable = value (user variables)
- ✅ SET NAMES charset
- ✅ SET CHARACTER SET charset
- ✅ SET TRANSACTION characteristics
- ✅ SET [SESSION|GLOBAL] variable = value

**Not intercepted** (would pass to backend):
- ❌ SET PASSWORD = 'newpass' (if not in middleware)
- ❌ Custom SET commands specific to your backend

## Architecture Diagram

```
Client sends: SET NAMES utf8mb4
         ↓
   mysql-mimic server
         ↓
   Session.query()
         ↓
   Middleware chain
         ↓
   _set_middleware (INTERCEPTS HERE)
         ↓
   session.variables.set("character_set_client", "utf8mb4")
   session.variables.set("character_set_connection", "utf8mb4")
   session.variables.set("character_set_results", "utf8mb4")
         ↓
   Return: [], [] (empty result)
         ↓
   Client: OK (command succeeded)

   ❌ Never reaches backend!
   ❌ Never goes through query pipeline!
   ❌ Never hits validation rules!
```

Compare to regular query:

```
Client sends: SELECT * FROM table
         ↓
   mysql-mimic server
         ↓
   Session.query()
         ↓
   Middleware chain (passes through)
         ↓
   QueryPipeline.process()
         ↓
   Validation, transformation, etc.
         ↓
   Backend execution
         ↓
   Return results
```

## Benefits for Your Use Case

### Problem Solved
**Error**: "SET NAMES not allowed by driver"

**Solution**:
- Proxy intercepts `SET NAMES` locally
- Backend never sees the command
- Driver limitation is bypassed
- Client connection succeeds

### Additional Benefits
1. **Tableau compatibility** - Handles all Tableau's SET commands
2. **ODBC compatibility** - Handles ODBC driver initialization
3. **Session isolation** - Proper session variable tracking
4. **No backend changes** - Works with your existing backend

## Configuration

No configuration needed! The middleware is **automatically enabled** in `src/core/session.py`.

If you want to disable it (not recommended):

```python
# This would break SET NAMES handling
self.middlewares = [
    self._set_var_middleware,  # Keep user variables
    # self._set_middleware,     # ← Remove this line
    self._use_middleware,       # Keep database tracking
]
```

## Summary

✅ **Fixed**: `SET NAMES` now works in the proxy
✅ **Location**: Handled by `_set_middleware` in session
✅ **Scope**: All SET commands (NAMES, CHARACTER SET, TRANSACTION, variables)
✅ **Backend impact**: None - commands handled locally
✅ **Client compatibility**: Full MySQL client support

Your backend driver limitations are completely bypassed - all SET commands work perfectly!
