# Troubleshooting ChronosProxy

## Common Errors

### 1. OSError: [WinError 64] The specified network name is no longer available

**Symptom**: Tableau connects briefly, then connection drops with this error.

**Cause**: Backend MySQL connection is being closed/dropped.

**Possible Reasons**:

#### A. Backend Timeout
Your backend MySQL server may have short timeout settings.

**Solution**: Increase backend timeouts:
```sql
-- On backend MySQL server
SET GLOBAL wait_timeout = 28800;  -- 8 hours
SET GLOBAL interactive_timeout = 28800;
```

Or configure in backend `my.cnf`:
```ini
[mysqld]
wait_timeout = 28800
interactive_timeout = 28800
```

#### B. Backend Single Connection Limitation ⚠️ **MOST COMMON CAUSE**
Your backend driver may only support a single connection at a time.

**Status**: ✅ **FIXED** - Set pool_size to 1

**Solution**: Set pool size to 1 in `config/config.yaml`:
```yaml
backend:
  connection_type: odbc
  pool_size: 1  # CRITICAL: Backend only supports 1 connection!
  pool_recycle: 3600
  pool_pre_ping: true
```

This is the **primary fix** for WinError 64 when backend has single-connection limitation.

#### C. Connection Pool Issues (Multiple Connection Backends)
If your backend supports multiple connections, the ODBC connection pool may be reusing a stale connection.

**Solution 1**: Enable connection health checks in `config/config.yaml`:
```yaml
backend:
  connection_type: odbc
  pool_size: 10
  health_check_enabled: true  # Enable health checks
  health_check_interval: 30   # Check every 30 seconds
```

**Solution 2**: Reduce pool size to prevent stale connections:
```yaml
backend:
  pool_size: 3  # Smaller pool, fewer stale connections
```

#### D. Backend Driver Limitations
Your backend driver may close connections after certain queries.

**Debug**: Check backend logs when error occurs. Look for:
- Connection closed messages
- Query errors
- Timeout messages

#### E. Too Many Queries
Tableau sends many queries on connection, overwhelming backend.

**Solution**: Add query throttling or connection limits in backend.

### 2. 'QueryLogger' object has no attribute 'info'

**Status**: ✅ **FIXED** in commit bf68198

**Cause**: Incorrect logging method call.

**Fix**: Updated to use `self.query_logger.logger.info()`.

### 3. unable to find entity 'columns' for data portal

**Symptom**: Backend doesn't recognize INFORMATION_SCHEMA queries.

**Status**: ✅ **FIXED** - Queries now converted to SHOW commands or return empty.

**Queries affected**:
- `SELECT * FROM INFORMATION_SCHEMA.COLUMNS` → Converted to `SHOW COLUMNS`
- Complex queries → Return empty result gracefully

### 4. cob_date filter is mandatory

**Symptom**: Metadata queries rejected for missing cob_date.

**Status**: ✅ **FIXED** - Metadata queries bypass validation.

**Queries that now work**:
- `SHOW DATABASES`
- `SHOW TABLES`
- `SELECT * FROM INFORMATION_SCHEMA.TABLES`

## Debugging Steps

### Enable Debug Logging

In `config/config.yaml`:
```yaml
logging:
  level: DEBUG  # Change from INFO to DEBUG
  console_colors: true
```

Restart proxy and check `logs/chronosproxy.log` for detailed information.

### Check Backend Connection

Test backend connection manually:

**Using ODBC**:
```python
import pyodbc

conn_str = "DSN=MySQL_ChronosProxy;UID=root;PWD=yourpassword"
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

# Test query
cursor.execute("SHOW DATABASES")
for row in cursor:
    print(row)

cursor.close()
conn.close()
```

**Using mysql client**:
```bash
# Connect directly to backend
mysql -h backend_host -P 3306 -u root -p

# Test queries that Tableau sends
SHOW DATABASES;
SHOW TABLES;
SHOW STATUS LIKE 'Threads_connected';
```

### Monitor Backend Logs

Check your backend MySQL logs for:
- Connection attempts
- Query errors
- Timeout messages
- Connection closed events

### Test with Simple Client

Instead of Tableau, test with MySQL command-line client:

```bash
# Connect to proxy
mysql -h localhost -P 3307 -u root -p

# Run queries Tableau would send
SET NAMES utf8mb4;
SELECT CONNECTION_ID();
SHOW DATABASES;
SHOW TABLES;
SELECT * FROM INFORMATION_SCHEMA.TABLES;
```

