"""Durable outbound-GPU queue. This module never executes a renderer or a model."""
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from gpu_storyboard_limits import MAX_SECONDS, MAX_NARRATION_CHARS, MAX_SCENE_CHARS, MAX_RESULT_BYTES, valid_duration

ID = re.compile(r'^[a-f0-9]{40}$')
LEASE_SECONDS = 180
MAX_ATTEMPTS = 3
MAX_RESULT = MAX_RESULT_BYTES


def root_dir():
    root = Path(os.getenv('GPU_JOB_DIR', str(Path(__file__).parent / 'private-gpu-jobs')))
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


@contextmanager
def connect():
    root = root_dir()
    db = sqlite3.connect(root / 'queue.sqlite3', timeout=20)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, data TEXT NOT NULL, lease TEXT, deadline REAL DEFAULT 0)')
    db.execute('CREATE TABLE IF NOT EXISTS worker (id INTEGER PRIMARY KEY CHECK(id=1), seen REAL)')
    db.execute('CREATE TABLE IF NOT EXISTS worker_capabilities (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT)')
    try:
        with db:
            yield db
    finally:
        db.close()


def save(db, job):
    db.execute('UPDATE jobs SET data=? WHERE id=?', (json.dumps(job), job['id']))


def reap(db):
    for row in db.execute('SELECT * FROM jobs WHERE deadline>0 AND deadline<?', (time.time(),)).fetchall():
        job = json.loads(row['data'])
        if job['status'] == 'rendering':
            exhausted = job['attempts'] >= MAX_ATTEMPTS
            job.update(status='failed' if exhausted else 'queued', progress=0,
                       message='GPU worker disconnected; retry limit reached. / 工作机离线，重试次数已用完。' if exhausted else 'Waiting for GPU worker to reconnect. / 等待5090重新连接。')
            save(db, job)
            db.execute('UPDATE jobs SET lease=NULL, deadline=0 WHERE id=?', (job['id'],))


def readiness():
    with connect() as db:
        row = db.execute('SELECT seen FROM worker WHERE id=1').fetchone()
        caps = db.execute('SELECT data FROM worker_capabilities WHERE id=1').fetchone()
    seen = row['seen'] if row else None
    return {'configured': token_path().is_file(), 'online': bool(seen and time.time()-seen < 65), 'last_seen': seen,
            'compute': 'Windows RTX 5090', 'max_seconds': 20, 'storyboard_max_seconds':MAX_SECONDS,
            'storyboard_ready':bool(seen and time.time()-seen<65 and caps and 'portrait_storyboard_v1' in json.loads(caps['data']))}


