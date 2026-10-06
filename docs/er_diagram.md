# Core schema entity relationship diagram

```mermaid
erDiagram
    CUSTOMERS ||--o{ ORDERS : "places"
    ORDERS ||--|{ ORDER_ITEMS : "contains"
    PRODUCTS ||--o{ ORDER_ITEMS : "appears in"
    SELLERS ||--o{ ORDER_ITEMS : "fulfills"
    ORDERS ||--o{ PAYMENTS : "paid through"
    ORDERS ||--o{ REVIEWS : "receives"

    CATEGORY_TRANSLATION {
        string category_pt PK
        string category_en
    }

    CUSTOMERS {
        string customer_id PK
        string customer_unique_id
        int zip_prefix
        string city
        string state
    }

    SELLERS {
        string seller_id PK
        int zip_prefix
        string city
        string state
    }

    PRODUCTS {
        string product_id PK
        string category_pt
        string category_en
        int name_length
        int description_length
        int photos_qty
        numeric weight_g
        numeric length_cm
        numeric height_cm
        numeric width_cm
    }

    GEOLOCATION {
        int zip_prefix PK
        numeric lat
        numeric lng
        string city
        string state
    }

    ORDERS {
        string order_id PK
        string customer_id FK
        string order_status
        timestamp purchase_ts
        timestamp approved_ts
        timestamp delivered_carrier_ts
        timestamp delivered_customer_ts
        timestamp estimated_delivery_ts
    }

    ORDER_ITEMS {
        string order_id PK, FK
        int order_item_id PK
        string product_id FK
        string seller_id FK
        timestamp shipping_limit_ts
        numeric price
        numeric freight_value
    }

    PAYMENTS {
        string order_id PK, FK
        int payment_sequential PK
        string payment_type
        smallint installments
        numeric payment_value
    }

    REVIEWS {
        string review_id PK
        string order_id PK, FK
        smallint review_score
        string title
        string message
        timestamp creation_ts
        timestamp answer_ts
    }

    DIM_CUSTOMER_UNIQUE {
        string customer_unique_id PK
        timestamp first_order_ts
        timestamp last_order_ts
        string state
        string city
    }
```

`customers.customer_unique_id` identifies a person across order-specific customer IDs. It is
indexed but is not a foreign key to `dim_customer_unique`, which is populated after the order
facts in the Phase 3 load sequence. `products.category_pt` and `category_en` are intentionally
not foreign keys: some source categories do not have translations. `geolocation` is a one-row-per-
zip-prefix reference table and is not constrained to customer or seller rows.

Revenue is merchandise value: `SUM(order_items.price)` for delivered orders. Freight is excluded.
