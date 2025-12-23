# Windows ODBC Setup Guide

## Your Question: Can I Leave Both Blank?

**Yes!** If you configure credentials in Windows ODBC Data Source Administrator, you don't need them in `.env` or `config.yaml`.

## Three Ways to Connect on Windows

### Option 1: Windows ODBC DSN (Recommended - What You Want)

**Credentials stored in Windows ODBC Data Source Administrator**

#### Step 1: Create ODBC DSN in Windows

1. Open **ODBC Data Sources (64-bit)**:
   - Press `Win + R`
   - Type: `odbcad32.exe`
   - Press Enter

2. Click **Add** (System DSN or User DSN tab)

3. Select **MySQL ODBC 8.0 Driver**

4. Configure DSN:
   - **Data Source Name**: `MySQL_ChronosProxy`
   - **Description**: ChronosProxy Backend
   - **TCP/IP Server**: `your-mysql-server.com`
   - **Port**: `3306`
   - **User**: `your_username`
   - **Password**: `your_password`
   - **Database**: `your_database`
   - Click **Test** to verify connection
   - Click **OK**

#### Step 2: Configure ChronosProxy

**config/config.yaml**:
```yaml
backend:
  connection_type: odbc
  odbc:
    # Use DSN - credentials already configured in Windows
    connection_string: "DSN=MySQL_ChronosProxy;"
```

**`.env` file** (leave blank or omit entirely):
```bash
# No credentials needed - they're in the DSN!
# MYSQL_USER=  (not needed)
# MYSQL_PASSWORD=  (not needed)
```

✅ **Done!** No credentials in your code or config files.

---

### Option 2: Direct Connection WITHOUT Credentials in .env

If you have a MySQL server that doesn't require authentication (local dev):

**config/config.yaml**:
```yaml
backend:
  connection_type: odbc
  odbc:
    # No USER/PASSWORD parameters
    connection_string: "DRIVER={MySQL ODBC 8.0 Driver};SERVER=localhost;PORT=3306;DATABASE=test_db;OPTION=3;"
```

**`.env` file** (leave blank):
```bash
# Not needed for this connection type
```

---

### Option 3: Direct Connection WITH Credentials from .env

If you want credentials in environment variables (previous approach):

**config/config.yaml**:
```yaml
backend:
  connection_type: odbc
  odbc:
    connection_string: "DRIVER={MySQL ODBC 8.0 Driver};SERVER=localhost;PORT=3306;DATABASE=test_db;USER=${MYSQL_USER};PASSWORD=${MYSQL_PASSWORD};OPTION=3;"
```

**`.env` file**:
```bash
MYSQL_USER=myuser
MYSQL_PASSWORD=mypassword
```

---

## For Your Use Case

Based on your question, you want **Option 1 (ODBC DSN)**:

### Quick Setup

1. **Create Windows DSN** (see Step 1 above)

2. **Edit `config/config.yaml`**:
   ```yaml
   backend:
     connection_type: odbc
     odbc:
       connection_string: "DSN=MySQL_ChronosProxy;"
   ```

3. **`.env` file** - Create empty or minimal:
   ```bash
   # Optional config overrides only
   LOG_LEVEL=INFO

   # MYSQL_USER and MYSQL_PASSWORD not needed!
   ```

4. **Test**:
   ```bash
   python src/main.py
   ```

## Verifying Your DSN

Test DSN connection before using ChronosProxy:

```bash
# In Windows Command Prompt or PowerShell
odbcconf /q /A {CONFIGSYSDSN "MySQL ODBC 8.0 Driver" "DSN=MySQL_ChronosProxy"}
```

Or test with Python:
```python
import pyodbc
conn = pyodbc.connect('DSN=MySQL_ChronosProxy')
print("Connection successful!")
conn.close()
```

## Troubleshooting

### Error: "Data source name not found"

```
[IM002] [Microsoft][ODBC Driver Manager] Data source name not found
```

**Cause**: DSN not configured or wrong name.

**Fix**:
1. Check DSN exists: Open `odbcad32.exe` → Check System DSN or User DSN tabs
2. Verify name matches exactly in config: `DSN=YourDSNName`
3. Use System DSN (not User DSN) if running as service

### Error: "Access denied"

```
[HY000] [MySQL][ODBC 8.0 Driver] Access denied for user
```

**Cause**: Wrong credentials in DSN.

**Fix**:
1. Open `odbcad32.exe`
2. Select your DSN → Configure
3. Update username/password
4. Click Test to verify

### DSN Not Appearing

**Problem**: Created DSN but ChronosProxy can't find it.

**Reasons**:
1. **32-bit vs 64-bit mismatch**:
   - ChronosProxy uses 64-bit Python → needs 64-bit DSN
   - Use `C:\Windows\System32\odbcad32.exe` (64-bit)
   - NOT `C:\Windows\SysWOW64\odbcad32.exe` (32-bit)

2. **User vs System DSN**:
   - User DSN: Only for current user
   - System DSN: Available to all users/services
   - Recommended: Use System DSN

### Finding the Right ODBC Admin

```bash
# 64-bit ODBC Admin (for 64-bit Python)
%windir%\System32\odbcad32.exe

# 32-bit ODBC Admin (for 32-bit Python)
%windir%\SysWOW64\odbcad32.exe
```

To check your Python:
```bash
python -c "import struct; print(struct.calcsize('P') * 8, 'bit')"
```

## Advanced: Connection String Parameters

Full list of parameters you can use:

```
DSN=MySQL_ChronosProxy;               # Data Source Name
DRIVER={MySQL ODBC 8.0 Driver};       # Driver name
SERVER=hostname;                       # MySQL server
PORT=3306;                             # MySQL port
DATABASE=dbname;                       # Database
USER=username;                         # Username
PASSWORD=password;                     # Password
OPTION=3;                              # Options flag
CHARSET=utf8mb4;                       # Character set
INITSTMT=SET NAMES utf8mb4;           # Initial statement
SSLMODE=REQUIRED;                      # SSL mode
SSLCA=C:\path\to\ca.pem;              # SSL CA certificate
```

## Security Best Practices

### ✅ Recommended: Windows DSN

**Pros**:
- Credentials stored in Windows Credential Manager (encrypted)
- No credentials in code/config files
- Can use Windows authentication
- Easy to update without code changes

**Cons**:
- Requires Windows ODBC setup on each machine
- Not portable across different OS

### ⚠️ Not Recommended: Credentials in .env

**Pros**:
- Easy to configure
- Portable

**Cons**:
- Credentials in plain text
- Risk of committing to git
- Less secure

### 🏆 Best Practice: Production

For production, use one of:

1. **Windows Credential Manager** (via DSN)
2. **Azure Key Vault** (for Azure deployments)
3. **AWS Secrets Manager** (for AWS)
4. **Environment variables from orchestrator** (Kubernetes secrets, etc.)

## Summary

| Method | .env Credentials | Security | Setup Complexity |
|--------|-----------------|----------|------------------|
| **Windows DSN** | ❌ Not needed | ✅ High | Medium |
| **Direct + .env** | ✅ Required | ⚠️ Medium | Low |
| **Direct no auth** | ❌ Not needed | ❌ Low | Low |

**For your use case**: Use Windows DSN (Option 1) - no credentials needed in `.env`! ✅
