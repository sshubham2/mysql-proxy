"""
Test the ParenthesizedQueryUnwrapper
"""

from src.transformation.paren_query_unwrapper import ParenthesizedQueryUnwrapper

# Test cases
test_cases = [
    # (query, should_unwrap, expected_result)
    (
        "(SELECT col1, col2 FROM my_table WHERE date_index = -1) LIMIT 0",
        True,
        "SELECT col1, col2 FROM my_table WHERE date_index = -1 LIMIT 0"
    ),
    (
        "(SELECT * FROM users WHERE active = 1) LIMIT 10",
        True,
        "SELECT * FROM users WHERE active = 1 LIMIT 10"
    ),
    (
        "(SELECT col1 FROM table1)",
        True,
        "SELECT col1 FROM table1"
    ),
    (
        "SELECT col1 FROM table1",  # No parentheses
        False,
        None
    ),
    (
        "SELECT * FROM (SELECT col1 FROM table1) sub",  # Subquery in FROM, not outer parens
        False,
        None
    ),
]

print("=" * 80)
print("Testing ParenthesizedQueryUnwrapper")
print("=" * 80)

for i, (query, should_unwrap, expected) in enumerate(test_cases, 1):
    print(f"\nTest {i}:")
    print(f"Query: {query}")

    needs_unwrap = ParenthesizedQueryUnwrapper.needs_unwrapping(query)
    print(f"Needs unwrapping: {needs_unwrap} (expected: {should_unwrap})")

    if needs_unwrap != should_unwrap:
        print("  FAIL: Detection mismatch!")
        continue

    if needs_unwrap:
        unwrapped = ParenthesizedQueryUnwrapper.unwrap(query)
        print(f"Unwrapped: {unwrapped}")

        if unwrapped == expected:
            print("  PASS")
        else:
            print(f"  FAIL: Expected '{expected}'")
    else:
        print("  PASS: Correctly skipped")

print("\n" + "=" * 80)
print("All tests completed")
print("=" * 80)
