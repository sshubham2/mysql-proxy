# Date Filter Validation (cob_date OR date_index)

## Overview

ChronosProxy enforces a **mandatory date filter** business rule to ensure temporal consistency. All data queries must include **either** a `cob_date` **OR** `date_index` filter in the WHERE clause.

## Configuration

In `config/config.yaml`:

```yaml
business_rules:
  # Date filter is MANDATORY (cob_date OR date_index)
  require_cob_date: true
```

**Note**: Despite the name `require_cob_date`, this setting now validates for **either** `cob_date` **OR** `date_index`.

## Filter Options

### Option 1: cob_date (Explicit Date)

Use when you know the exact date:

```sql
SELECT product_id, sales_amount
FROM sales_data
WHERE cob_date = '2024-01-15'
  AND region = 'US'
```

**Format**: String date in `'YYYY-MM-DD'` format

### Option 2: date_index (Relative Date)

Use when you want a date relative to today:

```sql
SELECT product_id, sales_amount
FROM sales_data
WHERE date_index = -1
  AND region = 'US'
```

**Format**: Integer value
- `0` = Today
- `-1` = Yesterday (today - 1 day)
- `-2` = Day before yesterday (today - 2 days)
- `-7` = One week ago
- etc.

### Option 3: Both (Either is Sufficient)

You can include both, and the validation will pass:

```sql
SELECT product_id, sales_amount
FROM sales_data
WHERE cob_date = '2024-01-15'
  AND date_index = -1
  AND region = 'US'
```

## Why This Rule Exists

### Temporal Consistency

- Ensures queries operate on a specific date's data snapshot
- Prevents accidental queries across multiple dates
- Maintains data consistency for reporting

### Business Logic

Your backend uses date-based data partitioning or versioning. The date filter:
1. Tells the backend which date's snapshot to query
2. Ensures consistent results across multiple queries
3. Prevents mixing data from different dates

## Validation Behavior

### Valid Queries (Accepted)

```sql
-- With cob_date
SELECT * FROM products WHERE cob_date = '2024-01-15'

-- With date_index
SELECT * FROM products WHERE date_index = -1

-- With both
SELECT * FROM products WHERE cob_date = '2024-01-15' AND date_index = -1

-- With other conditions
SELECT * FROM products WHERE date_index = -1 AND category = 'Electronics'
```

### Invalid Queries (Rejected)

```sql
-- No date filter
SELECT * FROM products WHERE category = 'Electronics'

-- Only other filters
SELECT * FROM products WHERE region = 'US' AND status = 'active'
```

**Error Message**:
```
MySQL Proxy Error: Date filter is mandatory

All queries must include either a cob_date OR date_index filter in the WHERE clause to ensure temporal consistency.

Required format (Option 1 - cob_date):
  SELECT column1, column2
  FROM table_name
  WHERE cob_date = '2024-01-15' AND other_conditions...

Required format (Option 2 - date_index):
  SELECT column1, column2
  FROM table_name
  WHERE date_index = -1 AND other_conditions...
  (date_index = -1 means today, -2 means yesterday, etc.)

Business Rule: Mandatory Date Filter (cob_date OR date_index)
Status: Rejected - Add cob_date or date_index filter and retry
```

## Queries That Bypass Validation

Certain queries automatically bypass date filter validation:

### Metadata Queries
```sql
-- SHOW commands
SHOW DATABASES
SHOW TABLES
SHOW COLUMNS FROM table_name

-- INFORMATION_SCHEMA queries
SELECT * FROM INFORMATION_SCHEMA.TABLES
SELECT * FROM INFORMATION_SCHEMA.SCHEMATA
```

### Static Queries
```sql
-- Connection tests
SELECT 1
SELECT CONNECTION_ID()
```

### SET Commands
```sql
SET NAMES utf8mb4
SET @var = 'value'
```

## Implementation Details

### Code Location

`src/validation/cob_date_validator.py`:

```python
def validate(self, sql: str, ast: exp.Expression):
    # Check if cob_date OR date_index is in WHERE clause
    has_cob_date = self.sql_parser.has_column_in_where(ast, 'cob_date')
    has_date_index = self.sql_parser.has_column_in_where(ast, 'date_index')

    if not has_cob_date and not has_date_index:
        raise MissingCobDateError(error_msg)
```

