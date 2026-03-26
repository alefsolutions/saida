![SAIDA Banner](assets/github-banner.png)

# SAIDA Prompt Playbook

This file is a practical dictionary of prompts you can try against SAIDA.

It is built from the live prompt families and compute workflows in the current codebase.

Use it when you want to:

- learn what SAIDA can do
- see what prompt shapes work well
- understand what placeholders to swap in
- test one family at a time

## How To Read This File

Prompts use placeholders such as:

- `[measure]`
  - a numeric field like `revenue`, `resolution_hours`, or `csat_score`
- `[dimension]`
  - a categorical/grouping field like `region`, `channel`, `team`, or `priority`
- `[time_field]`
  - a datetime field like `created_at` or `posted_at`
- `[field]`
  - any field or column
- `[identifier]`
  - a likely ID field like `ticket_id` or `order_id`
- `[value]`
  - a literal value from a field
- `[n]`
  - a number such as `5`, `10`, or `20`
- `[year]`
  - a year like `2025`
- `[month]`
  - a month like `January`
- `[quarter]`
  - a quarter like `Q1`
- `[threshold]`
  - a numeric threshold like `20`

## Important Notes

- Replace placeholders with real column names from your dataset.
- Some prompt families require the field types to make sense.
  - Example: `[measure]` should really be numeric.
- Some workflows are `governed` and strict.
- Some are `partial`, which means they work but can still be broader or more heuristic.

## Prompt Family Index

| Family | Governance | Primary Shape | Main Compute Action(s) |
| --- | --- | --- | --- |
| `anova` | `governed` | `table` | `anova` |
| `categorical_column_count` | `governed` | `count` | `categorical_column_count` |
| `categorical_column_inventory` | `governed` | `table` | `categorical_column_inventory` |
| `chi_square` | `governed` | `table` | `chi_square` |
| `column_count` | `governed` | `count` | `column_count` |
| `column_inventory` | `governed` | `table` | `column_inventory` |
| `column_presence_check` | `governed` | `verification` | `column_presence_check` |
| `column_property_check` | `governed` | `verification` | `column_property_check` |
| `column_type_inventory` | `governed` | `table` | `column_type_inventory` |
| `column_type_lookup` | `governed` | `scalar` | `column_type_inventory` |
| `confidence_interval` | `governed` | `table` | `confidence_interval` |
| `dimension_count` | `governed` | `count` | `dimension_count` |
| `dimension_inventory` | `governed` | `table` | `dimension_inventory` |
| `distinct_value_count` | `governed` | `count` | `distinct_value_count` |
| `distinct_value_listing` | `governed` | `table` | `distinct_values` |
| `exploratory_metric_overview` | `partial` | `table`, `timeseries` | `dataset_summary`, `time_trend`, `group_breakdown`, `numeric_summary`, more |
| `group_ranking` | `governed` | `table` | `ranked_breakdown` |
| `grouped_entity_count` | `governed` | `table` | `grouped_tabular_query` |
| `grouped_metric_table` | `governed` | `table` | `grouped_tabular_query` |
| `high_cardinality_count` | `governed` | `count` | `high_cardinality_count` |
| `high_cardinality_inventory` | `governed` | `table` | `high_cardinality_inventory` |
| `identifier_count` | `governed` | `count` | `identifier_count` |
| `identifier_inventory` | `governed` | `table` | `identifier_inventory` |
| `mann_whitney` | `governed` | `table` | `mann_whitney` |
| `measure_count` | `governed` | `count` | `measure_count` |
| `measure_inventory` | `governed` | `table` | `measure_inventory` |
| `metric_aggregate` | `partial` | `aggregate`, `count` | aggregate metric workflows |
| `missing_value_inventory` | `governed` | `table` | `missing_value_inventory` |
| `null_verification` | `governed` | `verification` | `null_check` |
| `numeric_column_count` | `governed` | `count` | `numeric_column_count` |
| `numeric_column_inventory` | `governed` | `table` | `numeric_column_inventory` |
| `power_analysis` | `governed` | `table` | `power_analysis` |
| `regression_significance` | `governed` | `table` | `regression_significance` |
| `representation_ranking` | `governed` | `table` | `count_rows_by_group` |
| `row_count` | `governed` | `count` | `row_count` |
| `row_existence_check` | `governed` | `verification` | `row_existence` |
| `row_ranking` | `governed` | `table` | `ranked_rows` |
| `sample_size_estimate` | `governed` | `table` | `sample_size_estimate` |
| `significance_inference` | `governed` | `table` | `significance_inference` |
| `t_test` | `governed` | `table` | `t_test` |
| `tabular_record_retrieval` | `governed` | `recordset` | `tabular_query` |
| `threshold_verification` | `governed` | `verification` | `threshold_check` |
| `time_bucket_breakdown` | `governed` | `table` | `time_bucket_breakdown` |
| `time_bucket_counts` | `partial` | `table` | `count_rows_by_group`, `time_bucket_counts` |
| `time_column_count` | `governed` | `count` | `time_column_count` |
| `time_column_inventory` | `governed` | `table` | `time_column_inventory` |
| `time_coverage` | `governed` | `table` | `time_coverage` |
| `time_period_comparison` | `governed` | `table` | `period_comparison`, `grouped_period_comparison` |
| `time_value_verification` | `governed` | `verification` | `time_value_exists` |

