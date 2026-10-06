# Phase 5 findings

The tables cover purchases in the inclusive configured window 2017-01-01 to
2018-08-31. `orders_enriched` keeps all statuses; the other order-derived
modeling views use the configured delivered status.

| Table | Rows |
|---|---:|
| `orders_enriched` | 112,279 |
| `customer_orders` | 96,211 |
| `interactions` | 99,915 |
| `products_enriched` | 32,951 |
| `reviews_clean` | 96,095 |

- **2+ delivered orders:** 2,789 of 93,104 distinct customers (3.00%).
- **Reviews with text:** 40,607 of 96,095 (42.26%).
- **Single-product-order reviews:** 91,583 of 96,095 (95.30%).
- Merchandise in `customer_orders` sums to BRL 13,181,027.13, matching the
  configured-window `analytics.valid_orders` total; freight is stored separately.

## Data-quality notes

- 610 products (1.85%) have no category. The category stays null rather than
  assigning an invented value.
- 870 products (2.64%) had no delivered-window sale, so their sales price and
  sale-time summaries are null and their order/unit counts are zero.
- 55,488 reviews (57.74%) have no review text. Their score and order fields are
  still available for order-level analysis.
- 4,512 reviews (4.70%) are not attributed to a product because their order
  contains multiple products or does not resolve to exactly one category.
- 8 delivered orders lack a usable delivery-date pair, so `is_late` is null for
  those records rather than treating missing dates as on-time.

Extraction generated data version `b93765692a88`. The file-level row counts,
column dtypes, query hashes, parquet hashes, timestamps and configuration are in
`data/processed/manifest.json`; extracted files are intentionally untracked.
