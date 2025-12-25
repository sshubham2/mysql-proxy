# Tableau Query Patterns and Handling

## Discovery Phase Queries

### 1. Get Database List
```sql
SELECT NULL, NULL, NULL, SCHEMA_NAME
FROM INFORMATION_SCHEMA.SCHEMATA
WHERE SCHEMA_NAME LIKE '%'
ORDER BY SCHEMA_NAME
```

**Status**: ✅ Converts to `SHOW DATABASES`
**Handling**: INFORMATION_SCHEMA converter

### 2. Get Table List
```sql
SELECT TABLE_NAME, TABLE_COMMENT, IF(TABLE_TYPE='BASE TABLE','TABLE', TABLE_TYPE), TABLE_SCHEMA
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA LIKE '<DB_NAME>'
  AND (TABLE_TYPE='BASE TABLE' OR TABLE_TYPE='VIEW')
ORDER BY TABLE_SCHEMA, TABLE_NAME
```

**Status**: ✅ Converts to `SHOW TABLES FROM <DB_NAME>`
**Handling**: INFORMATION_SCHEMA converter (now allows TABLE_TYPE filter)

## Custom SQL Queries

### 3. Custom Query Wrapper
```sql
SELECT * FROM (<custom_query>) `Custom SQL Query`
```

**Status**: ✅ Unwrapped to inner query
**Handling**: TableauWrapperUnwrapper

## Metadata/Schema Queries

### 4. Foreign Key Information (NOT SUPPORTED)
```sql
SELECT A.REFERENCED_TABLE_SCHEMA AS PKTABLE_CAT,
       NULL AS PKTABLE_SCHEM,
       A.REFERENCED_TABLE_NAME AS PKTABLE_NAME,
       ... (complex JOIN query)
FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE A
JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE D ON ...
JOIN INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS R ON ...
WHERE D.CONSTRAINT_NAME='PRIMARY'
  AND A.TABLE_SCHEMA='<DB_NAME>'
  AND A.TABLE_NAME='<TABLE_NAME>'
```

**Status**: ⚠️ Returns empty result
**Reason**: Too complex to convert, has JOINs
**Impact**: Tableau won't show FK relationships (acceptable)

### 5. Index/Key Information (NOT SUPPORTED)
```sql
SHOW KEYS FROM <DB_NAME>.<TABLE_NAME>
```

**Status**: ❌ Backend doesn't support
**Handling**: Need to return empty result
**Impact**: Tableau won't show index info (acceptable)

## Data Sampling Queries

### 6. Sample Data (TOP 1)
```sql
SELECT TOP 1 * FROM <TABLE_NAME>
```

**Status**: ❌ Fails cob_date validation
**Solution**: Add exemption for LIMIT/TOP queries OR require cob_date

**Alternative**: Tableau might also use:
```sql
SELECT * FROM <TABLE_NAME> LIMIT 1
```

### 7. Verify Subquery Support
```sql
SELECT COL FROM (SELECT 1 AS COL) AS SUBQUERY
```

**Status**: ⚠️ Should work with _static_query_middleware
**Handling**: Static subquery, executed locally

### 8. Test Max Function
```sql
SELECT MAX(1) AS TblMax FROM (SELECT * FROM <TABLE_NAME>) <TABLE_NAME>
```

**Status**: ❌ Fails cob_date validation
**Reason**: Subquery has no cob_date filter
**Solution**: Add exemption OR require cob_date in inner query

### 9. Connection Test
```sql
SELECT 1
```

**Status**: ✅ Should work
**Handling**: _static_query_middleware (executes locally)

## Summary of Handling

| Query Type | Backend Support | Proxy Handling | Result |
|------------|----------------|----------------|--------|
| INFORMATION_SCHEMA.SCHEMATA | ❌ No | ✅ Convert to SHOW DATABASES | Works |
| INFORMATION_SCHEMA.TABLES | ❌ No | ✅ Convert to SHOW TABLES | Works |
| Custom SQL wrapper | N/A | ✅ Unwrap to inner query | Works |
| KEY_COLUMN_USAGE (FK) | ❌ No | ⚠️ Return empty | Partial |
| SHOW KEYS | ❌ No | ❌ Needs handler | Fails |
| TOP 1 / LIMIT 1 | ✅ Yes | ❌ Needs cob_date exemption | Fails |
| SELECT 1 | N/A | ✅ Local execution | Works |
| Subquery tests | Varies | ✅ Local or backend | Works |

## Recommendations

### Priority 1: SHOW KEYS Handler
Create handler to return empty result for `SHOW KEYS` queries:
```python
# In query_pipeline.py or as middleware
if sql.upper().startswith('SHOW KEYS'):
    return empty_result()
```

### Priority 2: TOP/LIMIT Exemption
Exempt `LIMIT 1` or `TOP 1` queries from cob_date validation:
```python
# In cob_date_validator.py
if has_limit_1(ast):
    return  # Skip validation for sampling queries
```

### Priority 3: Cache Metadata
Cache results from `SHOW DATABASES`, `SHOW TABLES` to reduce backend load.

## Testing Each Pattern

```python
# Test script
test_queries = [
    ("DB List", "SELECT NULL, NULL, NULL, SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA"),
    ("Table List", "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='test'"),
    ("Custom SQL", "SELECT * FROM (SELECT col FROM table WHERE cob_date='2024-01-01') t"),
    ("SELECT 1", "SELECT 1"),
    ("Limit Test", "SELECT * FROM table LIMIT 1"),
]

for name, query in test_queries:
    print(f"Testing: {name}")
    result = pipeline.process(query)
    print(f"  Success: {result.success}")
    print(f"  Rows: {len(result.rows)}")
```
