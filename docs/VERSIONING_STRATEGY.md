# Dependency Versioning Strategy

## Philosophy: Flexible by Default, Locked in Production

ChronosProxy uses a **flexible versioning strategy** that balances security, compatibility, and ease of updates.

## Versioning Approach

### Development & Library Mode: Flexible Ranges

We use **compatible release** specifiers (`>=X.Y.Z,<MAJOR+1.0`) that allow:
- ✅ Patch updates (bug fixes)
- ✅ Minor updates (new features, backward compatible)
- ❌ Major updates (breaking changes)

**Example**:
```toml
"sqlglot>=20.11.0,<25.0"  # Allows 20.11.1, 20.12.0, 21.0.0... but not 25.0.0
```

### Production Deployment: Lock File

For production deployments, generate a lock file:
```bash
pip freeze > requirements.lock
```

Then deploy with exact versions:
```bash
pip install -r requirements.lock
```

## Why Flexible Ranges?

### ❌ Problems with Exact Pinning (`==`)

```toml
# TOO RESTRICTIVE - Don't do this in library code
dependencies = [
    "sqlglot==20.11.0",  # ❌ Blocks security updates
    "pytest==7.4.3",     # ❌ Blocks bug fixes
]
```

**Issues**:
1. **Security vulnerabilities**: Can't get patch releases with security fixes
2. **Dependency conflicts**: Hard to use with other packages
3. **Maintenance burden**: Manual updates for every patch
4. **No bug fixes**: Stuck with known bugs until manual update

### ❌ Problems with No Upper Bound (`>=`)

```toml
# TOO FLEXIBLE - Can break unexpectedly
dependencies = [
    "sqlglot>=20.11.0",  # ❌ Could install sqlglot 100.0.0 with breaking changes
]
```

**Issues**:
1. **Breaking changes**: Major version updates can break code
2. **Unpredictable builds**: Different installs get different versions
3. **Hard to debug**: "Works on my machine" problems

### ✅ Sweet Spot: Compatible Release (`>=X,<MAJOR+1`)

```toml
# JUST RIGHT - Flexible but safe
dependencies = [
    "sqlglot>=20.11.0,<25.0",  # ✅ Gets updates, blocks breaking changes
]
```

**Benefits**:
1. ✅ **Security patches**: Automatically get bug fixes
2. ✅ **New features**: Get non-breaking improvements
3. ✅ **Stable**: Block breaking changes
4. ✅ **Compatible**: Works with other packages

## ChronosProxy's Versioning Rules

### Core Dependencies (Runtime)

```toml
dependencies = [
    "mysql-mimic>=0.3.0,<1.0",           # Pre-1.0: Any 0.x
    "pyodbc>=5.0.1,<6.0",                # Mature: Any 5.x
    "sqlglot>=20.11.0,<25.0",            # Active: Allow ~5 major versions
    "pyyaml>=6.0.1,<7.0",                # Stable: Any 6.x
]
```

**Strategy**:
- **Pre-1.0 packages** (`mysql-mimic`): Allow 0.x, block 1.0 (major API change expected)
- **Mature packages** (`pyodbc`, `pyyaml`): Allow current major version
- **Active packages** (`sqlglot`): Allow reasonable range (5 major versions)

### Dev Dependencies (Testing/Linting)

```toml
dev = [
    "pytest>=7.4.3,<9.0",      # Allow 7.x and 8.x
    "mypy>=1.7.0,<2.0",        # Block 2.x (could have breaking changes)
    "ruff>=0.1.0",             # No upper bound (rapid development, tooling)
]
```

**Strategy**:
- **Test frameworks**: Wider range (less breaking changes)
- **Type checkers**: Conservative (strict on breaking changes)
- **Dev tools** (ruff): Very flexible (tooling, not runtime)

## Version Specifier Syntax

Python supports several version specifiers:

```python
# Exact version (too restrictive)
"package==1.0.0"

# Minimum version (too flexible)
"package>=1.0.0"

# Compatible release (recommended for libraries)
"package~=1.0.0"  # Same as ">=1.0.0,<1.1.0"

# Range (our approach - explicit and clear)
"package>=1.0.0,<2.0"

# Exclude specific versions (use sparingly)
"package>=1.0.0,<2.0,!=1.5.0"
```

## When to Use Each Strategy

### Use Flexible Ranges When:
- ✅ Developing a library or reusable package
- ✅ You want automatic security updates
- ✅ Dependencies follow semantic versioning
- ✅ You run tests regularly

### Use Lock Files When:
- ✅ Deploying to production
- ✅ Need reproducible builds
- ✅ Compliance/audit requirements
- ✅ Deploying to multiple servers

