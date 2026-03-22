# Prompt Family Catalog

This file is a human-readable snapshot of the live prompt family catalog in `src/saida/core/prompt_family_catalog.py`.

| Family | Governance | Plan Compilation | Intents | Required Parameters | Primary Result Shapes | Plan Actions | Forbidden Primary Results |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `anova` | `governed` | `manual` | - | target | table | anova | - |
| `categorical_column_inventory` | `governed` | `manual` | categorical_column_inventory | - | table | categorical_column_inventory | - |
| `chi_square` | `governed` | `manual` | - | target, group_by | table | chi_square | - |
| `column_inventory` | `governed` | `manual` | column_inventory | - | table | column_inventory | - |
| `column_presence_check` | `governed` | `template` | existence_check | requested_column | verification | column_presence_check | - |
| `column_property_check` | `governed` | `manual` | existence_check | requested_column, expected_property | verification | column_property_check | - |
| `column_type_inventory` | `governed` | `manual` | column_type_inventory | - | table | column_type_inventory | - |
| `column_type_lookup` | `governed` | `template` | column_type_inventory | target | scalar | column_type_inventory | - |
| `confidence_interval` | `governed` | `manual` | - | target | table | confidence_interval | - |
| `dimension_inventory` | `governed` | `manual` | dimension_inventory | - | table | dimension_inventory | - |
| `distinct_value_listing` | `governed` | `template` | distinct_values | target | table | distinct_values | numeric_summary |
| `group_ranking` | `governed` | `manual` | group_ranking | target, group_by | table | ranked_breakdown | - |
| `grouped_entity_count` | `governed` | `template` | grouped_tabular_query | group_by | table | grouped_tabular_query | numeric_summary |
| `grouped_metric_table` | `governed` | `manual` | grouped_tabular_query | target, group_by | table | grouped_tabular_query | - |
| `high_cardinality_inventory` | `governed` | `manual` | high_cardinality_inventory | - | table | high_cardinality_inventory | - |
| `identifier_inventory` | `governed` | `manual` | identifier_inventory | - | table | identifier_inventory | - |
| `legacy_metric_overview` | `legacy` | `manual` | - | target | - | - | - |
| `mann_whitney` | `governed` | `manual` | - | target | table | mann_whitney | - |
| `measure_inventory` | `governed` | `manual` | measure_inventory | - | table | measure_inventory | - |
| `metric_aggregate` | `partial` | `manual` | - | target | aggregate, count | - | - |
| `missing_value_inventory` | `governed` | `manual` | missing_value_inventory | - | table | missing_value_inventory | - |
| `null_verification` | `governed` | `manual` | existence_check | target | verification | null_check | - |
| `numeric_column_inventory` | `governed` | `manual` | numeric_column_inventory | - | table | numeric_column_inventory | - |
| `power_analysis` | `governed` | `manual` | - | target | table | power_analysis | - |
| `regression_significance` | `governed` | `manual` | - | target | table | regression_significance | - |
| `representation_ranking` | `governed` | `template` | representation_ranking | target | table | count_rows_by_group | numeric_summary |
| `row_count` | `governed` | `template` | row_count | - | count | row_count | - |
| `row_existence_check` | `governed` | `manual` | existence_check | - | verification | row_existence | - |
| `row_ranking` | `governed` | `manual` | row_ranking | target | table | ranked_rows | - |
| `sample_size_estimate` | `governed` | `manual` | - | target | table | sample_size_estimate | - |
| `significance_inference` | `governed` | `manual` | - | target | table | significance_inference | - |
| `t_test` | `governed` | `manual` | - | target | table | t_test | - |
| `tabular_record_retrieval` | `governed` | `template` | tabular_query | - | table | tabular_query | - |
| `threshold_verification` | `governed` | `manual` | existence_check | target, threshold_value, threshold_operator | verification | threshold_check | - |
| `time_bucket_breakdown` | `governed` | `manual` | time_bucket_breakdown | target | table | time_bucket_breakdown | - |
| `time_bucket_counts` | `partial` | `manual` | time_bucket_counts | - | table | count_rows_by_group, time_bucket_counts | - |
| `time_column_inventory` | `governed` | `manual` | time_column_inventory | - | table | time_column_inventory | - |
| `time_coverage` | `governed` | `manual` | time_coverage | - | table | time_coverage | - |
| `time_period_comparison` | `governed` | `manual` | time_period_comparison | target, time_reference | table | period_comparison, grouped_period_comparison | - |
| `time_value_verification` | `governed` | `manual` | existence_check | target | verification | time_value_exists | - |

## Notes

- `governed`: family has a stable explicit intent surface and defined invariants.
- `partial`: family is explicit, but some plan or result behavior still relies on legacy branching.
- `legacy`: family exists mainly to expose non-governed fallback behavior while migration continues.
