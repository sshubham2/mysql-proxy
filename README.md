# ChronosProxy - MySQL Protocol Proxy Server

An intelligent MySQL protocol proxy server that sits between Tableau and a custom MySQL server with limited SQL capabilities. It acts as a transparent intermediary that automatically transforms unsupported SQL patterns into compatible queries while enforcing business rules and security policies.

## Features

- **MySQL Protocol Implementation**: Full MySQL wire protocol support using `mysql-mimic`
- **Automatic Query Transformation**:
  - Unwraps Tableau's subquery wrapper patterns
  - Auto-fixes incomplete GROUP BY clauses
- **Capability Detection**: Rejects unsupported features with clear error messages:
  - JOINs (all types)
  - UNIONs
  - Window functions
  - COUNT() aggregation
- **Business Rule Enforcement**:
  - Mandatory `cob_date` filter validation
  - Complete GROUP BY requirement
- **Security Controls**:
  - Blocks write operations (INSERT, UPDATE, DELETE, etc.)
  - Database access control
- **Flexible Backend Connectivity**:
  - ODBC connection support (primary)
  - Native MySQL connector (fallback)
  - Connection pooling with health checks
- **Comprehensive Logging**:
  - Colored console output for development
  - JSON-structured file logging for production
  - Query transformation tracking
  - Aggregate metrics

## Quick Start

### Prerequisites

- Python 3.11+
- MySQL ODBC Driver (MySQL Connector/ODBC 8.0+)
- Backend MySQL server

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd mysql-proxy
   ```

2. **Create virtual environment**:
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   # Production installation
   pip install -r requirements.txt

   # OR install as editable package with dev dependencies
   pip install -e ".[dev]"
   ```

4. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env and set MYSQL_PASSWORD
   ```

5. **Configure application**:
   ```bash
   # Edit config/config.yaml with your settings
   # Ensure ODBC connection string points to your backend MySQL server
   ```

### Running ChronosProxy

```bash
# Start with default configuration
python src/main.py

# Start with custom config file
python src/main.py --config config/production.yaml

# Start with debug logging
python src/main.py --log-level DEBUG
```

### Connecting Tableau

1. **Add MySQL Connection** in Tableau
2. **Server**: `localhost` (or proxy server hostname)
3. **Port**: `3307` (or configured port)
4. **Database**: Your production database
5. **Username/Password**: Backend MySQL credentials

## Architecture

```
┌─────────────────┐
│  Tableau Client │
└────────┬────────┘
         │ MySQL Protocol (Port 3307)
         │
┌────────▼──────────────────────────────────────────┐
│              ChronosProxy Server                   │
│                                                    │
│  ┌──────────────────────────────────────────────┐ │
│  │  Query Pipeline                               │ │
│  │  1. Metadata Query Detection                 │ │
│  │  2. Security Validation (Write Blocker)      │ │
│  │  3. SQL Parsing                              │ │
│  │  4. Capability Detection                     │ │
│  │  5. Query Transformation                     │ │
│  │     - Subquery Unwrapping                    │ │
│  │     - GROUP BY Auto-Fix                      │ │
│  │  6. Business Rule Validation (cob_date)      │ │
│  │  7. Backend Execution                        │ │
│  └──────────────────────────────────────────────┘ │
└────────┬───────────────────────────────────────────┘
         │ ODBC Connection
         │
┌────────▼──────────────────────┐
│  Custom MySQL Server          │
│  (Limited SQL Capabilities)   │
└───────────────────────────────┘
```

## Query Processing Example

**Tableau generates**:
```sql
SELECT * FROM (
    SELECT category, SUM(amount)
    FROM sales
    WHERE cob_date='2024-01-15'
) sub
WHERE category='Electronics'
```

**ChronosProxy transforms to**:
```sql
SELECT category, SUM(amount)
FROM sales
WHERE cob_date='2024-01-15' AND category='Electronics'
GROUP BY category
```

**Transformations applied**:
1. ✅ Unwrapped subquery
2. ✅ Merged WHERE conditions
3. ✅ Added missing GROUP BY

## Configuration

Key configuration sections in `config/config.yaml`:

### Proxy Settings
```yaml
proxy:
  host: 0.0.0.0
  port: 3307
  max_connections: 100
