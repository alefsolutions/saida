![SAIDA Banner](../../assets/github-banner.png)

# Dataset: Sales Data 800 Rows

## Source Summary
Order-level sales records across regions, countries, channels, customer segments, product categories, and sales reps covering 2024 through 2025.

## Metric Definitions
quantity = number of units sold on the order line
unit_price = selling price per unit before discounts, tax, and shipping
gross_sales = quantity multiplied by unit_price before discounts
discount_pct = discount rate stored as a decimal fraction, for example 0.10 means 10 percent
discount_amount = currency value removed from gross_sales due to the applied discount
tax_rate = tax rate stored as a decimal fraction
tax_amount = currency value added as tax for the order
shipping_fee = shipping charge added to the order
total_sales = final customer-facing order total after discount plus tax and shipping

## Business Rules
- order_id is the preferred unique order identifier
- order_date is the trusted transaction date for calendar analysis
- ship_date is the shipping event date and can occur after order_date
- quarter, month, weekday, and year are calendar attributes aligned to order_date
- total_sales = gross_sales - discount_amount + tax_amount + shipping_fee
- order_status describes the operational state of the order, including completed, pending, cancelled, and returned

## Caveats
- quantity is numeric and can be analyzed as a measure, but some prompts may also use it in a count-like business sense
- ship_date can extend beyond the order_date range because shipment may happen after the order is placed
- total_sales can be greater than gross_sales when tax and shipping outweigh discounts
- discount_pct and tax_rate are decimal rates, not whole-number percentages

## Trusted Date Fields
- order_date
- ship_date

## Preferred Identifiers
- order_id
