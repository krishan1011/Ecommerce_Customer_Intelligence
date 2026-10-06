-- Phase 5 modeling views. Dates and included statuses are controlled by
-- analytics.config, which is refreshed from params.yaml by src.db views.

-- Grain: one order item in the configured purchase window, including every
-- order status. Item and payment facts are pre-aggregated to prevent fan-out.
-- Main payment type is the method with the greatest paid value; ties sort by name.
CREATE OR REPLACE VIEW analytics.model_orders_enriched AS
WITH item_counts AS (
    SELECT order_id, COUNT(*)::INTEGER AS item_count_in_order
    FROM core.order_items
    GROUP BY order_id
), payment_by_method AS (
    SELECT order_id, payment_type, SUM(payment_value) AS method_value
    FROM core.payments
    GROUP BY order_id, payment_type
), ranked_payment AS (
    SELECT order_id, payment_type,
        ROW_NUMBER() OVER (
            PARTITION BY order_id ORDER BY method_value DESC NULLS LAST, payment_type
        ) AS method_rank
    FROM payment_by_method
), payment_summary AS (
    SELECT order_id, MAX(installments)::INTEGER AS max_installments
    FROM core.payments
    GROUP BY order_id
)
SELECT
    o.order_id,
    oi.order_item_id,
    c.customer_unique_id,
    c.state AS customer_state,
    oi.product_id,
    oi.seller_id,
    s.state AS seller_state,
    p.category_en,
    oi.price,
    oi.freight_value,
    o.order_status,
    o.purchase_ts,
    o.approved_ts,
    o.delivered_carrier_ts,
    o.delivered_customer_ts,
    o.estimated_delivery_ts,
    oi.shipping_limit_ts,
    (o.order_status = ANY(cfg.valid_statuses)) AS is_delivered,
    CASE
        WHEN NOT (o.order_status = ANY(cfg.valid_statuses)) THEN NULL
        WHEN o.delivered_customer_ts IS NULL OR o.estimated_delivery_ts IS NULL THEN NULL
        ELSE o.delivered_customer_ts > o.estimated_delivery_ts
    END AS is_late,
    EXTRACT(EPOCH FROM (o.delivered_customer_ts - o.purchase_ts)) / 86400.0 AS delivery_days,
    EXTRACT(EPOCH FROM (o.estimated_delivery_ts - o.purchase_ts)) / 86400.0 AS estimated_days,
    ic.item_count_in_order,
    rp.payment_type AS payment_type_main,
    ps.max_installments
FROM core.orders AS o
JOIN core.customers AS c ON c.customer_id = o.customer_id
JOIN core.order_items AS oi ON oi.order_id = o.order_id
LEFT JOIN core.products AS p ON p.product_id = oi.product_id
LEFT JOIN core.sellers AS s ON s.seller_id = oi.seller_id
JOIN item_counts AS ic ON ic.order_id = o.order_id
LEFT JOIN ranked_payment AS rp ON rp.order_id = o.order_id AND rp.method_rank = 1
LEFT JOIN payment_summary AS ps ON ps.order_id = o.order_id
CROSS JOIN analytics.config AS cfg
WHERE o.purchase_ts >= cfg.analysis_start::TIMESTAMP
  AND o.purchase_ts < (cfg.analysis_end + 1)::TIMESTAMP;

COMMENT ON VIEW analytics.model_orders_enriched IS
    'Grain: one order item in the configured window and all statuses; payment facts are pre-aggregated; is_delivered uses analytics.config.valid_statuses.';

