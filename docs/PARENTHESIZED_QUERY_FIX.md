# Parenthesized Query Fix (LIMIT 0 Schema Discovery)

## Problem

Tableau sends queries wrapped in parentheses with `LIMIT 0` to discover the schema (column names and types) without fetching actual data:

```sql
(SELECT col1, col2 FROM my_table WHERE date_index = -1) LIMIT 0
```

When the proxy received this query, it would pass it to the backend **with the parentheses intact**, causing the backend to receive:

```sql
(SELECT col1, col2 FROM my_table WHERE date_index = -1) LIMIT 0
```

## Why This Happens

When sqlglot parses `(SELECT ...) LIMIT 0`, it treats it as a **Subquery expression** (not a Select statement). When the AST is converted back to SQL, sqlglot preserves the parentheses.

```python
from sqlglot import parse_one

query = "(SELECT col1 FROM table) LIMIT 0"
ast = parse_one(query, dialect='mysql')
print(type(ast).__name__)  # Output: Subquery (not Select!)

regenerated = ast.sql(dialect='mysql')
print(regenerated)  # Output: (SELECT col1 FROM table) LIMIT 0
# Parentheses are kept!
```

## What is `LIMIT 0`?

`LIMIT 0` tells the database to:
- Execute the query
- Return the **column metadata** (names, types)
- Return **zero rows** of data

Tableau uses this to discover the schema of custom SQL queries efficiently, without transferring large result sets.

## Solution

Created `ParenthesizedQueryUnwrapper` to detect and unwrap this pattern **before** any other processing.

### Pattern Detection

The unwrapper detects two patterns:

1. **Parenthesized SELECT with LIMIT**: `(SELECT ...) LIMIT N`
2. **Parenthesized SELECT alone**: `(SELECT ...)`

### Transformation

**Before unwrapping**:
```sql
(SELECT col1, col2 FROM my_table WHERE date_index = -1) LIMIT 0
```

**After unwrapping**:
```sql
SELECT col1, col2 FROM my_table WHERE date_index = -1 LIMIT 0
```

The `LIMIT 0` clause is **preserved** and moved inside the query.

## Implementation

### Code Location

`src/transformation/paren_query_unwrapper.py`:

```python
class ParenthesizedQueryUnwrapper:
    @staticmethod
    def needs_unwrapping(sql: str) -> bool:
        """Check if query matches (SELECT ...) LIMIT N pattern"""
        sql_stripped = sql.strip()

        # Pattern 1: (SELECT ...) LIMIT N
        if re.match(r'^\(SELECT\s+.*\)\s+LIMIT\s+\d+$', sql_stripped, re.IGNORECASE | re.DOTALL):
            return True

        # Pattern 2: Just (SELECT ...)
        if re.match(r'^\(SELECT\s+.*\)$', sql_stripped, re.IGNORECASE | re.DOTALL):
            return True

        return False

    @staticmethod
    def unwrap(sql: str) -> Optional[str]:
        """Remove outer parentheses and preserve LIMIT clause"""
        sql_stripped = sql.strip()

        # Pattern 1: (SELECT ...) LIMIT N
        match = re.match(
            r'^\((SELECT\s+.+)\)\s+(LIMIT\s+\d+)$',
            sql_stripped,
            re.IGNORECASE | re.DOTALL
        )
        if match:
            inner_query = match.group(1).strip()
            limit_clause = match.group(2).strip()
            return f"{inner_query} {limit_clause}"

        # Pattern 2: Just (SELECT ...)
        match = re.match(
            r'^\((SELECT\s+.+)\)$',
            sql_stripped,
            re.IGNORECASE | re.DOTALL
        )
        if match:
            inner_query = match.group(1).strip()
            return inner_query

        return None
```

### Integration

Integrated into `src/core/query_pipeline.py` as **Step 0** (before all other processing):

