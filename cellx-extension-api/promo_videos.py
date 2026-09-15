"""Admin-only, single-worker photo slideshows. No publishing or external URLs."""
from array import array
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import textwrap
import time
import wave

LOCK = threading.Lock()
WORKER = threading.BoundedSemaphore(1)
SIZES = {"9:16": (720, 1280), "16:9": (1280, 720), "1:1": (720, 720)}


def root_dir():
    root = Path(os.getenv("PROMO_VIDEO_DIR", str(Path(__file__).parent / "private-videos")))
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


def options_from(value):
    value = value or {}
    if not isinstance(value, dict):
        raise ValueError("Invalid video options.")
    try:
        duration = float(value.get("duration_seconds", 10))
    except (ValueError, TypeError):
        raise ValueError("Duration must be between 5 and 60 seconds.") from None
    if not math.isfinite(duration) or not 5 <= duration <= 60:
        raise ValueError("Duration must be between 5 and 60 seconds.")
    aspect = value.get("aspect_ratio", "9:16")
    if aspect not in SIZES:
        raise ValueError("Choose 9:16, 16:9 or 1:1.")
    from video_music import settings
    music = settings(value, 'default')
    title = str(value.get("title", "")).strip()
    if len(title) > 100:
        raise ValueError("Title must be 100 characters or fewer.")
    return {"duration_seconds": duration, "aspect_ratio": aspect, **music, "title": title}


def write_status(root, job):
    path = root / (job["id"] + ".json")
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(job), encoding="utf-8")
    temporary.chmod(0o600)
    os.replace(temporary, path)


def make_music(path, duration):
    # Original soft arpeggio; no third-party recordings or licensing dependency.
    rate = 22050
    notes = [261.63, 329.63, 392, 523.25, 220, 261.63, 329.63, 440]
    samples = array("h")
    for i in range(int(rate * duration)):
        t = i / rate
        phase = t % .75
        freq = notes[int(t / .75) % len(notes)]
        env = min(1, phase / .03) * math.exp(-phase * 3) * min(1, t / .5, max(0, (duration-t) / .8))
        samples.append(int(2600 * env * (math.sin(2*math.pi*freq*t) + .2*math.sin(4*math.pi*freq*t))))
    with wave.open(str(path), "wb") as handle:
        handle.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        handle.writeframes(samples.tobytes())


