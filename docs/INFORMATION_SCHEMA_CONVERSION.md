# INFORMATION_SCHEMA Query Conversion

## The Problem

Tableau and MySQL clients query `INFORMATION_SCHEMA` to discover database structure:
```sql
SELECT * FROM INFORMATION_SCHEMA.TABLES
SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'users'
```

However, your backend MySQL driver **doesn't support INFORMATION_SCHEMA** queries!

Meanwhile, `SHOW` commands work fine:
```sql
SHOW TABLES  -- ✅ Works
SHOW COLUMNS FROM users  -- ✅ Works
```

## The Solution

ChronosProxy **automatically converts** INFORMATION_SCHEMA queries to equivalent SHOW commands before sending them to the backend.

### Conversion Examples

| INFORMATION_SCHEMA Query | Converted SHOW Command |
|--------------------------|------------------------|
| `SELECT * FROM INFORMATION_SCHEMA.TABLES` | `SHOW TABLES` |
| `SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'mydb'` | `SHOW TABLES FROM mydb` |
| `SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'users'` | `SHOW COLUMNS FROM users` |
| `SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'mydb' AND TABLE_NAME = 'users'` | `SHOW COLUMNS FROM mydb.users` |
| `SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA` | `SHOW DATABASES` |

## How It Works

### Query Flow

```
Tableau sends: SELECT * FROM INFORMATION_SCHEMA.TABLES
         ↓
   Proxy detects: INFORMATION_SCHEMA = metadata query
         ↓
   Bypass validation (no cob_date required)
         ↓
   Converter checks: Can this be converted to SHOW? ✅
         ↓
   Convert: SELECT * FROM INFORMATION_SCHEMA.TABLES → SHOW TABLES
         ↓
   Send to backend: SHOW TABLES
         ↓
   Backend returns results ✅
         ↓
   Return to Tableau (appears as INFORMATION_SCHEMA results)
```

### Implementation

Located in [src/utils/information_schema_converter.py](src/utils/information_schema_converter.py):

```python
class InformationSchemaConverter:
    @staticmethod
    def can_convert(sql: str) -> bool:
        """Check if query can be converted to SHOW"""
        sql_upper = sql.upper()
        convertible = [
            'INFORMATION_SCHEMA.TABLES',
            'INFORMATION_SCHEMA.COLUMNS',
            'INFORMATION_SCHEMA.SCHEMATA',
        ]
        return any(pattern in sql_upper for pattern in convertible)

    @staticmethod
    def convert_to_show(sql: str) -> Optional[str]:
        """Convert INFORMATION_SCHEMA query to SHOW command"""
        # Parse SQL and extract intent
        # Return equivalent SHOW command
```

