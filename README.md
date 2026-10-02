# E-Commerce Customer Intelligence & Recommendation Platform

(Summary written in Phase 24.)

## Quick start
```bash
git clone <repo> && cd ecommerce-intelligence
cp .env.example .env            # set a password
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
docker compose up -d postgres
pytest -q
```
Put the Olist CSVs in `data/raw/`.