```

### Backend Connection (ODBC)
```yaml
backend:
  connection_type: odbc
  odbc:
    connection_string: "DRIVER={MySQL ODBC 8.0 Driver};SERVER=localhost;PORT=3306;DATABASE=test_db;USER=root;PASSWORD=${MYSQL_PASSWORD}"
  pool_size: 10
```

### Transformations
```yaml
transformations:
  unwrap_subqueries: true
  auto_fix_group_by: true
  max_subquery_depth: 2
```

### Business Rules
```yaml
business_rules:
  require_cob_date: true
  require_complete_group_by: true
```

## Error Messages

ChronosProxy provides clear, actionable error messages:

**Example - JOIN Rejection**:
```
MySQL Proxy Error: JOINs are not supported

Your query contains table joins which are not supported by the backend MySQL server.

Detected: INNER JOIN

Suggestions:
  • Create a denormalized view or table that combines the required data
  • Use Tableau's data blending feature instead of SQL joins
  • Contact your database administrator about enabling JOIN support
```

**Example - Missing cob_date**:
```
MySQL Proxy Error: cob_date filter is mandatory

All queries must include a cob_date filter in the WHERE clause to ensure temporal consistency.

Required format:
  SELECT column1, column2
  FROM table_name
  WHERE cob_date = '2024-01-15' AND other_conditions...
```

## Logging

ChronosProxy provides comprehensive logging:

### Console Output
- Colored, human-readable format
- Real-time query processing status
- Transformation details
- Error messages

### File Logging
- JSON-structured logs in `logs/chronosproxy.log`
- Query transformations with before/after
- Execution metrics
- Aggregate statistics

### Metrics
- Success/failure rates
- Transformation rates
- Rejection breakdown by reason
- Performance metrics

## Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_subquery_unwrapper.py
```

## Project Structure

```
mysql-proxy/
├── src/
│   ├── config/          # Configuration management
│   ├── core/            # Server and query pipeline
│   ├── backend/         # Database connectivity
│   ├── security/        # Security controls
│   ├── detection/       # Feature detection
│   ├── validation/      # Business rules
│   ├── transformation/  # Query transformations
│   └── utils/           # Utilities
├── tests/               # Test suite
├── config/              # Configuration files
├── logs/                # Log output
└── docs/                # Documentation
```

## Troubleshooting

### Connection Issues

**Problem**: Cannot connect to backend
```bash
# Check ODBC driver
odbcinst -j

# Test ODBC connection
isql -v "MySQL-DSN"
```

**Problem**: Tableau cannot connect
```bash
# Check if proxy is listening
netstat -an | grep 3307

# Check logs
tail -f logs/chronosproxy.log
```

### Query Rejections

**Problem**: Queries with JOINs rejected
- **Solution**: Create denormalized views or use Tableau data blending

**Problem**: Missing cob_date errors
- **Solution**: Add `WHERE cob_date = 'YYYY-MM-DD'` to all queries

**Problem**: COUNT() not supported
- **Solution**: Replace `COUNT(*)` with `SUM(1)`

## Performance

**Expected Overhead**:
- Query parsing & transformation: ~10-20ms
- Backend execution: 30-500ms (depends on query complexity)
- Total response time: ~50-500ms (acceptable for Tableau)

**Optimization**:
- Connection pooling (default: 10 connections)
- Connection health checks (pre-ping)
- Efficient SQL parsing (sqlglot)

## License

MIT License - See LICENSE file for details

## Support

For issues, questions, or contributions:
- GitHub Issues: [repository-url]/issues
- Documentation: See `docs/` directory

## Version

Current version: **1.0.0**