Integrated in [src/core/query_pipeline.py:260-276](src/core/query_pipeline.py#L260-L276):

```python
def _execute_metadata_query(self, query_id: str, sql: str):
    # Check if INFORMATION_SCHEMA query needs conversion
    if InformationSchemaConverter.can_convert(sql):
        converted_sql = InformationSchemaConverter.convert_to_show(sql)
        if converted_sql:
            final_sql = converted_sql  # Use converted SHOW command

    # Execute SHOW command on backend
    exec_result = self.executor.execute(final_sql)
```

## Supported Conversions

### 1. INFORMATION_SCHEMA.TABLES → SHOW TABLES

**Pattern**: Queries for table list

```sql
-- These all convert to SHOW TABLES
SELECT * FROM INFORMATION_SCHEMA.TABLES
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
SELECT TABLE_NAME, TABLE_TYPE FROM INFORMATION_SCHEMA.TABLES
```

**With database filter**:
```sql
-- Converts to: SHOW TABLES FROM mydb
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = 'mydb'

-- Converts to: SHOW TABLES (uses current database)
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = DATABASE()
```

### 2. INFORMATION_SCHEMA.COLUMNS → SHOW COLUMNS

**Pattern**: Queries for column information

```sql
-- Converts to: SHOW COLUMNS FROM users
SELECT * FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'users'

-- Converts to: SHOW COLUMNS FROM mydb.users
SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'mydb' AND TABLE_NAME = 'users'
```

### 3. INFORMATION_SCHEMA.SCHEMATA → SHOW DATABASES

**Pattern**: Queries for database list

```sql
-- Converts to: SHOW DATABASES
SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA
SELECT * FROM INFORMATION_SCHEMA.SCHEMATA
```

## Conversion Logic

### Extracting Database from WHERE Clause

The converter analyzes WHERE conditions to find:

```sql
-- Database specified as literal
WHERE TABLE_SCHEMA = 'mydb'  → Use 'mydb'

-- Database from function
WHERE TABLE_SCHEMA = DATABASE()  → Use current database (NULL)

-- No filter
(no WHERE)  → Use current database
```

### Extracting Table Name from WHERE Clause

```sql
-- Table specified as literal
WHERE TABLE_NAME = 'users'  → Extract 'users'

-- Multiple conditions
WHERE TABLE_SCHEMA = 'mydb' AND TABLE_NAME = 'users'
  → Extract both database and table
```

## Limitations

### Queries That Can't Be Converted

Some INFORMATION_SCHEMA queries are too complex to convert to SHOW:

```sql
-- Complex JOINs
SELECT t.TABLE_NAME, c.COLUMN_NAME
FROM INFORMATION_SCHEMA.TABLES t
JOIN INFORMATION_SCHEMA.COLUMNS c ON t.TABLE_NAME = c.TABLE_NAME

-- Aggregations
SELECT TABLE_SCHEMA, COUNT(*)
FROM INFORMATION_SCHEMA.TABLES
GROUP BY TABLE_SCHEMA

-- Complex WHERE conditions
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_ROWS > 1000 OR CREATE_TIME > '2024-01-01'
```

**Fallback**: If conversion fails, the original query is sent to backend (may fail if not supported).

### Result Format Differences

SHOW commands return different columns than INFORMATION_SCHEMA:

**INFORMATION_SCHEMA.TABLES**:
```
TABLE_SCHEMA | TABLE_NAME | TABLE_TYPE | ENGINE | ...
```

**SHOW TABLES**:
```
Tables_in_database
```

**Current behavior**: Return SHOW results as-is (Tableau adapts)

**Future enhancement**: Map SHOW columns to INFORMATION_SCHEMA column names

## Configuration

No configuration needed! Conversion happens automatically.

### Disabling Conversion (Not Recommended)

If you want to disable conversion and send INFORMATION_SCHEMA queries directly:

```python
# In src/core/query_pipeline.py
def _execute_metadata_query(self, query_id: str, sql: str):
    # Comment out conversion logic:
    # if InformationSchemaConverter.can_convert(sql):
    #     converted_sql = InformationSchemaConverter.convert_to_show(sql)
    #     ...

    # Just execute original query
    exec_result = self.executor.execute(sql)
```

**Warning**: This will break Tableau if backend doesn't support INFORMATION_SCHEMA!

## Testing

### Test Converter Directly

```python
from src.utils.information_schema_converter import InformationSchemaConverter

# Test conversion
sql = "SELECT * FROM INFORMATION_SCHEMA.TABLES"
converted = InformationSchemaConverter.convert_to_show(sql)
print(converted)  # "SHOW TABLES"

# Test with WHERE clause
sql = "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'users'"
converted = InformationSchemaConverter.convert_to_show(sql)
print(converted)  # "SHOW COLUMNS FROM users"
```

### Test with MySQL Client

```sql
-- Connect to ChronosProxy
mysql -h localhost -P 3307 -u root

-- These should all work (converted to SHOW)
SELECT * FROM INFORMATION_SCHEMA.TABLES;
-- Executed as: SHOW TABLES

SELECT TABLE_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'my_table';
-- Executed as: SHOW COLUMNS FROM my_table

SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA;
-- Executed as: SHOW DATABASES
```

### Check Logs

The proxy logs conversions:

```
INFO: Converting INFORMATION_SCHEMA query to SHOW command
  query_id: abc-123
  original: SELECT * FROM INFORMATION_SCHEMA.TABLES
  converted: SHOW TABLES
```

## Tableau Compatibility

Common Tableau queries that now work:

```sql
-- Initial connection - discover databases
SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA
→ SHOW DATABASES ✅

-- Select database - discover tables
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = DATABASE()
→ SHOW TABLES ✅

-- Select table - discover columns
SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'my_table'
→ SHOW COLUMNS FROM my_table ✅
```

## Benefits

✅ **Backend compatibility** - Works with drivers that don't support INFORMATION_SCHEMA
✅ **Tableau works** - Clients can discover schema
✅ **Transparent** - Conversion is automatic
✅ **Logged** - Conversions tracked for debugging
✅ **Fallback** - If conversion fails, tries original query

## Summary

| What | Where | How |
|------|-------|-----|
| **Detect** | Query pipeline | Check if INFORMATION_SCHEMA query |
| **Convert** | InformationSchemaConverter | Parse and map to SHOW command |
| **Execute** | Backend | Run SHOW command |
| **Return** | Client | Return results (as-is for now) |

ChronosProxy automatically converts INFORMATION_SCHEMA queries to SHOW commands, enabling full Tableau compatibility even when your backend driver doesn't support INFORMATION_SCHEMA! 🎉
