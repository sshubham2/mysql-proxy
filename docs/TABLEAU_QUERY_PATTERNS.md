# Tableau Query Patterns

## Pattern 1: (SELECT ...) LIMIT 0
Handler: ParenthesizedQueryUnwrapper
Transforms: `(\n  SELECT...\n) LIMIT 0` → `SELECT... LIMIT 0`

## Pattern 2: SELECT * FROM (subquery) alias
Handler: TableauWrapperUnwrapper
Transforms: `SELECT * FROM (SELECT...)` → `SELECT...`

## Pattern 3: SELECT alias.col FROM (subquery) alias
Handler: SubqueryUnwrapper
Transforms: `SELECT alias.col FROM (SELECT...) alias LIMIT 3` → `SELECT... LIMIT 3`
