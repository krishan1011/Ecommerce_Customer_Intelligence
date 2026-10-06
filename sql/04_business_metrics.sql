-- Phase 4 business questions. Revenue and dates are sourced from the analytics
-- views/config; the queries below are reusable templates for analysts.

-- Q01 Business question: What are monthly revenue, orders, unique customers and MoM growth?
-- Grain: calendar month. Assumptions: merchandise revenue excludes freight.
SELECT month, revenue, orders, customers, revenue_mom_growth,
       orders_mom_growth, customers_mom_growth
FROM analytics.monthly_kpis ORDER BY month;

-- Q02 Business question: What is overall merchandise AOV in the configured window?
-- Grain: one summary row. Assumptions: the order count is the denominator.
SELECT SUM(item_revenue) / NULLIF(COUNT(*), 0) AS aov
FROM analytics.valid_orders;

-- Q03 Business question: How does merchandise AOV vary by month?
-- Grain: calendar month. Assumptions: valid orders only.
SELECT month, revenue / NULLIF(orders, 0) AS aov
FROM analytics.monthly_kpis ORDER BY month;

-- Q04 Business question: Which states have the highest merchandise AOV?
-- Grain: customer state. Assumptions: customer state is the order destination proxy.
SELECT state, SUM(item_revenue) / NULLIF(COUNT(*), 0) AS aov, COUNT(*) AS orders
FROM analytics.valid_orders GROUP BY state ORDER BY aov DESC NULLS LAST;

-- Q05 Business question: What is merchandise AOV by payment type?
-- Grain: payment type and order. Assumptions: order merchandise is attributed evenly
-- across the distinct payment methods attached to that order to prevent fan-out.
WITH order_methods AS (
    SELECT p.order_id, p.payment_type
    FROM core.payments AS p
    JOIN analytics.valid_orders AS vo USING (order_id)
    GROUP BY p.order_id, p.payment_type
), allocated AS (
    SELECT om.payment_type,
        vo.item_revenue / NULLIF(COUNT(*) OVER (PARTITION BY om.order_id), 0) AS revenue_share
    FROM order_methods AS om
    JOIN analytics.valid_orders AS vo USING (order_id)
)
SELECT payment_type, SUM(revenue_share) / NULLIF(COUNT(*), 0) AS aov,
       SUM(revenue_share) AS attributed_revenue, COUNT(*) AS order_method_rows
FROM allocated GROUP BY payment_type ORDER BY attributed_revenue DESC;

-- Q06 Business question: What share of customers purchased more than once?
-- Grain: one summary row. Assumptions: customer identity is customer_unique_id.
SELECT COUNT(*) FILTER (WHERE order_count >= 2)::NUMERIC / NULLIF(COUNT(*), 0)
           AS repeat_purchase_rate,
       COUNT(*) FILTER (WHERE order_count >= 2) AS repeat_customers,
       COUNT(*) AS customers
FROM analytics.customer_summary;

-- Q07 Business question: How long do customers wait between their first and second order?
-- Grain: one summary row across repeat customers. Assumptions: timestamp difference in days.
WITH ranked AS (
    SELECT customer_unique_id, purchase_ts,
        ROW_NUMBER() OVER (PARTITION BY customer_unique_id ORDER BY purchase_ts, order_id) AS rn
    FROM analytics.customer_orders
), first_second AS (
    SELECT customer_unique_id,
        MAX(purchase_ts) FILTER (WHERE rn = 1) AS first_ts,
        MAX(purchase_ts) FILTER (WHERE rn = 2) AS second_ts
    FROM ranked WHERE rn <= 2 GROUP BY customer_unique_id HAVING COUNT(*) = 2
)
SELECT AVG(EXTRACT(EPOCH FROM (second_ts - first_ts)) / 86400.0) AS avg_days_first_to_second
FROM first_second;

-- Q08 Business question: Which ten products lead merchandise revenue and units?
-- Grain: product. Assumptions: ranking and shares use configured-window valid orders.
SELECT product_id, category, revenue, units, revenue_share, cumulative_revenue_share
FROM analytics.product_performance
ORDER BY revenue DESC, product_id LIMIT 10;