def start(payload):
    try:
        opts = payload.get('options', {})
        ids = payload.get('photo_ids', [])
        job_id = payload.get('request_id', '')
        script = opts.get('narration', '')
        voice = opts.get('voice', 'zh-male')
        aspect = opts.get('aspect_ratio', '9:16')
        multi=opts.get('mode')=='portrait_storyboard'
        if not ID.fullmatch(job_id): raise ValueError('A valid request_id is required.')
        if not isinstance(ids, list) or not (2<=len(ids)<=10 if multi else len(ids)==1) or any(not isinstance(i,str) or not ID.fullmatch(i) for i in ids) or len(set(ids))!=len(ids):
            raise ValueError('Choose one uploaded portrait. / 请选择一张人像照片。')
        if not isinstance(script, str) or not 1 <= len(script.strip()) <= (MAX_NARRATION_CHARS if multi else 100):
            raise ValueError('Use 1–100 characters of narration, at most 20 seconds. / 口播限100字、20秒以内。')
        if voice not in {'zh-male', 'zh-female', 'en-male', 'en-female'} or aspect not in {'9:16', '16:9', '1:1'}:
            raise ValueError('Invalid voice or aspect ratio.')
        normalized = {'mode': 'portrait', 'narration': script.strip(), 'voice': voice, 'aspect_ratio': aspect}
        if multi:
            portrait=opts.get('portrait_photo_id');scenes=opts.get('storyboard_scenes');duration=opts.get('duration_seconds')
            if portrait not in ids or not isinstance(scenes,list) or len(scenes)!=len(ids):raise ValueError('Choose the portrait and provide narration for every uploaded photo. / 请选择人像并为每张图片填写分镜口播。')
            ordered=[portrait]+[i for i in ids if i!=portrait]
            if [s.get('photo_id') if isinstance(s,dict) else None for s in scenes]!=ordered:raise ValueError('Scene order must be portrait first, then all other uploaded photos in order.')
            lines=[s.get('narration') for s in scenes]
            if any(not isinstance(s,str) or not s.strip() or len(s)>MAX_SCENE_CHARS for s in lines) or len(lines[0])>100 or len('\n'.join(lines))>MAX_NARRATION_CHARS:raise ValueError('Opening at most 100 characters, each later scene at most 6000, total at most 10000.')
            if not valid_duration(duration):raise ValueError('Choose 15–300 seconds (5 minutes) for the complete video; the talking opening stays within 20 seconds.')
            normalized.update(mode='portrait_storyboard',portrait_photo_id=portrait,duration_seconds=duration,scenes=[{'photo_id':i,'narration':s.strip()} for i,s in zip(ordered,lines)],narration='\n'.join(s.strip() for s in lines))
            ids=ordered
            from gpu_copy_timing import signature
            proof=opts.get('ai_draft_signature','')
            if isinstance(proof,str) and proof and hmac.compare_digest(proof,signature(ids,portrait,duration,voice,normalized['scenes'])):
                normalized['auto_timing_revision']=True
                draft=(opts.get('product_analysis') or {}).get('draft') or {}
                context={'product_notes':str(opts.get('product_info',''))[:2500],
                         'visual_evidence':[{'photo_id':s.get('photo_id'),'visual_description':str(s.get('visual_description',''))[:240]} for s in draft.get('scenes',scenes) if isinstance(s,dict) and s.get('photo_id') in ids]}
                normalized['copy_context']=context
        fingerprint = hashlib.sha256(json.dumps([ids, normalized], sort_keys=True).encode()).hexdigest()
        with connect() as db:
            db.execute('BEGIN IMMEDIATE')
            prior = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
            if prior:
                if prior['fingerprint'] != fingerprint: return {'ok': False, 'message': 'Request ID already used with different content.'}, 409
                return json.loads(prior['data']), 200
            reap(db)
            if db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0] >= 100:
                raise ValueError('GPU video storage is full. Remove an older video first.')
            if sum(p.stat().st_size for p in root_dir().glob('*.mp4')) > 420*1024*1024:
                raise ValueError('GPU video storage is full.')
            photos = Path(os.getenv('PHOTO_UPLOAD_DIR', str(Path(__file__).parent / 'private-photos')))
            from photo_uploads import LOCK
            with LOCK:
                raws=[]
                for photo_id in ids:
                    source=photos/(photo_id+'.bin')
                    if not source.is_file() or not 0<source.stat().st_size<=20*1024*1024:raise ValueError('Photo missing or larger than 20MB.')
                    raw=source.read_bytes()
                    if not (raw.startswith(b'\xff\xd8\xff') or raw.startswith(b'\x89PNG\r\n\x1a\n') or (raw[:4]==b'RIFF' and raw[8:12]==b'WEBP')):raise ValueError('Use JPG, PNG or WebP photos.')
                    raws.append(raw)
                if sum(map(len,raws))>100*1024*1024:raise ValueError('Selected photos exceed 100MB.')
            for index,raw in enumerate(raws):
                image=photo_path(job_id,index);image.write_bytes(raw);image.chmod(0o600)
            job = {'ok': True, 'id': job_id, 'provider': 'portrait', 'status': 'queued', 'progress': 0,
                   'created_at': time.time(), 'options': normalized, 'photo_count': len(ids), 'photo_ids':ids, 'attempts': 0,
                   'message': 'Queued for home RTX 5090. / 已排队，等待家中5090生成。', 'compute': 'Windows RTX 5090'}
            db.execute('INSERT INTO jobs(id,fingerprint,data) VALUES (?,?,?)', (job_id, fingerprint, json.dumps(job)))
        return job, 202
    except (ValueError, TypeError, AttributeError) as exc:
        return {'ok': False, 'message': str(exc)}, 400


def video_request(method, job_id, binary=False):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        reap(db)
        row = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row: return None
        job = json.loads(row['data'])
        if method == 'DELETE' and not binary:
            if job['status'] in {'queued', 'rendering'}: return {'ok': False, 'message': 'Wait for GPU generation to finish.'}, 409
            db.execute('DELETE FROM jobs WHERE id=?', (job_id,))
            (root_dir()/(job_id+'.mp4')).unlink(missing_ok=True)
            for i in range(job.get('photo_count',1)):photo_path(job_id,i).unlink(missing_ok=True)
            return {'ok': True}, 200
        if method != 'GET': return {'ok': False, 'message': 'Method not allowed.'}, 405
        if binary:
            if job['status'] != 'completed': return {'ok': False, 'message': 'Video is not ready.'}, 409
            return root_dir() / (job_id + '.mp4'), 200
        return {**job, 'worker': readiness()}, 200


def token_path():
    return Path(os.getenv('GPU_WORKER_TOKEN_FILE', str(Path(__file__).parent / 'gpu-worker-token')))


