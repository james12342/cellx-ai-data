# Automatic photo descriptions and ordered narration

## Using the Agent page

Save the current draft before refreshing an older open Agent page. Upload one batch of photos. After the whole batch is saved, automatic analysis sends the current ordered set to the backend OpenAI Responses integration. Open Preview Video and find Image analysis & storyboard.

- Empty or previously AI-owned product details are filled automatically. Existing manual text stays intact; Use AI draft explicitly replaces it.
- Each photo gets an editable description and narration line. Move earlier/later controls in the upload dialog reorder photos. Edited narration stays associated with its photo ID.
- Adding, removing, or reordering photos invalidates old responses and schedules analysis of the resulting set. A failed request leaves edits intact and requires Analyze / Retry.
- Automatic analysis can be disabled. Explicit Analyze / Retry still works without re-enabling that preference.
- Use in Economy Ad copies the ordered narration into the photo-ad settings. It does not generate a video.
- Portrait mode retains its separate single-photo narration. Multi-image scripts do not overwrite its narration automatically.
- Existing ChatGPT manual prompt/import remains available. Its provider selector applies to that manual route; the separate automatic-analysis checkbox controls upload-triggered OpenAI use.

## Cost and limits

Automatic analysis uses the server-side OPENAI_API_KEY and PRODUCT_BRIEF_MODEL (default gpt-4o-mini), and is usage billed. Images are resized to 768 pixels and sent with low detail. No browser API key, automatic video job, or automatic paid-video fallback is added. Exact repeated results are cached for one hour in process memory. Failures are not automatically retried.

One storyboard supports 1–10 distinct uploaded photos, JPEG/PNG/WebP, up to 20MB and 40 megapixels each. Requested economy duration is 15–60 seconds. Speech duration depends on synthesis; the duration matching process below measures actual audio. Users should review generated factual claims before publishing.

## Verification and deployment

- Five backend tests pass: strict structured output with all photos and order, caching, wrong order rejection, missing file rejection, timeout and input validation.
- Queue/UI tests pass: one request per batch, no partial-batch request, stale response rejection, manual edits, reorder/remove association, explicit retry, preserved ChatGPT route, no video request.
- Existing economy and GPU portrait UI tests pass.
- Live AWS test on 2026-09-17 UTC: two authorized house photos uploaded in one batch into existing Video Studio containing one portrait. The backend returned HTTP 200 for exactly one product-brief request and generated three Chinese scenes in image order. The original manual description and portrait narration remained unchanged. The 5090 worker remained online. No video-generation POST occurred during this test.
- Deployment preserves the live index and uses SHA-256 guards, backups, atomic file replacement, service/scheduler health checks and rollback. Backup: `/tmp/cellx-before-photos-m2hxusmw`.
- Runtime dependency installed on AWS: Ubuntu python3-pil, used by /usr/bin/python3.

Source files: product_storyboards.py, product_briefs.py, workflow-product-analysis.js, workflow-photos.js, workflow-video.js and workflow-video.css.

## Existing-page refresh fix

The user reported an already-open dialog without the new panel. Public /agent/, /agent/index.html and legacy /workflow/ and /ext/ routes were checked and resolve to the updated page. The exact user's old tab was not accessible; it must not be mistaken for the separately verified Video Studio tab.

The Agent and legacy workflow static locations now send `Cache-Control: no-cache, max-age=0, must-revalidate`, and affected asset URLs use `20260917-auto-copy-v2`. Save ad brief and Save Draft before refreshing an older tab; a one-time Ctrl+Shift+R bypasses old cached responses. Existing photos can be analyzed with Analyze all photos + storyboard. Both that top button and the economy narration button use the ordered batch module when loaded. The ChatGPT route remains unchanged. Regression tests verify the unified button still works with auto-analysis disabled and preserves that preference and manual text.

This fix only reloads nginx, not the API or GPU worker. Nginx config validation passed; live headers and a normal-refresh browser test confirmed the new assets and preserved draft. Backup: `/tmp/cellx-cache-fix-jl7j9iuk`.

## Custom duration matching (2026-09-17)

The former prompt specified only a maximum narration length, so short slogans passed even at 40 or 55 seconds. The request now includes the selected voice and user product notes as well as ordered images, language and duration. The cache distinguishes those inputs. Initial character/word budgets differ by language and voice, and the strict output schema enforces substantive per-image paragraphs. Notes are treated as data; unknown facts must not be invented to fill time.

For voiced storyboards, Edge generates each scene's speech using the same voice mapping as the economy renderer. FFprobe measures every audio file. If speech differs substantially from the target, at most one additional OpenAI revision uses the measured duration to recalculate the content budget. If the resulting speed factor falls in 0.88–1.12, FFmpeg atempo makes a small pitch-preserving speed adjustment; FFprobe then measures those WAVs. This process adds no padding or long silence. A remaining mismatch is explicitly reported, is not cached as a successful fit, and cannot silently be presented as the target duration. OpenAI usage can therefore include two model calls; service/network failures still do not loop-retry.

The UI shows target time, measured speech time, and speed factor. Planned per-image durations sum to the requested duration and preserve photo order. Changing duration invalidates in-flight results immediately and triggers a new analysis after the change. Edited scenes and manual product text remain protected. Manual edits invalidate the applicability of the previous speech measurement; Use AI draft is the explicit replacement action. Only an unchanged, successfully measured draft with matching duration/voice/photo IDs sets `fit_narration` on an economy render request. The renderer reruns the same TTS and bounded correction before scene editing; subtitles are scaled with the audio. Manually written narration keeps the existing workflow. Silent mode is marked estimated, not measured. The single-person 5090 path remains limited to 20 seconds.

Live HTTPS tests used three existing authorized house photos in order (exterior aerial, fireplace living room, dining room), Chinese female Xiaoxiao voice, and no video job:

| Requested | Chinese characters | Raw speech | Corrected speech, FFprobe | Speed | Copy revisions |
| --- | ---: | ---: | ---: | ---: | ---: |
| 40 s | 177 | 42.768 s | 39.943 s | 1.0692× | 1 |
| 55 s | 256 | 61.320 s | 54.946 s | 1.11490909× | 0 |

Acceptance tolerance is max(1.5 seconds, 5% of requested duration), not a promise of exact timing for every voice. Both samples were within 0.06 seconds. A separate speech-only check running as the actual `cellxrunner` render user reproduced 54.946166 seconds for the 55-second sample, confirming executable paths, permissions and the shared render correction. No paid video or GPU job was submitted.

Backend regressions: 8 storyboard tests, 2 speech-timing tests, 8 economy tests. UI/queue regressions cover actual 40→55 request payloads, voice propagation, stale 40-second rejection, preserved manual text/scenes and invalidation of edited-draft measurements, plus the existing GPU/economy UI suites. Browser refresh confirms the new timing notice, preserved portrait script, ChatGPT controls and online 5090. Results are in `outputs/duration-copy-deploy/verified-40-zh-female.json` and `verified-55-zh-female.json`.

Deployment preserves live HTML and no-cache headers. Product-brief requests now allow 330 seconds at nginx for bounded analysis, speech measurement and one revision. Main backup: `/tmp/cellx-before-photos-h5lcxnzb`; subsequent paragraph-budget tuning backup: `/tmp/cellx-before-photos-kemkb6mr`; final UI backup: `/tmp/cellx-cache-fix-3s4ta7eq`. The worker installation and GPU job code were not changed.
