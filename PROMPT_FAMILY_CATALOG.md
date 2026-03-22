# Prompt Family Catalog

This file is a human-readable snapshot of the live prompt family catalog in `src/saida/core/prompt_family_catalog.py`.

| Family | Governance | Plan Compilation | Result Shaping | Intents | Required Parameters | Primary Result Shapes | Plan Actions | Forbidden Primary Results |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `anova` | `governed` | `manual` | `manual` | - | target | table | anova | - |
| `categorical_column_inventory` | `governed` | `manual` | `manual` | categorical_column_inventory | - | table | categorical_column_inventory | - |
| `chi_square` | `governed` | `manual` | `manual` | - | target, group_by | table | chi_square | - |
| `column_inventory` | `governed` | `manual` | `manual` | column_inventory | - | table | column_inventory | - |
| `column_presence_check` | `governed` | `template` | `template` | existence_check | requested_column | verification | column_presence_check | - |
| `column_property_check` | `governed` | `manual` | `manual` | existence_check | requested_column, expected_property | verification | column_property_check | - |
| `column_type_inventory` | `governed` | `manual` | `manual` | column_type_inventory | - | table | column_type_inventory | - |
| `column_type_lookup` | `governed` | `template` | `template` | column_type_inventory | target | scalar | column_type_inventory | - |
| `confidence_interval` | `governed` | `manual` | `manual` | - | target | table | confidence_interval | - |
| `dimension_inventory` | `governed` | `manual` | `manual` | dimension_inventory | - | table | dimension_inventory | - |
| `distinct_value_listing` | `governed` | `template` | `template` | distinct_values | target | table | distinct_values | numeric_summary |
| `exploratory_metric_overview` | `partial` | `manual` | `manual` | - | target | table, timeseries | dataset_summary, time_trend, period_comparison, grouped_period_comparison, group_breakdown, ranked_breakdown, top_movers, top_dimension_breakdown, top_dimension_ranking, top_dimension_movers, contribution_breakdown, missingness_summary, numeric_summary, distribution_summary, target_correlation, anomaly_summary, time_series_diagnostics, group_mean_comparison | - |
| `group_ranking` | `governed` | `manual` | `manual` | group_ranking | target, group_by | table | ranked_breakdown | - |
| `grouped_entity_count` | `governed` | `template` | `template` | grouped_tabular_query | group_by | table | grouped_tabular_query | numeric_summary |
| `grouped_metric_table` | `governed` | `manual` | `manual` | grouped_tabular_query | target, group_by | table | grouped_tabular_query | - |
| `high_cardinality_inventory` | `governed` | `manual` | `manual` | high_cardinality_inventory | - | table | high_cardinality_inventory | - |
| `identifier_inventory` | `governed` | `manual` | `manual` | identifier_inventory | - | table | identifier_inventory | - |
| `mann_whitney` | `governed` | `manual` | `manual` | - | target | table | mann_whitney | - |
| `measure_inventory` | `governed` | `manual` | `manual` | measure_inventory | - | table | measure_inventory | - |
| `metric_aggregate` | `partial` | `manual` | `manual` | - | target | aggregate, count | - | - |
| `missing_value_inventory` | `governed` | `manual` | `manual` | missing_value_inventory | - | table | missing_value_inventory | - |
| `null_verification` | `governed` | `manual` | `manual` | existence_check | target | verification | null_check | - |
| `numeric_column_inventory` | `governed` | `manual` | `manual` | numeric_column_inventory | - | table | numeric_column_inventory | - |
| `power_analysis` | `governed` | `manual` | `manual` | - | target | table | power_analysis | - |
| `regression_significance` | `governed` | `manual` | `manual` | - | target | table | regression_significance | - |
| `representation_ranking` | `governed` | `template` | `template` | representation_ranking | target | table | count_rows_by_group | numeric_summary |
| `row_count` | `governed` | `template` | `template` | row_count | - | count | row_count | - |
| `row_existence_check` | `governed` | `manual` | `manual` | existence_check | - | verification | row_existence | - |
| `row_ranking` | `governed` | `manual` | `manual` | row_ranking | target | table | ranked_rows | - |
| `sample_size_estimate` | `governed` | `manual` | `manual` | - | target | table | sample_size_estimate | - |
| `significance_inference` | `governed` | `manual` | `manual` | - | target | table | significance_inference | - |
| `t_test` | `governed` | `manual` | `manual` | - | target | table | t_test | - |
| `tabular_record_retrieval` | `governed` | `template` | `template` | tabular_query | - | recordset | tabular_query | - |
| `threshold_verification` | `governed` | `manual` | `manual` | existence_check | target, threshold_value, threshold_operator | verification | threshold_check | - |
| `time_bucket_breakdown` | `governed` | `manual` | `manual` | time_bucket_breakdown | target | table | time_bucket_breakdown | - |
| `time_bucket_counts` | `partial` | `manual` | `manual` | time_bucket_counts | - | table | count_rows_by_group, time_bucket_counts | - |
| `time_column_inventory` | `governed` | `manual` | `manual` | time_column_inventory | - | table | time_column_inventory | - |
| `time_coverage` | `governed` | `manual` | `manual` | time_coverage | - | table | time_coverage | - |
| `time_period_comparison` | `governed` | `manual` | `manual` | time_period_comparison | target, time_reference | table | period_comparison, grouped_period_comparison | - |
| `time_value_verification` | `governed` | `manual` | `manual` | existence_check | target | verification | time_value_exists | - |

## Notes

- `governed`: family has a stable explicit intent surface and defined invariants.
- `partial`: family is explicit, but some plan or result behavior still relies on dynamic compiler logic or heuristic entry criteria.