## 1. Exploratory Metric Overview

Family: `exploratory_metric_overview`  
Governance: `partial`  
Result shape: `table` or `timeseries`

Use this when you want a broad overview of a metric instead of one very narrow computation.

Prompt templates:

- `Show [measure].`
- `Analyze [measure].`
- `Summarize [measure].`
- `Give me an overview of [measure].`
- `Explore [measure].`
- `What is going on with [measure]?`
- `Explain [measure].`

Good examples:

- `Show revenue.`
- `Analyze resolution_hours.`
- `Give me an overview of csat_score.`

## 2. Metric Aggregate

Family: `metric_aggregate`  
Governance: `partial`  
Result shape: `aggregate` or `count`

Use this when you want one scalar metric result.

Prompt templates:

- `What is the total [measure]?`
- `What is the sum of [measure]?`
- `What is the average [measure]?`
- `What is the mean [measure]?`
- `What is the maximum [measure]?`
- `What is the highest [measure]?`
- `What is the minimum [measure]?`
- `What is the lowest [measure]?`
- `Count total [measure] values.`

Good examples:

- `What is the total revenue?`
- `What is the average resolution_hours?`
- `What is the maximum csat_score?`

## 3. Row Count

Family: `row_count`  
Governance: `governed`  
Result shape: `count`

Prompt templates:

- `How many rows are in the dataset?`
- `What is the row count?`
- `Count rows.`
- `How many records are there?`
- `Count total rows in dataset.`
- `How many rows are in [quarter]?`
- `Count rows for [month] [year].`
- `How many rows were created in [year]?`

Good examples:

- `How many rows are in Q1?`
- `Count total rows in dataset for Q1.`
- `How many rows are in January 2025?`

## 4. Tabular Record Retrieval

Family: `tabular_record_retrieval`  
Governance: `governed`  
Result shape: `recordset`

Use this when you want rows, selected columns, sorting, filtering, limits, or pagination.

### Basic row retrieval

- `Show all rows.`
- `List all records.`
- `Return all entries.`
- `Show every row in dataset.`

### Selected columns

- `Show [field] and [field].`
- `Show [field], [field], and [field] rows.`
- `Return [field] and [field] records.`

### Sorting

- `Show [field] and [field] rows sorted by [field].`
- `Show rows ordered by [field].`
- `Return the latest rows sorted by [time_field].`
- `List records sorted by [measure] descending.`

### Limits and paging

- `Show first [n] rows.`
- `Return first [n] records sorted by [field].`
- `Show page [n] page size [n] sorted by [field].`
- `Return first [n] rows page [n] page size [n].`

### Filtered retrieval

- `Show all rows where [dimension] is [value].`
- `List rows for [month] [year].`
- `Show records where [measure] is above [threshold].`
- `Return rows where [dimension] is [value] and [dimension] is [value].`

### Calendar-aware retrieval variations

- `List all rows on the [n]th day of every month.`
- `List all rows on Mondays.`
- `List all rows on weekdays.`
- `List all rows on the first day of every month.`
- `List all rows on the last day of every month.`
- `List all rows for Q1.`
- `List all rows from the last 7 days.`
- `List all rows on the first Monday of every month.`
- `List all rows on the last Friday of every month.`

Good examples:

- `Show ticket_id and priority rows sorted by created_at.`
- `List all rows for January 2025.`
- `Show all tickets created on the first Monday of every month.`

