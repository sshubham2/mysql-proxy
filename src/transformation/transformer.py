"""
Query Transformer
Coordinates all query transformations
"""

from sqlglot import exp
from typing import List, Dict, Any, Optional, Tuple
from src.config.settings import Settings
from src.utils.sql_parser import SQLParser
from src.transformation.subquery_unwrapper import SubqueryUnwrapper
from src.transformation.group_by_fixer import GroupByFixer


class TransformationRecord:
    """Record of a query transformation"""

    def __init__(
        self,
        sequence: int,
        transformation_type: str,
        description: str,
        before: str,
        after: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize transformation record

        Args:
            sequence: Sequence number
            transformation_type: Type of transformation
            description: Human-readable description
            before: SQL before transformation
            after: SQL after transformation
            details: Additional details
        """
        self.sequence = sequence
        self.transformation_type = transformation_type
        self.description = description
        self.before = before
        self.after = after
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'sequence': self.sequence,
            'type': self.transformation_type,
            'description': self.description,
            'before': self.before,
            'after': self.after,
            **self.details
        }


class TransformationResult:
    """Result of query transformation pipeline"""

    def __init__(
        self,
        original_query: str,
        final_query: str,
        final_ast: exp.Expression,
        was_transformed: bool,
        transformations: List[TransformationRecord]
    ):
        """
        Initialize transformation result

        Args:
            original_query: Original SQL query
            final_query: Final transformed SQL query
            final_ast: Final AST
            was_transformed: Whether any transformations were applied
            transformations: List of transformations applied
        """
        self.original_query = original_query
        self.final_query = final_query
        self.final_ast = final_ast
        self.was_transformed = was_transformed
        self.transformations = transformations


class Transformer:
    """Query transformation coordinator"""

    def __init__(self, settings: Settings):
        """
        Initialize transformer

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.sql_parser = SQLParser()
        self.subquery_unwrapper = SubqueryUnwrapper(settings, self.sql_parser)
        self.group_by_fixer = GroupByFixer(settings, self.sql_parser)

    def transform(self, sql: str, ast: exp.Expression) -> TransformationResult:
        """
        Apply all transformations to query

        Args:
            sql: Original SQL query
            ast: Parsed SQL AST

        Returns:
            TransformationResult with all transformations applied

        Raises:
            SubqueryTooComplex: If subquery cannot be unwrapped
        """
        transformations = []
        current_sql = sql
        current_ast = ast
        sequence = 1

        # Phase 1: Subquery Unwrapping
        unwrapped, unwrapped_sql, unwrapped_ast = self.subquery_unwrapper.unwrap(
            current_sql, current_ast
        )

        if unwrapped:
            transformations.append(TransformationRecord(
                sequence=sequence,
                transformation_type='SUBQUERY_UNWRAP',
                description='Flattened Tableau subquery wrapper',
                before=current_sql,
                after=unwrapped_sql
            ))
            current_sql = unwrapped_sql
            current_ast = unwrapped_ast
            sequence += 1

        # Phase 2: GROUP BY Auto-Fix
        fixed, fixed_sql, fixed_ast, added_cols = self.group_by_fixer.fix(
            current_sql, current_ast
        )

        if fixed:
            transformations.append(TransformationRecord(
                sequence=sequence,
                transformation_type='GROUP_BY_AUTO_FIX',
                description='Added/completed GROUP BY clause',
                before=current_sql,
                after=fixed_sql,
                details={'columns_added': added_cols}
            ))
            current_sql = fixed_sql
            current_ast = fixed_ast
            sequence += 1

        # Build result
        was_transformed = len(transformations) > 0

        return TransformationResult(
            original_query=sql,
            final_query=current_sql,
            final_ast=current_ast,
            was_transformed=was_transformed,
            transformations=transformations
        )
