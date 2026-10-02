# Scope Note

## Business problem
An online marketplace has roughly 97% one-time buyers. Managers need to know where revenue comes from, which customers will buy again and what they are worth, what to recommend, what customers say in reviews, which orders will arrive late, and what demand to expect, so they can act on retention, merchandising, logistics and planning.

## Questions managers must be able to answer
1. How are revenue, orders and customers trending, and where do they come from (category, state, seller)?
2. Which customers are likely to repurchase, which high-value customers are at risk, and what is a customer worth (CLV)?
3. Which customer segments exist and what action fits each?
4. What demand and revenue should we expect over the next weeks?
5. Which orders are likely to be delivered late, and which sellers/states cause it?
6. Which products should be recommended to a given customer?
7. What do customers praise or complain about, and how does delivery affect satisfaction?
8. Is the system healthy: has the data drifted and do models need retraining?

## Dataset
Olist Brazilian E-Commerce (Kaggle), non-commercial licence, credited in docs/data_source.md. Analysis window confirmed in Phase 1 (default 2017-01 to 2018-08), stored in params.yaml.

## Framing decisions
- Target: repeat-purchase propensity within H days of a snapshot date (churn probability = 1 - p).
- Customer key: customer_unique_id, never customer_id.
- Splits: chronological only. Seed: RANDOM_STATE = 42 (params.yaml / src/config.py).
- Revenue = SUM(order_items.price) for delivered orders; freight excluded unless stated.
- Uplift results are labelled "simulated"; no claim of real campaign effect.

## Non-goals
- No real-time streaming.
- No paid cloud services (free tiers only).
- No Kubernetes.
- No technique that does not serve a business purpose (stated in README if dropped).

## Deliverables
Appendix C of the Extended Pipeline Guide (Database through Deployment and Docs; GenAI add-on optional).