-- Q09 Business question: Which ten categories lead merchandise revenue and units?
-- Grain: category. Assumptions: uncategorized products remain visible.
SELECT category, revenue, units, revenue_share, cumulative_revenue_share
FROM analytics.category_performance ORDER BY revenue DESC LIMIT 10;

-- Q10 Business question: How is revenue distributed across customer spend segments?
-- Grain: spend segment. Assumptions: quartile cuts are ranked on merchandise spend.
WITH bucketed AS (
    SELECT customer_unique_id, total_revenue,
        NTILE(4) OVER (ORDER BY total_revenue) AS spend_quartile
    FROM analytics.customer_summary
), segmented AS (
    SELECT *, CASE
        WHEN spend_quartile = 1 THEN '1_low'
        WHEN spend_quartile = 2 THEN '2_mid_low'
        WHEN spend_quartile = 3 THEN '3_mid_high'
        ELSE '4_high' END AS spend_segment
    FROM bucketed
)
SELECT spend_segment, COUNT(*) AS customers, SUM(total_revenue) AS revenue,
       SUM(total_revenue) / NULLIF(SUM(SUM(total_revenue)) OVER (), 0) AS revenue_share
FROM segmented GROUP BY spend_segment ORDER BY spend_segment;

-- Q11 Business question: How many customers placed 1, 2, 3, or 4+ orders?
-- Grain: purchase-frequency bucket. Assumptions: counts are within the analysis window.
SELECT CASE WHEN order_count >= 4 THEN '4+' ELSE order_count::TEXT END AS frequency,
       COUNT(*) AS customers
FROM analytics.customer_summary
GROUP BY CASE WHEN order_count >= 4 THEN '4+' ELSE order_count::TEXT END
ORDER BY frequency;

-- Q12 Business question: How do category ratings and one-star shares trend by month?
-- Grain: category and month. Assumptions: review_trends assigns an order review to each item category.
SELECT category, month, reviews, avg_rating, one_star_reviews, one_star_share
FROM analytics.review_trends ORDER BY category, month;

-- Q13 Business question: What is delivery lateness and delay by state?
-- Grain: customer state. Assumptions: rows without both dates are excluded;
-- states need at least 100 dated orders for stable rate comparisons.
SELECT state, COUNT(*) FILTER (WHERE late_flag IS NOT NULL) AS dated_orders,
       AVG(late_flag::INT) FILTER (WHERE late_flag IS NOT NULL) AS late_rate,
       AVG(delivery_delta_days) AS avg_delay_days
FROM analytics.delivery_performance
GROUP BY state
HAVING COUNT(*) FILTER (WHERE late_flag IS NOT NULL) >= 100
ORDER BY late_rate DESC NULLS LAST;

-- Q14 Business question: Do late orders receive different average ratings?
-- Grain: late flag. Assumptions: only orders with delivery dates and reviews are included.
SELECT late_flag, COUNT(*) AS orders, AVG(avg_review) AS average_review_score
FROM analytics.delivery_performance
WHERE late_flag IS NOT NULL AND avg_review IS NOT NULL
GROUP BY late_flag ORDER BY late_flag;

-- Q15 Business question: What is the payment method mix and installment profile?
-- Grain: payment type. Assumptions: payment values are transaction amounts; each payment row counted once.
SELECT p.payment_type, COUNT(*) AS payment_rows,
       COUNT(DISTINCT p.order_id) AS orders,
       SUM(p.payment_value) AS payment_value,
       AVG(p.installments) AS average_installments
FROM core.payments AS p
JOIN analytics.valid_orders AS vo USING (order_id)
GROUP BY p.payment_type ORDER BY payment_value DESC;

-- Q16 Business question: How do credit card and boleto compare in paid value?
-- Grain: payment type, limited to credit card and boleto. Assumptions: source payment values.
SELECT p.payment_type, SUM(p.payment_value) AS payment_value,
       AVG(p.payment_value) AS average_payment_value,
       COUNT(DISTINCT p.order_id) AS orders
FROM core.payments AS p
JOIN analytics.valid_orders AS vo USING (order_id)
WHERE p.payment_type IN ('credit_card', 'boleto')
GROUP BY p.payment_type ORDER BY p.payment_type;

