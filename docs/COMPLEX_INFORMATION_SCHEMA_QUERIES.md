# Handling Complex INFORMATION_SCHEMA Queries

## The Problem

Some INFORMATION_SCHEMA queries are **too complex** to convert to SHOW commands:

### Example: Tableau's ENUM Query

```sql
SELECT table_name, column_name
FROM information_schema.columns
WHERE data_type='enum' AND table_schema=''
```

**Issues**:
1. Filters by `data_type='enum'` - SHOW COLUMNS can't filter by data type
2. Empty `table_schema=''` - not a valid database name
3. No specific `TABLE_NAME` - can't determine which table to SHOW

**Can't convert to**: SHOW COLUMNS (would need a table name)

## The Solution

For queries that **can't be converted**, the proxy returns an **empty result** instead of:
- ❌ Sending to backend (would fail: "unable to find entity 'columns'")
- ❌ Returning an error (would break Tableau)

### Behavior

```
Tableau: SELECT table_name, column_name FROM information_schema.columns
         WHERE data_type='enum' AND table_schema=''
    ↓
Proxy detects: INFORMATION_SCHEMA.COLUMNS query
    ↓
Converter checks: Can we convert to SHOW COLUMNS?
    ↓
Analysis:
  - Has filter on DATA_TYPE ❌ (not convertible)
  - No specific TABLE_NAME ❌ (SHOW needs table name)
    ↓
Decision: Too complex to convert
    ↓
Return: Empty result (0 rows, 0 columns) ✅
    ↓
Tableau: Interprets as "no ENUM columns found" ✅
```

## What Makes a Query "Too Complex"

### Convertible Queries

Simple queries with only `TABLE_NAME` and/or `TABLE_SCHEMA` filters:

```sql
-- ✅ Simple - converts to SHOW COLUMNS FROM users
SELECT * FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'users'

-- ✅ Simple - converts to SHOW COLUMNS FROM mydb.users
SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'mydb' AND TABLE_NAME = 'users'

-- ✅ Simple - converts to SHOW TABLES FROM mydb
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = 'mydb'
```

### Too Complex (Returns Empty)

Queries with filters on metadata columns:

```sql
-- ❌ Too complex - filters by DATA_TYPE
SELECT * FROM INFORMATION_SCHEMA.COLUMNS
WHERE data_type='enum'

-- ❌ Too complex - filters by COLUMN_NAME
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.COLUMNS
WHERE COLUMN_NAME LIKE '%_id'

-- ❌ Too complex - filters by IS_NULLABLE
SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
WHERE IS_NULLABLE = 'NO'

-- ❌ Too complex - OR conditions
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = 'db1' OR TABLE_SCHEMA = 'db2'

-- ❌ Too complex - no TABLE_NAME specified
SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
WHERE DATA_TYPE = 'varchar'
```

## Detection Logic