-- Grain: one configured delivered order per customer_unique_id. Assumptions:
-- order value includes freight; item revenue is merchandise only; one latest
-- review is attached per order using creation time, answer time and review ID.
CREATE OR REPLACE VIEW analytics.model_customer_orders AS
WITH category_counts AS (
    SELECT oi.order_id, COUNT(DISTINCT p.category_en)::INTEGER AS n_categories
    FROM core.order_items AS oi
    LEFT JOIN core.products AS p ON p.product_id = oi.product_id
    GROUP BY oi.order_id
), latest_review AS (
    SELECT r.order_id, r.review_score, r.creation_ts AS review_ts,
        ROW_NUMBER() OVER (
            PARTITION BY r.order_id
            ORDER BY r.creation_ts DESC NULLS LAST, r.answer_ts DESC NULLS LAST, r.review_id DESC
        ) AS review_rank
    FROM core.reviews AS r
)
SELECT
    vo.customer_unique_id,
    vo.order_id,
    vo.purchase_ts,
    (vo.item_revenue + vo.freight)::NUMERIC(14, 2) AS order_value,
    vo.item_revenue,
    vo.freight,
    vo.item_count AS n_items,
    COALESCE(cc.n_categories, 0) AS n_categories,
    vo.state,
    dp.late_flag AS is_late,
    lr.review_score,
    lr.review_ts
FROM analytics.valid_orders AS vo
LEFT JOIN category_counts AS cc ON cc.order_id = vo.order_id
LEFT JOIN analytics.delivery_performance AS dp ON dp.order_id = vo.order_id
LEFT JOIN latest_review AS lr ON lr.order_id = vo.order_id AND lr.review_rank = 1;

COMMENT ON VIEW analytics.model_customer_orders IS
    'Grain: one configured valid (delivered) order per customer_unique_id; order-level facts avoid item and review fan-out.';

-- Grain: one customer_unique_id, product_id and order_id purchase. Assumptions:
-- price is the sum paid for that product within the order; quantity counts lines.
CREATE OR REPLACE VIEW analytics.model_interactions AS
SELECT
    vo.customer_unique_id,
    oi.product_id,
    p.category_en,
    vo.order_id,
    vo.purchase_ts,
    SUM(oi.price)::NUMERIC(14, 2) AS price,
    COUNT(*)::INTEGER AS quantity
FROM analytics.valid_orders AS vo
JOIN core.order_items AS oi ON oi.order_id = vo.order_id
LEFT JOIN core.products AS p ON p.product_id = oi.product_id
GROUP BY vo.customer_unique_id, oi.product_id, p.category_en, vo.order_id, vo.purchase_ts;

COMMENT ON VIEW analytics.model_interactions IS
    'Grain: one customer_unique_id/product/order purchase among configured valid orders; quantity counts item lines.';

-- Grain: one review_id and order_id. Portuguese source text is preserved;
-- product sentiment is attributed only for orders with exactly one distinct
-- product and one non-null category. All reviews remain available for order analysis.
CREATE OR REPLACE VIEW analytics.model_reviews_clean AS
WITH order_shape AS (
    SELECT
        oi.order_id,
        COUNT(DISTINCT oi.product_id)::INTEGER AS n_products,
        COUNT(DISTINCT p.category_en)::INTEGER AS n_categories,
        COUNT(DISTINCT oi.seller_id)::INTEGER AS n_sellers,
        ARRAY_AGG(DISTINCT oi.product_id) FILTER (WHERE oi.product_id IS NOT NULL) AS product_ids,
        ARRAY_AGG(DISTINCT p.category_en) FILTER (WHERE p.category_en IS NOT NULL) AS categories
    FROM core.order_items AS oi
    LEFT JOIN core.products AS p ON p.product_id = oi.product_id
    GROUP BY oi.order_id
), review_rows AS (
    SELECT
        r.review_id,
        r.order_id,
        c.customer_unique_id,
        r.review_score,
        r.title,
        r.message,
        NULLIF(
            BTRIM(CONCAT_WS(' ', NULLIF(BTRIM(r.title), ''), NULLIF(BTRIM(r.message), ''))),
            ''
        ) AS review_text,
        r.creation_ts,
        r.answer_ts,
        vo.purchase_ts AS order_purchase_ts,
        vo.delivered_customer_ts,
        CASE
            WHEN vo.delivered_customer_ts IS NULL OR vo.estimated_delivery_ts IS NULL THEN NULL
            ELSE vo.delivered_customer_ts > vo.estimated_delivery_ts
        END AS is_late,
        COALESCE(os.n_products, 0) AS n_products,
        COALESCE(os.n_sellers, 0) AS n_sellers,
        COALESCE(os.n_categories, 0) AS n_categories,
        os.product_ids,
        os.categories
    FROM core.reviews AS r
    JOIN analytics.valid_orders AS vo ON vo.order_id = r.order_id
    JOIN core.orders AS o ON o.order_id = r.order_id
    JOIN core.customers AS c ON c.customer_id = o.customer_id
    LEFT JOIN order_shape AS os ON os.order_id = r.order_id
)
SELECT
    rr.review_id,
    rr.order_id,
    rr.customer_unique_id,
    rr.review_score,
    rr.title,
    rr.message,
    rr.review_text,
    (rr.review_text IS NOT NULL) AS has_text,
    rr.creation_ts,
    rr.answer_ts,
    rr.order_purchase_ts,
    rr.delivered_customer_ts,
    rr.is_late,
    rr.n_products,
    rr.n_sellers,
    CASE WHEN rr.n_products = 1 AND rr.n_categories = 1 THEN rr.product_ids[1] END
        AS primary_product_id,
    CASE WHEN rr.n_products = 1 AND rr.n_categories = 1 THEN rr.categories[1] END
        AS category_en,
    (rr.n_products = 1 AND rr.n_categories = 1) AS single_product_order
