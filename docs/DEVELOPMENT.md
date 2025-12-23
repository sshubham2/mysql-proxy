# Development Guide - ChronosProxy

This guide is for developers who want to understand, modify, or extend ChronosProxy.

## Architecture Overview

ChronosProxy follows a pipeline architecture where each query goes through multiple stages:

```
Client Query → Security → Parsing → Detection → Transformation → Validation → Execution → Results
```

## Code Organization

### Layer 1: Configuration (`src/config/`)

**Purpose**: Manage application settings and logging

**Key Files**:
- `settings.py`: Loads YAML config, handles environment variables
- `logging_config.py`: Sets up colored console and JSON file logging

**When to modify**:
- Adding new configuration options
- Changing logging format or behavior

### Layer 2: Utilities (`src/utils/`)

**Purpose**: Reusable helper functions

**Key Files**:
- `sql_parser.py`: SQL parsing wrapper around sqlglot
- `error_formatter.py`: User-friendly error messages
- `result_converter.py`: Convert backend results to MySQL format

**When to modify**:
- Adding new SQL analysis capabilities
- Creating new error message formats
- Handling new data types

### Layer 3: Backend Connectivity (`src/backend/`)

**Purpose**: Database connection management

**Key Files**:
- `odbc_connection.py`: ODBC connection pool
- `native_connection.py`: Native MySQL connector
- `connection_factory.py`: Create connections based on config
- `executor.py`: Execute queries and handle results

**When to modify**:
- Adding new database connector types
- Changing connection pool behavior
- Adding query execution hooks

### Layer 4: Security (`src/security/`)

**Purpose**: Security controls and access management

**Key Files**:
- `write_blocker.py`: Block write operations

**When to modify**:
- Adding new security rules
- Implementing user authentication
- Adding query-level permissions

### Layer 5: Detection (`src/detection/`)

**Purpose**: Detect unsupported SQL features

**Key Files**:
- `unsupported_detector.py`: Orchestrates all detection

**When to modify**:
- Adding detection for new unsupported features
- Changing detection logic

### Layer 6: Validation (`src/validation/`)

**Purpose**: Enforce business rules

**Key Files**:
- `cob_date_validator.py`: Validate cob_date filter

**When to modify**:
- Adding new business rules
- Changing validation logic

### Layer 7: Transformation (`src/transformation/`)

**Purpose**: Transform queries to compatible format

**Key Files**:
- `subquery_unwrapper.py`: Flatten subqueries
- `group_by_fixer.py`: Auto-fix GROUP BY
- `transformer.py`: Coordinate transformations

**When to modify**:
- Adding new transformation types
- Changing transformation behavior

### Layer 8: Core (`src/core/`)

**Purpose**: MySQL protocol server and query pipeline

**Key Files**:
- `server.py`: MySQL protocol server
- `session.py`: Per-connection session handler
- `query_pipeline.py`: Main query processing orchestrator

**When to modify**:
- Changing query processing flow
- Adding pipeline stages
- Modifying MySQL protocol behavior

## Adding New Features

### Adding a New Unsupported Feature Detector

**Example**: Detect CASE statements

1. **Create detection method** in `src/detection/unsupported_detector.py`:

```python
def _check_case_statements(self, sql: str, ast: exp.Expression):
    """Check for CASE statements"""
    has_case = len(list(ast.find_all(exp.Case))) > 0

    if has_case:
        error_msg = ErrorFormatter.format_case_error(sql)
        raise UnsupportedFeatureDetected('case_statement', error_msg)
```

2. **Add to check_query** method:

```python
def check_query(self, sql: str, ast: exp.Expression):
    # ... existing checks ...

    if self.settings.is_unsupported_feature('case_statements'):
        self._check_case_statements(sql, ast)
```

3. **Add error formatter** in `src/utils/error_formatter.py`:

```python
@staticmethod
def format_case_error(query: str) -> str:
    return """MySQL Proxy Error: CASE statements are not supported

Your query uses CASE statements which are not supported by the backend.

Suggestions:
  • Pre-compute CASE logic in a database view
  • Use Tableau calculated fields instead
"""
```

4. **Update configuration** in `config/config.yaml`:

```yaml
capabilities:
  unsupported_features:
    - case_statements  # Add this
```

5. **Write tests** in `tests/unit/test_unsupported_detector.py`:

