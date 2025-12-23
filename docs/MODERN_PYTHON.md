# Modern Python Packaging (pyproject.toml)

## Why pyproject.toml?

ChronosProxy uses `pyproject.toml` (PEP 518, 621) instead of the legacy `setup.py`. This is the modern standard for Python packaging.

### Benefits

1. **Declarative**: Configuration is in TOML format, not executable Python code
2. **Standardized**: Single source of truth for project metadata
3. **Tool Configuration**: All tools (pytest, mypy, ruff) configured in one file
4. **Better Isolation**: Build dependencies separated from runtime dependencies
5. **Future-proof**: Officially recommended by Python Packaging Authority

## Installation Methods

### Production Installation

**Basic installation** (from requirements.txt):
```bash
pip install -r requirements.txt
```

**Package installation** (from pyproject.toml):
```bash
pip install .
```

### Development Installation

**Editable install with dev dependencies**:
```bash
pip install -e ".[dev]"
```

This installs:
- All runtime dependencies
- Testing tools (pytest, pytest-cov)
- Type checking (mypy)
- Linting/formatting (ruff)

**What is `-e` flag?**
- Makes installation "editable"
- Changes to source code immediately reflected
- No need to reinstall after code changes

### Why Not Just `requirements.txt`?

You can still use `requirements.txt` for simple deployment, but `pyproject.toml` offers:
- Optional dependency groups (`[dev]`, `[docs]`, etc.)
- Entry points for CLI commands
- Standardized metadata for publishing to PyPI

## Tool Configuration

All development tools are configured in `pyproject.toml`:

### Pytest

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

Run tests:
```bash
pytest
```

### Coverage

```toml
[tool.coverage.run]
source = ["src"]
```

Run with coverage:
```bash
pytest --cov=src --cov-report=html
```

### MyPy (Type Checking)

```toml
[tool.mypy]
python_version = "3.11"
check_untyped_defs = true
```

Run type checking:
```bash
mypy src/
```

### Ruff (Linting & Formatting)

Ruff is a modern, fast linter/formatter that replaces:
- flake8
- pylint
- isort
- black
- pyupgrade

```toml
[tool.ruff]
line-length = 100
target-version = "py311"
```

**Lint code**:
```bash
ruff check src/
```

**Format code**:
```bash
ruff format src/
```

**Auto-fix issues**:
```bash
ruff check --fix src/
```

## Project Structure

```
mysql-proxy/
├── pyproject.toml          # Modern packaging (NEW STANDARD)
├── requirements.txt        # Core dependencies only
├── src/                    # Source code
│   └── ...
└── tests/                  # Test suite
    └── ...
```

## Common Commands

**Install for development**:
```bash
pip install -e ".[dev]"
```

**Run tests**:
```bash
pytest
```

**Check types**:
```bash
mypy src/
```

**Lint code**:
```bash
ruff check src/
```

**Format code**:
```bash
ruff format src/
```

**Run all checks**:
```bash
pytest && mypy src/ && ruff check src/
```

## Publishing to PyPI (Future)

With `pyproject.toml`, publishing is simple:

```bash
# Build distribution
python -m build

# Upload to PyPI
python -m twine upload dist/*
```

Then users can install:
```bash
pip install chronosproxy
```

## Migration from setup.py

Old way (setup.py):
```python
from setuptools import setup

setup(
    name="chronosproxy",
    version="1.0.0",
    install_requires=[...],
    # ... lots of Python code
)
```

New way (pyproject.toml):
```toml
[project]
name = "chronosproxy"
version = "1.0.0"
dependencies = [...]
```

**Advantages**:
- ✅ No executable code in configuration
- ✅ Easier to parse and validate
- ✅ All tools in one file
- ✅ Standard format

## Dependency Management

### Core Dependencies

Defined in `pyproject.toml`:
```toml
[project]
dependencies = [
    "mysql-mimic>=0.3.0",
    "sqlglot>=20.11.0",
    # ...
]
```

### Optional Dependencies

```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.4.3",
    "mypy>=1.7.0",
    # ...
]
```

Install with:
```bash
pip install -e ".[dev]"
```

### Lock Files (Future Enhancement)

For production, consider using:
- **pip-tools**: Generate `requirements.lock`
- **poetry**: Full dependency management
- **PDM**: Modern alternative

Example with pip-tools:
```bash
pip install pip-tools
pip-compile pyproject.toml
pip-sync requirements.txt
```

## Best Practices

1. **Use editable installs for development**:
   ```bash
   pip install -e ".[dev]"
   ```

2. **Pin dependencies in production**:
   - Use `pip freeze > requirements.lock`
   - Deploy with: `pip install -r requirements.lock`

3. **Run checks before commit**:
   ```bash
   pytest && mypy src/ && ruff check src/
   ```

4. **Keep pyproject.toml updated**:
   - Add new dependencies to `[project] dependencies`
   - Add dev tools to `[project.optional-dependencies] dev`

## Further Reading

- [PEP 518](https://peps.python.org/pep-0518/) - pyproject.toml specification
- [PEP 621](https://peps.python.org/pep-0621/) - Project metadata
- [Python Packaging Guide](https://packaging.python.org/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)

## Summary

ChronosProxy uses modern Python packaging standards:
- ✅ `pyproject.toml` for metadata and configuration
- ✅ `requirements.txt` for simple deployment
- ✅ `pip install -e ".[dev]"` for development
- ✅ All tools configured in one place
- ✅ Future-proof and standards-compliant