### Use Exact Pins When:
- ⚠️ Known incompatibility with newer versions
- ⚠️ Temporary workaround for bug
- ⚠️ Legacy system (not recommended)

## Production Deployment Workflow

### 1. Development (Flexible)

```bash
# Use flexible ranges
pip install -e ".[dev]"

# Run tests regularly to catch issues
pytest
```

### 2. Pre-Production (Lock)

```bash
# Generate lock file with exact versions
pip freeze > requirements.lock

# Test with locked versions
pip install -r requirements.lock
pytest
```

### 3. Production (Deploy Lock)

```bash
# Deploy with exact versions from lock file
pip install -r requirements.lock

# No surprises - exact same versions as tested
```

### 4. Updates (Controlled)

```bash
# Periodically update dependencies
pip install --upgrade -e ".[dev]"

# Run full test suite
pytest

# If passing, regenerate lock file
pip freeze > requirements.lock

# Deploy updated lock file
```

## Semantic Versioning Refresher

Dependencies should follow [SemVer](https://semver.org/):

```
MAJOR.MINOR.PATCH

1.2.3
│ │ │
│ │ └─ Bug fixes (backward compatible)
│ └─── New features (backward compatible)
└───── Breaking changes
```

**Our ranges block MAJOR updates**:
```toml
"package>=1.2.3,<2.0"  # Blocks breaking changes
```

## Special Cases

### Pre-release Packages (0.x.x)

```toml
"mysql-mimic>=0.3.0,<1.0"  # Any 0.x, block 1.0
```

**Rationale**: Version 1.0 often brings major API changes.

### Rapidly Evolving Tools

```toml
"ruff>=0.1.0"  # No upper bound
```

**Rationale**: Dev tools iterate fast; we want improvements.

### Stable, Mature Packages

```toml
"pyyaml>=6.0.1,<7.0"  # One major version range
```

**Rationale**: Unlikely to break, but be safe.

## Dependency Management Tools

### pip-tools (Recommended)

```bash
# Install
pip install pip-tools

# Generate requirements from pyproject.toml
pip-compile pyproject.toml

# Sync environment
pip-sync requirements.txt
```

### poetry (Alternative)

```bash
# Install
pip install poetry

# poetry.lock automatically generated
poetry install
```

### PDM (Modern Alternative)

```bash
# Install
pip install pdm

# pdm.lock automatically generated
pdm install
```

## Checking for Updates

### Manual Check

```bash
# List outdated packages
pip list --outdated

# Update specific package
pip install --upgrade sqlglot
```

### Automated (pip-review)

```bash
# Install tool
pip install pip-review

# Interactive update
pip-review --interactive
```

## Security Considerations

### Automated Security Scanning

Use tools like:
- **Safety**: `pip install safety && safety check`
- **Dependabot**: GitHub automated PRs for updates
- **Snyk**: Continuous security monitoring

### Regular Updates

```bash
# Monthly/quarterly update cycle
pip install --upgrade -e ".[dev]"
pytest  # Verify everything works
pip freeze > requirements.lock
```

## Summary: ChronosProxy's Approach

| Aspect | Strategy |
|--------|----------|
| **Development** | Flexible ranges (`>=X,<MAJOR+1`) |
| **Production** | Lock file (`requirements.lock`) |
| **Updates** | Controlled, tested upgrades |
| **Security** | Automatic patches within range |
| **Testing** | CI runs with latest versions |

## Best Practices

1. ✅ **Use ranges in `pyproject.toml`**: Allow updates, block breaking changes
2. ✅ **Generate lock file for production**: Reproducible builds
3. ✅ **Run tests regularly**: Catch incompatibilities early
4. ✅ **Update dependencies monthly**: Stay current with security
5. ✅ **Review changelogs**: Understand what's changing
6. ✅ **Pin only when necessary**: Workarounds, not defaults

## Further Reading

- [PEP 440](https://peps.python.org/pep-0440/) - Version specifiers
- [Semantic Versioning](https://semver.org/) - Version scheme
- [pip-tools](https://github.com/jazzband/pip-tools) - Dependency management
- [Poetry](https://python-poetry.org/) - Modern packaging
- [PDM](https://pdm.fming.dev/) - PEP 582 package manager

## TL;DR

**Question**: Why not pin exact versions?

**Answer**:
- ❌ Exact pins (`==1.0.0`) block security updates
- ✅ Flexible ranges (`>=1.0.0,<2.0`) get patches, block breaking changes
- ✅ Use lock files in production for reproducible builds
- ✅ Best of both worlds: flexibility + stability
