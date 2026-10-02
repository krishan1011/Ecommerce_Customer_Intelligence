# Phase 1 Findings: Olist Dataset Understanding

## 1. Analysis Window & Rationale
- **Raw Timestamp Range**: `2016-09-04 21:15:19` to `2018-10-17 17:30:18`
- **Confirmed Stable Analysis Window**: `2017-01-01` to `2018-08-31` (20 consecutive months)
- **Rationale**: 
  - **Late 2016 Ramp-up**: September 2016 (4 orders), October 2016 (324 orders), and December 2016 (1 order) were early marketplace onboarding and pilot operations.
  - **September - October 2018 Drop-off**: September 2018 recorded only 16 orders and October 2018 recorded 4 orders, representing truncation in the Olist public dump rather than normal business operations.
  - **Recommendation**: Restrict analytical snapshots, ML features, and time-series forecasting to `2017-01-01` through `2018-08-31` to prevent ramp-up and cut-off boundary artifacts.

## 2. Order Status Breakdown & Valid Status Definition
Across the 99,441 orders in the raw dataset:
- `delivered`: 96,478 (97.02%)
- `shipped`: 1,107 (1.11%)
- `canceled`: 625 (0.63%)
- `unavailable`: 609 (0.61%)
- `invoiced`: 314 (0.32%)
- `processing`: 301 (0.30%)
- `created`: 5 (0.01%)
- `approved`: 2 (0.00%)

- **Valid Statuses for Revenue & Analytics**: `["delivered"]`
  - Per project design rules, completed revenue is strictly `SUM(order_items.price)` on `delivered` orders, excluding freight unless explicitly noted.
  - Non-delivered orders (canceled, unavailable, etc.) should not count towards fulfilled customer lifetime value or repeat purchase targets.

## 3. Customer Identity & Repeat Purchase Dynamics
- **Key distinction**: `customer_id` is an order-session token (99,441 unique values, exactly 1 per order). `customer_unique_id` represents the actual individual human customer (96,096 unique values across all 99,441 orders).
- **Repeat Buyers**:
  - Across all orders: 2,997 customers out of 96,096 made > 1 purchase (**3.12% repeat rate**).
  - Delivered orders only: 2,801 customers out of 93,358 made > 1 delivered purchase (**3.00% repeat rate**).
- **Modeling Implications**:
  - ~97% of customers in Olist are single-event purchasers ("one-and-done").
  - Churn prediction cannot use standard contractual churn definitions; it must be framed as **repeat purchase propensity within horizon $H$ days after snapshot $T$**.
  - Accuracy is an inappropriate evaluation metric (a naive majority-class model achieves 97% accuracy). Models must be evaluated on **PR-AUC, Lift@10%, and calibration**. Any metric $> 0.95$ indicates data leakage.

## 4. Review Text Coverage & Rating Distribution
- **Total Reviews**: 99,224
- **Review Titles**: 11,568 (11.66% coverage)
- **Review Message Body**: 40,977 (41.30% coverage)
- **Either Title or Message**: 42,706 (43.04% coverage)
- **Review Scores**:
  - 1 star: 11,424 (11.51%)
  - 2 stars: 3,151 (3.18%)
  - 3 stars: 8,179 (8.24%)
  - 4 stars: 19,142 (19.29%)
  - 5 stars: 57,328 (57.78%)
- **NLP Implications**:
  - More than 56% of reviews have no text (only numeric star ratings).
  - Sentiment analysis and Portuguese NLP pipelines must handle null text gracefully and preserve Portuguese accents, contractions, and negation markers (`não`, `nunca`, `jamais`).

## 5. Delivery Performance & Logistics State Mix
- **Delivered Orders with Dates**: 96,470 orders with both `order_delivered_customer_date` and `order_estimated_delivery_date`.
- **Late Deliveries**: 7,826 orders delivered past estimated date (**8.11% late delivery rate**).
- **Fulfillment State Mix**:
  - Total items analyzed: 112,650
  - Same-state fulfillment (Customer state == Seller state): 40,756 items (**36.18%**)
  - Inter-state cross-country fulfillment: 71,894 items (**63.82%**)
- **Delivery Delay Model Implications**:
  - Brazil's continental geography means inter-state shipments dominate (nearly 64%), contributing significantly to transit variance.
  - Delay prediction features must strictly use pre-purchase / pre-shipment information: seller historical expanding delivery performance, distance/state crossing, item physical dimensions (weight, volume), and freight value. Never use post-purchase delivery events.