def render_job(root, job, work):
    try:
        deadline = time.monotonic() + 180
        uid = gid = None
        if os.name == "posix" and os.geteuid() == 0:
            import pwd
            user = pwd.getpwnam(os.getenv("SCRIPT_RUNNER_USER", "cellxrunner"))
            uid, gid = user.pw_uid, user.pw_gid
            os.chown(work, uid, gid)
            for file in work.iterdir():
                os.chown(file, uid, gid)
        def run(args):
            kwargs = {"user": uid, "group": gid, "extra_groups": []} if uid is not None else {}
            result = subprocess.run(args, cwd=work, env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
                                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    timeout=max(.1, min(60, deadline-time.monotonic())), **kwargs)
            if result.returncode:
                raise ValueError("Cannot decode a photo or render video. Use valid JPG, PNG or WebP images.")
            return result.stdout
        opts = job["options"]
        width, height = SIZES[opts["aspect_ratio"]]
        frames = round(opts["duration_seconds"] * 24)
        count = job["photo_count"]
        common = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-max_alloc", "67108864", "-threads", "1", "-filter_threads", "1"]
        if opts["title"]:
            (work / "title.txt").write_text(textwrap.fill(opts["title"], width=38), encoding="utf-8")
            (work / "title.txt").chmod(0o644)
        for index, photo in enumerate(sorted(work.glob("photo-*"))):
            probe = json.loads(run(["ffprobe", "-v", "error", "-max_alloc", "67108864", "-protocol_whitelist", "file,pipe", "-f", "image2", "-pattern_type", "none", "-i", photo.name, "-show_entries", "stream=width,height", "-of", "json"]))
            stream = probe["streams"][0]
            if not 0 < stream["width"] * stream["height"] <= 40000000:
                raise ValueError("Photo resolution exceeds 40 megapixels.")
            nframes = frames // count + (1 if index < frames % count else 0)
            duration = nframes / 24
            fade = min(.25, duration / 4)
            filters = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=white,setsar=1,format=yuv420p"
            if opts["title"]:
                filters += ",drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:textfile=title.txt:expansion=none:fontsize=24:fontcolor=white:box=1:boxcolor=black@0.65:boxborderw=12:x=(w-text_w)/2:y=h-text_h-50"
            filters += f",fade=t=in:st=0:d={fade},fade=t=out:st={duration-fade}:d={fade}"
            run(common + ["-protocol_whitelist", "file,pipe", "-f", "image2", "-pattern_type", "none", "-loop", "1", "-framerate", "24", "-i", photo.name,
                          "-vf", filters, "-frames:v", str(nframes), "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-threads", "1", "-an", f"part-{index:02}.mp4"])
            job["progress"] = round((index+1) / count * 85)
            write_status(root, job)
        (work / "parts.txt").write_text("".join(f"file 'part-{i:02}.mp4'\n" for i in range(count)))
        (work / "parts.txt").chmod(0o644)
        args = common + ["-f", "concat", "-safe", "1", "-i", "parts.txt"]
        if opts["music_preset"] != "none":
            from video_music import make_music as make_track
            make_track(work / "music.wav", frames/24, opts["music_preset"], opts.get("music_volume", .35))
            (work / "music.wav").chmod(0o644)
            args += ["-i", "music.wav", "-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", "96k"]
        args += ["-c:v", "copy", "-t", str(frames/24), "-movflags", "+faststart", "output.mp4"]
        run(args)
        output = work / "output.mp4"
        if not 100 < output.stat().st_size <= 80*1024*1024:
            raise ValueError("Video output size is outside the allowed range.")
        destination = root / (job["id"] + ".mp4")
        shutil.copyfile(output, destination)
        destination.chmod(0o600)
        job.update(status="completed", progress=100, size=destination.stat().st_size,
                   width=width, height=height, duration_seconds=frames/24,
                   download_url="/ext-api/promo-videos/"+job["id"]+"/file",
                   message="Video ready to preview. Nothing has been published.")
    except Exception as error:
        job.update(status="failed", message=str(error) if isinstance(error, ValueError) else "Video render failed or timed out. Please retry.")
    finally:
        try:
            write_status(root, job)
        finally:
            shutil.rmtree(work, ignore_errors=True)
            WORKER.release()