-- Q17 Business question: Which sellers have the strongest revenue and service outcomes?
-- Grain: seller. Assumptions: seller-level metrics are already protected from item fan-out.
SELECT seller_id, revenue, orders, avg_rating, late_rate
FROM analytics.seller_performance ORDER BY revenue DESC LIMIT 50;

-- Q18 Business question: What is monthly cohort retention in months 1 through 12?
-- Grain: cohort month and age month. Assumptions: month 0 is cohort size, excluded here.
SELECT cohort_month, month_number, returning_customers, cohort_customers, returning_percent
FROM analytics.cohort_retention
WHERE month_number BETWEEN 1 AND 12 ORDER BY cohort_month, month_number;

-- Q19 Business question: Which customers spend above the mean customer spend?
-- Grain: customer. Assumptions: mean is across customers in the configured window.
SELECT customer_unique_id, order_count, total_revenue, avg_order_revenue
FROM analytics.customer_summary
WHERE total_revenue > (SELECT AVG(total_revenue) FROM analytics.customer_summary)
ORDER BY total_revenue DESC;

-- Q20 Business question: What is the cumulative monthly merchandise revenue?
-- Grain: calendar month. Assumptions: running total follows calendar order.
SELECT month, revenue,
       SUM(revenue) OVER (ORDER BY month ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
           AS running_total_revenue
FROM analytics.monthly_kpis ORDER BY month;

-- Q21 Business question: How do products rank within their own category?
-- Grain: product within category. Assumptions: ties share a rank.
SELECT category, product_id, revenue, units,
       RANK() OVER (PARTITION BY category ORDER BY revenue DESC) AS category_rank
FROM analytics.product_performance ORDER BY category, category_rank, product_id;

-- Q22 Business question: When are orders placed by weekday and hour?
-- Grain: weekday and local timestamp hour. Assumptions: source timestamps have no timezone.
SELECT EXTRACT(ISODOW FROM purchase_ts)::INTEGER AS weekday,
       EXTRACT(HOUR FROM purchase_ts)::INTEGER AS order_hour,
       COUNT(*) AS orders, COUNT(DISTINCT customer_unique_id) AS customers
FROM analytics.valid_orders
GROUP BY EXTRACT(ISODOW FROM purchase_ts), EXTRACT(HOUR FROM purchase_ts)
ORDER BY weekday, order_hour;

-- Q23 Business question: How does AOV compare by state and calendar month?
-- Grain: state and month. Assumptions: revenue excludes freight.
SELECT state, DATE_TRUNC('month', purchase_ts)::DATE AS order_month,
       SUM(item_revenue) / NULLIF(COUNT(*), 0) AS aov, COUNT(*) AS orders
FROM analytics.valid_orders GROUP BY state, DATE_TRUNC('month', purchase_ts)::DATE
ORDER BY order_month, aov DESC;

-- Q24 Business question: What are delivery and review outcomes by state and month?
-- Grain: state and purchase month. Assumptions: reviews are averaged per order before aggregation.
WITH order_review AS (
    SELECT order_id, AVG(review_score) AS avg_review FROM core.reviews GROUP BY order_id
)
SELECT dp.state, DATE_TRUNC('month', dp.delivered_customer_ts)::DATE AS delivery_month,
       AVG(dp.delivery_delta_days) AS avg_delay_days,
       AVG(dp.late_flag::INT) FILTER (WHERE dp.late_flag IS NOT NULL) AS late_rate,
       AVG(orev.avg_review) AS avg_review_score
FROM analytics.delivery_performance AS dp
LEFT JOIN order_review AS orev USING (order_id)
GROUP BY dp.state, DATE_TRUNC('month', dp.delivered_customer_ts)::DATE
ORDER BY delivery_month, dp.state;

-- Q25 Business question: Which categories exceed the average category revenue?
-- Grain: category. Assumptions: compare with the mean category revenue.
SELECT category, revenue, units
FROM analytics.category_performance
WHERE revenue > (SELECT AVG(revenue) FROM analytics.category_performance)
ORDER BY revenue DESC;
