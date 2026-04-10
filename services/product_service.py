"""Re-export shim for backwards compatibility.

All implementation has been split into focused modules:
- product_crud.py      — CRUD operations and list_products
- product_scoring.py   — Scoring formula and weight computation
- product_filters.py   — Advanced filtering logic
- product_duplicate.py — Duplicate detection and merging
- product_eans.py      — EAN CRUD operations
"""

from services.product_crud import (
    _get_product_flags,
    _set_user_flags,
    set_system_flag,
    list_products,
    add_product,
    update_product,
    delete_product,
)
from services.product_eans import (
    list_eans,
    add_ean,
    delete_ean,
    set_primary_ean,
    unsync_ean,
)
from services.product_scoring import (
    _load_weight_config,
    _compute_category_ranges,
    _score_product,
    _compute_completeness,
)
from services.product_filters import (
    _parse_condition,
    _condition_to_sql,
    _convert_legacy_format,
    _count_conditions,
    _parse_advanced_filters,
    _evaluate_post_node,
    _apply_post_filters,
)
from services.product_duplicate import (
    _find_duplicate,
    check_duplicate_for_edit,
    merge_products,
)

__all__ = [
    "_get_product_flags",
    "_set_user_flags",
    "set_system_flag",
    "list_products",
    "add_product",
    "update_product",
    "delete_product",
    "list_eans",
    "add_ean",
    "delete_ean",
    "set_primary_ean",
    "unsync_ean",
    "_load_weight_config",
    "_compute_category_ranges",
    "_score_product",
    "_compute_completeness",
    "_parse_condition",
    "_condition_to_sql",
    "_convert_legacy_format",
    "_count_conditions",
    "_parse_advanced_filters",
    "_evaluate_post_node",
    "_apply_post_filters",
    "_find_duplicate",
    "check_duplicate_for_edit",
    "merge_products",
]
