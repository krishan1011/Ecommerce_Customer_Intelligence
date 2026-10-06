-- Phase 4 clean analytics views. The reporting window is controlled only by
-- analytics.config, populated from params.yaml by `python -m src.db views`.

-- Grain: one row per order. Assumptions: item_revenue is merchandise only;
-- freight is separate; item_count counts order lines.
CREATE OR REPLACE VIEW analytics.order_revenue AS
SELECT
    oi.order_id,
    SUM(oi.price)::NUMERIC(14, 2) AS item_revenue,
    SUM(oi.freight_value)::NUMERIC(14, 2) AS freight,
    COUNT(*)::INTEGER AS item_count
FROM core.order_items AS oi
GROUP BY oi.order_id;

COMMENT ON VIEW analytics.order_revenue IS
    'Grain: one row per order; sole merchandise revenue definition is SUM(core.order_items.price); freight is separate.';

-- Grain: one row per order. Assumptions: payment types counts distinct methods;
-- max_installments ignores null values.
CREATE OR REPLACE VIEW analytics.order_payments_agg AS
SELECT
    p.order_id,
    SUM(p.payment_value)::NUMERIC(14, 2) AS total_paid,
    COUNT(DISTINCT p.payment_type)::INTEGER AS payment_types_count,
    MAX(p.installments)::INTEGER AS max_installments,
    ARRAY_AGG(DISTINCT p.payment_type ORDER BY p.payment_type) AS payment_types
FROM core.payments AS p
GROUP BY p.order_id;

COMMENT ON VIEW analytics.order_payments_agg IS
    'Grain: one row per order; payments are aggregated before joining to order metrics.';

-- Grain: one row per valid order. Assumptions: start and end dates are inclusive;
-- valid statuses and dates come from the one-row analytics.config table.
CREATE OR REPLACE VIEW analytics.valid_orders AS
SELECT
    o.order_id,
    c.customer_unique_id,
    c.state,
    o.purchase_ts,
    o.order_status,
    o.delivered_customer_ts,
    o.estimated_delivery_ts,
    COALESCE(r.item_revenue, 0)::NUMERIC(14, 2) AS item_revenue,
    COALESCE(r.freight, 0)::NUMERIC(14, 2) AS freight,
    COALESCE(r.item_count, 0) AS item_count,
    COALESCE(p.total_paid, 0)::NUMERIC(14, 2) AS total_paid,
    COALESCE(p.payment_types_count, 0) AS payment_types_count,
    p.max_installments,
    p.payment_types
FROM core.orders AS o
JOIN core.customers AS c ON c.customer_id = o.customer_id
LEFT JOIN analytics.order_revenue AS r ON r.order_id = o.order_id
LEFT JOIN analytics.order_payments_agg AS p ON p.order_id = o.order_id
CROSS JOIN analytics.config AS cfg
WHERE o.purchase_ts >= cfg.analysis_start::TIMESTAMP
  AND o.purchase_ts < (cfg.analysis_end + 1)::TIMESTAMP
  AND o.order_status = ANY(cfg.valid_statuses);

COMMENT ON VIEW analytics.valid_orders IS
    'Grain: one row per order in the configured inclusive date window and valid status list.';

-- Grain: one row per customer_unique_id and order_id. Assumptions: this is the
-- person-level RFM base; order_value includes merchandise and freight.
CREATE OR REPLACE VIEW analytics.customer_orders AS
SELECT
    vo.customer_unique_id,
    vo.order_id,
    vo.purchase_ts,
    vo.item_revenue,
    vo.freight,
    (vo.item_revenue + vo.freight)::NUMERIC(14, 2) AS order_value
FROM analytics.valid_orders AS vo;

COMMENT ON VIEW analytics.customer_orders IS
    'Grain: one row per (customer_unique_id, order_id); order_value includes merchandise plus freight.';

-- Grain: one row per order item. Assumptions: each line is allocated its
-- proportional share of the canonical order merchandise revenue.
CREATE OR REPLACE VIEW analytics.order_item_revenue AS
SELECT
    oi.order_id,
    oi.order_item_id,
    oi.product_id,
    oi.seller_id,
    oi.price AS item_price,
    oi.freight_value,
    CASE
        WHEN r.item_revenue = 0 THEN 0::NUMERIC
        ELSE (oi.price / r.item_revenue * r.item_revenue)::NUMERIC(14, 2)
    END AS item_revenue
