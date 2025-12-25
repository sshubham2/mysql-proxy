# mysql-mimic AssertionError Fix

## Problem

Tableau was able to query the database list from backend, backend responded successfully, but Tableau showed "no database found" and the proxy threw an `AssertionError` from `mysql-mimic\results.py`.

## Root Cause

The `mysql-mimic` library has strict validation in `results.py` that **asserts** the number of column names must exactly match the number of values in each row:

```python
# In mysql-mimic/results.py (approximate)
assert len(column_names) == len(row_values), "Column count must match row value count"
```

When this assertion fails, it raises an `AssertionError` and stops query processing.

### Why the Mismatch Occurred

Several scenarios can cause column count mismatch:

1. **Backend returns different metadata than expected**
   - Backend ODBC driver may not return complete column descriptions
   - Some columns might be synthetic (like NULL columns in Tableau queries)

2. **Column extraction fails partially**
   - If `cursor.description` is incomplete or malformed
   - Type mapping issues in `_map_odbc_type()`

3. **Query has computed columns**
   ```sql
   SELECT NULL, NULL, NULL, SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA
   ```
   - 4 columns in result, but backend might only report SCHEMA_NAME in description

## Solution

Added **validation and auto-correction** in `session.py` before returning results to mysql-mimic:

### Code Changes

```python
# Validate result format before returning to mysql-mimic
if result.rows and column_names:
    first_row = result.rows[0]
    if len(first_row) != len(column_names):
        # Log the mismatch
        logger.warning(
            f"Column count mismatch: {len(column_names)} columns but row has {len(first_row)} values"
        )

        # Fix the mismatch
        if len(first_row) > len(column_names):
            # More values than columns - add generic column names
            for i in range(len(column_names), len(first_row)):
                column_names.append(f'column_{i+1}')
        elif len(first_row) < len(column_names):
            # Fewer values than columns - truncate column names
            column_names = column_names[:len(first_row)]
```

### How It Works

**Scenario 1: More values than columns** (most common)
```
Backend returns:
  Columns: ['SCHEMA_NAME']
  Row: (None, None, None, 'test_db')

Fix:
  Columns: ['SCHEMA_NAME', 'column_2', 'column_3', 'column_4']
  Row: (None, None, None, 'test_db')
```

**Scenario 2: Fewer values than columns**
```
Backend returns:
  Columns: ['col1', 'col2', 'col3', 'col4']
  Row: ('test_db',)

Fix:
  Columns: ['col1']
  Row: ('test_db',)
```

## Testing

### Test Case 1: Database List Query

**Query**:
```sql
SELECT NULL, NULL, NULL, SCHEMA_NAME
FROM INFORMATION_SCHEMA.SCHEMATA
WHERE SCHEMA_NAME LIKE '%'
ORDER BY SCHEMA_NAME
```

**Before Fix**:
- Backend returns 4 values per row
- Only 1 column name extracted (SCHEMA_NAME)
- AssertionError in mysql-mimic
- Tableau shows "no database found"

**After Fix**:
- Mismatch detected: 4 values, 1 column name
- Auto-padding: ['SCHEMA_NAME', 'column_2', 'column_3', 'column_4']
- No AssertionError
- Tableau receives results correctly

### Verification

With DEBUG logging enabled, you should see:

```json
{
  "message": "Column count mismatch: 1 columns but row has 4 values",
  "columns": ["SCHEMA_NAME"],
  "first_row": "(None, None, None, 'test_db')"
}
```

Followed by:

```json
{
  "message": "INFORMATION_SCHEMA result",
  "columns": ["SCHEMA_NAME", "column_2", "column_3", "column_4"],
  "row_count": 5,
  "sample_row": "(None, None, None, 'test_db')"
}
```

## Impact

**Before Fix**:
- AssertionError crashes query processing
- Results not returned to client
- Tableau shows "no database found" even though backend succeeded

**After Fix**:
- Column count automatically corrected
- Results properly formatted for mysql-mimic
- Tableau receives database list successfully
- Warning logged for debugging

## Related Issues

This fix complements:
1. **Graceful error handling** - Prevents traceback spam
2. **Backtick identifier fix** - Ensures INFORMATION_SCHEMA queries work
3. **SHOW TABLES connection test** - Backend compatibility

## Files Changed

- `src/core/session.py`:
  - Added column/row count validation
  - Auto-padding for missing column names
  - Auto-truncation for extra column names
  - Warning logs for debugging

## Alternative Solutions Considered

### Option 1: Fix at Backend Level
**Rejected**: Can't modify backend ODBC driver behavior

### Option 2: Always Return Generic Column Names
**Rejected**: Loses useful column metadata for other queries

### Option 3: Catch AssertionError
**Rejected**: Assertions should not be caught; they indicate programming errors

### Option 4: Pre-validate and Fix (Chosen)
**Selected**: Prevents the assertion from ever triggering by ensuring data integrity before passing to mysql-mimic

## Commit

Commit: `c84ce8b`
Message: "Fix mysql-mimic AssertionError by validating column/row count match"
