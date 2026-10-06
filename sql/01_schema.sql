-- ============================================================================
-- 01_SCHEMA.SQL: Database Schema Design (Phase 2)
-- Three layers: raw (landing), core (cleaned, relational, constrained), analytics (views)
-- Idempotent script: drops and recreates raw, core, analytics.
-- ============================================================================

DROP SCHEMA IF EXISTS analytics CASCADE;
DROP SCHEMA IF EXISTS core CASCADE;
DROP SCHEMA IF EXISTS raw CASCADE;

CREATE SCHEMA raw;
CREATE SCHEMA core;
CREATE SCHEMA analytics;

COMMENT ON SCHEMA raw IS 'Raw landing tables loaded 1:1 from Olist CSV files with TEXT columns and no constraints.';
COMMENT ON SCHEMA core IS 'Cleaned, typed, normalized, and relationally constrained entities for the full dataset.';
COMMENT ON SCHEMA analytics IS 'Read-only views, to be added in Phase 4.';

-- ============================================================================
-- 1. RAW SCHEMA (TEXT-only staging mirroring CSV column names and spellings)
-- ============================================================================

CREATE TABLE raw.olist_customers (
    customer_id TEXT,
    customer_unique_id TEXT,
    customer_zip_code_prefix TEXT,
    customer_city TEXT,
    customer_state TEXT
);

CREATE TABLE raw.olist_orders (
    order_id TEXT,
    customer_id TEXT,
    order_status TEXT,
    order_purchase_timestamp TEXT,
    order_approved_at TEXT,
    order_delivered_carrier_date TEXT,
    order_delivered_customer_date TEXT,
    order_estimated_delivery_date TEXT
);

CREATE TABLE raw.olist_order_items (
    order_id TEXT,
    order_item_id TEXT,
    product_id TEXT,
    seller_id TEXT,
    shipping_limit_date TEXT,
    price TEXT,
    freight_value TEXT
);

CREATE TABLE raw.olist_order_payments (
    order_id TEXT,
    payment_sequential TEXT,
    payment_type TEXT,
    payment_installments TEXT,
    payment_value TEXT
);

CREATE TABLE raw.olist_order_reviews (
    review_id TEXT,
    order_id TEXT,
    review_score TEXT,
    review_comment_title TEXT,
    review_comment_message TEXT,
    review_creation_date TEXT,
    review_answer_timestamp TEXT
);

CREATE TABLE raw.olist_products (
    product_id TEXT,
    product_category_name TEXT,
    product_name_lenght TEXT,
    product_description_lenght TEXT,
    product_photos_qty TEXT,
    product_weight_g TEXT,
    product_length_cm TEXT,
    product_height_cm TEXT,
    product_width_cm TEXT
);

CREATE TABLE raw.olist_sellers (
    seller_id TEXT,
    seller_zip_code_prefix TEXT,
    seller_city TEXT,
    seller_state TEXT
);

CREATE TABLE raw.olist_geolocation (
    geolocation_zip_code_prefix TEXT,
    geolocation_lat TEXT,
    geolocation_lng TEXT,
    geolocation_city TEXT,
    geolocation_state TEXT
);

CREATE TABLE raw.product_category_name_translation (
    product_category_name TEXT,
    product_category_name_english TEXT
);

-- ============================================================================
-- 2. CORE SCHEMA (Typed, constrained, indexed; keeps ALL rows)
-- ============================================================================

-- 2.1 Category Translation
CREATE TABLE core.category_translation (
    category_pt TEXT PRIMARY KEY,
    category_en TEXT NOT NULL
);

-- 2.2 Customers
CREATE TABLE core.customers (
    customer_id TEXT PRIMARY KEY,
    customer_unique_id TEXT NOT NULL,
    zip_prefix INT,
    city TEXT,
    state TEXT
);

-- 2.3 Sellers
CREATE TABLE core.sellers (
    seller_id TEXT PRIMARY KEY,
    zip_prefix INT,
    city TEXT,
    state TEXT
);

