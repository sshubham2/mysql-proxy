# NULL Column Name Fix for Tableau Database List

## Problem

Tableau was unable to display the database list even though:
- Backend successfully returned the data
- No errors in proxy logs
- Direct Tableau → Backend connection worked fine

## Root Cause Discovery

**Log analysis revealed**:
```json
{
  "backend_columns": [["NULL", "VARCHAR"], ["NULL", "VARCHAR"], ["NULL", "VARCHAR"], ["SCHEMA_NAME", "VARCHAR"]],
  "backend_row_count": 10,
  "backend_sample_rows": "[('','','','RDE_BANSHEE'), ('','','','RDE_COMMON'), ('','','','RDE_CUCHULAINN')]"
}
```

**The Issue**: Backend was returning column names as the literal string **"NULL"** (not actual NULL values).

### The Query

Tableau's database list query:
```sql
SELECT NULL, NULL, NULL, SCHEMA_NAME
FROM INFORMATION_SCHEMA.SCHEMATA
WHERE SCHEMA_NAME LIKE '%'
ORDER BY SCHEMA_NAME
```

This query has 4 columns:
1. `NULL` - computed NULL value
2. `NULL` - computed NULL value
3. `NULL` - computed NULL value
4. `SCHEMA_NAME` - actual column

### What Backend Returns

**Column Metadata**:
- Column 1 name: `"NULL"` (string)
- Column 2 name: `"NULL"` (string)
- Column 3 name: `"NULL"` (string)
- Column 4 name: `"SCHEMA_NAME"`

**Row Data**:
- Values: `('', '', '', 'RDE_BANSHEE')`
- Empty strings for the NULL columns (backend specific behavior)

### Why Tableau Couldn't Parse This

Tableau's database list parser expects proper column identifiers, not the literal string "NULL". When it received columns named "NULL", it likely:
1. Couldn't distinguish between actual NULL values and column names
2. Failed to extract the database name from the expected column position
3. Showed "no database found" even though data was present

### Why Direct Connection Works

When Tableau connects directly to MySQL backend:
- Uses native MySQL protocol with binary column metadata
- MySQL wire protocol has different handling for computed NULL columns
- Tableau's MySQL driver knows how to ignore/handle "NULL" column names
- Focuses on row data rather than relying on column names

When going through our proxy:
- We extract column names from ODBC cursor description
- ODBC reports column name as literal "NULL" string
- We pass this to mysql-mimic
- mysql-mimic sends this to Tableau
- Tableau's parser gets confused by "NULL" as column name

## Solution

**Rename "NULL" column names to generic identifiers**:

```python
# Fix column names that are literally "NULL" (string)
for i, col_name in enumerate(column_names):
    if col_name.upper() == 'NULL':
        column_names[i] = f'expr_{i+1}'  # expr_1, expr_2, expr_3, etc.
```

### Before Fix

```
Columns: ["NULL", "NULL", "NULL", "SCHEMA_NAME"]
Row:     ('', '', '', 'RDE_BANSHEE')
Result:  Tableau shows "no database found"
```

### After Fix

```
Columns: ["expr_1", "expr_2", "expr_3", "SCHEMA_NAME"]
Row:     ('', '', '', 'RDE_BANSHEE')
Result:  Tableau displays database list correctly
```

## Implementation Details

### Code Location

`src/core/session.py` - in the `query()` method, after extracting column names from result:

```python
if result.columns:
    column_names = [col[0] if isinstance(col, (tuple, list)) else str(col) for col in result.columns]

    # Fix column names that are literally "NULL" (string)
    for i, col_name in enumerate(column_names):
        if col_name.upper() == 'NULL':
            column_names[i] = f'expr_{i+1}'
            logger.debug(f"Renamed NULL column to {column_names[i]}")
```

### Why "expr_N" Naming

