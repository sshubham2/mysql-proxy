# Quick Start Guide - ChronosProxy

This guide will get you up and running with ChronosProxy in under 10 minutes.

## Prerequisites Checklist

- [ ] Python 3.11 or higher installed
- [ ] MySQL ODBC Driver installed (MySQL Connector/ODBC 8.0+)
- [ ] Access to backend MySQL server (host, port, credentials)
- [ ] Git installed (for cloning)

## Step-by-Step Setup

### 1. Clone and Setup Environment

```bash
# Clone the repository
git clone <your-repo-url>
cd mysql-proxy

# Create virtual environment
python3.11 -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
# Option 1: Simple installation
pip install -r requirements.txt

# Option 2: Editable install with dev tools (recommended for development)
pip install -e ".[dev]"
```

### 2. Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and set your MySQL password
# On Linux/Mac:
nano .env
# On Windows:
notepad .env

# Set the following:
MYSQL_PASSWORD=your_actual_password
```

### 3. Configure Backend Connection

Edit `config/config.yaml`:

```yaml
backend:
  connection_type: odbc
  odbc:
    # Update this connection string with your backend details
    connection_string: "DRIVER={MySQL ODBC 8.0 Driver};SERVER=your-mysql-host;PORT=3306;DATABASE=your_database;USER=your_username;PASSWORD=${MYSQL_PASSWORD};OPTION=3;"
```

**Key parameters to update**:
- `SERVER`: Your MySQL server hostname or IP
- `PORT`: MySQL server port (usually 3306)
- `DATABASE`: Database name
- `USER`: MySQL username

### 4. Test Backend Connection

```bash
# Start ChronosProxy (this will test the connection)
python src/main.py

# You should see:
# ============================================================
# ChronosProxy - MySQL Protocol Proxy Server
# ============================================================
# Configuration: config/config.yaml
# Testing backend connection...
# Backend connection successful
# Listening on 0.0.0.0:3307
```

If you see an error:
- Check ODBC driver is installed: `odbcinst -j`
- Verify connection string is correct
- Check network connectivity to backend MySQL

### 5. Test with MySQL Client

Open a new terminal and test connection:

```bash
# Connect using mysql client
mysql -h 127.0.0.1 -P 3307 -u your_username -p

# Enter your password when prompted

# Test a simple query (must include cob_date!)
mysql> SELECT * FROM your_table WHERE cob_date='2024-01-15' LIMIT 5;
```

### 6. Connect Tableau

1. Open Tableau Desktop
2. Click "Connect" → "MySQL"
3. Enter connection details:
   - **Server**: `localhost` (or your proxy server IP)
   - **Port**: `3307`
   - **Username**: Your backend MySQL username
   - **Password**: Your backend MySQL password
4. Click "Sign In"
5. Select your database and start creating visualizations

## Common First-Time Issues

### Issue: "Backend connection test failed"

**Solution**:
```bash
# Check ODBC driver installation
odbcinst -j

# List installed drivers
odbcinst -q -d

# You should see "MySQL ODBC 8.0 Driver" or similar
```

If driver not found:
- **Ubuntu/Debian**: `sudo apt-get install libmyodbc`
- **RHEL/CentOS**: `sudo yum install mysql-connector-odbc`
- **Mac**: `brew install mysql-connector-odbc`
- **Windows**: Download from [MySQL website](https://dev.mysql.com/downloads/connector/odbc/)

### Issue: "Port 3307 already in use"

**Solution**: Change port in `config/config.yaml`:
```yaml
proxy:
  port: 3308  # Use different port
```

Then connect to new port: `mysql -h 127.0.0.1 -P 3308`

### Issue: "cob_date filter is mandatory" errors in Tableau

**Solution**: Always include `cob_date` in WHERE clause:

**Wrong**:
```sql
SELECT category, SUM(amount) FROM sales
```

**Correct**:
```sql
SELECT category, SUM(amount)
FROM sales
WHERE cob_date='2024-01-15'
```

### Issue: "JOINs are not supported" error

**Solution**: Use one of these alternatives:
1. Create a denormalized view in the database
2. Use Tableau's data blending feature
3. Use separate data sources and join in Tableau

### Issue: "COUNT() not supported" error

**Solution**: Replace COUNT with SUM(1):

**Wrong**:
```sql
SELECT category, COUNT(*) FROM sales WHERE cob_date='2024-01-15'
```

**Correct**:
```sql
SELECT category, SUM(1) AS count FROM sales WHERE cob_date='2024-01-15'
```

## Verification Checklist

Test that everything works:

- [ ] ChronosProxy starts without errors
- [ ] MySQL client can connect to port 3307
- [ ] Simple SELECT query works
- [ ] Query with cob_date filter works
- [ ] Query without cob_date is rejected
- [ ] Tableau can connect to ChronosProxy
- [ ] Tableau can run queries and visualize data

## Next Steps

Now that ChronosProxy is running:

1. **Configure Tableau Data Source**:
   - Set up custom SQL connections
   - Add cob_date parameter for date selection
   - Test visualizations

2. **Review Logs**:
   ```bash
   # Watch logs in real-time
   tail -f logs/chronosproxy.log

   # View transformation details
   grep "TRANSFORMED" logs/chronosproxy.log
   ```

3. **Performance Tuning**:
   - Adjust connection pool size in config
   - Monitor query execution times
   - Review rejection patterns

4. **Production Deployment**:
   - See `docs/deployment.md`
   - Set up as system service
   - Configure monitoring

## Getting Help

- **Logs**: Check `logs/chronosproxy.log` for detailed error messages
- **Verbose Mode**: Run with `python src/main.py --log-level DEBUG`
- **Documentation**: See `docs/` directory for detailed guides
- **Issues**: Report problems on GitHub Issues

## Quick Reference

**Start Server**:
```bash
python src/main.py
```

**Start with Debug Logging**:
```bash
python src/main.py --log-level DEBUG
```

**Use Custom Config**:
```bash
python src/main.py --config config/production.yaml
```

**View Logs**:
```bash
tail -f logs/chronosproxy.log
```

**Test Connection**:
```bash
mysql -h 127.0.0.1 -P 3307 -u username -p
```

## Success!

You should now have ChronosProxy running and accepting connections from Tableau.

If you encounter any issues, check the troubleshooting section above or review the full documentation in the `docs/` directory.
