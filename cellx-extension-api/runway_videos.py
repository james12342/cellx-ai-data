"""Paid product-ad jobs; credentials and uploaded originals remain server-side."""
import base64
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import sys
import threading
import time
import urllib.parse
import urllib.request
from budget_videos import MODELS, catalog, price, fal_task

LOCK = threading.RLock()
ACTIVE = set()
RATIOS = {"9:16": "720:1280", "16:9": "1280:720", "1:1": "960:960"}
STYLES = {
    "custom": "Follow the user's creative direction for the visual style and pacing.",
    "studio": "Clean studio commercial, neutral backdrop, soft directional lighting, gentle camera movement.",
    "lifestyle": "Natural everyday product-use setting, realistic lighting, warm approachable commercial.",
    "cinematic": "Premium cinematic product close-ups, controlled lighting, slow camera movement.",
}


def api_key():
    return os.getenv("RUNWAYML_API_SECRET", "").strip() or os.getenv("RUNWAY_API_KEY", "").strip()


def provider_info():
    return {"ok": True, "runway_configured": bool(api_key()), "recipe": "product_ad",
            "version": "2026-07", "base_credits": 200, "extra_second_credits": 36,
            "credit_usd": .01, "sdk": "runwayml",
            "pricing_url": "https://docs.dev.runwayml.com/guides/pricing/", "models": catalog(bool(api_key()))}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def task_value(task, key, default=None):
    if isinstance(task, dict):
        return task.get(key, default)
    return getattr(task, key, default)


def task_failure_details(error):
    if error.__class__.__name__ != "TaskFailedError":
        return None
    details = getattr(error, "task_details", None)
    if details is None:
        details = getattr(error, "taskDetails", None)
    if isinstance(details, dict):
        failure = details.get("failure") or details.get("failureCode")
        if isinstance(failure, str) and failure.strip():
            return failure.strip()
    return str(error) or "Runway generation failed."


def product_ad_task(opts, images):
    sdk_dir = str(Path(__file__).parent / "runway-sdk")
    if Path(sdk_dir).is_dir() and sdk_dir not in sys.path:
        sys.path.insert(0, sdk_dir)
    try:
        from runwayml import RunwayML
    except ImportError as error:
        raise RuntimeError("Runway Python SDK is not installed.") from error
    if not os.getenv("RUNWAYML_API_SECRET") and os.getenv("RUNWAY_API_KEY"):
        os.environ["RUNWAYML_API_SECRET"] = os.getenv("RUNWAY_API_KEY", "")
    client = RunwayML(max_retries=0)
    concept = STYLES[opts["style"]] + " Preserve the reference product's shape, colors and branding. Do not invent claims or add text overlays. " + opts["concept"]
    if opts.get("model") == "gen4_turbo":
        prompt = concept + " Product: " + opts["product_info"]
        if len(prompt.encode("utf-16-le")) // 2 > 1000:
            raise ValueError("Runway Turbo: shorten product details and creative direction to fit 1000 characters combined.")
        return client.image_to_video.create(model="gen4_turbo", prompt_image=images[0]["uri"],
            prompt_text=prompt, duration=opts["duration_seconds"], ratio=RATIOS[opts["aspect_ratio"]]).wait_for_task_output()
    return client.recipes.product_ad(
        version="2026-07",
        product_images=images,
        product_info=opts["product_info"],
        user_concept=concept,
        duration=opts["duration_seconds"],
        ratio=RATIOS[opts["aspect_ratio"]],
        audio=opts["audio"],
    ).wait_for_task_output()


