from draive import AttributeRequirement, DataModel
from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue

__all__ = [
    "prepare_filter",
]


def prepare_filter[Model: DataModel](
    requirements: AttributeRequirement[Model] | None,
) -> Filter | None:
    if requirements := requirements:
        return _convert(requirements)

    else:
        return None


def _convert[Model: DataModel](
    requirements: AttributeRequirement[Model],
    /,
) -> Filter:
    match requirements.operator:
        case "equal":
            return Filter(
                must=[
                    FieldCondition(
                        key=str(requirements.lhs),
                        match=MatchValue(value=requirements.rhs),
                    )
                ]
            )

        case "not_equal":
            return Filter(
                must_not=[
                    FieldCondition(
                        key=str(requirements.lhs),
                        match=MatchValue(value=requirements.rhs),
                    )
                ]
            )

        case "contained_in":
            return Filter(
                must=[
                    FieldCondition(
                        key=str(requirements.rhs),
                        match=MatchAny(any=requirements.lhs),
                    )
                ]
            )

        case "contains_any":
            return Filter(
                must=[
                    FieldCondition(
                        key=str(requirements.rhs),
                        match=MatchAny(any=requirements.lhs),
                    )
                ]
            )

        case "and":
            return Filter(
                must=[
                    _convert(requirements.lhs),
                    _convert(requirements.rhs),
                ]
            )

        case "or":
            return Filter(
                should=[
                    _convert(requirements.lhs),
                    _convert(requirements.rhs),
                ]
            )

        case "contains":
            raise NotImplementedError("'contains' requirement is supported with Qdrant")