If this works, issue is specific to Tableau.
If this fails, issue is with proxy or backend.

### Check Network

**Firewall**:
- Ensure proxy port (3307) is open
- Ensure backend port (3306) is accessible from proxy

**Test connectivity**:
```bash
# From proxy machine, test backend
telnet backend_host 3306
```

### Review Query Logs

Check `logs/chronosproxy.log` for:

**Successful conversion**:
```json
{
  "message": "Converting INFORMATION_SCHEMA query to SHOW command",
  "query_id": "abc-123",
  "original": "SELECT * FROM INFORMATION_SCHEMA.TABLES",
  "converted": "SHOW TABLES"
}
```

**Complex query (returns empty)**:
```json
{
  "message": "INFORMATION_SCHEMA query too complex to convert, returning empty result",
  "query_id": "abc-123",
  "original": "SELECT * WHERE data_type='enum'"
}
```

**Backend errors**:
```json
{
  "status": "ERROR",
  "error": "unable to find entity 'columns'",
  "query": "SELECT * FROM INFORMATION_SCHEMA.COLUMNS"
}
```

## Configuration Tuning

### For Tableau Connections

```yaml
# config/config.yaml
backend:
  connection_type: odbc
  pool_size: 5  # Moderate pool size
  timeout: 60  # 60 second query timeout

validation:
  require_cob_date: true  # Keep for data queries

security:
  block_writes: true  # Read-only for Tableau
```

### For High Query Volume

```yaml
backend:
  pool_size: 20  # Larger pool for many concurrent queries
  health_check_enabled: true
  health_check_interval: 10  # Check every 10 seconds
```

### For Slow Backend

```yaml
backend:
  timeout: 300  # 5 minute timeout for slow queries
  pool_size: 3  # Smaller pool to avoid overwhelming backend
```

## Common Tableau Issues

### Issue: Tableau connects but shows no tables

**Check**:
1. Does `SHOW TABLES` work directly on backend?
2. Check logs for conversion errors
3. Verify database selected in Tableau

**Solution**:
- Ensure correct database selected
- Check backend permissions
- Verify SHOW TABLES returns results

### Issue: Tableau shows tables but can't query data

**Check**:
1. Does query have `cob_date` filter?
2. Check logs for validation rejections

**Solution**:
- Add `cob_date` filter to Tableau data source
- Or disable cob_date requirement temporarily (not recommended)

### Issue: Connection drops after few minutes

**Cause**: Backend timeout or stale connection.

**Solution**:
1. Increase backend wait_timeout
2. Enable connection health checks
3. Reduce connection pool size

## Getting Help

If issues persist:

1. **Collect Information**:
   - `logs/chronosproxy.log` (last 100 lines)
   - Backend MySQL error log
   - Exact error message from Tableau
   - Query that caused the error

2. **Check Documentation**:
   - `docs/IMPLEMENTATION_STATUS.md` - Known fixes
   - `docs/INFORMATION_SCHEMA_CONVERSION.md` - Query conversion
   - `docs/METADATA_QUERY_BYPASS.md` - Validation bypass

3. **Test Incrementally**:
   - Test backend connection directly
   - Test proxy with mysql client
   - Test with simple Tableau query
   - Add complexity gradually

## Quick Fixes

### Reset Everything

```bash
# Stop proxy
# Clear logs
rm logs/*.log

# Restart backend MySQL
# Restart proxy
python src/main.py

# Try connecting again
```

### Disable Validation Temporarily

For testing only - disable cob_date requirement:

```yaml
# config/config.yaml
validation:
  require_cob_date: false  # TEMPORARY - for testing only
```

Restart proxy and test. If this fixes it, issue is with cob_date validation.

### Use Direct Connection Instead of DSN

```yaml
# config/config.yaml
backend:
  connection_type: odbc
  connection_string: "DRIVER={MySQL ODBC 8.0 Driver};SERVER=localhost;PORT=3306;DATABASE=mydb;USER=root;PASSWORD=pass;"
```

Instead of:
```yaml
  connection_string: "DSN=MySQL_ChronosProxy;UID=root;PWD=pass;"
```

## Summary

Most common issue: **Backend connection drops (WinError 64)**

**Top 3 Solutions**:
1. **Set pool_size: 1** if backend only supports single connection (MOST COMMON FIX)
2. Increase backend `wait_timeout` and `interactive_timeout`
3. Check backend logs for connection/query errors

If still stuck, provide:
- Proxy logs (`logs/chronosproxy.log`)
- Backend error logs
- Exact error from Tableau
- Queries being sent (from logs)