FROM review_rows AS rr;

COMMENT ON VIEW analytics.model_reviews_clean IS
    'Grain: one review_id/order_id for configured valid orders; product-level sentiment uses only single_product_order reviews, while order-level analysis can use all rows; text remains Portuguese.';

-- Grain: one product. Assumptions: sales and product review summaries use
-- configured delivered-window orders; reviews are attributed only under the
-- single_product_order rule from model_reviews_clean.
CREATE OR REPLACE VIEW analytics.model_products_enriched AS
WITH sales AS (
    SELECT
        oi.product_id,
        AVG(oi.price)::NUMERIC(14, 4) AS price_mean,
        MIN(oi.price)::NUMERIC(14, 2) AS price_min,
        MAX(oi.price)::NUMERIC(14, 2) AS price_max,
        COUNT(DISTINCT vo.order_id)::BIGINT AS n_orders,
        COUNT(*)::BIGINT AS units_sold,
        MIN(vo.purchase_ts) AS first_sale_ts,
        MAX(vo.purchase_ts) AS last_sale_ts
    FROM analytics.valid_orders AS vo
    JOIN core.order_items AS oi ON oi.order_id = vo.order_id
    GROUP BY oi.product_id
), product_reviews AS (
    SELECT
        mr.primary_product_id AS product_id,
        COUNT(*)::BIGINT AS review_count,
        AVG(mr.review_score)::NUMERIC(5, 2) AS review_avg,
        (COUNT(*) FILTER (WHERE mr.review_score IN (1, 2))::NUMERIC
            / NULLIF(COUNT(*), 0))::NUMERIC(12, 6) AS share_low_score
    FROM analytics.model_reviews_clean AS mr
    WHERE mr.single_product_order
    GROUP BY mr.primary_product_id
)
SELECT
    p.product_id,
    p.category_en,
    s.price_mean,
    s.price_min,
    s.price_max,
    p.name_length,
    p.description_length,
    p.photos_qty,
    p.weight_g,
    (p.length_cm * p.height_cm * p.width_cm)::NUMERIC(14, 2) AS volume_cm3,
    COALESCE(s.n_orders, 0)::BIGINT AS n_orders,
    COALESCE(s.units_sold, 0)::BIGINT AS units_sold,
    s.first_sale_ts,
    s.last_sale_ts,
    COALESCE(pr.review_count, 0)::BIGINT AS review_count,
    pr.review_avg,
    pr.share_low_score
FROM core.products AS p
LEFT JOIN sales AS s ON s.product_id = p.product_id
LEFT JOIN product_reviews AS pr ON pr.product_id = p.product_id;

COMMENT ON VIEW analytics.model_products_enriched IS
    'Grain: one product; sales use configured valid orders and product sentiment includes only single_product_order reviews.';