FROM core.order_items AS oi
JOIN analytics.valid_orders AS vo ON vo.order_id = oi.order_id
JOIN analytics.order_revenue AS r ON r.order_id = oi.order_id;

COMMENT ON VIEW analytics.order_item_revenue IS
    'Grain: one row per in-window valid order item; item revenue allocates the canonical order merchandise revenue.';

-- Grain: one row per calendar month. Assumptions: customers are distinct people;
-- growth is relative to the previous observed month.
CREATE OR REPLACE VIEW analytics.monthly_kpis AS
WITH monthly AS (
    SELECT
        DATE_TRUNC('month', vo.purchase_ts)::DATE AS month,
        COUNT(DISTINCT vo.order_id)::BIGINT AS orders,
        COUNT(DISTINCT vo.customer_unique_id)::BIGINT AS customers,
        SUM(vo.item_revenue)::NUMERIC(16, 2) AS revenue,
        SUM(vo.item_revenue + vo.freight)::NUMERIC(16, 2) AS revenue_with_freight
    FROM analytics.valid_orders AS vo
    GROUP BY 1
)
SELECT
    month,
    orders,
    customers,
    revenue,
    revenue_with_freight,
    (revenue / NULLIF(orders, 0))::NUMERIC(14, 2) AS aov,
    LAG(revenue) OVER (ORDER BY month) AS prior_month_revenue,
    (revenue / NULLIF(LAG(revenue) OVER (ORDER BY month), 0) - 1)::NUMERIC(12, 4)
        AS revenue_mom_growth,
    LAG(orders) OVER (ORDER BY month) AS prior_month_orders,
    (orders::NUMERIC / NULLIF(LAG(orders) OVER (ORDER BY month), 0) - 1)::NUMERIC(12, 4)
        AS orders_mom_growth,
    LAG(customers) OVER (ORDER BY month) AS prior_month_customers,
    (customers::NUMERIC / NULLIF(LAG(customers) OVER (ORDER BY month), 0) - 1)::NUMERIC(12, 4)
        AS customers_mom_growth
FROM monthly;

COMMENT ON VIEW analytics.monthly_kpis IS
    'Grain: one row per calendar month; revenue excludes freight and AOV uses merchandise revenue.';

-- Grain: one row per customer_unique_id. Assumptions: customer value and AOV
-- use merchandise revenue; avg_review is the average review score for their orders.
CREATE OR REPLACE VIEW analytics.customer_summary AS
WITH reviews_by_order AS (
    SELECT r.order_id, AVG(r.review_score)::NUMERIC(5, 2) AS avg_review
    FROM core.reviews AS r
    GROUP BY r.order_id
), customer_base AS (
    SELECT
        co.customer_unique_id,
        COUNT(*)::BIGINT AS order_count,
        MIN(co.purchase_ts) AS first_order_ts,
        MAX(co.purchase_ts) AS last_order_ts,
        SUM(co.item_revenue)::NUMERIC(16, 2) AS total_revenue,
        SUM(co.freight)::NUMERIC(16, 2) AS total_freight,
        AVG(co.item_revenue)::NUMERIC(14, 2) AS avg_order_revenue,
        AVG(rbo.avg_review)::NUMERIC(5, 2) AS avg_review
    FROM analytics.customer_orders AS co
    LEFT JOIN reviews_by_order AS rbo ON rbo.order_id = co.order_id
    GROUP BY co.customer_unique_id
)
SELECT
    cb.customer_unique_id,
    d.state,
    cb.order_count,
    cb.first_order_ts,
    cb.last_order_ts,
    cb.total_revenue,
    cb.total_freight,
    cb.avg_order_revenue,
    cb.avg_review,
    (SELECT cfg.analysis_end FROM analytics.config AS cfg) - cb.last_order_ts::DATE
        AS recency_days
FROM customer_base AS cb
LEFT JOIN core.dim_customer_unique AS d USING (customer_unique_id);

COMMENT ON VIEW analytics.customer_summary IS
    'Grain: one row per customer_unique_id; RFM revenue and AOV exclude freight.';

