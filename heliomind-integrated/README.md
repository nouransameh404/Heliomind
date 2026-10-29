# Heliomind runtime

Use ../START.bat or, from this folder:

```bash
docker compose --parallel 1 up --build -d --wait --wait-timeout 240
```

UI: http://localhost:5500 · API: http://localhost:8000/docs

The original frontend design/navigation are retained. All actions use the actual gateway and model services. Forecast/Anomaly accept prepared features (11/18 columns); JSON and CSV examples are available. No local-model fallback is used. Sizing uses the original on-grid, no-battery rules, manual monthly PSH inputs and AUD prices. Forecast is fixed to the Alice Springs/DKASC reference system. Sizing plans a separate proposed Alice Springs installation; resource and prices are illustrative/manual inputs. Anomaly is labelled as a Kaggle research benchmark from India.

Five containers: frontend → gateway → forecast/sizing/anomaly. Only 5500 and 8000 are published to localhost. nginx re-resolves gateway DNS after recreation. Service metadata loads independently and retries on action/refresh. Startup failures are shown only on the affected page.

`GET /services`, `/forecast/features`, `/anomaly/features`, `/sizing/example` provide status and input references. Swagger includes complete valid examples, including explicit nulls for imputed history values. The backend rejects invalid schemas with 422, unavailable services with 503, and timeouts with 504.

After a model export, run `python ../scripts/sync_artifacts.py`, then restart the affected services. Changed gateway examples or code require rebuilding. Model and imputer must be a matching set. Update examples too if the feature schema changes.

Tests and full notes are in the root README and CHANGES.md.