def video_request(method, path, payload):
    root = root_dir()
    if method == 'POST' and path == '/promo-videos/product-brief':
        from product_briefs import generate
        return generate(payload)
    music_match = re.fullmatch(r"/promo-videos/([a-f0-9]{40})/music", path)
    if music_match and method == 'POST':
        from video_music import settings, mix_music
        if not WORKER.acquire(blocking=False):
            return {'ok': False, 'message': 'Another video is processing.'}, 409
        try:
            config = settings(payload)
            meta = root / (music_match[1] + '.json')
            if not meta.is_file():
                return {'ok': False, 'message': 'Video not found.'}, 404
            old = json.loads(meta.read_text())
            if old.get('status') != 'completed':
                return {'ok': False, 'message': 'Wait for the video to finish.'}, 409
            source_id = old.get('music_source_id', old['id'])
            source = root / (source_id + '.mp4')
            clean_source = root / (source_id + '.source.mp4')
            if clean_source.is_file():
                source = clean_source
            if not source.is_file():
                return {'ok': False, 'message': 'Original video is missing.'}, 404
            if len(list(root.glob('*.json'))) >= 100 or sum(p.stat().st_size for p in root.glob('*.mp4')) > 420*1024*1024:
                raise ValueError('Video storage is full.')
            new_id = secrets.token_hex(20)
            destination = root / (new_id + '.mp4')
            if config['music_preset'] == 'none':
                shutil.copyfile(source, destination)
                destination.chmod(0o600)
            else:
                mix_music(source, destination, config['music_preset'], config['music_volume'])
            job = {**old, 'id': new_id, 'music_source_id': source_id, 'created_at': time.time(),
                   'options': {**old.get('options', {}), **config}, 'size': destination.stat().st_size,
                   'download_url': '/ext-api/promo-videos/' + new_id + '/file', 'message': 'Background music applied. Original video retained.'}
            write_status(root, job)
            return job, 201
        except (ValueError, TypeError, OSError, subprocess.SubprocessError):
            return {'ok': False, 'message': 'Unable to apply music. Original video retained.'}, 400
        finally:
            WORKER.release()
    if method == "GET" and path == "/promo-videos/providers":
        from runway_videos import provider_info
        return provider_info(), 200
    if method == "POST" and path == "/promo-videos":
        if isinstance(payload, dict) and isinstance(payload.get("options"), dict) and payload["options"].get("mode") == "runway":
            from runway_videos import start
            return start(root, payload)
        try:
            if not isinstance(payload, dict):
                raise ValueError("Invalid request.")
            ids = payload.get("photo_ids")
            if not isinstance(ids, list) or not 1 <= len(ids) <= 10 or any(not isinstance(i,str) or not re.fullmatch(r"[a-f0-9]{40}", i) for i in ids):
                raise ValueError("Select 1 to 10 uploaded photos.")
            options = options_from(payload.get("options"))
            if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
                return {"ok": False, "message": "Video renderer is not installed."}, 503
            if not WORKER.acquire(blocking=False):
                return {"ok": False, "message": "Another video is rendering. Please retry when it finishes."}, 409
            work = None
            try:
                if sum(p.stat().st_size for p in root.glob("*.mp4")) > 420*1024*1024 or len(list(root.glob("*.json"))) >= 100:
                    raise ValueError("Video storage is full. Remove an older video first.")
                work = Path(tempfile.mkdtemp(prefix="cellx-slideshow-"))
                work.chmod(0o700)
                photos = Path(os.getenv("PHOTO_UPLOAD_DIR", str(Path(__file__).parent / "private-photos")))
                from photo_uploads import LOCK as PHOTO_LOCK
                with PHOTO_LOCK:
                    for index, file_id in enumerate(ids):
                        src = photos / (file_id + ".bin")
                        meta = photos / (file_id + ".json")
                        if not src.is_file() or not meta.is_file():
                            raise ValueError("A photo is missing. Upload it again.")
                        mime = json.loads(meta.read_text())["mime_type"]
                        extension = {"image/png":"png", "image/jpeg":"jpg", "image/webp":"webp"}[mime]
                        shutil.copyfile(src, work / f"photo-{index:02}.{extension}")
                job = {"ok":True, "id":secrets.token_hex(20), "status":"rendering", "progress":0,
                       "photo_count":len(ids), "options":options, "created_at":time.time()}
                write_status(root,job)
                threading.Thread(target=render_job,args=(root,dict(job),work),daemon=True).start()
                return job,202
            except Exception:
                if work: shutil.rmtree(work)
                WORKER.release()
                raise
        except (ValueError, KeyError, TypeError) as error:
            return {"ok":False, "message":str(error)},400
    match = re.fullmatch(r"/promo-videos/([a-f0-9]{40})(/file)?",path)
    if not match:
        return {"ok":False,"message":"Not found."},404
    file_id, binary = match.groups()
    meta = root / (file_id+".json")
    if not meta.is_file():
        return {"ok":False,"message":"Video not found."},404
    job = json.loads(meta.read_text())
    if job.get("provider") == "runway" and method == "GET" and not binary:
        from runway_videos import poll
        job = poll(root, job)
    if job.get("provider") != "runway" and job["status"] == "rendering" and time.time()-job["created_at"] > 240:
        job.update(status="failed",message="Render interrupted. Please generate the video again.")
    if method == "DELETE" and not binary:
        if job["status"] in {"rendering", "submitting"}:
            return {"ok":False,"message":"Wait for rendering to finish."},409
        (root/(file_id+".mp4")).unlink(missing_ok=True)
        (root/(file_id+".source.mp4")).unlink(missing_ok=True)
        meta.unlink(missing_ok=True)
        return {"ok":True},200
    if method != "GET":
        return {"ok":False,"message":"Method not allowed."},405
    if binary:
        file = root/(file_id+".mp4")
        if job["status"] != "completed" or not file.is_file():
            return {"ok":False,"message":"Video is not ready."},409
        return file,200
    return job,200