-- Grain: one row per product_id. Assumptions: only configured valid orders;
-- item revenue reuses analytics.order_revenue through order_item_revenue.
CREATE OR REPLACE VIEW analytics.product_performance AS
SELECT
    p.product_id,
    p.category_en AS category,
    SUM(oir.item_revenue)::NUMERIC(16, 2) AS revenue,
    COUNT(*)::BIGINT AS units,
    COUNT(DISTINCT oir.order_id)::BIGINT AS orders,
    (SUM(oir.item_revenue) / NULLIF(SUM(SUM(oir.item_revenue)) OVER (), 0))::NUMERIC(12, 6)
        AS revenue_share,
    (SUM(SUM(oir.item_revenue)) OVER (
        ORDER BY SUM(oir.item_revenue) DESC, p.product_id
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) / NULLIF(SUM(SUM(oir.item_revenue)) OVER (), 0))::NUMERIC(12, 6)
        AS cumulative_revenue_share
FROM analytics.order_item_revenue AS oir
JOIN core.products AS p ON p.product_id = oir.product_id
GROUP BY p.product_id, p.category_en;

COMMENT ON VIEW analytics.product_performance IS
    'Grain: one row per product; configured-window merchandise revenue, units, share and Pareto cumulative share.';

-- Grain: one row per product category. Assumptions: uncategorized products are
-- retained as '(uncategorized)'; revenue excludes freight.
CREATE OR REPLACE VIEW analytics.category_performance AS
SELECT
    COALESCE(p.category_en, '(uncategorized)') AS category,
    SUM(oir.item_revenue)::NUMERIC(16, 2) AS revenue,
    COUNT(*)::BIGINT AS units,
    COUNT(DISTINCT oir.order_id)::BIGINT AS orders,
    (SUM(oir.item_revenue) / NULLIF(SUM(SUM(oir.item_revenue)) OVER (), 0))::NUMERIC(12, 6)
        AS revenue_share,
    (SUM(SUM(oir.item_revenue)) OVER (
        ORDER BY SUM(oir.item_revenue) DESC, COALESCE(p.category_en, '(uncategorized)')
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) / NULLIF(SUM(SUM(oir.item_revenue)) OVER (), 0))::NUMERIC(12, 6)
        AS cumulative_revenue_share
FROM analytics.order_item_revenue AS oir
JOIN core.products AS p ON p.product_id = oir.product_id
GROUP BY COALESCE(p.category_en, '(uncategorized)');

COMMENT ON VIEW analytics.category_performance IS
    'Grain: one row per category; configured-window merchandise revenue, units, share and Pareto cumulative share.';

-- Grain: one row per seller_id. Assumptions: ratings and lateness are averaged
-- per seller-order before seller-level aggregation to avoid item fan-out.
CREATE OR REPLACE VIEW analytics.seller_performance AS
WITH seller_order AS (
    SELECT
        oir.seller_id,
        oir.order_id,
        SUM(oir.item_revenue)::NUMERIC(14, 2) AS revenue
    FROM analytics.order_item_revenue AS oir
    GROUP BY oir.seller_id, oir.order_id
), order_review AS (
    SELECT r.order_id, AVG(r.review_score)::NUMERIC(5, 2) AS avg_review
    FROM core.reviews AS r
    GROUP BY r.order_id
), order_delivery AS (
    SELECT DISTINCT vo.order_id,
        CASE
            WHEN vo.delivered_customer_ts IS NULL OR vo.estimated_delivery_ts IS NULL THEN NULL
            WHEN vo.delivered_customer_ts > vo.estimated_delivery_ts THEN 1 ELSE 0
        END AS late_flag
    FROM analytics.valid_orders AS vo
)
SELECT
    so.seller_id,
    SUM(so.revenue)::NUMERIC(16, 2) AS revenue,
    COUNT(DISTINCT so.order_id)::BIGINT AS orders,
    AVG(orv.avg_review)::NUMERIC(5, 2) AS avg_rating,
    AVG(od.late_flag::NUMERIC)::NUMERIC(8, 4) AS late_rate
FROM seller_order AS so
LEFT JOIN order_review AS orv ON orv.order_id = so.order_id
LEFT JOIN order_delivery AS od ON od.order_id = so.order_id
GROUP BY so.seller_id;

COMMENT ON VIEW analytics.seller_performance IS
    'Grain: one row per seller; order-level review and delivery values prevent item-level fan-out.';

