# Phase 4 findings

**Scope:** Olist delivered orders purchased from 2017-01-01 through 2018-08-31,
inclusive, from `params.yaml`. `customer_unique_id` is the person-level key.
Merchandise revenue is `SUM(order_items.price)`; freight is separate.

| Metric | Result |
|---|---:|
| Valid delivered orders | 96,211 |
| Delivered customers | 93,104 |
| Merchandise revenue | BRL 13,181,027.13 |
| Freight, reported separately | BRL 2,192,092.88 |
| Merchandise AOV | BRL 137.00 |
| Repeat purchase rate | 3.00% (2,789 customers) |
| Late rate among orders with both delivery dates | 8.13% (96,203 dated orders) |
| Top category | Health and beauty: BRL 1,229,557.50 (9.33% share; 9,422 units) |
| Average review, late orders | 2.57 |
| Average review, on-time orders | 4.30 |
| Review difference, late minus on-time | -1.73 points |

November 2017 was the strongest month: BRL 987,765.37 in merchandise revenue
from 7,289 orders and 7,183 customers. The average time from first to second
purchase among repeat customers was 80.22 days. Delivery was 11.11 days earlier
than the estimate on average, even though 8.13% of orders with both dates were
late; those two statistics use signed delay and a late/not-late threshold,
respectively.

The Phase 3 anchors (96,478 delivered orders, 93,358 delivered customers, BRL
13,221,498.11 merchandise revenue and BRL 2,198,275.64 freight) cover the full
dataset. Their difference from these Phase 4 figures is the configured analysis
window, which excludes purchases after August 31, 2018.
