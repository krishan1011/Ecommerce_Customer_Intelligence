# Olist E-Commerce Entity-Relationship Diagram

```mermaid
erDiagram
    CUSTOMERS ||--o{ ORDERS : "places (customer_id)"
    ORDERS ||--|{ ORDER_ITEMS : "contains (order_id)"
    ORDERS ||--o{ ORDER_PAYMENTS : "paid via (order_id)"
    ORDERS ||--o{ ORDER_REVIEWS : "reviewed in (order_id)"
    SELLERS ||--o{ ORDER_ITEMS : "fulfills (seller_id)"
    PRODUCTS ||--o{ ORDER_ITEMS : "ordered as (product_id)"
    CATEGORY_TRANSLATION ||--o{ PRODUCTS : "translates (product_category_name)"
    GEOLOCATION }o--o{ CUSTOMERS : "locates prefix"
    GEOLOCATION }o--o{ SELLERS : "locates prefix"

    CUSTOMERS {
        string customer_id PK "Unique per order session"
        string customer_unique_id "Identifier for actual person"
        string customer_zip_code_prefix
        string customer_city
        string customer_state
    }

    ORDERS {
        string order_id PK "Unique order identifier"
        string customer_id FK "References CUSTOMERS.customer_id"
        string order_status "delivered, shipped, canceled, etc."
        timestamp order_purchase_timestamp
        timestamp order_approved_at
        timestamp order_delivered_carrier_date
        timestamp order_delivered_customer_date
        timestamp order_estimated_delivery_date
    }

    ORDER_ITEMS {
        string order_id PK, FK "References ORDERS.order_id"
        int order_item_id PK "Sequential item number (1..N)"
        string product_id FK "References PRODUCTS.product_id"
        string seller_id FK "References SELLERS.seller_id"
        timestamp shipping_limit_date
        float price "Item sale price (used for revenue)"
        float freight_value "Item freight charge"
    }

    ORDER_PAYMENTS {
        string order_id PK, FK "References ORDERS.order_id"
        int payment_sequential PK "Payment sequence number (1..N)"
        string payment_type "credit_card, boleto, voucher, debit_card"
        int payment_installments "Number of installments"
        float payment_value "Transaction payment amount"
    }

    ORDER_REVIEWS {
        string review_id PK "Review identifier"
        string order_id PK, FK "References ORDERS.order_id"
        int review_score "1 to 5 stars"
        string review_comment_title "Optional review headline"
        string review_comment_message "Optional review body (Portuguese)"
        timestamp review_creation_date
        timestamp review_answer_timestamp
    }

    PRODUCTS {
        string product_id PK "Product SKU identifier"
        string product_category_name FK "Portuguese category name"
        int product_name_lenght
        int product_description_lenght
        int product_photos_qty
        float product_weight_g
        float product_length_cm
        float product_height_cm
        float product_width_cm
    }

    SELLERS {
        string seller_id PK "Seller merchant identifier"
        string seller_zip_code_prefix
        string seller_city
        string seller_state
    }

    GEOLOCATION {
        string geolocation_zip_code_prefix "Zip prefix (non-unique)"
        float geolocation_lat "Latitude"
        float geolocation_lng "Longitude"
        string geolocation_city "City name"
        string geolocation_state "State code"
    }

    CATEGORY_TRANSLATION {
        string product_category_name PK "Portuguese category name"
        string product_category_name_english "English translated name"
    }
```

## Entity Notes and Key Invariants
1. **Customer Grain (`customer_id` vs `customer_unique_id`)**:
   - `customer_id` is 1:1 with an order row.
   - `customer_unique_id` tracks an individual human over multiple purchases across time.
2. **Order Revenue Definition**:
   - `SUM(order_items.price)` on delivered orders.
   - Payments (`order_payments.payment_value`) include freight, vouchers, and card processing fees; item prices reflect actual product merchandise value.
3. **Review Multiplicity**:
   - Primary key is composite `(review_id, order_id)` due to occasional multi-order reviews or duplicate survey submissions.
4. **Geolocation**:
   - Geolocation is a spatial lookup table with multiple coordinate samples per `zip_code_prefix`. It does not have a single-column primary key.