-- Grain: one row per delivered order. Assumptions: delay is actual minus
-- estimated customer delivery in days; late flag is null if either date is missing.
CREATE OR REPLACE VIEW analytics.delivery_performance AS
SELECT
    vo.order_id,
    vo.customer_unique_id,
    vo.state,
    vo.delivered_customer_ts,
    vo.estimated_delivery_ts,
    EXTRACT(EPOCH FROM (vo.delivered_customer_ts - vo.estimated_delivery_ts)) / 86400.0
        AS delivery_delta_days,
    CASE
        WHEN vo.delivered_customer_ts IS NULL OR vo.estimated_delivery_ts IS NULL THEN NULL
        WHEN vo.delivered_customer_ts > vo.estimated_delivery_ts THEN TRUE ELSE FALSE
    END AS late_flag,
    r.avg_review
FROM analytics.valid_orders AS vo
LEFT JOIN LATERAL (
    SELECT AVG(rv.review_score)::NUMERIC(5, 2) AS avg_review
    FROM core.reviews AS rv
    WHERE rv.order_id = vo.order_id
) AS r ON TRUE;

COMMENT ON VIEW analytics.delivery_performance IS
    'Grain: one row per configured valid order; late status is null when delivery dates are unavailable.';

-- Grain: one row per cohort month and age month. Assumptions: cohort membership
-- is the first configured-window purchase; month 0 is cohort size.
CREATE OR REPLACE VIEW analytics.cohort_retention AS
WITH customer_month AS (
    SELECT DISTINCT co.customer_unique_id,
        DATE_TRUNC('month', co.purchase_ts)::DATE AS order_month
    FROM analytics.customer_orders AS co
), cohorts AS (
    SELECT customer_unique_id, MIN(order_month) AS cohort_month
    FROM customer_month
    GROUP BY customer_unique_id
), cohort_activity AS (
    SELECT c.cohort_month, cm.order_month,
        ((EXTRACT(YEAR FROM cm.order_month) - EXTRACT(YEAR FROM c.cohort_month)) * 12
         + EXTRACT(MONTH FROM cm.order_month) - EXTRACT(MONTH FROM c.cohort_month))::INTEGER
            AS month_number,
        COUNT(DISTINCT cm.customer_unique_id)::BIGINT AS customers
    FROM cohorts AS c
    JOIN customer_month AS cm USING (customer_unique_id)
    GROUP BY c.cohort_month, cm.order_month
)
SELECT
    cohort_month,
    month_number,
    customers AS returning_customers,
    MAX(customers) FILTER (WHERE month_number = 0)
        OVER (PARTITION BY cohort_month) AS cohort_customers,
    (customers::NUMERIC / NULLIF(MAX(customers) FILTER (WHERE month_number = 0)
        OVER (PARTITION BY cohort_month), 0))::NUMERIC(12, 6) AS returning_percent
FROM cohort_activity;

COMMENT ON VIEW analytics.cohort_retention IS
    'Grain: one row per first-purchase cohort month and age month; retention is returning customers divided by cohort size.';

-- Grain: one row per product category and review month. Assumptions: reviews
-- follow the order purchase month and only configured valid orders are included.
CREATE OR REPLACE VIEW analytics.review_trends AS
WITH order_categories AS (
    SELECT DISTINCT oi.order_id, COALESCE(p.category_en, '(uncategorized)') AS category
    FROM core.order_items AS oi
    JOIN core.products AS p ON p.product_id = oi.product_id
)
SELECT
    oc.category,
    DATE_TRUNC('month', vo.purchase_ts)::DATE AS month,
    COUNT(*)::BIGINT AS reviews,
    AVG(r.review_score)::NUMERIC(5, 2) AS avg_rating,
    COUNT(*) FILTER (WHERE r.review_score = 1)::BIGINT AS one_star_reviews,
    (COUNT(*) FILTER (WHERE r.review_score = 1)::NUMERIC / NULLIF(COUNT(*), 0))
        ::NUMERIC(12, 6) AS one_star_share
FROM analytics.valid_orders AS vo
JOIN core.reviews AS r ON r.order_id = vo.order_id
JOIN order_categories AS oc ON oc.order_id = vo.order_id
GROUP BY oc.category, DATE_TRUNC('month', vo.purchase_ts)::DATE;

COMMENT ON VIEW analytics.review_trends IS
    'Grain: one row per category and purchase month; a multi-item order contributes once to each distinct item category.';
