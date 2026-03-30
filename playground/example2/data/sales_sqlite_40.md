# Sales SQLite 40 Context

## Dataset Overview

This dataset is a small SQLite-backed sales example for testing SAIDA source loading and plan execution.

- Table name: `sales_orders`
- Row count: `40`
- Column count: `10`
- Grain: one row per order

## Identifier

- Preferred identifier: `order_id`

## Trusted Date Fields

- `order_date`

## Dimensions

- `country`
- `region`
- `sales_channel`
- `product_category`

## Measures

- `quantity`
- `unit_price`
- `discount_amount`
- `total_sales`

## Business Rules

- `total_sales` is the net sales amount after subtracting `discount_amount` from `quantity * unit_price`.
- `order_date` should be treated as the main time field for filtering, grouping, and trend analysis.
- `quantity` is the number of units sold on the order.

## Suggested Prompt Patterns

- `How many rows are in the dataset?`
- `What are the columns in the dataset?`
- `Show total total_sales by country.`
- `Show total total_sales by product_category.`
- `What is the average total_sales by sales_channel?`
- `List all rows for January 2026.`