### Validation Logic

1. Check if `require_cob_date` is enabled in config
2. Only validate SELECT queries (skip SET, SHOW, etc.)
3. Parse WHERE clause for `cob_date` column
4. Parse WHERE clause for `date_index` column
5. If **neither** is found → reject query
6. If **either** is found → accept query

## Tableau Integration

### Using cob_date in Tableau

When creating Custom SQL in Tableau:

```sql
SELECT product_id, product_name, sales_amount
FROM sales_data
WHERE cob_date = '2024-01-15'
```

Or use Tableau parameters:

```sql
SELECT product_id, product_name, sales_amount
FROM sales_data
WHERE cob_date = <Parameters.ReportDate>
```

### Using date_index in Tableau

For "today's data" dashboards:

```sql
SELECT product_id, product_name, sales_amount
FROM sales_data
WHERE date_index = -1
```

For "yesterday's data" dashboards:

```sql
SELECT product_id, product_name, sales_amount
FROM sales_data
WHERE date_index = -2
```

## Disabling Validation (Not Recommended)

To disable date filter validation (for testing only):

```yaml
# config/config.yaml
business_rules:
  require_cob_date: false  # DANGER: Allows queries without date filters
```

**Warning**: Disabling this rule may result in:
- Inconsistent data across queries
- Performance issues (querying all dates)
- Incorrect business logic results

Only disable for:
- Development/testing environments
- Temporary debugging
- Non-production use cases

## Examples by Use Case

### Daily Sales Report (Today)
```sql
SELECT product_id, SUM(sales_amount) as total_sales
FROM sales_data
WHERE date_index = -1
GROUP BY product_id
```

### Historical Analysis (Specific Date)
```sql
SELECT product_id, SUM(sales_amount) as total_sales
FROM sales_data
WHERE cob_date = '2024-01-01'
GROUP BY product_id
```

### Week-over-Week Comparison
```sql
-- This week (combine multiple queries in Tableau)
SELECT SUM(sales_amount) as this_week_sales
FROM sales_data
WHERE date_index = -1

-- Last week
SELECT SUM(sales_amount) as last_week_sales
FROM sales_data
WHERE date_index = -8
```

### Trend Analysis (Date Range - Requires Multiple Queries)

Since the proxy requires a date filter on each query, date ranges require multiple queries or backend support:

**Option 1**: Use backend date range function (if supported)
```sql
SELECT * FROM sales_data
WHERE date_index IN (-1, -2, -3, -4, -5, -6, -7)
```

**Option 2**: Run multiple queries and combine in Tableau
```sql
-- Query 1
SELECT * FROM sales_data WHERE date_index = -1

-- Query 2
SELECT * FROM sales_data WHERE date_index = -2

-- Combine with UNION in Tableau Custom SQL (if proxy allows UNION)
```

## Troubleshooting

### Issue: Query rejected even with cob_date

**Check**:
1. Is `cob_date` in the WHERE clause (not SELECT)?
2. Is spelling correct (`cob_date`, not `cobdate` or `cob-date`)?
3. Is there actually a WHERE clause?

**Example of common mistake**:
```sql
-- WRONG: cob_date in SELECT, not WHERE
SELECT cob_date, product_name FROM products

-- CORRECT: cob_date in WHERE
SELECT product_name FROM products WHERE cob_date = '2024-01-15'
```

### Issue: Query rejected even with date_index

**Check**:
1. Is `date_index` in the WHERE clause?
2. Is spelling correct (`date_index`, not `dateindex` or `date-index`)?

### Issue: Metadata queries being rejected

**Check**:
- SHOW, DESCRIBE, INFORMATION_SCHEMA queries should automatically bypass validation
- If they're being rejected, check proxy logs for the query type detection

## Related Documentation

- `docs/TROUBLESHOOTING.md` - Issue #7: cob_date filter is mandatory
- `config/config.yaml` - Business rules configuration
- `src/validation/cob_date_validator.py` - Validation implementation