def validate(payload):
    opts = payload.get("options")
    if not isinstance(opts, dict):
        raise ValueError("Invalid video options.")
    model = opts.get("model", "product_ad")
    if not isinstance(model, str) or model not in MODELS:
        raise ValueError("Unknown video model.")
    spec = MODELS[model]
    duration = opts.get("duration_seconds", spec["durations"][0])
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration != int(duration) or duration not in spec["durations"]:
        raise ValueError("Unsupported duration for " + spec["name"] + ". Allowed seconds: " + str(spec["durations"]))
    aspect, style = opts.get("aspect_ratio", "9:16"), opts.get("style", "studio")
    if aspect not in RATIOS or style not in STYLES:
        raise ValueError("Invalid aspect ratio or ad style.")
    info, concept = opts.get("product_info", ""), opts.get("concept", "")
    if not isinstance(info, str) or not info.strip() or len(info) > 2500:
        raise ValueError("Enter product details and selling points (up to 2500 characters).")
    if not isinstance(concept, str) or len(concept) > 2500:
        raise ValueError("Creative direction must be 2500 characters or fewer.")
    if not isinstance(opts.get("audio", False), bool):
        raise ValueError("Invalid audio option.")
    if opts.get("audio") and not spec["audio"]:
        raise ValueError("This model generates silent video. Add background music separately.")
    if model == "gen4_turbo":
        prompt = STYLES[style] + " Preserve the reference product's shape, colors and branding. Do not invent claims or add text overlays. " + concept.strip() + " Product: " + info.strip()
        if len(prompt.encode("utf-16-le")) // 2 > 1000:
            raise ValueError("Runway Turbo: shorten product details and creative direction to fit 1000 characters combined.")
    ids = payload.get("photo_ids")
    if not isinstance(ids, list) or not ids or any(not isinstance(i, str) or not re.fullmatch(r"[a-f0-9]{40}", i) for i in ids):
        raise ValueError("Select uploaded product photos.")
    if len(ids) > spec["photos"] and model != "product_ad":
        raise ValueError("This model accepts one reference photo per video.")
    if len(ids) > 10:
        raise ValueError("Runway accepts at most 10 reference photos per video. Your uploaded originals are unchanged.")
    from video_music import settings
    return {**settings(opts), "mode": "runway", "model": model, "duration_seconds": int(duration), "aspect_ratio": aspect,
            "style": style, "product_info": info.strip(), "concept": concept.strip(), "audio": opts.get("audio", False)}


def photo_data(ids):
    from photo_uploads import LOCK as PHOTO_LOCK
    folder = Path(os.getenv("PHOTO_UPLOAD_DIR", str(Path(__file__).parent / "private-photos")))
    images = []
    with PHOTO_LOCK:
        for file_id in ids:
            src, meta = folder / (file_id + ".bin"), folder / (file_id + ".json")
            if not src.is_file() or not meta.is_file():
                raise ValueError("A photo is missing. Upload it again.")
            mime = json.loads(meta.read_text())["mime_type"]
            if not 0 < src.stat().st_size:
                raise ValueError("Invalid product photo.")
            images.append({"uri": "data:" + mime + ";base64," + base64.b64encode(src.read_bytes()).decode()})
    return images


def download(url, destination):
    # Only provider CDN origins, no redirects, no bearer token on media requests.
    parsed = urllib.parse.urlsplit(url)
    host = parsed.hostname or ""
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in {None, 443} or not (host == "storage.googleapis.com" or any(host.endswith("." + d) for d in ("cloudfront.net", "runwayml.com", "fal.media"))):
        raise ValueError("Unexpected video download host.")
    if any(not ipaddress.ip_address(addr[4][0]).is_global for addr in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)):
        raise ValueError("Unsafe video download address.")
    temporary = destination.with_suffix(".part")
    deadline = time.monotonic() + 120
    try:
        with urllib.request.build_opener(NoRedirect).open(url, timeout=30) as response, temporary.open("wb") as out:
            temporary.chmod(0o600)
            size = 0
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                size += len(chunk)
                if size > 80 * 1024 * 1024 or time.monotonic() > deadline:
                    raise ValueError("Video download exceeded size or time limit.")
                out.write(chunk)
        with temporary.open("rb") as check:
            header = check.read(32)
        if size < 100 or header[4:8] != b"ftyp":
            raise ValueError("Provider did not return an MP4 video.")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def submit(root, job, images):
    from promo_videos import write_status
    opts = job["options"]
    try:
        job.update(status="rendering", message=MODELS[opts.get("model", "product_ad")]["name"] + " is generating the video.")
        write_status(root, job)
        task = fal_task(root, job, images) if job.get("provider") == "fal" else product_ad_task(opts, images)
        task_id = task_value(task, "id", "")
        if not isinstance(task_id, str) or not re.fullmatch(r"[a-zA-Z0-9-]{1,100}", task_id):
            raise ValueError("Missing task ID.")
        urls = task_value(task, "output")
        if not isinstance(urls, list) or not urls or not isinstance(urls[0], str):
            raise ValueError("Missing output video.")
        destination = root / (job["id"] + ".mp4")
        download(urls[0], destination)
        if opts.get("music_preset", "none") != "none":
            import shutil
            from video_music import mix_music
            original = root / (job["id"] + ".source.mp4")
            shutil.copyfile(destination, original)
            original.chmod(0o600)
            mix_music(destination, destination, opts["music_preset"], opts.get("music_volume", .35))
        job.update(task_id=task_id, status="completed", progress=100, size=destination.stat().st_size,
                   download_url="/ext-api/promo-videos/" + job["id"] + "/file",
                   message="AI video ready. Review product accuracy before publishing.")
    except RuntimeError as error:
        job.update(status="failed", message=str(error) + " Install the runwayml package on the backend.")
    except ValueError as error:
        job.update(status="failed", message=str(error))
    except Exception as error:
        details = task_failure_details(error)
        http_status = getattr(error, "status_code", getattr(error, "code", None))
        if job.get("provider") == "fal":
            if not job.get("task_id") and http_status in {400, 401, 402, 403, 422, 429}:
                job.update(status="failed", message="fal rejected the request (HTTP " + str(http_status) + "). Check credentials, credits and inputs.")
            else:
                job.update(status="needs_review", message="fal task needs review. Resume to retrieve an existing request; check fal history if no request ID was received.")
            return
        rejected = {
            400: "Runway rejected the video inputs. Check reference photos (maximum 10), image format and ad settings.",
            401: "Runway rejected the API key. Update the server credential before trying again.",
            402: "Runway requires available API credits. Check billing before trying again.",
            403: "Runway denied access. Check the API key permissions.",
            422: "Runway rejected the video inputs. Check reference photos and ad settings.",
            429: "Runway rate limit reached. Wait before manually trying again.",
        }
        if http_status in rejected:
            job.update(status="failed", provider_http_status=http_status, message=rejected[http_status])
        elif details:
            job.update(status="failed", message="Runway generation failed: " + details)
        else:
            job.update(status="needs_review", message="Submission outcome is uncertain. Check Runway task history before creating another paid video.")
    finally:
        with LOCK:
            try:
                write_status(root, job)
            finally:
                ACTIVE.discard(job["id"])