-- 2.4 Products
-- Note: NO foreign key to category_translation because 2 categories lack translation.
CREATE TABLE core.products (
    product_id TEXT PRIMARY KEY,
    category_pt TEXT NULL,
    category_en TEXT NULL,
    name_length INT CHECK (name_length IS NULL OR name_length >= 0),
    description_length INT CHECK (description_length IS NULL OR description_length >= 0),
    photos_qty INT CHECK (photos_qty IS NULL OR photos_qty >= 0),
    weight_g NUMERIC(10,2) CHECK (weight_g IS NULL OR weight_g >= 0),
    length_cm NUMERIC(10,2) CHECK (length_cm IS NULL OR length_cm >= 0),
    height_cm NUMERIC(10,2) CHECK (height_cm IS NULL OR height_cm >= 0),
    width_cm NUMERIC(10,2) CHECK (width_cm IS NULL OR width_cm >= 0)
);

-- 2.5 Geolocation
CREATE TABLE core.geolocation (
    zip_prefix INT PRIMARY KEY,
    lat NUMERIC(10,6),
    lng NUMERIC(10,6),
    city TEXT,
    state TEXT
);

-- 2.6 Orders
CREATE TABLE core.orders (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES core.customers(customer_id),
    order_status TEXT NOT NULL CHECK (
        order_status IN (
            'created',
            'approved',
            'invoiced',
            'processing',
            'shipped',
            'delivered',
            'unavailable',
            'canceled'
        )
    ),
    purchase_ts TIMESTAMP NOT NULL,
    approved_ts TIMESTAMP,
    delivered_carrier_ts TIMESTAMP,
    delivered_customer_ts TIMESTAMP,
    estimated_delivery_ts TIMESTAMP
);

-- 2.7 Order Items
CREATE TABLE core.order_items (
    order_id TEXT NOT NULL REFERENCES core.orders(order_id),
    order_item_id INT NOT NULL,
    product_id TEXT REFERENCES core.products(product_id),
    seller_id TEXT REFERENCES core.sellers(seller_id),
    shipping_limit_ts TIMESTAMP,
    price NUMERIC(12,2) NOT NULL CHECK (price >= 0),
    freight_value NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (freight_value >= 0),
    PRIMARY KEY (order_id, order_item_id)
);

-- 2.8 Payments
CREATE TABLE core.payments (
    order_id TEXT NOT NULL REFERENCES core.orders(order_id),
    payment_sequential INT NOT NULL,
    payment_type TEXT NOT NULL CHECK (
        payment_type IN ('credit_card', 'boleto', 'voucher', 'debit_card', 'not_defined')
    ),
    installments SMALLINT CHECK (installments IS NULL OR installments >= 0),
    payment_value NUMERIC(12,2) CHECK (payment_value IS NULL OR payment_value >= 0),
    PRIMARY KEY (order_id, payment_sequential)
);

-- 2.9 Reviews
CREATE TABLE core.reviews (
    review_id TEXT NOT NULL,
    order_id TEXT NOT NULL REFERENCES core.orders(order_id),
    review_score SMALLINT NOT NULL CHECK (review_score BETWEEN 1 AND 5),
    title TEXT,
    message TEXT,
    creation_ts TIMESTAMP,
    answer_ts TIMESTAMP,
    PRIMARY KEY (review_id, order_id)
);

-- 2.10 Dim Customer Unique (Person-level dimension, populated in Phase 3)
CREATE TABLE core.dim_customer_unique (
    customer_unique_id TEXT PRIMARY KEY,
    first_order_ts TIMESTAMP,
    last_order_ts TIMESTAMP,
    state TEXT,
    city TEXT
);

-- ============================================================================
-- 3. INDEXES
-- ============================================================================

CREATE INDEX idx_orders_customer_id ON core.orders(customer_id);
CREATE INDEX idx_orders_purchase_ts ON core.orders(purchase_ts);
CREATE INDEX idx_orders_order_status ON core.orders(order_status);
CREATE INDEX idx_order_items_product_id ON core.order_items(product_id);
CREATE INDEX idx_order_items_seller_id ON core.order_items(seller_id);
CREATE INDEX idx_reviews_order_id ON core.reviews(order_id);
CREATE INDEX idx_customers_customer_unique_id ON core.customers(customer_unique_id);
CREATE INDEX idx_payments_order_id ON core.payments(order_id);
CREATE INDEX idx_products_category_en ON core.products(category_en);

