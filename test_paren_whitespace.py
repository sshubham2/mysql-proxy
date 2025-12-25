"""
Test the ParenthesizedQueryUnwrapper with various whitespace scenarios
"""

from src.transformation.paren_query_unwrapper import ParenthesizedQueryUnwrapper

# Test cases with various whitespace
test_cases = [
    # (query, should_unwrap, description)
    (
        "(SELECT col1, col2 FROM my_table WHERE date_index = -1) LIMIT 0",
        True,
        "Normal spacing"
    ),
    (
        "  (SELECT col1, col2 FROM my_table WHERE date_index = -1) LIMIT 0  ",
        True,
        "Leading/trailing spaces"
    ),
    (
        "\n\n(SELECT col1, col2 FROM my_table WHERE date_index = -1) LIMIT 0\n\n",
        True,
        "Leading/trailing newlines"
    ),
    (
        "(SELECT\ncol1,\ncol2\nFROM\nmy_table\nWHERE\ndate_index = -1)\nLIMIT\n0",
        True,
        "Newlines throughout"
    ),
    (
        "(SELECT  col1,  col2  FROM  my_table  WHERE  date_index = -1)  LIMIT  0",
        True,
        "Multiple spaces"
    ),
    (
        "( SELECT col1 FROM table ) LIMIT 0",
        True,
        "Space after opening paren"
    ),
]

print("=" * 80)
print("Testing ParenthesizedQueryUnwrapper with whitespace variations")
print("=" * 80)

for i, (query, should_unwrap, description) in enumerate(test_cases, 1):
    print(f"\nTest {i}: {description}")
    print(f"Query repr: {repr(query[:60])}")

    needs_unwrap = ParenthesizedQueryUnwrapper.needs_unwrapping(query)
    print(f"Needs unwrapping: {needs_unwrap} (expected: {should_unwrap})")

    if needs_unwrap != should_unwrap:
        print("  ❌ FAIL: Detection mismatch!")
        continue

    if needs_unwrap:
        unwrapped = ParenthesizedQueryUnwrapper.unwrap(query)
        print(f"Unwrapped: {unwrapped}")

        # Check if unwrapped correctly (no parens, has LIMIT)
        if unwrapped and not unwrapped.strip().startswith('('):
            print("  ✅ PASS: Successfully unwrapped")
        else:
            print(f"  ❌ FAIL: Still has parentheses or failed")
    else:
        print("  ✅ PASS: Correctly skipped")

print("\n" + "=" * 80)
print("All tests completed")
print("=" * 80)
