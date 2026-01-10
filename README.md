# askziva

FastAPI service powering AskZiva commerce intelligence.

## Run Locally

1. Install dependencies and Playwright Chromium:

```
pip install -r requirements.txt
python -m playwright install chromium
```

2. Start the API:

```
uvicorn app:app --host 0.0.0.0 --port 10000
```

## Deploy on Render

This repo includes a [render.yaml](render.yaml) Blueprint:

- Build Command: `pip install -r requirements.txt && python -m playwright install chromium`
- Start Command: `uvicorn app:app --host 0.0.0.0 --port $PORT`

### Option A: Use the Blueprint
1. In Render, create a new Blueprint.
2. Point it at this GitHub repo.
3. Render will read `render.yaml` and provision the service.

### Option B: Update an existing Web Service
1. Open your service in Render.
2. Set Build Command to: `pip install -r requirements.txt && python -m playwright install chromium`
3. Set Start Command to: `uvicorn app:app --host 0.0.0.0 --port $PORT`
4. Save and trigger a redeploy.

Notes:
- This app uses FastAPI and `uvicorn`. Do not use `gunicorn`.
- Ensure `GEMINI_API_KEY` is configured in Render Environment Variables if AI analysis is needed.