-- ============================================================================
-- 4. COMMENTS ON TABLES & KEY COLUMNS (Grain documentation)
-- ============================================================================

COMMENT ON TABLE core.category_translation IS 'Grain: One row per Portuguese category name translation.';
COMMENT ON COLUMN core.category_translation.category_pt IS 'Primary key: Portuguese product category name.';
COMMENT ON COLUMN core.category_translation.category_en IS 'English product category translation.';

COMMENT ON TABLE core.customers IS 'Grain: One row per customer order session (customer_id).';
COMMENT ON COLUMN core.customers.customer_id IS 'Primary key: Order-specific customer identifier.';
COMMENT ON COLUMN core.customers.customer_unique_id IS 'Unique identifier representing the persistent individual customer across orders.';

COMMENT ON TABLE core.sellers IS 'Grain: One row per seller merchant account.';
COMMENT ON COLUMN core.sellers.seller_id IS 'Primary key: Merchant seller identifier.';

COMMENT ON TABLE core.products IS 'Grain: One row per catalog product SKU.';
COMMENT ON COLUMN core.products.product_id IS 'Primary key: Product identifier.';
COMMENT ON COLUMN core.products.category_pt IS 'Portuguese product category name.';
COMMENT ON COLUMN core.products.category_en IS 'English category translation (or Portuguese fallback).';

COMMENT ON TABLE core.geolocation IS 'Grain: One row per unique zip code prefix with aggregated median coordinates.';
COMMENT ON COLUMN core.geolocation.zip_prefix IS 'Primary key: 5-digit postal code prefix.';

COMMENT ON TABLE core.orders IS 'Grain: One row per placed customer order.';
COMMENT ON COLUMN core.orders.order_id IS 'Primary key: Unique order identifier.';
COMMENT ON COLUMN core.orders.customer_id IS 'Foreign key referencing core.customers(customer_id).';
COMMENT ON COLUMN core.orders.order_status IS 'Order status lifecycle stage.';

COMMENT ON TABLE core.order_items IS 'Grain: One row per individual item line within an order.';
COMMENT ON COLUMN core.order_items.order_id IS 'Composite primary key component: References core.orders(order_id).';
COMMENT ON COLUMN core.order_items.order_item_id IS 'Composite primary key component: 1..N sequence within the order.';
COMMENT ON COLUMN core.order_items.product_id IS 'Foreign key referencing core.products(product_id).';
COMMENT ON COLUMN core.order_items.seller_id IS 'Foreign key referencing core.sellers(seller_id).';
COMMENT ON COLUMN core.order_items.price IS 'Item sale price in BRL. Used as sole merchandise revenue base.';
COMMENT ON COLUMN core.order_items.freight_value IS 'Item freight shipping fee in BRL.';

COMMENT ON TABLE core.payments IS 'Grain: One row per payment method installment/transaction within an order.';
COMMENT ON COLUMN core.payments.order_id IS 'Composite primary key component: References core.orders(order_id).';
COMMENT ON COLUMN core.payments.payment_sequential IS 'Composite primary key component: 1..N payment attempt sequence.';
COMMENT ON COLUMN core.payments.payment_type IS 'Payment method; includes not_defined as present in the source data.';

COMMENT ON TABLE core.reviews IS 'Grain: One row per customer review record linked to an order.';
COMMENT ON COLUMN core.reviews.review_id IS 'Composite primary key component: Review submission ID.';
COMMENT ON COLUMN core.reviews.order_id IS 'Composite primary key component: References core.orders(order_id).';
COMMENT ON COLUMN core.reviews.review_score IS 'Customer rating between 1 (worst) and 5 (best).';

COMMENT ON TABLE core.dim_customer_unique IS 'Grain: One row per unique individual human customer across lifetime history.';
COMMENT ON COLUMN core.dim_customer_unique.customer_unique_id IS 'Primary key: Unique individual customer identifier.';
