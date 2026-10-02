# Success Criteria (written before any results; do not edit after modeling starts)

| Component | Criterion | Baseline to beat |
|---|---|---|
| Database | Row counts reconcile CSV vs raw vs core; SQL totals match pandas | n/a |
| SQL | 20+ documented queries, 7+ analytics views, 5+ cross-checked with pandas | n/a |
| Validation | pandera schemas for every parquet table; hard checks stop the pipeline | n/a |
| Features | Leakage test passes; chronological splits | n/a |
| Churn / propensity | Test PR-AUC beats logistic regression; top-decile lift reported; calibrated | Dummy, logistic regression |
| Uplift (simulated) | Experiment design + power calculation shipped; numbers labelled simulated | Random targeting |
| Segmentation | Stable across seeds (adjusted Rand index > 0.8); each segment has a business name and action | Quintile RFM rules |
| CLV | Predicted 6-month repeat purchases within an agreed error of holdout total | Average repeat rate |
| Forecasting | MASE < 1 on rolling-origin backtests | Seasonal naive |
| Delivery delay | PR-AUC and recall at fixed precision beat rule "inter-state and long estimate"; no leakage | Dummy, logistic regression, rule |
| Recommender | NDCG@10 beats popularity, or result reported honestly; user counts and bootstrap CIs given | Popularity |
| Sentiment | Macro-F1 on 200-review hand-labelled gold set, justified against label noise | TF-IDF + logistic regression |
| Deep learning | MLP vs boosting on identical split, 3-5 seeds, written verdict | Gradient boosting |
| Monitoring | Injected drift scenario triggers an alert in a test | None (new) |
| Power BI | 7 pages, validated measures, drill-through, PDF export | n/a |
| API | /health + 7 endpoints, tests pass, < 200 ms churn/recommend locally | n/a |
| Streamlit | 9 pages via API, error handling, demo recording | n/a |
| CI/CD | Lint, tests, metrics gate, Docker build on every push | n/a |
| Deployment | Public API answers /health and one prediction in < 2 s after wake-up | Local run |
| Reproducibility | Clean clone -> documented commands -> DB, models, services, app run | n/a |