- `expr_1`, `expr_2`, etc. is a common naming convention for computed/expression columns
- Tableau recognizes this pattern
- Clearly indicates these are computed values, not actual table columns
- Incremental numbering maintains column order

### Scope

This fix applies to **all queries**, not just INFORMATION_SCHEMA:
- Any query with computed NULL columns will benefit
- Doesn't affect columns with actual names
- Only renames columns literally named "NULL"

## Testing

### Test Case 1: Database List Query

**Query**:
```sql
SELECT NULL, NULL, NULL, SCHEMA_NAME
FROM INFORMATION_SCHEMA.SCHEMATA
WHERE SCHEMA_NAME LIKE '%'
```

**Backend Response**:
- Columns: `["NULL", "NULL", "NULL", "SCHEMA_NAME"]`
- Rows: `[('', '', '', 'RDE_BANSHEE'), ...]`

**After Fix**:
- Columns sent to Tableau: `["expr_1", "expr_2", "expr_3", "SCHEMA_NAME"]`
- Tableau successfully displays: RDE_BANSHEE, RDE_COMMON, RDE_CUCHULAINN, etc.

### Test Case 2: Table List Query

**Query**:
```sql
SELECT TABLE_NAME, TABLE_COMMENT, IF(TABLE_TYPE='BASE TABLE','TABLE', TABLE_TYPE), TABLE_SCHEMA
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA LIKE 'RDE_BANSHEE'
```

**Backend Response**:
- Columns: `["TABLE_NAME", "TABLE_COMMENT", "NULL", "TABLE_SCHEMA"]`
  - Note: `IF()` expression returns "NULL" as column name
- Rows: `[('users', '', 'TABLE', 'RDE_BANSHEE'), ...]`

**After Fix**:
- Columns: `["TABLE_NAME", "TABLE_COMMENT", "expr_3", "TABLE_SCHEMA"]`
- Tableau successfully displays table list

### Verification

With DEBUG logging, you'll see:
```
Renamed NULL column to expr_1
Renamed NULL column to expr_2
Renamed NULL column to expr_3
```

Then in INFO log:
```json
{
  "columns": ["expr_1", "expr_2", "expr_3", "SCHEMA_NAME"],
  "row_count": 10,
  "sample_rows": "[('', '', '', 'RDE_BANSHEE'), ...]"
}
```

## Impact

**Before Fix**:
- Tableau: "no database found"
- Backend: Successfully returned data
- Proxy: No errors, but Tableau couldn't parse results

**After Fix**:
- Tableau: Database list appears correctly
- Backend: Same data
- Proxy: Automatically renames "NULL" columns to "expr_N"

## Alternative Solutions Considered

### Option 1: Drop NULL Columns
**Rejected**: Tableau expects exactly 4 columns for database list query. Dropping columns would cause count mismatch.

### Option 2: Use Empty String as Column Name
**Rejected**: Empty column names also confuse Tableau and violate SQL standards.

### Option 3: Use Original Query Position Names
**Rejected**: Column names like "column1", "column2" are less semantic than "expr_1", "expr_2".

### Option 4: Rename to "expr_N" (Chosen)
**Selected**: Standard naming convention, clear semantic meaning, Tableau-compatible.

## Related Issues

This complements:
1. **AssertionError fix** - Ensures column count matches row count
2. **Backtick identifier fix** - Ensures queries are processed correctly
3. **Backend response logging** - Helped discover this issue!

## Files Changed

- `src/core/session.py`:
  - Added NULL column name detection (case-insensitive)
  - Rename to expr_N format
  - Debug logging for renamed columns

## Commit

Commit: `eff3cf5`
Message: "Fix Tableau database list by renaming NULL column names"

## Future Considerations

If backend behavior changes to return better column names for computed expressions, this fix will gracefully do nothing (won't match "NULL" pattern).

If we need more sophisticated column naming:
- Could parse original query to extract expression text
- Could use MySQL's column alias syntax to name them properly
- For now, generic expr_N naming is sufficient and works reliably