def photo_path(job_id,index):
    if not ID.fullmatch(job_id) or not isinstance(index,int) or not 0<=index<10:raise ValueError('Invalid image index.')
    return root_dir()/(job_id+('.photo' if index==0 else f'.photo-{index}'))


def authorized(headers):
    try: expected = token_path().read_text().strip()
    except OSError: return False
    return bool(expected) and hmac.compare_digest(headers.get('Authorization', ''), 'Bearer ' + expected)


def lease_row(db, job_id, lease):
    row = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
    if not row or not lease or not hmac.compare_digest(row['lease'] or '', lease):
        raise ValueError('Stale job lease.')
    job = json.loads(row['data'])
    if job['status'] != 'completed' and row['deadline'] < time.time(): raise ValueError('Expired job lease.')
    return job


def worker_action(action, payload):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('INSERT OR REPLACE INTO worker(id,seen) VALUES(1,?)', (time.time(),))
        reap(db)
        if action == 'claim':
            capabilities=payload.get('capabilities',[])
            if not isinstance(capabilities,list):capabilities=[]
            db.execute('INSERT OR REPLACE INTO worker_capabilities(id,data) VALUES(1,?)',(json.dumps([c for c in capabilities if c in {'portrait_storyboard_v1','portrait_storyboard_300_v2'}]),))
            rows = db.execute('SELECT * FROM jobs ORDER BY rowid').fetchall()
            if any(json.loads(row['data'])['status'] == 'rendering' for row in rows): return {'ok': True, 'job': None}
            for row in rows:
                job = json.loads(row['data'])
                if job['status'] != 'queued': continue
                if job['options'].get('mode')=='portrait_storyboard' and 'portrait_storyboard_v1' not in capabilities:continue
                if job['options'].get('mode')=='portrait_storyboard' and job['options']['duration_seconds']>60 and 'portrait_storyboard_300_v2' not in capabilities:continue
                lease = secrets.token_hex(24)
                job.update(status='rendering', attempts=job['attempts']+1, progress=3,
                           message='RTX 5090 preparing narration. / 5090正在准备口播。')
                save(db, job)
                db.execute('UPDATE jobs SET lease=?,deadline=? WHERE id=?', (lease, time.time()+LEASE_SECONDS, job['id']))
                return {'ok': True, 'job': job, 'lease': lease}
            return {'ok': True, 'job': None}
        job = lease_row(db, payload.get('id'), payload.get('lease'))
        if action == 'heartbeat':
            if job['status'] == 'rendering':
                job['progress'] = max(job['progress'], min(95, int(payload.get('progress', 5))))
                job['message'] = 'RTX 5090 generating video. / 家中5090正在生成视频。'
                save(db, job)
                db.execute('UPDATE jobs SET deadline=? WHERE id=?', (time.time()+LEASE_SECONDS, job['id']))
        elif action == 'fail':
            if job['status'] != 'rendering': return {'ok': True}
            retry = bool(payload.get('retryable')) and job['attempts'] < MAX_ATTEMPTS
            code = payload.get('code')
            message = {'audio_too_long': 'Narration exceeds 20 seconds; shorten it. / 口播超过20秒，请缩短。',
                       'storyboard_timing':'Opening must be within 20 seconds and total speech near the selected duration. Regenerate or edit the storyboard. / 开场须在20秒内，整段口播需接近所选时长，请重新生成或编辑分镜。',
                       'invalid_photo': 'Unable to process portrait. Use a clear front-facing photo. / 请换清晰正面人像。'}.get(code, 'GPU generation failed; please retry. / 5090生成失败，请重试。')
            job.update(status='queued' if retry else 'failed', message=message, progress=0)
            if code=='storyboard_timing':
                timing=payload.get('timing',{})
                keys=['opening_seconds','raw_seconds','target_seconds','adjusted_seconds','adjusted_opening_seconds','tempo','revisions']
                if isinstance(timing,dict) and all(type(timing.get(k)) in (int,float) and math.isfinite(timing[k]) and 0<=timing[k]<=6000 for k in keys):
                    job['timing']={k:timing[k] for k in keys}
                    job['message']=f"实测开场 {timing['opening_seconds']:.2f} 秒，整段 {timing['raw_seconds']:.2f} 秒，目标 {timing['target_seconds']:.0f} 秒；小幅调速后开场 {timing['adjusted_opening_seconds']:.2f} 秒、整段 {timing['adjusted_seconds']:.2f} 秒，仍不符合时长。原文案已保留。点击“AI 写分镜口播”，检查后点击“使用这份AI草稿”再生成；或编辑口播后重试。"
            save(db, job)
            db.execute('UPDATE jobs SET lease=NULL,deadline=0 WHERE id=?', (job['id'],))
        else: raise ValueError('Unknown worker action.')
        return {'ok': True}


