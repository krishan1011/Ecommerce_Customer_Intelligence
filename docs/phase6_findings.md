# Phase 6 findings: cleaning and EDA

## Data-quality summary

The configured purchase window is 2017-01-01 through 2018-08-31, inclusive.
The cleaning pipeline reads the five Phase 5 parquet tables and validates each
output against the clean-table Pandera schemas.

| Table | Rows before | Rows after | Null rate before | Null rate after | Exact duplicate rows after |
|---|---:|---:|---:|---:|---:|
| Orders (item grain) | 112,279 | 112,279 | 0.371% | 0.371% | 0 |
| Customers (customer-order grain) | 96,211 | 96,211 | 0.122% | 0.122% | 0 |
| Interactions | 99,915 | 99,915 | 0.200% | 0.200% | 0 |
| Products | 32,951 | 32,951 | 2.098% | 1.819% | 0 |
| Reviews | 96,095 | 95,568 | 11.944% | 11.936% | 0 |

Null rates compare columns present in both versions. The product catalog is
enriched from the raw product file before missingness is assessed. Product
dimension missingness flags were added before category-median/global-median
imputation; missing original weight and length/height/width values each affected
2 products, while name length, description length and photo count each affected
610 products. Volume was recomputed from dimensions.

Review deduplication keeps the latest creation timestamp per order, removing
527 rows for order-level analysis. It does not alter the Phase 5 source table.
No negative item prices were found or dropped. Quality flags were retained:

| Flag | Item rows |
|---|---:|
| Price less than or equal to zero | 0 |
| Freight greater than item price | 4,116 |
| Customer delivery before purchase | 0 |
| Approval before purchase | 0 |
| Estimated delivery before purchase | 0 |
| Delivered order missing customer delivery timestamp | 8 |

## Numbered insights

1. November 2017 was the largest month at **7,451 delivered orders**, 46.2%
   above the average of October and December (5,096).
2. **2,789 of 93,104 customers (3.00%)** placed at least two delivered orders
   in the configured window.
3. Customer merchandise spend has a **Gini coefficient of 0.520**; median
   merchandise spend was **BRL 89.70**, excluding freight.
4. São Paulo and Rio de Janeiro account for **52,716 delivered orders**
   combined.
5. Median purchase-to-delivery time was **10.21 days**. The recorded late rate
   was **8.13%** among orders with lateness labels.
6. Inter-state orders were late **9.29%** of the time, compared with **6.07%**
   for same-state orders.
7. Median estimated delivery duration was **23.22 days**, compared with **10.21
   actual days**.
8. Five-star reviews made up **59.22%** of order-level reviews. Median score
   was **2 for late deliveries and 5 for on-time deliveries**.
9. Review text was missing for about **57.7%** of deduplicated reviews.
   Among reviews with text, text length and score had Spearman rho **-0.334**.
10. The top ten product categories represented **64.6%** of observed units.
    Product photo count had near-zero association with units sold (Spearman
    rho **0.018**).
11. Credit card was the main payment type on **75.4%** of delivered orders.
12. The daily series covers about **20 months**: enough to examine weekly
    patterns, but not annual seasonality.

## Statistical tests

| Comparison | Test statistic | p-value | Effect size | n |
|---|---:|---:|---:|---:|
| Late vs on-time review score | Mann-Whitney U = 150,207,354.5 | <1e-300 | Rank-biserial = -0.554 | 95,560 |
| Repeat vs one-time first-order item revenue | Mann-Whitney U = 121,299,780.5 | 0.000893 | Rank-biserial = -0.0369 | 93,104 |
| First category vs repeat purchase | Chi-square = 395.19 | 4.22e-52 | Cramér's V = 0.0656 | 91,789 |
| First-order lateness vs repeat purchase | Fisher exact | 0.0114 | Odds ratio = 0.827 | 93,096 |
| Delivery delay vs review score | Spearman rho = -0.1767 | <1e-300 | rho = -0.1767 | 95,560 |

P-values below 1e-300 underflowed to zero in floating-point output. The large
sample makes small effects statistically detectable; for example, the
repeat-versus-one-time revenue effect is small despite its p-value.

## Decisions list for Phases 7 and 8

- **Features:** customer recency, frequency, and merchandise-only monetary
  value; category/product popularity; missing-dimension flags; actual versus
  estimated delivery gap; lateness and review features; weekly calendar lags.
- **Drop or isolate:** raw customer/order/product identifiers are keys, not
  predictors. Keep review bodies out of tabular models unless a separate NLP
  feature is built. Exclude post-outcome delivery and review data from
  pre-purchase prediction.
- **Transform:** use log1p for skewed spend, price, and counts. Preserve
  uncapped source values for reports. The clean parquet cap columns are
  exploratory 1st/99th percentile previews; recompute imputation and capping
  parameters inside each chronological training fold before modeling.
- **Encode:** learn category mappings on training data only, group rare
  categories, and keep an unknown-category bucket for later periods.
- **Snapshots and horizon:** repeat purchasing is 3.00%; use explicit
  observation snapshots and label horizons, and report class prevalence and
  precision-recall metrics.
- **Forecasting:** the 20-month history supports weekly patterns but cannot
  estimate annual seasonality.
- **Risks:** one-time buyers dominate; review scores and text are noisy and
  text is frequently absent; post-purchase fields can leak future information.
  Large samples can make small associations look statistically decisive.
