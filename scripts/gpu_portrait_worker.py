"""Outbound-only Windows GPU worker. Config/credentials are never logged."""
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import requests
from gpu_storyboard_limits import MAX_RESULT_BYTES

BASE = Path(__file__).resolve().parent
CONFIG = json.loads((BASE / 'worker-config.json').read_text(encoding='utf-8-sig'))
ROOT = Path(CONFIG['model_root'])
API = CONFIG['api_url'].rstrip('/')
if not API.startswith('https://'): raise ValueError('HTTPS required')
TOKEN = Path(CONFIG['token_file']).read_text().strip()
PYTHON = str(Path(CONFIG['python']))
os.environ['PATH'] = CONFIG.get('ffmpeg_dir', 'C:/ffmpeg/bin') + os.pathsep + os.environ['PATH']
os.environ['PYTHONUTF8'] = '1'
log = logging.getLogger('gpu-worker')
log.setLevel(logging.INFO)
handler = RotatingFileHandler(BASE/'worker.log', maxBytes=2_000_000, backupCount=3, encoding='utf-8')
handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
log.addHandler(handler)


def session():
    s = requests.Session()
    s.headers['Authorization'] = 'Bearer ' + TOKEN
    return s


def request(s, action, data):
    response = s.post(API + '/gpu-worker/' + action, json=data, timeout=(15, 40), allow_redirects=False)
    response.raise_for_status()
    return response.json()


