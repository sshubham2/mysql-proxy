# WinError 64 Fix: Backend Single Connection Limitation

## Problem

**Error**: `OSError: [WinError 64] The specified network name is no longer available`

**Symptom**: Tableau connects to ChronosProxy briefly, then the connection drops immediately with the above error.

**Root Cause**: The backend MySQL driver/server only supports **one connection at a time**, but ChronosProxy was configured with `pool_size: 10`, attempting to create and manage multiple connections.

## Solution

**Changed**: `config/config.yaml`

**Before**:
```yaml
backend:
  pool_size: 10              # Number of connections in pool
```

**After**:
```yaml
backend:
  pool_size: 1               # CRITICAL: Backend only supports 1 connection!
```

## Why This Fixes It

1. **Single Connection Backend**: Many custom MySQL implementations, embedded databases, or special ODBC drivers have single-connection limitations.

2. **Connection Pool Behavior**: When pool_size > 1, the connection pool tries to:
   - Create multiple connections to the backend
   - Reuse connections across different client queries
   - Keep idle connections open for performance

3. **Backend Rejection**: When backend only supports 1 connection:
   - Second connection attempt fails or closes first connection
   - Leads to "network name no longer available" as connection is dropped
   - Proxy can't maintain stable connection to backend

4. **pool_size: 1 Fix**: With single connection:
   - Proxy creates and maintains exactly ONE connection to backend
   - All Tableau queries are serialized through this single connection
   - No connection conflicts or drops
   - Stable, reliable communication

## Testing the Fix

### Step 1: Restart Proxy

```bash
# Stop current proxy process (Ctrl+C)

# Start proxy with new configuration
python src/main.py
```

### Step 2: Test with Script

```bash
# Update credentials in test_tableau_queries.py first
python test_tableau_queries.py
```

**Expected Output**:
- All Phase 1-3 tests should pass
- Phase 4 tests may return empty (expected for unsupported queries)
- No connection drops or WinError 64

### Step 3: Test with Tableau

1. Open Tableau Desktop
2. Connect to MySQL Server:
   - Server: localhost
   - Port: 3307
   - Username: root
   - Password: (your password)

3. **Connection Test**:
   - Tableau should connect successfully
   - Database list should appear
   - Selecting a database should show table list

4. **Monitor Logs**:
   ```bash
   # Watch proxy logs in real-time
   tail -f logs/chronosproxy.log
   ```

   **Look for**:
   - No "connection closed" errors
   - Queries being processed successfully
   - No WinError 64 messages

### Step 4: Create Custom SQL Data Source

1. In Tableau, after selecting database:
   - New Custom SQL Query
   - Enter query with `cob_date` filter:
     ```sql
     SELECT * FROM your_table
     WHERE cob_date = '2024-01-01'
     LIMIT 100
     ```

2. **Expected**:
   - Query executes successfully
   - Data preview shows results
   - No connection drops

## Performance Implications

### ⚠️ Important Considerations

**Single Connection = Serialized Queries**

With `pool_size: 1`:
- All queries are processed sequentially (one at a time)
- Multiple Tableau users will queue their queries
- Long-running queries will block subsequent queries

**Impact**:
- ✅ Stable connection (no drops)
- ✅ Predictable behavior
- ⚠️ Lower throughput for concurrent users
- ⚠️ Slower response for multiple simultaneous dashboards

### When This is Acceptable

**Single User / Single Dashboard**:
- Perfect for development/testing
- Tableau creates many sequential queries on connection
- Single dashboard typically queries one at a time

**Custom SQL Workflows**:
- Tableau Custom SQL is usually manually written
- One user executes one query at a time
- No concurrent query issues

**Embedded/Development Backends**:
- If backend is embedded database or development server
- Single connection is expected limitation

### When This May Not Scale

**Multiple Concurrent Users**:
- 5+ users running dashboards simultaneously
- Queries will queue and slow down
- May need backend upgrade to support multiple connections

**Complex Dashboards with Parallel Queries**:
- Some Tableau dashboards issue multiple queries in parallel
- With pool_size: 1, these serialize automatically
- Dashboard load time may increase

## Alternative Solutions (If Single Connection is Not Acceptable)

### Option 1: Upgrade Backend

If backend supports multiple connections:

```yaml
backend:
  pool_size: 10              # Use multiple connections
  pool_pre_ping: true        # Test connections before use
  pool_recycle: 3600         # Recycle every hour
```

**Check your backend documentation** to verify multi-connection support.

### Option 2: Connection Queuing

Keep pool_size: 1 but add explicit queuing:

```yaml
backend:
  pool_size: 1
  max_queue_size: 50         # Queue up to 50 requests
  queue_timeout: 60          # Wait up to 60s in queue
```

(Not yet implemented - would require custom queue management)

### Option 3: Multiple Proxy Instances

Run separate proxy instances for each user:

```bash
# User 1: proxy on port 3307
python src/main.py --port 3307

# User 2: proxy on port 3308
python src/main.py --port 3308
```

Each proxy maintains its own single connection to backend.

**Requires backend to support multiple connections overall** (just not in a pool from single process).

## Verification Checklist

After applying fix, verify:

- [ ] `pool_size: 1` set in `config/config.yaml`
- [ ] Proxy restarted with new configuration
- [ ] Test script `test_tableau_queries.py` runs successfully
- [ ] Tableau connects without WinError 64
- [ ] Database list appears in Tableau
- [ ] Table list appears after selecting database
- [ ] Custom SQL query executes successfully
- [ ] No connection drops during Tableau session
- [ ] Logs show queries being processed (no errors)

## Troubleshooting

### Still Getting WinError 64?

**Check**:

1. **Verify pool_size configuration**:
   ```bash
   grep "pool_size" config/config.yaml
   ```
   Should show: `pool_size: 1`

2. **Check if proxy restarted**:
   - Stop proxy completely (Ctrl+C)
   - Start fresh: `python src/main.py`
   - Verify in logs: "Starting ChronosProxy"

3. **Check backend logs**:
   - Backend may be rejecting connection for other reasons
   - Look for authentication errors, permission errors

4. **Test backend connection directly**:
   ```python
   import pyodbc
   conn_str = "DSN=your_dsn;UID=user;PWD=pass"
   conn = pyodbc.connect(conn_str)
   cursor = conn.cursor()
   cursor.execute("SHOW STATUS LIKE 'Threads_connected'")
   print(cursor.fetchall())
   conn.close()
   ```

### Different Error After Fix?

If you get a **different error** after setting pool_size: 1:

- ✅ Good sign! Connection issue is resolved
- The new error is likely a query compatibility issue
- Check `logs/chronosproxy.log` for details
- Refer to `docs/TROUBLESHOOTING.md` for other common issues

## Summary

**Problem**: WinError 64 due to backend single-connection limitation

**Fix**: Set `pool_size: 1` in `config/config.yaml`

**Result**: Stable connection, sequential query processing

**Trade-off**: Lower throughput for concurrent users (acceptable for single-user or development scenarios)

**Next Steps**: Test with Tableau, monitor logs, verify no connection drops
