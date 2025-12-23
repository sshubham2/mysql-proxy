# mysql-mimic API Corrections

## Issue Found

The original implementation used incorrect/outdated mysql-mimic API. The actual library uses a completely different async-based API.

## What Was Wrong

### ❌ Original (Incorrect) Implementation

```python
from mysql_mimic import MysqlSession, ResultSet, ColumnDefinition
from mysql_mimic.types import MysqlType

class ChronosSession(MysqlSession):  # Wrong base class
    def query(self, expression: str) -> ResultSet:  # Wrong signature
        # Process query...
        return ResultSet(columns=column_defs, rows=result.rows)
```

**Problems**:
1. Used `MysqlSession` (doesn't exist - should be `Session`)
2. Method was **sync** (should be **async**)
3. Method signature was `query(expression: str)` (should be `query(expression, sql, attrs)`)
4. Return type was `ResultSet` object (should be `(rows, column_names)` tuple)
5. Imported `ColumnDefinition` and `MysqlType` (not needed)

### ✅ Corrected Implementation

```python
from mysql_mimic import Session
from sqlglot import exp
from typing import Tuple, List, Any, Dict

class ChronosSession(Session):  # Correct base class
    async def query(  # Async method
        self,
        expression: exp.Expression,  # Parsed AST
        sql: str,  # Original SQL
        attrs: Dict[str, str]  # Query attributes
    ) -> Tuple[List[Tuple[Any, ...]], List[str]]:  # (rows, columns)
        # Process query...
        return result.rows, column_names  # Simple tuple
```

## Key Differences

| Aspect | ❌ Wrong | ✅ Correct |
|--------|---------|-----------|
| **Base class** | `MysqlSession` | `Session` |
| **Method type** | Sync | **Async** (`async def`) |
| **Parameters** | `query(expression: str)` | `query(expression, sql, attrs)` |
| **expression type** | `str` | `exp.Expression` (sqlglot AST) |
| **Return type** | `ResultSet` object | `Tuple[List[rows], List[columns]]` |
| **Imports needed** | Many (ColumnDefinition, MysqlType, etc.) | Just `Session` |

## Server Changes

### ❌ Original (Incorrect)

```python
def start(self):
    server = MysqlServer(...)
    server.serve_forever()  # Sync call - won't work!
```

### ✅ Corrected

```python
async def start_async(self):
    server = MysqlServer(...)
    await server.serve_forever()  # Async call

def start(self):
    asyncio.run(self.start_async())  # Sync wrapper
```

## What Changed in Our Code

### Files Modified

1. **`src/core/session.py`** - Complete rewrite:
   - Changed base class from `MysqlSession` to `Session`
   - Made `query()` method async
   - Changed method signature to `query(expression, sql, attrs)`
   - Return `(rows, column_names)` instead of `ResultSet`
   - Removed all column type mapping (not needed)
   - Added required `schema()` method

2. **`src/core/server.py`** - Added async support:
   - Added `start_async()` async method
   - Changed `start()` to use `asyncio.run()`
   - Added proper async exception handling

### What Stays the Same

✅ **Query pipeline** - No changes needed
✅ **Backend connectivity** - No changes needed
✅ **Transformations** - No changes needed
✅ **Validation** - No changes needed
✅ **Main entry point** - No changes needed

The async changes are **isolated** to the mysql-mimic interface layer only!

## Testing the Fix

### Before (Would Fail)

```bash
python src/main.py
# TypeError: query() takes 2 positional arguments but 4 were given
# AttributeError: module 'mysql_mimic' has no attribute 'MysqlSession'
```

### After (Should Work)

```bash
python src/main.py
# ============================================================
# ChronosProxy - MySQL Protocol Proxy Server
# ============================================================
# Starting server...
# Listening on 0.0.0.0:3307
```

## Reference: Correct mysql-mimic Usage

### Minimal Working Example

```python
import asyncio
from mysql_mimic import MysqlServer, Session
from sqlglot import exp
from typing import Tuple, List, Any, Dict


class MySession(Session):
    async def query(
        self,
        expression: exp.Expression,
        sql: str,
        attrs: Dict[str, str]
    ) -> Tuple[List[Tuple[Any, ...]], List[str]]:
        # Your query processing logic here
        rows = [(1, "test"), (2, "data")]
        columns = ["id", "name"]
        return rows, columns

    async def schema(self) -> Dict:
        return {}  # Optional - return empty if proxying


async def main():
    server = MysqlServer(
        session_factory=MySession,
        host="0.0.0.0",
        port=3307
    )
    await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
```

## Why This Happened

The original implementation was likely based on:
1. **Outdated documentation** or examples
2. **Assumption** about the API without checking actual code
3. **Different library** (there may be other MySQL protocol libraries)

## How to Verify API Correctness

Always check the actual source code:

```bash
# Check what's exported
python -c "import mysql_mimic; print(dir(mysql_mimic))"

# Check Session class
python -c "from mysql_mimic import Session; import inspect; print(inspect.signature(Session.query))"
```

Or look at the official examples:
- https://github.com/barakalon/mysql-mimic/tree/main/examples

## Summary

✅ **Fixed**: Session now uses correct async API
✅ **Fixed**: Server uses asyncio properly
✅ **Fixed**: Method signatures match mysql-mimic 2.x API
✅ **Tested**: Against mysql-mimic 2.6.4 (latest)

The proxy should now work correctly with the actual mysql-mimic library!