## 5. Grouped Entity Count

Family: `grouped_entity_count`  
Governance: `governed`  
Result shape: `table`

Use this when you want counts by group.

Prompt templates:

- `Count rows by [dimension].`
- `How many records per [dimension]?`
- `Give me total rows by [dimension].`
- `Count [entity] by [dimension].`
- `How many [entity] per [dimension]?`
- `Give me total [entity] per [dimension].`
- `Count rows by [dimension] and [dimension].`

Good examples:

- `Count tickets by channel.`
- `How many rows per team?`
- `Give me total tickets per channel and priority.`

## 6. Grouped Metric Table

Family: `grouped_metric_table`  
Governance: `governed`  
Result shape: `table`

Use this when you want an aggregate metric by one or more groups.

Prompt templates:

- `Give me total [measure] by [dimension].`
- `Show average [measure] by [dimension].`
- `Show sum of [measure] per [dimension].`
- `Show [measure] by [dimension] as table.`
- `Give me total [measure] by [dimension] and [dimension].`
- `Show average [measure] by [dimension], [dimension], and [dimension].`

Good examples:

- `Give me total revenue by region.`
- `Show average resolution_hours by team.`
- `Show csat_score by channel as table.`

## 7. Distinct Value Listing

Family: `distinct_value_listing`  
Governance: `governed`  
Result shape: `table`

Prompt templates:

- `List all [dimension] values.`
- `What are the distinct values of [dimension]?`
- `Show the different [dimension] values.`
- `What are the available [dimension] categories?`
- `Give me all [dimension] types.`

Good examples:

- `List all channel values.`
- `What are the distinct values of priority?`

## 8. Distinct Value Count

Family: `distinct_value_count`  
Governance: `governed`  
Result shape: `count`

Prompt templates:

- `How many unique [dimension] values are there?`
- `How many distinct [dimension] values are there?`
- `How many different [dimension] types are there?`
- `Count unique [dimension].`
- `Count total unique [dimension] values in dataset.`

Good examples:

- `How many unique team values are there?`
- `How many different channel types are there?`

## 9. Representation Ranking

Family: `representation_ranking`  
Governance: `governed`  
Result shape: `table`

Use this when you want the most or least represented category by row count.

Prompt templates:

- `Which [dimension] has the most rows?`
- `Which [dimension] has the fewest rows?`
- `What is the most represented [dimension]?`
- `What is the least represented [dimension]?`
- `Show the top [n] [dimension]s by count.`
- `Show the bottom [n] [dimension]s by count.`

Good examples:

- `Which channel has the most tickets?`
- `What is the least represented team?`

## 10. Group Ranking

Family: `group_ranking`  
Governance: `governed`  
Result shape: `table`

Use this when you want the top or bottom groups by an aggregated metric.

Prompt templates:

- `Which [dimension] has the highest total [measure]?`
- `Which [dimension] has the lowest average [measure]?`
- `Show top [n] [dimension]s by total [measure].`
- `Show bottom [n] [dimension]s by average [measure].`
- `Rank [dimension] by total [measure].`

Good examples:

- `Which region has the highest total revenue?`
- `Show top 5 teams by average resolution_hours.`

## 11. Row Ranking

Family: `row_ranking`  
Governance: `governed`  
Result shape: `table`

Use this when you want the top or bottom rows by a numeric field.

Prompt templates:

- `Show top [n] rows by [measure].`
- `Show bottom [n] rows by [measure].`
- `Which row has the highest [measure]?`
- `Which record has the lowest [measure]?`
- `Rank rows by [measure].`

Good examples:

- `Show top 10 rows by revenue.`
- `Which record has the highest resolution_hours?`

## 12. Column Inventory

Family: `column_inventory`  
Governance: `governed`  
Result shape: `table`

Prompt templates:

- `What are the columns in the dataset?`
- `List the fields in the dataset.`
- `Show all columns.`
- `What are the columns or fields in the dataset?`

## 13. Column Count

Family: `column_count`  
Governance: `governed`  
Result shape: `count`

Prompt templates:

- `How many columns are in the dataset?`
- `How many fields does the dataset have?`
- `Count total columns in dataset.`
- `What is the column count?`

## 14. Column Type Inventory

Family: `column_type_inventory`  
Governance: `governed`  
Result shape: `table`

Prompt templates:

