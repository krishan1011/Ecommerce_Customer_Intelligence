# Phase 4 SQL performance

Measured on the Neon PostgreSQL database on 2026-10-06 with
`EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`. The three chosen paths cover product
ranking, customer spend filtering and category/month review aggregation.

| Query path | Before index review (ms) | After review (ms) | Planned rows |
|---|---:|---:|---:|
| Top products from `product_performance` | 1,314.193 | 1,142.472 | 10 |
| Customers above average spend | 1,324.441 | 1,335.222 | 31,158 |
| Top review trends | 507.313 | 562.012 | 100 |

No indexes were added: the review showed inconsistent timing changes across
repeat runs, and the existing schema already indexes order purchase time,
customer identity, product category, item product/seller keys and review order
keys. These hosted-database timings are a baseline rather than a stable latency
promise; the second measurement made no schema or index changes.
