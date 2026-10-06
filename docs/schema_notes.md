# Database schema notes

## Layers and invariants

- `raw` is the text-only landing layer. Its nine tables mirror the CSV headers, and loading never
  transforms or modifies those source values.
- `core` contains typed, constrained relational entities and keeps all source rows. Customer
  identity is `customer_unique_id`; `customer_id` identifies an order-specific customer record.
- `analytics` is reserved for read-only views, to be added in Phase 4. Apply the 2017-01 through
  2018-08 analysis window in those views; do not filter rows out of `core`.
- Merchandise revenue is `SUM(order_items.price)` for delivered orders. `freight_value` is excluded.

## Core tables

| Table | Grain | Primary key | Foreign keys | Design decisions |
|---|---|---|---|---|
| `category_translation` | One row per Portuguese category name | `category_pt` | None | English translation is required when a translation row exists. |
| `customers` | One row per order-specific customer ID | `customer_id` | None | `customer_unique_id` preserves person-level identity across orders; indexed. |
| `sellers` | One row per seller merchant account | `seller_id` | None | Seller postal prefix and location remain nullable source attributes. |
| `products` | One row per catalog product SKU | `product_id` | None | Category columns are not FKs because two source categories are untranslated. Nullable product measurements and lengths have non-negative checks that allow NULL. |
| `geolocation` | One row per postal-code prefix | `zip_prefix` | None | Coordinates represent aggregated median locations; source samples are not unique by prefix. |
| `orders` | One row per order | `order_id` | `customer_id` → `customers.customer_id` | Purchase timestamp is required; status is limited to the eight observed lifecycle values. |
| `order_items` | One row per item line within an order | (`order_id`, `order_item_id`) | `order_id` → `orders.order_id`; `product_id` → `products.product_id`; `seller_id` → `sellers.seller_id` | Price and freight are non-negative `NUMERIC(12,2)` values; freight defaults to zero. Price alone contributes merchandise revenue. |
| `payments` | One row per payment sequence within an order | (`order_id`, `payment_sequential`) | `order_id` → `orders.order_id` | Installments allow zero; payment type includes `not_defined`. |
| `reviews` | One review record for an order | (`review_id`, `order_id`) | `order_id` → `orders.order_id` | Composite key accommodates duplicate review IDs across orders; score is constrained to 1–5. |
| `dim_customer_unique` | One row per persistent individual customer | `customer_unique_id` | None | Person-level dimension; populated after order facts in the Phase 3 load sequence. |

## Phase 3 load order

Load core tables in dependency order:

1. `category_translation`
2. `customers`
3. `sellers`
4. `products`
5. `geolocation`
6. `orders`
7. `order_items`
8. `payments`
9. `reviews`
10. `dim_customer_unique`
