.PHONY: setup db-up db-down test lint schema views all load-db extract validate clean features train-churn segment-clv forecast train-delay train-recsys train-nlp train-dl evaluate monitor export-bi
setup:
	python -m venv .venv
	.venv/bin/pip install -r requirements.txt
	.venv/bin/pre-commit install
db-up:
	docker compose up -d postgres
db-down:
	docker compose down
test:
	pytest -q
lint:
	ruff check . && black --check .

schema: ; python -m src.db schema --yes
views: ; python -m src.db views

# Pipeline targets (implemented phase by phase; see docs/copilot_prompt.md)
all: load-db extract validate features train-churn segment-clv forecast train-delay train-recsys train-nlp train-dl evaluate monitor export-bi
load-db:      ; python -m src.db load
extract:      ; python -m src.db extract
validate:     ; python -m src.validation run
clean:        ; python -m src.cleaning run
features:     ; python -m src.features build
train-churn:  ; python -m src.churn train
segment-clv:  ; python -m src.segmentation run && python -m src.clv run
forecast:     ; python -m src.forecast run
train-delay:  ; python -m src.delay train
train-recsys: ; python -m src.recsys train
train-nlp:    ; python -m src.nlp train
train-dl:     ; python -m src.dl train
evaluate:     ; python -m src.evaluate
monitor:      ; python -m monitoring.run_monitoring
export-bi:    ; python -m src.evaluate export-bi
