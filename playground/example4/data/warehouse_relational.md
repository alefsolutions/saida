# Dataset: Relational Warehouse

## Source Summary
Multi-table warehouse sales schema used to demonstrate source-aware relational materialization.

## Table Descriptions
customers: customer master data with geography.
products: product catalog with category and list price.
orders: order headers with customer linkage and sales totals.
order_items: order line items linking orders to products.

## Metric Definitions
total_sales: total order value from the order header.
line_total: total value for one order line.
quantity: units sold on one order line.

## Field Descriptions
customer_id: unique customer identifier.
country: customer country.
region: customer region.
product_name: product display name.
product_category: product category label.
order_date: order creation date.
sales_channel: selling channel for the order.

## Business Rules
- `orders.customer_id` joins to `customers.customer_id`.
- `order_items.order_id` joins to `orders.order_id`.
- `order_items.product_id` joins to `products.product_id`.
- `total_sales` is already aggregated at the order level.
