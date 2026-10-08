# Phase 8 feature design

## Framing and label

This is a repeat-purchase propensity dataset. At snapshot `T`, the population is customers identified by `customer_unique_id` with at least one delivered order whose `purchase_ts < T`. `label_repeat` is 1 when that customer has another delivered order with purchase time in `[T, T + H)`. A later model's churn probability is `1 - p(repeat)`.

About 97.0% of the dataset's customers have only one delivered order in the observed window. The business question is therefore whether an already observed customer returns, rather than whether an anonymous session converts.

Revenue is the sum of `order_items.price` for eligible orders. Freight is kept in separate fields and never added to monetary revenue. Customer identity is always `customer_unique_id`.

The source records only final order statuses, not status-change timestamps. Selecting orders whose final status is delivered therefore uses limited status knowledge that may not have been available exactly at `T`. It is accepted because the requested target is a later delivered purchase and Olist does not provide a status event history. Purchase time controls whether an order is in the feature history or label window; delivery and review fields have the stricter observation-time rules below.

## Horizon selection and purged chronological splits

Counts were computed from the delivered-order table. The customer counts below are customer-snapshot rows (train has two snapshots); positive rates are positives divided by those rows. Alternative layouts were selected to keep every label horizon observable and avoid overlap. Candidate horizons are ordered from smallest to largest; 300 positives is required in both validation and test.

| H (days) | Snapshot layout: train / val / test | Train rows | Train positives / rate | Val rows | Val positives / rate | Test rows | Test positives / rate |
|---:|---|---:|---:|---:|---:|---:|---:|
| 90 | 2017-05-31, 2017-08-31 / 2017-12-31 / 2018-04-30 | 31,705 | 289 / 0.91% | 42,066 | 303 / 0.72% | 68,397 | 427 / 0.62% |
| 120 | 2017-05-31, 2017-08-31 / 2017-12-31 / 2018-04-30 | 31,705 | 362 / 1.14% | 42,066 | 380 / 0.90% | 68,397 | 535 / 0.78% |
| 150 | 2017-03-31, 2017-05-31 / 2017-10-31 / 2018-04-01 | 15,221 | 206 / 1.35% | 29,586 | 392 / 1.32% | 62,042 | 600 / 0.97% |
| 180 | 2017-01-31, 2017-02-28 / 2017-08-31 / 2018-02-28 | 2,950 | 45 / 1.53% | 21,264 | 351 / 1.65% | 54,972 | 644 / 1.17% |

The selected configuration uses the smallest qualifying horizon, **H=90 days**: validation has 303 positive labels and test has 427. The configured snapshots are train `[2017-05-31, 2017-08-31]`, validation `[2017-12-31]`, and test `[2018-04-30]`.

The build enforces `max(T_train) + H <= min(T_val)`, `max(T_val) + H <= min(T_test)`, and `max(T_test) + H <= analysis_end + 1 day`. With H=90, the latest train label ends before December 31, the validation label window ends before April 30, and the test horizon ends before the configured September 1 exclusive boundary. Customer identities may recur across chronological snapshots; that is expected. Training labels are fully resolved before validation snapshots, and validation labels before test snapshots.

## As-of-T feature rules

- Purchase history contains final-delivered orders with `purchase_ts < T`. The final-status limitation is documented above.
- Delivery duration, lateness, and estimate error are calculated only where `delivered_customer_ts < T`. If delivery occurs at or after T, those fields remain missing.
- Review features use only reviews with `creation_ts < T`. A review created at or after T is ignored even when its order predates T.
- Recency and tenure are measured relative to T.
- Customer features use raw item prices, freight, timestamps, categories, payment fields, and geography. Full-window Phase 6 imputed or winsorized values, including imputed dimensions and `*_capped` columns, are excluded.
- Missing product dimensions remain NaN and receive missingness flags. Imputation, scaling, and encoding must be learned inside sklearn Pipelines on training folds only.

## Phase 9 evaluation slice

Report the normal test metrics and a second **new customers only** slice: customers in the test snapshot whose `customer_unique_id` does not occur in any training snapshot. These customers still have a delivered order before the test snapshot; “new” means new to the training snapshots. On this build, new customers are 47,133 rows with 320 positives (0.68%); seen customers are 21,264 rows with 107 positives (0.50%). The manifest records these cohort sizes so later evaluation can use the same definition.