- `What are the data types of each field?`
- `Show the data types of all columns.`
- `What is the schema of the dataset?`
- `List the type of every column.`

## 15. Column Type Lookup

Family: `column_type_lookup`  
Governance: `governed`  
Result shape: `scalar`

Prompt templates:

- `What is the data type of [field]?`
- `What type is [field]?`
- `What is the dtype of [field]?`

## 16. Numeric Column Inventory

Family: `numeric_column_inventory`  
Governance: `governed`  
Result shape: `table`

Prompt templates:

- `Which columns are numeric?`
- `List numeric fields.`
- `Show numerical columns.`

## 17. Numeric Column Count

Family: `numeric_column_count`  
Governance: `governed`  
Result shape: `count`

Prompt templates:

- `How many numeric columns are there?`
- `Count total numeric fields in dataset.`
- `What is the number of numerical columns?`

## 18. Categorical Column Inventory

Family: `categorical_column_inventory`  
Governance: `governed`  
Result shape: `table`

Prompt templates:

- `Which columns are categorical?`
- `List categorical fields.`
- `Show string columns.`
- `Which fields are text fields?`

## 19. Categorical Column Count

Family: `categorical_column_count`  
Governance: `governed`  
Result shape: `count`

Prompt templates:

- `How many categorical columns are there?`
- `Count total categorical fields in dataset.`
- `How many string columns are there?`

## 20. Measure Inventory

Family: `measure_inventory`  
Governance: `governed`  
Result shape: `table`

Prompt templates:

- `Which columns are measures?`
- `List measure columns.`
- `Show metric fields.`

## 21. Measure Count

Family: `measure_count`  
Governance: `governed`  
Result shape: `count`

Prompt templates:

- `How many measure columns are there?`
- `Count total measures in dataset.`
- `How many metric fields are there?`

## 22. Dimension Inventory

Family: `dimension_inventory`  
Governance: `governed`  
Result shape: `table`

Prompt templates:

- `Which columns are dimensions?`
- `List dimension fields.`
- `Show grouping columns.`

## 23. Dimension Count

Family: `dimension_count`  
Governance: `governed`  
Result shape: `count`

Prompt templates:

- `How many dimensions are there?`
- `Count total dimension columns in dataset.`
- `How many grouping fields are there?`

## 24. Time Column Inventory

Family: `time_column_inventory`  
Governance: `governed`  
Result shape: `table`

Prompt templates:

- `Which columns are time fields?`
- `Which columns are date fields?`
- `List datetime columns.`

## 25. Time Column Count

Family: `time_column_count`  
Governance: `governed`  
Result shape: `count`

Prompt templates:

- `How many time columns are there?`
- `Count total date fields in dataset.`
- `How many datetime columns are there?`

## 26. Identifier Inventory

Family: `identifier_inventory`  
Governance: `governed`  
Result shape: `table`

Prompt templates:

- `Which columns are likely identifiers?`
- `Show identifier fields.`
- `List primary key candidates.`

## 27. Identifier Count

Family: `identifier_count`  
Governance: `governed`  
Result shape: `count`

Prompt templates:

- `How many identifier columns are there?`
- `Count total identifier fields in dataset.`
- `How many primary key candidates are there?`

## 28. Missing Value Inventory

Family: `missing_value_inventory`  
Governance: `governed`  
Result shape: `table`

Prompt templates:

- `Which columns have missing values?`
- `Show fields with null values.`
- `List nullable columns.`

## 29. High-Cardinality Inventory

Family: `high_cardinality_inventory`  
Governance: `governed`  
Result shape: `table`

Prompt templates:

- `Which columns have high cardinality?`
- `Show fields with many unique values.`
- `List high-cardinality columns.`

## 30. High-Cardinality Count

Family: `high_cardinality_count`  
Governance: `governed`  
Result shape: `count`

Prompt templates:

- `How many high-cardinality columns are there?`
- `Count total fields with many unique values.`
- `How many columns have high cardinality?`

## 31. Column Presence Check

Family: `column_presence_check`  
Governance: `governed`  
Result shape: `verification`

Prompt templates:

- `Does the dataset have a [field] column?`
- `Is there a [field] field?`
- `Does [field] exist as a column?`

## 32. Column Property Check

Family: `column_property_check`  
Governance: `governed`  
Result shape: `verification`

### Numeric

- `Is [field] numeric?`
- `Is [field] a number field?`

### Datetime

