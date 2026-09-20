# Budget product video models

Open the existing Video Generation node, choose AI Product Ad, then select a model.
Existing workflows without a model retain Runway Product Ad. New selections are saved with the video brief.

| Model | Generation estimate, USD before tax | Inputs |
| --- | --- | --- |
| Wan 2.2 Turbo | $0.10 per 720p clip | First photo; provider-fixed duration |
| Hailuo 2.3 Fast | $0.19 / 6s; $0.32 / 10s, 768p | First photo; aspect follows photo |
| Kling 2.5 Turbo Pro | $0.35 / 5s; $0.70 / 10s | First photo; aspect follows photo |
| Runway Gen-4 Turbo | $0.25 / 5s; $0.50 / 10s | First photo; selected aspect ratio |
| Runway Product Ad | $2.00 for 4s + $0.36 per additional second | Up to 10 photos; existing recipe |

Prices checked September 15, 2026. They cover individual generations, excluding image preparation, voiceover, editing, tax and repeat attempts. Budget models generate silent video; the existing background music feature remains available. Wan's API has no duration field: the internal duration value 5 is a UI compatibility marker, not a promise of exact output length.

## Credentials

Runway models use the existing server-only `RUNWAYML_API_SECRET` (or `RUNWAY_API_KEY`). The other three models use fal's queue API and require server-only `FAL_KEY`. Configure it in the service's existing protected environment file, then restart the service when no video is rendering. Never place keys in workflow JSON, frontend code or Git. The model selector reports configuration status without exposing credentials.

## Job handling

The browser confirms the selected model, photo count and estimated cost. The backend independently validates model, duration, photo count, audio support and price before submitting. Each request is submitted once. fal request IDs and queue URLs are persisted before polling; Resume retrieves an existing request after interruption. If no receipt arrived, review provider history before creating another paid job. Outputs are downloaded into the existing private video store for preview, music and download.

## Verification

`python -m unittest discover -s cellx-extension-api -p test_budget_videos.py`

`python -m unittest discover -s cellx-extension-api -p test_runway_videos.py`

`python -m unittest discover -s cellx-extension-api -p test_promo_videos.py`

`node scripts/test_budget_video_ui.cjs` (uses the bundled Playwright runtime and Microsoft Edge; fixture catalog in outputs/video-catalog.json).

Tests use mocked provider responses and do not purchase video generations.

## Sources

- https://docs.dev.runwayml.com/guides/pricing/
- https://docs.dev.runwayml.com/api.md
- https://fal.ai/models/fal-ai/wan/v2.2-a14b/image-to-video/turbo
- https://fal.ai/models/fal-ai/minimax/hailuo-2.3-fast/standard/image-to-video
- https://fal.ai/models/fal-ai/kling-video/v2.5-turbo/pro/image-to-video
- https://fal.ai/docs/documentation/model-apis/inference/queue
