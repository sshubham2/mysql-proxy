# Backtick Identifier Fix for INFORMATION_SCHEMA Queries

## Problem

Tableau was sending INFORMATION_SCHEMA.COLUMNS queries with **backtick-quoted identifiers**:

```sql
SELECT `table_name`, `column_name`
FROM `information_schema`.`columns`
WHERE `data_type`='enum' AND `table_schema`=''
```

These queries were **bypassing** the INFORMATION_SCHEMA converter and being sent directly to the backend, causing:
- Backend errors (backend doesn't support COLUMNS queries)
- Connection drops
- Reconnection attempts

## Root Cause

The `can_convert()` method in `information_schema_converter.py` used pattern matching to detect INFORMATION_SCHEMA queries:

**Old logic**:
```python
convertible_patterns = [
    'INFORMATION_SCHEMA.TABLES',
    'INFORMATION_SCHEMA.COLUMNS',
    'INFORMATION_SCHEMA.SCHEMATA',
]
return any(pattern in sql_upper for pattern in convertible_patterns)
```

**Problem**: This pattern matching failed when identifiers were backtick-quoted:

| Query Format | Pattern | Match |
|--------------|---------|-------|
| `information_schema.columns` | `INFORMATION_SCHEMA.COLUMNS` | ✅ Match |
| `` `information_schema`.`columns` `` | `INFORMATION_SCHEMA.COLUMNS` | ❌ **No match!** |

The backticks between schema and table name broke the pattern: `` `INFORMATION_SCHEMA`.`COLUMNS` `` doesn't contain `INFORMATION_SCHEMA.COLUMNS`.

## Code Flow Analysis

### Before Fix (Backtick Query):

1. Query received: `` SELECT `table_name` FROM `information_schema`.`columns` ``
2. `is_metadata_query()` → **True** (contains "INFORMATION_SCHEMA")
3. Goes to `_execute_metadata_query()`
4. `can_convert()` → **False** (pattern doesn't match due to backticks)
5. **SKIPS** the INFORMATION_SCHEMA handling block
6. `return_empty` stays `False`
7. **Executes query against backend** → ❌ Backend error!
8. Connection drops, reconnection triggered

### After Fix (Backtick Query):

1. Query received: `` SELECT `table_name` FROM `information_schema`.`columns` ``
2. `is_metadata_query()` → **True**
3. Goes to `_execute_metadata_query()`
4. `can_convert()` → **True** (checks if 'INFORMATION_SCHEMA' anywhere in SQL)
5. `convert_to_show()` → **None** (COLUMNS not supported)
6. Sets `return_empty = True`
7. **Returns empty result WITHOUT executing** → ✅ Works!

## Solution

**Simplified the pattern matching** to check if 'INFORMATION_SCHEMA' appears **anywhere** in the SQL:

```python
@staticmethod
def can_convert(sql: str) -> bool:
    sql_upper = sql.upper()

    # Simple check: if INFORMATION_SCHEMA appears anywhere, consider it convertible
    # The actual conversion logic will determine if it's supported
    return 'INFORMATION_SCHEMA' in sql_upper
```

This handles:
- Unquoted: `information_schema.columns`
- Backticks: `` `information_schema`.`columns` ``
- Double quotes: `"information_schema"."columns"`
- Mixed case: `Information_Schema.COLUMNS`

The actual table detection in `convert_to_show()` uses **sqlglot parsing**, which already handles backticks correctly.

## Testing

### Test Case 1: Backtick Query (Tableau)
```python
query = "SELECT `table_name` FROM `information_schema`.`columns` WHERE `data_type`='enum'"

# Results:
can_convert(query)       # True ✅
convert_to_show(query)   # None ✅ (returns empty)
```

### Test Case 2: Unquoted Query
```python
query = "SELECT table_name FROM information_schema.columns WHERE data_type='enum'"

# Results:
can_convert(query)       # True ✅
convert_to_show(query)   # None ✅ (returns empty)
```

### Test Case 3: Supported TABLES Query
```python
query = "SELECT table_name FROM `information_schema`.`tables` WHERE table_schema='test'"

# Results:
can_convert(query)       # True ✅
convert_to_show(query)   # Original SQL ✅ (passes through to backend)
```

## Impact

**Before Fix**:
- COLUMNS queries with backticks → sent to backend → error → connection drop
- User saw new connection attempts after each COLUMNS query

**After Fix**:
- COLUMNS queries (any format) → return empty → no backend execution
- Stable connection, no errors

## Files Changed

- `src/utils/information_schema_converter.py`:
  - Simplified `can_convert()` to check for 'INFORMATION_SCHEMA' substring
  - Removed specific pattern list

## Verification

To verify the fix is working:

1. **Enable debug logging** in `config/config.yaml`:
   ```yaml
   logging:
     level: DEBUG
   ```

2. **Restart proxy**

3. **Run COLUMNS query from Tableau**

4. **Check logs** for:
   ```
   "COLUMNS query detected, returning None to block execution"
   "INFORMATION_SCHEMA query not supported, returning empty result"
   ```

5. **Verify NO backend error** in logs

6. **Verify connection stays stable** (no reconnection messages)

## Related Issues

- Pool size fix: Backend single connection limitation (pool_size: 1)
- INFORMATION_SCHEMA.TABLES whitelist: Only SCHEMATA and TABLES supported
- Metadata query bypass: Metadata queries skip cob_date validation

## Commit

Commit: `85549cc`
Message: "Fix INFORMATION_SCHEMA detection for backtick-quoted identifiers"