def worker_http(handler):
    """Dedicated bearer token, bounded bodies; no admin or model credentials on GPU host."""
    from urllib.parse import urlparse
    status, body = 200, {'ok': True}
    try:
        if not authorized(handler.headers):
            status, body = 401, {'ok': False, 'message': 'Worker authentication required.'}
        else:
            path = urlparse(handler.path).path.removeprefix('/ext-api')
            action = path.removeprefix('/gpu-worker/')
            if action == 'result' and handler.command == 'POST':
                length = int(handler.headers.get('Content-Length', '0'))
                job_id, lease = handler.headers.get('X-Job-Id', ''), handler.headers.get('X-Job-Lease', '')
                if not ID.fullmatch(job_id) or handler.headers.get('Transfer-Encoding') or not 100 < length <= MAX_RESULT: raise ValueError('Invalid result.')
                with connect() as db: expected_job=lease_row(db, job_id, lease)
                metadata={}
                if expected_job['options'].get('mode')=='portrait_storyboard':
                    raw_meta=handler.headers.get('X-Video-Metadata','')
                    if len(raw_meta)>4096:raise ValueError('Invalid metadata.')
                    metadata=json.loads(raw_meta)
                    durations=metadata.get('scene_durations',[])
                    if metadata.get('photo_ids')!=expected_job['photo_ids'] or len(durations)!=expected_job['photo_count'] or any(not isinstance(d,(int,float)) or not math.isfinite(d) or d<=0 for d in durations):raise ValueError('Invalid scene metadata.')
                    if durations[0]>20 or not 0<metadata.get('duration_seconds',0)<=MAX_SECONDS+.2:raise ValueError('Invalid video duration.')
                    metadata={k:metadata[k] for k in ['duration_seconds','scene_durations','photo_ids','width','height','narration_tempo']}
                tmp = root_dir() / (job_id + '.' + secrets.token_hex(8) + '.upload')
                try:
                    handler.connection.settimeout(180)
                    with tmp.open('wb') as out:
                        remaining = length
                        while remaining:
                            chunk = handler.rfile.read(min(65536, remaining))
                            if not chunk: raise ValueError('Incomplete upload.')
                            out.write(chunk); remaining -= len(chunk)
                    with tmp.open('rb') as stream:
                        if stream.read(12)[4:8] != b'ftyp': raise ValueError('Invalid MP4.')
                    with connect() as db:
                        db.execute('BEGIN IMMEDIATE')
                        job = lease_row(db, job_id, lease)
                        if job['status'] != 'completed':
                            tmp.chmod(0o600)
                            os.replace(tmp, root_dir() / (job_id + '.mp4'))
                            job.update(status='completed', progress=100, size=length,
                                       download_url='/ext-api/promo-videos/' + job_id + '/file',
                                       message='Generated on home RTX 5090. / 已由家中5090生成。')
                            job.update(metadata)
                            save(db, job)
                            db.execute('UPDATE jobs SET deadline=0 WHERE id=?', (job_id,))
                    body = {'ok': True, 'id': job_id}
                finally: tmp.unlink(missing_ok=True)
            elif action == 'photo' and handler.command == 'GET':
                job_id = handler.headers.get('X-Job-Id', '')
                index=int(handler.headers.get('X-Photo-Index','0'))
                with connect() as db:job=lease_row(db, job_id, handler.headers.get('X-Job-Lease', ''))
                if not 0<=index<job.get('photo_count',1):raise ValueError('Invalid image index.')
                body = photo_path(job_id,index)
            elif handler.command == 'POST' and action in {'claim', 'heartbeat', 'fail','revise-storyboard'}:
                length = int(handler.headers.get('Content-Length', '0'))
                if handler.headers.get('Transfer-Encoding') or not 0 < length <= 8192: raise ValueError('Invalid worker body.')
                payload = json.loads(handler.rfile.read(length))
                if not isinstance(payload, dict): raise ValueError('Invalid worker body.')
                if action=='revise-storyboard':
                    from gpu_copy_timing import revise
                    body=revise(payload)
                else:body = worker_action(action, payload)
            else: status, body = 404, {'ok': False}
    except (ValueError, TypeError, KeyError) as error:
        handler.log_message('GPU request validation: %s: %s',type(error).__name__,str(error)[:160])
        status, body = 409, {'ok': False, 'message': 'Invalid request or stale lease.'}
    except Exception: status, body = 503, {'ok': False, 'message': 'GPU queue unavailable.'}
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/octet-stream' if isinstance(body, Path) else 'application/json')
    handler.send_header('Cache-Control', 'no-store')
    handler.send_header('Connection', 'close')
    handler.close_connection = True
    raw = body.read_bytes() if isinstance(body, Path) else json.dumps(body).encode()
    handler.send_header('Content-Length', str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)