- `Is [field] a datetime field?`
- `Is [field] a time column?`

### Categorical

- `Is [field] categorical?`
- `Is [field] a string field?`

### Identifier

- `Is [field] an identifier?`
- `Is [field] likely an identifier?`

### Dimension

- `Is [field] a dimension?`
- `Is [field] a grouping field?`

### Measure

- `Is [field] a measure?`
- `Is [field] a metric column?`

### High cardinality

- `Is [field] high cardinality?`
- `Does [field] have many unique values?`

## 33. Null Verification

Family: `null_verification`  
Governance: `governed`  
Result shape: `verification`

Prompt templates:

- `Does [field] have missing values?`
- `Is [field] complete?`
- `Does [field] contain nulls?`
- `Are there null values in [field]?`

## 34. Threshold Verification

Family: `threshold_verification`  
Governance: `governed`  
Result shape: `verification`

Prompt templates:

- `Are any [measure] above [threshold]?`
- `Are any [measure] below [threshold]?`
- `Does [measure] fall between [value] and [value]?`
- `Is [measure] at least [threshold]?`
- `Is [measure] at most [threshold]?`

## 35. Row Existence Check

Family: `row_existence_check`  
Governance: `governed`  
Result shape: `verification`

Prompt templates:

- `Are there any rows where [dimension] is [value]?`
- `Does the dataset contain records where [dimension] is [value]?`
- `Are there any reopened tickets?`
- `Are there rows for [year]?`

## 36. Time Value Verification

Family: `time_value_verification`  
Governance: `governed`  
Result shape: `verification`

Prompt templates:

- `Are there records in [year]?`
- `Does the dataset contain rows for [month] [year]?`
- `Are there rows in Q[quarter]?`
- `Is there data for [year]?`

## 37. Time Coverage

Family: `time_coverage`  
Governance: `governed`  
Result shape: `table`

Prompt templates:

- `What is the date range of the dataset?`
- `What years are present in the data?`
- `What months are present in the data?`
- `What is the earliest and latest date?`

## 38. Time Bucket Counts

Family: `time_bucket_counts`  
Governance: `partial`  
Result shape: `table`

Prompt templates:

- `How many rows by year?`
- `How many records per month?`
- `How many tickets by quarter?`
- `Count rows by month.`
- `How many entries each year?`

## 39. Time Bucket Breakdown

Family: `time_bucket_breakdown`  
Governance: `governed`  
Result shape: `table`

Prompt templates:

- `Show [measure] by month.`
- `Show total [measure] by quarter.`
- `Show average [measure] by year.`
- `Break down [measure] by month.`

Good examples:

- `Show revenue by month.`
- `Show total resolution_hours by quarter.`

## 40. Time Period Comparison

Family: `time_period_comparison`  
Governance: `governed`  
Result shape: `table`

Prompt templates:

- `Compare [measure] this month to last month.`
- `Compare [measure] this quarter to last quarter.`
- `Compare [measure] this year to last year.`
- `How does [measure] compare this month versus last month?`
- `Compare [measure] by [dimension] this quarter to last quarter.`

Good examples:

- `Compare revenue this quarter to last quarter.`
- `Compare revenue by region this year to last year.`

## 41. Significance Inference

Family: `significance_inference`  
Governance: `governed`  
Result shape: `table`

Use this for natural-language group difference questions where SAIDA should infer a significance workflow.

Prompt templates:

- `Do [dimension] groups differ in [measure]?`
- `Is there a significant difference in [measure] by [dimension]?`
- `Does [measure] differ across [dimension]?`

## 42. T-Test

Family: `t_test`  
Governance: `governed`  
Result shape: `table`

Prompt templates:

- `Run a t-test for [measure] by [dimension].`
- `T test [measure] across [dimension].`
- `Perform a t-test on [measure] by [dimension].`

## 43. ANOVA

Family: `anova`  
Governance: `governed`  
Result shape: `table`

Prompt templates:

- `Run ANOVA for [measure] by [dimension].`
- `Perform an ANOVA on [measure] across [dimension].`
- `ANOVA [measure] by [dimension].`

## 44. Mann-Whitney

Family: `mann_whitney`  
Governance: `governed`  
Result shape: `table`

Prompt templates:

- `Run a Mann-Whitney test for [measure] by [dimension].`
- `Perform a Mann-Whitney test on [measure] across [dimension].`
- `Mann Whitney [measure] by [dimension].`

