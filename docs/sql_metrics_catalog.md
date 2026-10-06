# Phase 4 SQL metrics catalog

All results below were queried from Neon on 2026-10-06 using the inclusive
`params.yaml` window 2017-01-01 through 2018-08-31 and status `delivered`.
Revenue means merchandise value and excludes freight unless the query names
payment value explicitly.

| # | Business question | Grain | Primary view(s) | Finding from the loaded data |
|---:|---|---|---|---|
| 01 | Monthly revenue, order/customer counts and MoM growth | Month | `monthly_kpis` | November 2017 led the window with BRL 987,765.37, 7,289 orders and 7,183 customers. |
| 02 | Overall merchandise AOV | One summary row | `valid_orders` | Average merchandise value was BRL 137.00 per order. |
| 03 | Monthly merchandise AOV | Month | `monthly_kpis` | January 2017 had the highest monthly AOV at BRL 149.06. |
| 04 | Merchandise AOV by state | State | `valid_orders` | Paraíba had the highest state AOV at BRL 218.09 across 516 orders. |
| 05 | Merchandise AOV by payment type | Payment type | `valid_orders`, `core.payments` | Credit card had the highest attributed AOV at BRL 140.55; mixed-method order revenue is divided across its distinct methods. |
| 06 | Repeat purchase rate | One summary row | `customer_summary` | 2,789 of 93,104 customers placed multiple orders: 3.00%. |
| 07 | Average time from first to second order | Repeat customer | `customer_orders` | The 2,789 repeat purchasers averaged 80.22 days between their first two orders. |
| 08 | Top ten products by revenue and units | Product | `product_performance` | The top product (health and beauty) generated BRL 63,560.00 from 194 units. |
| 09 | Top ten categories by revenue and units | Category | `category_performance` | Health and beauty led with BRL 1,229,557.50 and 9,422 units (9.33% of merchandise revenue). |
| 10 | Revenue by customer spend quartile | Spend quartile | `customer_summary` | The highest spend quartile contributed BRL 8,241,251.01, about 62.5% of merchandise revenue. |
| 11 | Customer purchase frequency (1, 2, 3, 4+) | Frequency bucket | `customer_summary` | 90,315 customers ordered once; 47 customers placed at least four orders. |
| 12 | Category review and one-star trends | Category and month | `review_trends` | Bed and bath table had the most reviews in one category-month: 807 in November 2017, mean rating 3.69 and one-star share 18.34%. |
| 13 | Delivery lateness by state | State | `delivery_performance` | Among states with at least 100 dated orders, Alagoas had the highest late rate at 24.0%. |
| 14 | Review score for late versus on-time orders | Late flag | `delivery_performance` | Late orders averaged 2.57 versus 4.30 for on-time orders, a 1.73-point difference. |
| 15 | Payment mix and average installments | Payment type | `core.payments`, `valid_orders` | Credit card value was BRL 12,063,100.59 with 3.50 average installments; boleto value was BRL 2,762,300.80. |
| 16 | Credit card versus boleto paid value | Payment type | `core.payments`, `valid_orders` | Credit card paid value was about 4.4 times boleto value in the window. |
| 17 | Seller revenue, orders, rating and late rate | Seller | `seller_performance` | The leading seller generated BRL 226,987.93 across 1,124 orders, with a 4.15 rating and 11.57% late rate. |
| 18 | Cohort retention in months 1 through 12 | Cohort month and age month | `cohort_retention` | Of 718 January 2017 cohort customers, 2 returned in month 1 (0.28%). |
| 19 | Customers above average spend | Customer | `customer_summary` | 26,633 customers spent above the window-wide mean customer spend. |
| 20 | Running total merchandise revenue | Month | `monthly_kpis` | The running total reached BRL 13,181,027.13 by August 2018. |
| 21 | Product rank within category | Product and category | `product_performance` | The BRL 63,560 health and beauty leader ranked first within its category. |
| 22 | Order heatmap by weekday and hour | Weekday and hour | `valid_orders` | Tuesday at 14:00 was the busiest cell with 1,091 orders. |
| 23 | AOV by state and month | State and month | `valid_orders` | Mato Grosso in February 2017 had the highest state-month AOV at BRL 683.62, across 11 orders. |
| 24 | Delivery and review outcomes by state and month | State and delivery month | `delivery_performance` | Across the window, delivery averaged 11.11 days earlier than estimate; 8.13% of dated orders were late. |
| 25 | Categories above average category revenue | Category | `category_performance` | 20 of 74 categories exceeded the mean category revenue. |

Payment-type merchandise AOV allocates each order's merchandise revenue evenly
across the distinct payment methods used for that order. Payment-value queries
sum the original payment transactions and should not be added to merchandise
revenue.
