# Password Configuration Guide

## TL;DR

**Yes, you can leave it blank for no password:**

```bash
# In .env file
MYSQL_PASSWORD=
```

Or completely omit the variable - it will default to an empty password.

## How Password Configuration Works

### Three Options

1. **With Password** (recommended for security):
   ```bash
   MYSQL_PASSWORD=my_secure_password
   ```

2. **Blank Password** (for local development):
   ```bash
   MYSQL_PASSWORD=
   ```

3. **Omit Variable** (defaults to no password):
   ```bash
   # Don't include MYSQL_PASSWORD in .env at all
   ```

### How It's Used

The password is substituted into your ODBC connection string:

**In `config/config.yaml`**:
```yaml
backend:
  odbc:
    connection_string: "DRIVER={MySQL ODBC 8.0 Driver};SERVER=localhost;PORT=3306;DATABASE=test_db;USER=root;PASSWORD=${MYSQL_PASSWORD};OPTION=3;"
```

**After substitution**:

With password:
```
PASSWORD=my_secure_password
```

Without password (blank):
```
PASSWORD=
```

## Different MySQL Authentication Modes

### 1. Local Development (No Password)

```bash
# .env
MYSQL_PASSWORD=
```

```yaml
# config/config.yaml
connection_string: "DRIVER={MySQL ODBC 8.0 Driver};SERVER=localhost;PORT=3306;DATABASE=test;USER=root;PASSWORD=${MYSQL_PASSWORD}"
```

**MySQL Server Setup**:
```sql
-- Create user with no password (local development only!)
CREATE USER 'root'@'localhost' IDENTIFIED BY '';
GRANT ALL PRIVILEGES ON test.* TO 'root'@'localhost';
```

### 2. Password Authentication (Production)

```bash
# .env
MYSQL_PASSWORD=MySecureP@ssw0rd
```

**MySQL Server Setup**:
```sql
-- Create user with password
CREATE USER 'appuser'@'%' IDENTIFIED BY 'MySecureP@ssw0rd';
GRANT SELECT ON production.* TO 'appuser'@'%';
```

### 3. Socket Authentication (No Password Needed)

For local Unix socket connections on Linux/Mac:

```yaml
# config/config.yaml
backend:
  odbc:
    connection_string: "DRIVER={MySQL ODBC 8.0 Driver};SOCKET=/var/run/mysqld/mysqld.sock;DATABASE=test;USER=root"
```

No `PASSWORD=` needed at all - authentication via socket credentials.

### 4. Environment-Based Configuration

```bash
# .env.development
MYSQL_PASSWORD=

# .env.staging
MYSQL_PASSWORD=staging_password

# .env.production (use secrets manager instead!)
MYSQL_PASSWORD=prod_password_here
```

Then specify which env file to use:
```bash
cp .env.production .env
python src/main.py
```

## Security Best Practices

### ❌ Don't Do This

**Don't hardcode passwords in config files**:
```yaml
# BAD - password in plain text
connection_string: "...PASSWORD=hardcoded_password..."
```

**Don't commit .env files with real passwords**:
```bash
# BAD - .env in git
git add .env
git commit -m "Added config"  # ❌ Password now in git history!
```

### ✅ Do This

**Use environment variables**:
```yaml
# GOOD - password from environment
connection_string: "...PASSWORD=${MYSQL_PASSWORD}..."
```

**Keep .env in .gitignore**:
```bash
# .gitignore already includes this
.env
```

**Use secrets management in production**:
```bash
# AWS Secrets Manager
export MYSQL_PASSWORD=$(aws secretsmanager get-secret-value --secret-id mysql-password --query SecretString --output text)

# Kubernetes Secrets
# Mounted as environment variable in pod

# Azure Key Vault
export MYSQL_PASSWORD=$(az keyvault secret show --vault-name myVault --name mysql-password --query value -o tsv)
```

## Testing Different Configurations

### Test 1: No Password

```bash
# .env
MYSQL_PASSWORD=

# Test connection
python src/main.py
# Should connect to MySQL server without password
```

### Test 2: With Password

```bash
# .env
MYSQL_PASSWORD=test123

# Test connection
python src/main.py
# Should connect with password authentication
```

### Test 3: Variable Not Set

```bash
# .env - don't include MYSQL_PASSWORD at all

# Test
python src/main.py
# Will use empty password (defaults to blank)
```

## Troubleshooting

### Error: "Access denied for user"

```
ERROR: Access denied for user 'root'@'localhost' (using password: NO)
```

**Cause**: MySQL server requires a password, but none is set.

**Fix**:
```bash
# Set password in .env
MYSQL_PASSWORD=your_password
```

### Error: "Access denied for user" (with password)

```
ERROR: Access denied for user 'root'@'localhost' (using password: YES)
```

**Cause**: Wrong password or user doesn't have access.

**Fix**:
1. Check password is correct
2. Verify user permissions:
   ```sql
   SHOW GRANTS FOR 'root'@'localhost';
   ```

### Error: "Environment variable 'MYSQL_PASSWORD' not found"

**Cause**: Old version of code that required the variable.

**Fix**: Now handled automatically - variable is optional for passwords.

## Advanced: Multiple Databases

If connecting to multiple databases:

```bash
# .env
MYSQL_PASSWORD_PROD=prod_password
MYSQL_PASSWORD_DEV=dev_password
```

```yaml
# config/config.yaml
backend:
  odbc:
    connection_string: "...PASSWORD=${MYSQL_PASSWORD_PROD}..."
```

Switch by changing the variable name in config.

## Summary

| Scenario | .env Configuration | Result |
|----------|-------------------|--------|
| **Local dev, no password** | `MYSQL_PASSWORD=` | Empty password |
| **Local dev, omit variable** | (don't include) | Empty password |
| **Production with password** | `MYSQL_PASSWORD=secret` | Uses password |
| **Secrets manager** | Set via environment | Uses password from secret |

**Key Point**: The code now **allows blank passwords** by:
1. Accepting `MYSQL_PASSWORD=` (empty string)
2. Defaulting to `''` if variable is not set at all (for *PASSWORD variables only)

This gives you flexibility for local development while still supporting secure production deployments.