## 45. Chi-Square

Family: `chi_square`  
Governance: `governed`  
Result shape: `table`

Use this for association between two categorical fields.

Prompt templates:

- `Run a chi-square test for [dimension] and [dimension].`
- `Is there an association between [dimension] and [dimension]?`
- `Chi square [dimension] by [dimension].`

## 46. Confidence Interval

Family: `confidence_interval`  
Governance: `governed`  
Result shape: `table`

Prompt templates:

- `Show the confidence interval for [measure].`
- `What is the confidence range for [measure]?`
- `Give me confidence bounds for [measure].`

## 47. Power Analysis

Family: `power_analysis`  
Governance: `governed`  
Result shape: `table`

Prompt templates:

- `Do we have enough data to detect a difference in [measure] by [dimension]?`
- `Is there enough statistical power for [measure] by [dimension]?`
- `Run power analysis for [measure] by [dimension].`

## 48. Sample Size Estimate

Family: `sample_size_estimate`  
Governance: `governed`  
Result shape: `table`

Prompt templates:

- `How many rows per group do we need for [measure] by [dimension]?`
- `What sample size do we need for [measure] by [dimension]?`
- `Estimate required sample size for [measure] by [dimension].`

## 49. Regression Significance

Family: `regression_significance`  
Governance: `governed`  
Result shape: `table`

Prompt templates:

- `Does [measure] significantly affect [measure]?`
- `Which predictors significantly affect [measure]?`
- `Run regression significance for [measure] using [measure], [measure], and [measure].`

## 50. Prompt Variations By Workflow

These are not separate prompt families, but they are important variations that SAIDA supports well.

### Count-style phrasing

- `How many [entity] are there?`
- `Count [entity].`
- `Count total [entity].`
- `What is the number of [entity]?`

### Sum-style phrasing

- `What is the total [measure]?`
- `Sum [measure].`
- `Give me total [measure].`

### Average-style phrasing

- `What is the average [measure]?`
- `What is the mean [measure]?`
- `Average [measure] by [dimension].`

### Sorting and pagination

- `Show first [n] rows sorted by [field].`
- `Show page [n] page size [n] sorted by [field].`
- `Return latest [n] records.`

### Time filter variations

- `Show rows for [month] [year].`
- `Show rows in Q[quarter].`
- `Show rows in [year].`
- `Show rows on Mondays.`
- `Show rows on weekdays.`
- `Show rows on the first day of every month.`
- `Show rows on the last day of every month.`
- `Show rows from the last 7 days.`
- `Show rows on the first Monday of every month.`
- `Show rows on the last Friday of every month.`

## 51. Recommended Prompt Patterns

If you want the most reliable results, these patterns work well:

### Scalar metric

- `[aggregation] + [measure]`
- Example: `What is the average revenue?`

### Count by group

- `count + [entity] + by + [dimension]`
- Example: `Count tickets by channel.`

### Metric by group

- `[aggregation] + [measure] + by + [dimension]`
- Example: `Show total revenue by region.`

### Tabular rows

- `show/list/return + rows/records + filters/sort/columns`
- Example: `Show ticket_id and priority rows sorted by created_at.`

### Verification

- `does/is/are + [field or condition]`
- Example: `Does csat_score have missing values?`

### Statistical

- explicit test name or strong test language
- Example: `Run ANOVA for revenue by region.`

## 52. Quick Testing Set

If you want a fast way to sanity-check a dataset, try prompts in this order:

- `What are the columns in the dataset?`
- `What are the data types of each field?`
- `How many rows are in the dataset?`
- `How many columns are in the dataset?`
- `Which columns are numeric?`
- `Which columns are dimensions?`
- `How many unique [dimension] values are there?`
- `Count [entity] by [dimension].`
- `Show [measure] by [dimension].`
- `Show [field] and [field] rows sorted by [time_field].`
- `What is the date range of the dataset?`
- `How many rows by month?`

## 53. Final Advice

The strongest prompt shape in SAIDA is usually:

- **what operation do you want**
- **on what field or entity**
- **grouped by what**
- **filtered by what**

Examples:

- `Count tickets by channel.`
- `Show average resolution_hours by team.`
- `List all rows for January 2025.`
- `Does created_at exist as a column?`
- `How many unique team values are there?`

If you follow that pattern, you’ll usually land in the cleanest prompt family and get the most stable result.