```python
def test_detect_case_statement(self, detector, sql_parser):
    sql = "SELECT CASE WHEN x > 0 THEN 'positive' ELSE 'negative' END FROM t"
    ast = sql_parser.parse(sql)

    with pytest.raises(UnsupportedFeatureDetected) as exc_info:
        detector.check_query(sql, ast)

    assert exc_info.value.feature == 'case_statement'
```

### Adding a New Query Transformation

**Example**: Remove LIMIT > 1000

1. **Create transformer** in `src/transformation/limit_restrictor.py`:

```python
from sqlglot import exp
from typing import Tuple, Optional

class LimitRestrictor:
    """Restrict LIMIT to maximum value"""

    def __init__(self, settings, sql_parser):
        self.settings = settings
        self.sql_parser = sql_parser
        self.max_limit = settings.transformations.get('max_limit', 1000)

    def restrict(self, sql: str, ast: exp.Expression) -> Tuple[bool, Optional[str], Optional[exp.Expression]]:
        """Restrict LIMIT clause"""
        if not isinstance(ast, exp.Select):
            return False, None, None

        limit = ast.find(exp.Limit)
        if not limit:
            return False, None, None

        limit_val = self._get_limit_value(limit)
        if limit_val and limit_val > self.max_limit:
            # Clone and modify
            restricted_ast = ast.copy()
            restricted_ast.set('limit', exp.Limit(expression=exp.Literal.number(self.max_limit)))
            restricted_sql = self.sql_parser.to_sql(restricted_ast)

            return True, restricted_sql, restricted_ast

        return False, None, None

    def _get_limit_value(self, limit: exp.Limit) -> Optional[int]:
        if limit.expression and isinstance(limit.expression, exp.Literal):
            try:
                return int(limit.expression.this)
            except:
                pass
        return None
```

2. **Add to transformer** in `src/transformation/transformer.py`:

```python
from src.transformation.limit_restrictor import LimitRestrictor

class Transformer:
    def __init__(self, settings: Settings):
        # ... existing code ...
        self.limit_restrictor = LimitRestrictor(settings, self.sql_parser)

    def transform(self, sql: str, ast: exp.Expression) -> TransformationResult:
        # ... existing transformations ...

        # Phase 3: Limit Restriction
        restricted, restricted_sql, restricted_ast = self.limit_restrictor.restrict(
            current_sql, current_ast
        )

        if restricted:
            transformations.append(TransformationRecord(
                sequence=sequence,
                transformation_type='LIMIT_RESTRICT',
                description='Restricted LIMIT to maximum allowed',
                before=current_sql,
                after=restricted_sql
            ))
            current_sql = restricted_sql
            current_ast = restricted_ast
            sequence += 1

        # ... rest of method ...
```

3. **Add configuration**:

```yaml
transformations:
  max_limit: 1000
```

4. **Write tests**.

### Adding a New Business Rule Validator

**Example**: Require WHERE clause

1. **Create validator** in `src/validation/where_validator.py`:

```python
from sqlglot import exp
from src.utils.error_formatter import ErrorFormatter

class MissingWhereError(Exception):
    pass

class WhereValidator:
    def __init__(self, settings, sql_parser):
        self.settings = settings
        self.sql_parser = sql_parser
        self.require_where = settings.business_rules.get('require_where', False)

    def validate(self, sql: str, ast: exp.Expression):
        if not self.require_where:
            return

        if not isinstance(ast, exp.Select):
            return

        where = ast.find(exp.Where)
        if not where:
            error_msg = "All SELECT queries must include a WHERE clause"
            raise MissingWhereError(error_msg)
```

2. **Add to pipeline** in `src/core/query_pipeline.py`:

```python
from src.validation.where_validator import WhereValidator, MissingWhereError

class QueryPipeline:
    def __init__(self, settings, executor, connection_id, source_ip):
        # ... existing code ...
        self.where_validator = WhereValidator(settings, self.sql_parser)

    def process(self, sql: str) -> QueryPipelineResult:
        # ... existing steps ...

        # Add after cob_date validation
        try:
            self.where_validator.validate(final_sql, final_ast)
        except MissingWhereError as e:
            self.query_logger.log_rejected(query_id, 'missing_where', final_sql)
            return QueryPipelineResult(
                success=False,
                columns=[],
                rows=[],
                error_message=str(e)
            )
```