def process(claim):
    job, lease = claim['job'], claim['lease']
    job_id = job['id']
    import re
    if not re.fullmatch('[a-f0-9]{40}', job_id) or not re.fullmatch('[a-f0-9]{48}', lease): raise ValueError('Invalid job identity')
    run = BASE/'jobs'/job_id/lease[:12]
    run.mkdir(parents=True, exist_ok=True)
    state = {'progress': 5, 'last_ok': time.monotonic(), 'lost': False}
    stop = threading.Event()
    def heartbeat():
        with session() as s:
            while not stop.wait(20):
                try:
                    request(s, 'heartbeat', {'id': job_id, 'lease': lease, 'progress': state['progress']})
                    state['last_ok'] = time.monotonic()
                except requests.HTTPError as e:
                    if e.response.status_code in {401, 409}: state['lost'] = True; return
                except requests.RequestException: pass
                if time.monotonic()-state['last_ok'] > 135: state['lost'] = True; return
    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    def command(args, timeout, cwd=None):
        with (run/'render.log').open('ab') as out:
            p = subprocess.Popen(args, cwd=cwd or ROOT, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT)
            started = time.monotonic()
            try:
                while p.poll() is None:
                    if state['lost']: raise RuntimeError('Lease lost')
                    if time.monotonic()-started > timeout: raise TimeoutError('Render timeout')
                    time.sleep(1)
                if p.returncode: raise RuntimeError('Render command failed')
            finally:
                if p.poll() is None: p.kill(); p.wait()
    error_code = 'render_failed'
    try:
        with session() as s:
            opts = job['options']
            def download(index):
                response=s.get(API+'/gpu-worker/photo',headers={'X-Job-Id':job_id,'X-Job-Lease':lease,'X-Photo-Index':str(index)},timeout=(15,60),allow_redirects=False)
                response.raise_for_status()
                if len(response.content)>20*1024*1024:raise ValueError('Photo too large')
                source=run/f'input-{index}.photo';source.write_bytes(response.content);return source
            if opts.get('mode')=='portrait_storyboard':
                from gpu_storyboard_render import render
                def revise(timing):
                    response=s.post(API+'/gpu-worker/revise-storyboard',json={'id':job_id,'lease':lease,'attempt':timing['revisions']+1,'scene_seconds':timing['scene_seconds']},timeout=(15,170),allow_redirects=False)
                    response.raise_for_status();return response.json()
                target=render(job,run,PYTHON,command,download,state,revise)
            else:
                source = download(0)
                voices = {'zh-male':'zh-CN-YunxiNeural', 'zh-female':'zh-CN-XiaoxiaoNeural', 'en-male':'en-US-GuyNeural', 'en-female':'en-US-JennyNeural'}
                command([PYTHON, '-m', 'edge_tts', '--voice', voices[opts['voice']], '--text', opts['narration'], '--write-media', str(run/'speech.mp3')], 120)
                command(['ffmpeg', '-v', 'error', '-y', '-i', str(run/'speech.mp3'), '-ar', '16000', '-ac', '1', str(run/'speech.wav')], 60)
                import wave
                with wave.open(str(run/'speech.wav')) as wav: duration = wav.getnframes()/wav.getframerate()
                if not 0 < duration <= 20: error_code = 'audio_too_long'; raise ValueError('Audio exceeds limit')
                error_code = 'invalid_photo'
                from PIL import Image, ImageOps
                with Image.open(source) as image:
                    if image.width*image.height > 40_000_000: raise ValueError('Image too large')
                    image = ImageOps.exif_transpose(image).convert('RGB')
                    image.thumbnail((1024,1024))
                    image.save(run/'portrait.png')
                error_code = 'render_failed'
                state['progress'] = 25
                command([PYTHON, 'inference.py', '--source_image', str(run/'portrait.png'), '--driven_audio', str(run/'speech.wav'), '--result_dir', str(run), '--preprocess', 'full', '--still', '--size', '256', '--batch_size', '2', '--expression_scale', '0.65'], 1800)
                videos = sorted(run.glob('*.mp4'), key=lambda p:p.stat().st_mtime)
                if not videos: raise RuntimeError('No render result')
                width, height = {'9:16':(720,1280), '16:9':(1280,720), '1:1':(720,720)}[opts['aspect_ratio']]
                state['progress'] = 90
                target = run/'output.mp4'
                command(['ffmpeg','-v','error','-y','-i',str(videos[-1]),'-vf',f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1','-c:v','libx264','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart',str(target)], 120)
            if not 100 < target.stat().st_size <= MAX_RESULT_BYTES: raise ValueError('Output size invalid')
            result_headers={'Content-Type':'video/mp4','X-Job-Id':job_id,'X-Job-Lease':lease}
            if (run/'render-summary.json').exists():result_headers['X-Video-Metadata']=(run/'render-summary.json').read_text().replace('\n','')
            for attempt in range(5):
                if state['lost']: raise RuntimeError('Lease lost')
                try:
                    with target.open('rb') as file:
                        response = s.post(API+'/gpu-worker/result', data=file, headers=result_headers, timeout=(15,240), allow_redirects=False)
                    response.raise_for_status()
                    break
                except requests.RequestException:
                    if attempt == 4: raise
                    time.sleep(5)
            log.info('Completed job %s on RTX5090', job_id)
    except Exception as exc:
        if type(exc).__name__=='StoryboardTimingError':error_code='storyboard_timing'
        log.warning('Job %s failed: %s / %s', job_id, error_code, type(exc).__name__)
        if not state['lost']:
            try:
                with session() as s: request(s,'fail',{'id':job_id,'lease':lease,'code':error_code,'timing':getattr(exc,'timing',{}),'retryable':isinstance(exc,(requests.RequestException,TimeoutError))})
            except requests.RequestException: pass
    finally:
        stop.set(); thread.join(timeout=45)


def main():
    import torch
    if not torch.cuda.is_available() or '5090' not in torch.cuda.get_device_name(0):
        raise RuntimeError('RTX5090 CUDA device is required; no CPU fallback')
    # An OS-held lock prevents a task restart from running a second worker.
    import msvcrt
    lock = (BASE/'worker.lock').open('a+b')
    lock.seek(0); lock.write(b'0'); lock.flush(); lock.seek(0)
    try: msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError: return
    log.info('Worker started; model execution is local to RTX5090')
    with session() as s:
        while True:
            try:
                claim = request(s, 'claim', {'capabilities':['portrait_storyboard_v1','portrait_storyboard_300_v2']})
                if claim.get('job'): process(claim)
                else: time.sleep(5)
            except requests.RequestException:
                log.warning('Queue connection unavailable; retrying')
                time.sleep(15)
            except Exception as exc:
                log.warning('Worker recovered from %s', type(exc).__name__)
                time.sleep(15)


if __name__ == '__main__': main()
