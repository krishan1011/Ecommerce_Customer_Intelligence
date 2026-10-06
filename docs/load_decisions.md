# Phase 3 load decisions

- **CSV staging:** all nine source files are copied into same-named `raw` tables with UTF-8 CSV
  parsing. CSV record counts are computed separately with Python's CSV reader and checked against
  PostgreSQL raw row counts before transformation. Quoted commas and embedded newlines are handled
  by the CSV parser and PostgreSQL `COPY`.
- **Products:** source `product_name_lenght` and `product_description_lenght` map to the correctly
  spelled core fields `name_length` and `description_length`. English category names come from a
  left join to translations. The two untranslated source categories are `pc_gamer` and
  `portateis_cozinha_e_preparadores_de_alimentos`; both fall back to their Portuguese names. A
  missing category remains NULL. No product-to-translation foreign key is added because some
  categories have no translation.
- **Geolocation:** samples are grouped by integer zip prefix. Latitude and longitude are averaged;
  city and state use the most frequent non-empty values, with a lexical tie-break. Customer, seller,
  and geolocation city/state text is trimmed, lowercased, and accent-normalized consistently.
- **Reviews:** duplicates are ranked by `(review_id, order_id)`, newest answer timestamp first, then
  newest creation timestamp and stable text tie-breaks. The retained record and dropped duplicate
  count are recorded in `core.load_reconciliation`.
- **Orphans:** each required relationship is counted before insertion. Invalid customer/order,
  item/order, item/seller, payment/order, and review/order rows are dropped and reconciled. If an
  order item references an unknown non-empty product ID, the loader creates one `unknown` product
  and maps those item references to it so the item and its revenue are retained.
- **Payments:** `not_defined` payment types and zero installments remain unchanged; their counts are
  included in reconciliation notes.
- **Customer dimension:** one row is created per `customer_unique_id`. First/last order timestamps
  consider all statuses; location comes from that customer's most recent order.
- **Repeatability:** raw tables and core entity tables are truncated and rebuilt in one transaction.
  Reconciliation rows are retained by run timestamp so prior run outcomes remain auditable.
- **Sanity totals:** revenue is merchandise value `SUM(order_items.price)` on delivered orders;
  freight is reported separately. SQL totals are compared with independently read CSV totals after
  applying the same relationship validity rules.