In [src/utils/information_schema_converter.py:129-155](src/utils/information_schema_converter.py#L129-L155):

```python
@staticmethod
def _has_complex_where(ast: exp.Select) -> bool:
    """Check if WHERE clause is too complex to convert"""
    where = ast.find(exp.Where)
    if not where:
        return False

    # Check for conditions on columns other than TABLE_NAME and TABLE_SCHEMA
    for node in where.find_all(exp.Column):
        col_name = node.name.upper()
        if col_name not in ('TABLE_NAME', 'TABLE_SCHEMA'):
            return True  # Has filter on DATA_TYPE, COLUMN_NAME, etc.

    # Check for OR conditions
    if list(where.find_all(exp.Or)):
        return True

    return False
```

## Why Return Empty Instead of Error?

### Option 1: Return Error ❌
```
Proxy: "Query too complex to convert"
Tableau: Shows error dialog
User: Can't use Tableau
```

### Option 2: Send to Backend ❌
```
Proxy: Sends to backend as-is
Backend: "unable to find entity 'columns'"
Tableau: Shows error dialog
User: Can't use Tableau
```

### Option 3: Return Empty Result ✅ (Our Choice)
```
Proxy: Returns empty result (0 rows)
Tableau: Interprets as "no matching data"
User: Tableau works! Just doesn't see ENUMs (acceptable)
```

## Impact on Tableau

### What Works
- ✅ Connection succeeds
- ✅ Database discovery (SHOW DATABASES)
- ✅ Table listing (SHOW TABLES)
- ✅ Column discovery for specific tables (SHOW COLUMNS FROM table)
- ✅ Most metadata queries

### What Returns Empty
- Some advanced metadata queries (ENUM detection, etc.)
- Queries filtering by column properties (data_type, is_nullable, etc.)
- Cross-table metadata queries

### User Experience
- Tableau connects successfully ✅
- Can browse databases and tables ✅
- Can see columns and data types ✅
- Some advanced features may not work (ENUM lists, etc.) ⚠️

**Trade-off**: Minor feature limitations vs. total connection failure

## Implementation

### Converter Returns None

When query is too complex:

```python
@staticmethod
def _convert_columns_query(ast: exp.Select) -> Optional[str]:
    # Check complexity
    if InformationSchemaConverter._has_complex_where(ast):
        return None  # Can't convert

    # Normal conversion...
    return "SHOW COLUMNS FROM table"
```

### Pipeline Returns Empty

In [src/core/query_pipeline.py:265-297](src/core/query_pipeline.py#L265-L297):

```python
if InformationSchemaConverter.can_convert(sql):
    converted_sql = InformationSchemaConverter.convert_to_show(sql)
    if converted_sql:
        # Successfully converted
        final_sql = converted_sql
    else:
        # Too complex - return empty
        return_empty = True

if return_empty:
    return QueryPipelineResult(
        success=True,
        columns=[],  # No columns
        rows=[],     # No rows
        was_transformed=False,
        execution_time_ms=0.0
    )
```

## Logging

Complex queries are logged for debugging:

```
INFO: INFORMATION_SCHEMA query too complex to convert, returning empty result
  query_id: abc-123
  original: SELECT table_name, column_name FROM information_schema.columns
            WHERE data_type='enum' AND table_schema=''
```

## Testing

### Test Complex Query Detection

```python
from src.utils.information_schema_converter import InformationSchemaConverter

# Too complex - has DATA_TYPE filter
sql = "SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE data_type='enum'"
result = InformationSchemaConverter.convert_to_show(sql)
assert result is None  # Can't convert

# Simple - can convert
sql = "SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='users'"
result = InformationSchemaConverter.convert_to_show(sql)
assert result == "SHOW COLUMNS FROM users"  # Converted
```

### Test Empty Result Handling

```python
# In query pipeline
result = pipeline.process(
    "SELECT table_name, column_name FROM information_schema.columns "
    "WHERE data_type='enum'"
)

assert result.success == True
assert len(result.rows) == 0
assert len(result.columns) == 0
```

## Common Complex Queries

### From Tableau

```sql
-- ENUM detection (returns empty)
SELECT table_name, column_name
FROM information_schema.columns
WHERE data_type='enum' AND table_schema=''

-- Foreign key detection (returns empty)
SELECT * FROM information_schema.key_column_usage
WHERE referenced_table_name IS NOT NULL

-- Index information (returns empty)
SELECT * FROM information_schema.statistics
WHERE table_schema = DATABASE()
```

### From Other Clients

```sql
-- phpMyAdmin - table sizes (returns empty)
SELECT table_name, data_length, index_length
FROM information_schema.tables
WHERE table_schema = 'mydb'

-- MySQL Workbench - constraint info (returns empty)
SELECT * FROM information_schema.table_constraints
WHERE constraint_type = 'FOREIGN KEY'
```

## Future Enhancements

### Option 1: Partial Results
For some queries, we could return partial/synthetic data:

```sql
-- Query: Get all ENUM columns
SELECT table_name, column_name FROM information_schema.columns
WHERE data_type='enum'

-- Could return: Empty list OR synthetic data based on actual schema inspection
```

### Option 2: Schema Caching
Cache actual schema from SHOW commands and answer INFORMATION_SCHEMA queries from cache.

### Option 3: Backend Enhancement
If backend adds INFORMATION_SCHEMA support, remove conversion entirely.

## Summary

| Query Type | Behavior | Result |
|------------|----------|--------|
| Simple INFORMATION_SCHEMA | Convert to SHOW | Backend data ✅ |
| Complex INFORMATION_SCHEMA | Return empty | Empty result ✅ |
| Too complex for SHOW | Return empty | Empty result ✅ |
| Backend unsupported | Return empty | Empty result ✅ |

**Philosophy**:
- Fail gracefully with empty results
- Don't break client connections
- Log for debugging
- Accept minor feature limitations vs. total failure

Tableau and other clients work, even if some advanced metadata queries return empty! 🎉