def start(root, payload):
    from promo_videos import write_status
    try:
        opts = validate(payload)
        job_id = payload.get("request_id", "")
        if not isinstance(job_id, str) or not re.fullmatch(r"[a-f0-9]{40}", job_id):
            raise ValueError("A unique request ID is required.")
        with LOCK:
            existing = root / (job_id + ".json")
            if existing.exists():
                job = json.loads(existing.read_text())
                if job.get("provider") not in {"runway", "fal"}:
                    raise ValueError("Request ID is already in use.")
                return job, 200
            provider = MODELS[opts["model"]]["provider"]
            if provider == "fal" and not os.getenv("FAL_KEY", "").strip():
                return {"ok": False, "message": "fal is not configured. Set FAL_KEY in the backend environment."}, 503
            if provider == "runway" and not api_key():
                return {"ok": False, "message": "Runway is not configured. Set RUNWAYML_API_SECRET in the backend environment."}, 503
            credits = price(opts["model"], opts["duration_seconds"])
            if payload.get("confirm_paid") is not True or payload.get("approved_credits") != credits:
                return {"ok": False, "message": "Confirm the selected paid generation and photo transfer first.", "estimated_credits": credits}, 400
            jobs = [json.loads(p.read_text()) for p in root.glob("*.json")]
            if any(j.get("provider") in {"runway", "fal"} and j["status"] in {"submitting", "rendering", "needs_review"} for j in jobs):
                return {"ok": False, "message": "An AI video is pending. Resume it or check Runway history before starting another."}, 409
            if len(jobs) >= 100 or sum(p.stat().st_size for p in root.glob("*.mp4")) > 420 * 1024 * 1024:
                raise ValueError("Video storage is full. Remove an older video first.")
            images = photo_data(payload["photo_ids"])
            job = {"ok": True, "id": job_id, "provider": provider, "status": "submitting", "progress": 0,
                   "options": opts, "photo_count": len(images), "created_at": time.time(), "estimated_credits": credits,
                   "message": "Submitting to " + provider + ". Do not start another generation."}
            write_status(root, job)
            ACTIVE.add(job_id)
            threading.Thread(target=submit, args=(root, dict(job), images), daemon=True).start()
            return job, 202
    except ValueError as error:
        return {"ok": False, "message": str(error)}, 400
    except (TypeError, KeyError, OverflowError):
        return {"ok": False, "message": "Invalid AI video input. Check duration (4-15 seconds), product details, style and uploaded photos."}, 400

def refresh(root, job):
    return job


def poll(root, job):
    from promo_videos import write_status
    with LOCK:
        job = json.loads((root / (job["id"] + ".json")).read_text())
        if job.get("provider") == "fal" and job["status"] in {"rendering", "submitting", "needs_review"} and job["id"] not in ACTIVE and job.get("task_id"):
            ACTIVE.add(job["id"])
            job.update(status="rendering", message="Resuming existing fal request.")
            write_status(root, job)
            threading.Thread(target=submit, args=(root, dict(job), []), daemon=True).start()
        if job["status"] in {"submitting", "rendering"} and job["id"] not in ACTIVE:
            job.update(status="needs_review", message="Submission interrupted. Check provider task history before generating again.")
            write_status(root, job)
    return job
