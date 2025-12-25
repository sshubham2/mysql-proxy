"""
Test script to check if unwrapping adds parentheses
"""

from sqlglot import parse_one, exp

# Test 1: Simple custom query unwrapping
wrapper_query = """
SELECT * FROM (
    SELECT col1, col2 FROM my_table WHERE date_index = -1
) `Custom SQL` LIMIT 0
"""

print("=" * 80)
print("TEST 1: Tableau wrapper unwrapping")
print("=" * 80)
print(f"Original wrapper query:\n{wrapper_query}\n")

# Parse
ast = parse_one(wrapper_query, dialect='mysql')
print(f"AST type: {type(ast)}")

# Find the subquery
from_clause = ast.find(exp.From)
if from_clause:
    subquery = from_clause.find(exp.Subquery)
    if subquery:
        inner_select = subquery.this
        print(f"Inner SELECT AST type: {type(inner_select)}")

        # Convert back to SQL using different methods
        unwrapped_sql_1 = inner_select.sql(dialect='mysql')
        unwrapped_sql_2 = inner_select.sql(dialect='mysql', pretty=False)

        print(f"\nUnwrapped (method 1 - default):\n{unwrapped_sql_1}\n")
        print(f"Unwrapped (method 2 - pretty=False):\n{unwrapped_sql_2}\n")

        # Check if it has parentheses
        if unwrapped_sql_1.strip().startswith('(') and unwrapped_sql_1.strip().endswith(')'):
            print("WARNING: Unwrapped query has parentheses!")
        else:
            print("OK: No parentheses in unwrapped query")

# Test 2: Check what happens with SubqueryUnwrapper logic
print("\n" + "=" * 80)
print("TEST 2: SubqueryUnwrapper logic")
print("=" * 80)

# Simulate what SubqueryUnwrapper does
if isinstance(ast, exp.Select):
    from_clause = ast.find(exp.From)
    if from_clause:
        subquery = from_clause.find(exp.Subquery)
        if subquery:
            inner_select = subquery.this

            # Clone it (like SubqueryUnwrapper does)
            unwrapped = inner_select.copy()

            # Merge outer LIMIT
            outer_limit = ast.find(exp.Limit)
            if outer_limit:
                print(f"Outer LIMIT found: {outer_limit.sql()}")
                inner_limit = unwrapped.find(exp.Limit)
                if not inner_limit:
                    print("Adding outer LIMIT to unwrapped query")
                    unwrapped.set('limit', outer_limit)

            # Convert to SQL
            final_sql = unwrapped.sql(dialect='mysql', pretty=False)
            print(f"\nFinal unwrapped SQL:\n{final_sql}\n")

            # Check for parentheses
            if final_sql.strip().startswith('(') and final_sql.strip().endswith(')'):
                print("WARNING: Final query has parentheses!")
                # Try to remove them
                stripped = final_sql.strip()
                if stripped.startswith('(') and stripped.endswith(')'):
                    without_parens = stripped[1:-1]
                    print(f"\nWithout parentheses:\n{without_parens}\n")
            else:
                print("OK: No parentheses in final query")

# Test 3: Parse and regenerate a simple query
print("\n" + "=" * 80)
print("TEST 3: Simple query parse and regenerate")
print("=" * 80)

simple_query = "SELECT col1, col2 FROM my_table WHERE date_index = -1"
print(f"Original:\n{simple_query}\n")

simple_ast = parse_one(simple_query, dialect='mysql')
regenerated = simple_ast.sql(dialect='mysql', pretty=False)
print(f"Regenerated:\n{regenerated}\n")

if regenerated.strip().startswith('(') and regenerated.strip().endswith(')'):
    print("WARNING: Simple query got parentheses!")
else:
    print("OK: No parentheses added")