```python
# Step 0: Unwrap parenthesized queries (e.g., (SELECT ...) LIMIT 0)
# Tableau sends these to discover schema without fetching data
if ParenthesizedQueryUnwrapper.needs_unwrapping(sql):
    unwrapped = ParenthesizedQueryUnwrapper.unwrap(sql)
    if unwrapped:
        self.query_logger.logger.info(
            "Unwrapped parenthesized query",
            extra={
                'query_id': query_id,
                'original_full': sql,
                'unwrapped_full': unwrapped,
                'pattern': 'parenthesized_with_limit'
            }
        )
        sql = unwrapped  # Use unwrapped query for rest of pipeline
```

**Why Step 0?** This must happen **before**:
- Metadata query detection
- Tableau wrapper unwrapping (different pattern)
- Query parsing and validation
- Any transformations

## Testing

### Test Cases

All test cases pass in `test_paren_unwrapper.py`:

```python
# ✅ PASS: Unwrap with LIMIT
"(SELECT col1, col2 FROM my_table WHERE date_index = -1) LIMIT 0"
→ "SELECT col1, col2 FROM my_table WHERE date_index = -1 LIMIT 0"

# ✅ PASS: Unwrap without LIMIT
"(SELECT col1 FROM table1)"
→ "SELECT col1 FROM table1"

# ✅ PASS: Don't unwrap normal queries
"SELECT col1 FROM table1"
→ No unwrapping (correctly skipped)

# ✅ PASS: Don't unwrap subqueries in FROM clause
"SELECT * FROM (SELECT col1 FROM table1) sub"
→ No unwrapping (correctly skipped)
```

### Verification

With DEBUG logging enabled, you'll see:

```json
{
  "message": "RECEIVED QUERY",
  "SQL": ">>>(SELECT col1 FROM my_table WHERE date_index = -1) LIMIT 0<<<"
}
```

Followed by:

```json
{
  "message": "Unwrapped parenthesized query",
  "original_full": "(SELECT col1 FROM my_table WHERE date_index = -1) LIMIT 0",
  "unwrapped_full": "SELECT col1 FROM my_table WHERE date_index = -1 LIMIT 0",
  "pattern": "parenthesized_with_limit"
}
```

Then at backend execution:

```json
{
  "message": "BACKEND EXECUTE",
  "SQL": ">>>SELECT col1 FROM my_table WHERE date_index = -1 LIMIT 0<<<"
}
```

**No parentheses!** ✅

## Impact

**Before Fix**:
- Backend received: `(SELECT ...) LIMIT 0`
- Backend may not parse parenthesized queries correctly
- Schema discovery fails or returns incorrect results

**After Fix**:
- Backend receives: `SELECT ... LIMIT 0`
- Standard SQL format
- Schema discovery works correctly
- Tableau can display column names and types

## Related Patterns

This fix handles a **different pattern** than `TableauWrapperUnwrapper`:

| Pattern | Handler | Description |
|---------|---------|-------------|
| `(SELECT ...) LIMIT 0` | `ParenthesizedQueryUnwrapper` | Schema discovery query |
| `SELECT * FROM (SELECT ...) alias` | `TableauWrapperUnwrapper` | Custom SQL wrapper |
| `SELECT * FROM (SELECT ...) alias` | `SubqueryUnwrapper` | Subquery flattening |

All three can coexist - they handle different Tableau query patterns.

## Why LIMIT 0?

Tableau uses `LIMIT 0` for several purposes:

1. **Schema Discovery**: Get column names/types without data transfer
2. **Query Validation**: Verify custom SQL is syntactically correct
3. **Performance**: No need to fetch/transfer actual rows
4. **Connection Testing**: Ensure query will work before running full query

After schema discovery succeeds, Tableau runs the actual query **without** `LIMIT 0` to fetch data.

## Files Changed

- `src/transformation/paren_query_unwrapper.py` - New unwrapper class
- `src/core/query_pipeline.py` - Integration as Step 0
- `test_paren_unwrapper.py` - Unit tests
- `docs/PARENTHESIZED_QUERY_FIX.md` - This documentation

## Future Considerations

If Tableau's query patterns change, the regex patterns in `needs_unwrapping()` may need updates. The current implementation handles:
- Single or multiple spaces/newlines
- Case-insensitive SELECT keyword
- Any LIMIT value (not just 0)

If edge cases are found, add them to `test_paren_unwrapper.py` first, then update the regex patterns.