## Testing Guidelines

### Unit Testing

**Location**: `tests/unit/`

**Purpose**: Test individual components in isolation

**Example**:
```python
def test_subquery_unwrapper(unwrapper, sql_parser):
    sql = "SELECT * FROM (SELECT id FROM users) sub"
    ast = sql_parser.parse(sql)

    was_unwrapped, unwrapped_sql, unwrapped_ast = unwrapper.unwrap(sql, ast)

    assert was_unwrapped is True
    assert "FROM (SELECT" not in unwrapped_sql.upper()
```

**Run**: `pytest tests/unit/`

### Integration Testing

**Location**: `tests/integration/`

**Purpose**: Test component interactions

**Example**:
```python
def test_query_pipeline_with_transformation(settings, connection_pool):
    executor = QueryExecutor(connection_pool)
    pipeline = QueryPipeline(settings, executor, "test-conn", "127.0.0.1")

    sql = "SELECT * FROM (SELECT category, SUM(amount) FROM sales WHERE cob_date='2024-01-15') sub"

    result = pipeline.process(sql)

    assert result.success is True
    assert result.was_transformed is True
```

**Run**: `pytest tests/integration/`

### End-to-End Testing

**Purpose**: Test with real MySQL backend

**Setup**:
1. Create test MySQL database
2. Load test data
3. Configure ChronosProxy to connect to test DB
4. Run queries through proxy
5. Verify results match expectations

## Debugging

### Enable Debug Logging

```bash
python src/main.py --log-level DEBUG
```

### Watch Logs in Real-Time

```bash
tail -f logs/chronosproxy.log
```

### Debug Specific Query

Add debug logging in `query_pipeline.py`:

```python
import logging
logger = logging.getLogger(__name__)

def process(self, sql: str):
    logger.debug(f"Processing query: {sql}")
    logger.debug(f"Query ID: {query_id}")
    # ... rest of method ...
```

### Test Transformation Manually

```python
from src.utils.sql_parser import SQLParser
from src.transformation.subquery_unwrapper import SubqueryUnwrapper
from src.config.settings import get_settings

settings = get_settings()
parser = SQLParser()
unwrapper = SubqueryUnwrapper(settings, parser)

sql = "SELECT * FROM (SELECT id FROM users) sub"
ast = parser.parse(sql)

was_unwrapped, unwrapped_sql, unwrapped_ast = unwrapper.unwrap(sql, ast)

print(f"Was unwrapped: {was_unwrapped}")
print(f"Unwrapped SQL: {unwrapped_sql}")
```

## Performance Optimization

### Connection Pool Tuning

Adjust pool size based on load:

```yaml
backend:
  pool_size: 20  # Increase for high concurrency
  pool_recycle: 1800  # Recycle connections more frequently
```

### Query Parsing Cache

Add caching for parsed queries (future enhancement):

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def parse_cached(sql: str):
    return parse_one(sql, dialect='mysql')
```

### Profiling

Use Python profiler:

```bash
python -m cProfile -o profile.stats src/main.py
python -m pstats profile.stats
```

## Common Development Tasks

### Add New Configuration Option

1. Add to `config/config.yaml`
2. Access via `settings.your_section.get('option_name')`
3. Document in README

### Change Error Message

Edit `src/utils/error_formatter.py`

### Add New SQL Feature Detection

Edit `src/detection/unsupported_detector.py`

### Modify Transformation Logic

Edit files in `src/transformation/`

### Change Logging Format

Edit `src/config/logging_config.py`

## Code Style

- Follow PEP 8
- Use type hints
- Add docstrings to all functions
- Keep functions focused and small
- Use descriptive variable names

## Contribution Workflow

1. Create feature branch
2. Implement changes
3. Write tests
4. Update documentation
5. Run all tests: `pytest`
6. Submit pull request

## Resources

- **sqlglot Documentation**: https://github.com/tobymao/sqlglot
- **mysql-mimic Documentation**: https://github.com/kelsin/mysql-mimic
- **pyodbc Documentation**: https://github.com/mkleehammer/pyodbc
- **Tableau SQL Reference**: Tableau documentation

## Getting Help

- Review existing code for examples
- Check logs for error details
- Add debug logging to understand flow
- Write tests to isolate issues
