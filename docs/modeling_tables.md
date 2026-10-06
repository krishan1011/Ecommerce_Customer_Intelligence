# Phase 5 modeling tables

Extracted from Neon on 2026-10-06 for the inclusive `params.yaml` purchase
window 2017-01-01 through 2018-08-31 and configured valid status `delivered`.
`orders_enriched` retains all order statuses in that purchase window; the other
order-level modeling tables use configured valid orders. Parquet files use
Snappy compression and are ignored by Git.

| Parquet table | Source view | Grain | Rows | Key-column null rates |
|---|---|---|---:|---|
| `orders_enriched.parquet` | `analytics.model_orders_enriched` | One order item | 112,279 | `customer_unique_id` 0%; `product_id` 0%; `seller_id` 0%; `category_en` 1.43%; `purchase_ts` 0%; `delivered_customer_ts` 2.14%; `payment_type_main` 0% |
| `customer_orders.parquet` | `analytics.model_customer_orders` | One configured delivered order per `customer_unique_id` | 96,211 | `customer_unique_id` 0%; `review_score` 0.67%; `is_late` 0.01%; `review_ts` 0.67% |
| `interactions.parquet` | `analytics.model_interactions` | One customer/product/order purchase | 99,915 | `customer_unique_id` 0%; `product_id` 0%; `category_en` 1.40%; `purchase_ts` 0% |
| `products_enriched.parquet` | `analytics.model_products_enriched` | One product | 32,951 | `category_en` 1.85%; `price_mean` 2.64%; `first_sale_ts` 2.64%; `review_avg` 10.66%; `share_low_score` 10.66% |
| `reviews_clean.parquet` | `analytics.model_reviews_clean` | One `(review_id, order_id)` | 96,095 | `customer_unique_id` 0%; `review_text` 57.74%; `creation_ts` 0%; `primary_product_id` 4.70%; `category_en` 4.70%; `delivered_customer_ts` 0.01% |

## Columns by table

- **orders_enriched:** `order_id`, `order_item_id`, `customer_unique_id`,
  `customer_state`, `product_id`, `seller_id`, `seller_state`, `category_en`,
  `price`, `freight_value`, `order_status`, `purchase_ts`, `approved_ts`,
  `delivered_carrier_ts`, `delivered_customer_ts`, `estimated_delivery_ts`,
  `shipping_limit_ts`, `is_delivered`, `is_late`, `delivery_days`,
  `estimated_days`, `item_count_in_order`, `payment_type_main`,
  `max_installments`.
- **customer_orders:** `customer_unique_id`, `order_id`, `purchase_ts`,
  `order_value`, `item_revenue`, `freight`, `n_items`, `n_categories`, `state`,
  `is_late`, `review_score`, `review_ts`.
- **interactions:** `customer_unique_id`, `product_id`, `category_en`, `order_id`,
  `purchase_ts`, `price`, `quantity`.
- **products_enriched:** `product_id`, `category_en`, `price_mean`, `price_min`,
  `price_max`, `name_length`, `description_length`, `photos_qty`, `weight_g`,
  `volume_cm3`, `n_orders`, `units_sold`, `first_sale_ts`, `last_sale_ts`,
  `review_count`, `review_avg`, `share_low_score`.
- **reviews_clean:** `review_id`, `order_id`, `customer_unique_id`,
  `review_score`, `title`, `message`, `review_text`, `has_text`, `creation_ts`,
  `answer_ts`, `order_purchase_ts`, `delivered_customer_ts`, `is_late`,
  `n_products`, `n_sellers`, `primary_product_id`, `category_en`,
  `single_product_order`.

## Dtype and attribution decisions

Low-cardinality text fields are pandas categorical columns; identifier and review
text fields remain strings. Counts are downcast to the smallest integer type
that fits, continuous non-currency measures use float32 when appropriate, and
prices/revenue retain float64 precision. Source timestamps remain
`datetime64[ns]` columns.

`price` and `item_revenue` are merchandise only; freight remains a separate
column. `order_value` includes both. Main payment type is the payment method
with the largest summed payment value for that order, with payment type as a
deterministic tie-breaker.

Product sentiment is assigned only when an order contains exactly one distinct
product and exactly one non-null category. `model_products_enriched` review
aggregates use only those `single_product_order` reviews. All rows remain in
`reviews_clean` for order-level analysis. Review title/message text stays in
Portuguese, including original accents and negation; `review_text` only trims
and joins the two source fields.
