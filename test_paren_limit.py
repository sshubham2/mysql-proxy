"""
Test parsing queries with parentheses and LIMIT 0
"""

from sqlglot import parse_one

# Test the exact pattern you're seeing
query = "(SELECT col1, col2 FROM my_table WHERE date_index = -1) LIMIT 0"

print("=" * 80)
print("Original query:")
print(query)
print("=" * 80)

ast = parse_one(query, dialect='mysql')
print(f"\nAST type: {type(ast).__name__}")
print(f"AST: {ast}")

# Try to regenerate SQL
regenerated = ast.sql(dialect='mysql', pretty=False)
print(f"\nRegenerated SQL:")
print(regenerated)

# Check if it keeps parentheses
if regenerated.strip().startswith('('):
    print("\n⚠️  PROBLEM: Parentheses are kept!")
else:
    print("\n✅ OK: No parentheses")

# Now test WITHOUT parentheses
print("\n" + "=" * 80)
query_no_parens = "SELECT col1, col2 FROM my_table WHERE date_index = -1 LIMIT 0"
print("Query without parentheses:")
print(query_no_parens)
print("=" * 80)

ast2 = parse_one(query_no_parens, dialect='mysql')
print(f"\nAST type: {type(ast2).__name__}")

regenerated2 = ast2.sql(dialect='mysql', pretty=False)
print(f"\nRegenerated SQL:")
print(regenerated2)

# Try to see if we can detect and unwrap the parentheses
print("\n" + "=" * 80)
print("SOLUTION: Detect and remove outer parentheses")
print("=" * 80)

if regenerated.strip().startswith('(') and regenerated.strip().endswith(')'):
    # Try to unwrap
    inner = regenerated.strip()[1:-1].strip()
    print(f"Unwrapped: {inner}")

    # But we need to be careful - what if there's LIMIT after the paren?
    # Pattern: (SELECT ...) LIMIT 0
    # We need to extract the SELECT and keep the LIMIT

    import re
    match = re.match(r'^\((.*)\)\s+(LIMIT\s+\d+)$', regenerated.strip(), re.IGNORECASE | re.DOTALL)
    if match:
        inner_query = match.group(1).strip()
        limit_clause = match.group(2).strip()
        unwrapped_full = f"{inner_query} {limit_clause}"
        print(f"\nPattern matched!")
        print(f"Inner query: {inner_query}")
        print(f"LIMIT clause: {limit_clause}")
        print(f"Final unwrapped: {unwrapped_full}")
