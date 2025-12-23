# MySQL Credentials Configuration Guide

## TL;DR

**Username and password are both configurable via environment variables:**

```bash
# In .env file
MYSQL_USER=root              # Defaults to 'root' if omitted
MYSQL_PASSWORD=              # Blank = no password
```

Both can be omitted - will use defaults (user: `root`, password: empty).

## How Credentials Configuration Works

### Username Configuration

1. **Set username** (any MySQL user):
   ```bash
   MYSQL_USER=myapp
   ```

2. **Use default** (omit variable):
   ```bash
   # Don't include MYSQL_USER - defaults to 'root'
   ```

### Password Configuration

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
   # Don't include MYSQL_PASSWORD - defaults to empty
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

### 1. Local Development (Default root, No Password)

```bash
# .env (or omit these lines entirely - will use defaults)
MYSQL_USER=root
MYSQL_PASSWORD=
```

**MySQL Server Setup**:
```sql
-- Allow root with no password (local development only!)
CREATE USER 'root'@'localhost' IDENTIFIED BY '';
GRANT ALL PRIVILEGES ON test.* TO 'root'@'localhost';
```

### 2. Application User with Password (Production)

```bash
# .env
MYSQL_USER=chronos_app
MYSQL_PASSWORD=MySecureP@ssw0rd
```

**MySQL Server Setup**:
```sql
-- Create dedicated application user with limited permissions
CREATE USER 'chronos_app'@'%' IDENTIFIED BY 'MySecureP@ssw0rd';
GRANT SELECT ON production.* TO 'chronos_app'@'%';  -- Read-only!
FLUSH PRIVILEGES;
```

### 3. Read-Only User (Best Practice for Tableau)

```bash
# .env
MYSQL_USER=tableau_readonly
MYSQL_PASSWORD=Tableau2024!
```

**MySQL Server Setup**:
```sql
-- Create read-only user for Tableau
CREATE USER 'tableau_readonly'@'%' IDENTIFIED BY 'Tableau2024!';
GRANT SELECT ON analytics_db.* TO 'tableau_readonly'@'%';
FLUSH PRIVILEGES;
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

### Credential Configuration Matrix

| Scenario | MYSQL_USER | MYSQL_PASSWORD | Result |
|----------|-----------|---------------|--------|
| **Local dev (defaults)** | (omit) | (omit) | user: `root`, password: empty |
| **Local dev (explicit)** | `root` | `` (empty) | user: `root`, password: empty |
| **App user** | `myapp` | `secret123` | user: `myapp`, password: `secret123` |
| **Tableau readonly** | `tableau_ro` | `Tableau2024!` | user: `tableau_ro`, password set |
| **Production** | `prod_user` | From secrets | User/pass from secure storage |

### Default Behavior

**Username** (`MYSQL_USER`):
- If set: Uses specified username
- If omitted: Defaults to `root`

**Password** (`MYSQL_PASSWORD`):
- If set: Uses specified password
- If empty (`MYSQL_PASSWORD=`): Empty password
- If omitted: Defaults to empty password

**Key Points**:
1. Both username and password are now configurable via environment variables
2. Sensible defaults allow quick local setup
3. Production deployments should always set explicit credentials

This gives you flexibility for local development while still supporting secure production deployments.
