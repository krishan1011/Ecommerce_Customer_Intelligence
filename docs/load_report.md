# Phase 3 load sanity report

SQL and pandas metrics: **MATCH**.

## Core row counts

| Core table | Rows |
|---|---:|
| `category_translation` | 71 |
| `customers` | 99,441 |
| `sellers` | 3,095 |
| `products` | 32,951 |
| `geolocation` | 19,015 |
| `orders` | 99,441 |
| `order_items` | 112,650 |
| `payments` | 103,886 |
| `reviews` | 99,224 |
| `dim_customer_unique` | 96,096 |
| `load_reconciliation` | 119 |

## SQL and independent pandas metrics

| Metric | PostgreSQL | pandas from CSVs |
|---|---:|---:|
| Delivered orders | 96,478 | 96,478 |
| Distinct customer_unique_id, all orders | 96,096 | 96,096 |
| Distinct customer_unique_id, delivered orders | 93,358 | 93,358 |
| Delivered merchandise revenue (BRL) | 13,221,498.11 | 13,221,498.11 |
| Delivered freight (BRL, separate) | 2,198,275.64 | 2,198,275.64 |

Revenue is `SUM(order_items.price)` for delivered orders; freight is excluded.

## Phase 1 anchors

- customers: 99,441 (matches Phase 1 anchor).
- orders: 99,441 (matches Phase 1 anchor).
- order_items: 112,650 (matches Phase 1 anchor).
- payments: 103,886 (matches Phase 1 anchor).
- products: 32,951 (matches Phase 1 anchor).
- sellers: 3,095 (matches Phase 1 anchor).
- translations: 71 (matches Phase 1 anchor).
- delivered_orders: 96,478 (matches Phase 1 anchor).
- unique_customers_all_orders: 96,096 (matches Phase 1 anchor).
- unique_customers_delivered: 93,358 (matches Phase 1 anchor).
- raw_reviews: 99,224 (matches Phase 1 anchor).

## Latest reconciliation

| Run UTC | Table | CSV | Raw | Core | Dropped | Note |
|---|---|---:|---:|---:|---:|---|
| 2026-10-06T14:49:42.532126+00:00 | core.dim_customer_unique |  |  | 96,096 | 0 | One row per customer_unique_id; dates span all order statuses; location from most recent order. |
| 2026-10-06T14:49:42.532126+00:00 | orphan.order_items.orders |  |  |  | 0 | Orphan rows dropped before inserting core rows. |
| 2026-10-06T14:49:42.532126+00:00 | orphan.order_items.products |  |  |  | 0 | 0 orphan product references remapped to core.products.unknown. |
| 2026-10-06T14:49:42.532126+00:00 | orphan.order_items.sellers |  |  |  | 0 | Orphan rows dropped before inserting core rows. |
| 2026-10-06T14:49:42.532126+00:00 | orphan.orders.customer |  |  |  | 0 | Orphan rows dropped before inserting core rows. |
| 2026-10-06T14:49:42.532126+00:00 | orphan.payments.orders |  |  |  | 0 | Orphan rows dropped before inserting core rows. |
| 2026-10-06T14:49:42.532126+00:00 | orphan.reviews.orders |  |  |  | 0 | Orphan rows dropped before inserting core rows. |
| 2026-10-06T14:49:42.532126+00:00 | raw.olist_customers | 99,441 | 99,441 | 99,441 | 0 | Customer grain is customer_id; persistent identity is customer_unique_id. |
| 2026-10-06T14:49:42.532126+00:00 | raw.olist_geolocation | 1,000,163 | 1,000,163 | 19,015 | 981,148 | Aggregated samples by zip prefix; mean coordinates and normalized city/state modes. |
| 2026-10-06T14:49:42.532126+00:00 | raw.olist_order_items | 112,650 | 112,650 | 112,650 | 0 | Dropped 0 invalid-order and 0 invalid-seller rows; remapped 0 missing product references to unknown. |
| 2026-10-06T14:49:42.532126+00:00 | raw.olist_order_payments | 103,886 | 103,886 | 103,886 | 0 | Dropped 0 rows without a valid order; preserved not_defined=3 and installments=0=2. |
| 2026-10-06T14:49:42.532126+00:00 | raw.olist_order_reviews | 99,224 | 99,224 | 99,224 | 0 | Dropped 0 duplicate review rows and 0 orphan-order rows; kept latest review_answer_timestamp. |
| 2026-10-06T14:49:42.532126+00:00 | raw.olist_orders | 99,441 | 99,441 | 99,441 | 0 | Dropped 0 rows without a valid customer/order key. |
| 2026-10-06T14:49:42.532126+00:00 | raw.olist_products | 32,951 | 32,951 | 32,951 | 0 | Applied Portuguese fallback for 2 untranslated product categories; preserved 610 products without a category. |
| 2026-10-06T14:49:42.532126+00:00 | raw.olist_sellers | 3,095 | 3,095 | 3,095 | 0 | Typed source seller rows. |
| 2026-10-06T14:49:42.532126+00:00 | raw.product_category_name_translation | 71 | 71 | 71 | 0 | Typed source translations. |
| 2026-10-06T14:49:42.532126+00:00 | reviews.deduplication |  |  |  | 0 | Duplicate (review_id, order_id) rows removed; latest answer timestamp retained. |
