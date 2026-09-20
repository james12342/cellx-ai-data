"""Photo-first advertising pipeline, inspired by MoneyPrinterTurbo's modular workflow.

Original implementation using our existing private assets and FFmpeg renderer.
One script line per scene; narration duration drives the subtitle timeline.
"""
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import time

LOCK = threading.RLock()
ACTIVE = set()
VOICES = {'zh-female': 'zh-CN-XiaoxiaoNeural', 'zh-male': 'zh-CN-YunxiNeural',
          'en-female': 'en-US-JennyNeural', 'en-male': 'en-US-GuyNeural', 'none': None}


def tts_python():
    return os.getenv('ECONOMY_TTS_PYTHON', '/opt/cellx-economy-venv/bin/python')


def readiness():
    return {'renderer': bool(shutil.which('ffmpeg') and shutil.which('ffprobe')),
            'voice': Path(tts_python()).is_file(), 'script_ai': bool(os.getenv('OPENAI_API_KEY'))}


def compatible_voice(voice, script):
    chinese=len(re.findall(r'[\u4e00-\u9fff]',script))
    latin=len(re.findall(r'[A-Za-z]',script))
    if voice in {'en-female','en-male'} and chinese>=max(2,latin/2):
        return voice.replace('en-','zh-')
    return voice


def validate(payload):
    from video_music import settings
    from promo_videos import SIZES
    opts = payload.get('options', {})
    if not isinstance(opts, dict): raise ValueError('Invalid economy options.')
    script = opts.get('narration', '')
    if not isinstance(script, str) or not 1 <= len(script.strip()) <= 1200:
        raise ValueError('Enter a narration script of 1–1200 characters, one scene per line.')
    lines = [s.strip() for s in script.splitlines() if s.strip()]
    if not 1 <= len(lines) <= 10:
        raise ValueError('Use 1–10 scenes, at most 1200 characters in total.')
    duration = opts.get('duration_seconds', 30)
    if isinstance(duration, bool) or not isinstance(duration, (float, int)) or not math.isfinite(duration) or duration != int(duration) or not 15 <= duration <= 60:
        raise ValueError('Choose a duration from 15 to 60 whole seconds.')
    voice, aspect = opts.get('voice', 'zh-female'), opts.get('aspect_ratio', '9:16')
    if voice not in VOICES or aspect not in SIZES: raise ValueError('Invalid voice or aspect ratio.')
    ids = payload.get('photo_ids')
    if not isinstance(ids, list) or not 1 <= len(ids) <= 10 or any(not isinstance(i, str) or not re.fullmatch('[a-f0-9]{40}', i) for i in ids):
        raise ValueError('Select 1–10 uploaded product photos.')
    clip = opts.get('clip_id', '')
    if not isinstance(clip, str) or (clip and not re.fullmatch('[a-f0-9]{40}', clip)):
        raise ValueError('Invalid opening video.')
    texts = {}
    for key, limit in [('brand', 45), ('cta', 80)]:
        value = opts.get(key, '')
        if not isinstance(value, str) or len(value) > limit: raise ValueError('Brand or call to action is too long.')
        texts[key] = value.strip()
    voice=compatible_voice(voice,script)
    fit=opts.get('fit_narration',False)
    if not isinstance(fit,bool):raise ValueError('Invalid narration timing option.')
    return dict(mode='economy', duration_seconds=int(duration), voice=voice, aspect_ratio=aspect,fit_narration=fit,
                narration='\n'.join(lines), scenes=lines, clip_id=clip, **texts, **settings(opts))


def ass_text(text, width):
    # ASS override tags and escape sequences must never be interpreted as input.
    text = text.replace('\\', '／').replace('{', '（').replace('}', '）').replace('\r', ' ').replace('\n', ' ')
    lines, line, size = [], '', 0
    for word in re.findall(r'[\u2e80-\uffff]|[^\u2e80-\uffff\s]+\s*|\s+', text):
        weight = sum(2 if ord(c) >= 0x2e80 else 1 for c in word)
        if size + weight > width and line:
            lines.append(line.strip());line='';size=0
        line += word;size += weight
    if line: lines.append(line.strip())
    return r'\N'.join(lines)


def stamp(seconds):
    cs = round(seconds * 100)
    return f'{cs//360000}:{cs//6000%60:02}:{cs//100%60:02}.{cs%100:02}'


def read_cues(path):
    def seconds(value):
        h,m,s=value.replace(',','.').split(':');return int(h)*3600+int(m)*60+float(s)
    cues=[]
    for block in re.split(r'\n\s*\n',path.read_text(encoding='utf-8').replace('\r','').strip()):
        lines=block.splitlines()
        timeline=next((i for i,s in enumerate(lines) if ' --> ' in s),None)
        if timeline is None:continue
        a,b=lines[timeline].split(' --> ')
        cues.append((seconds(a),seconds(b),' '.join(lines[timeline+1:])))
    return cues


def subtitles(opts, times, width, height, scene_cues=None):
    font = 34 if width == 720 else 38
    header = f'''[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Narration,Noto Sans CJK SC,{font},&H00FFFFFF,&H00FFFFFF,&H00202020,&H80202020,0,0,0,0,100,100,0,0,3,2,0,2,45,45,100,1
Style: Brand,Noto Sans CJK SC,40,&H00FFFFFF,&H00FFFFFF,&H00202020,&H80202020,-1,0,0,0,100,100,0,0,3,2,0,8,40,40,60,1
Style: CTA,Noto Sans CJK SC,36,&H00FFFFFF,&H00FFFFFF,&H00202020,&H80202020,-1,0,0,0,100,100,0,0,3,2,0,5,50,50,30,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    elapsed = 0
    events = []
    for index,(text, duration) in enumerate(zip(opts['scenes'], times)):
        if scene_cues and scene_cues[index]:
            for start,end,caption in scene_cues[index]:
                if start>=duration:continue
                events.append(f'Dialogue: 0,{stamp(elapsed+start)},{stamp(elapsed+min(end,duration))},Narration,,0,0,0,,{ass_text(caption, int((width-90)/font*1.7))}')
            elapsed+=duration
            continue
        # Short captions cycle through long scene narration, avoiding six-line blocks.
        chunks = re.split(r'(?<=[。！？!?；;，,])\s*', text)
        chunks = [c for c in chunks if c]
        cursor = elapsed
        for chunk in chunks:
            end = cursor + duration * len(chunk) / sum(map(len, chunks))
            events.append(f'Dialogue: 0,{stamp(cursor)},{stamp(end)},Narration,,0,0,0,,{ass_text(chunk, int((width-90)/font*1.7))}')
            cursor = end
        elapsed += duration
    if opts['brand']: events.append(f'Dialogue: 1,0:00:00.00,{stamp(elapsed)},Brand,,0,0,0,,{ass_text(opts["brand"],40)}')
    if opts['cta']: events.append(f'Dialogue: 2,{stamp(max(0,elapsed-3))},{stamp(elapsed)},CTA,,0,0,0,,{ass_text(opts["cta"],36)}')
    return header + '\n'.join(events) + '\n'


def render(root, job, work):
    from promo_videos import write_status, WORKER, SIZES
    try:
        opts = job['options']
        width, height = SIZES[opts['aspect_ratio']]
        deadline = time.monotonic() + 1500
        identity={}
        if os.name=='posix' and os.geteuid()==0:
            import pwd
            user=pwd.getpwnam(os.getenv('SCRIPT_RUNNER_USER','cellxrunner'))
            os.chown(work,user.pw_uid,user.pw_gid)
            for file in work.iterdir():os.chown(file,user.pw_uid,user.pw_gid)
            identity=dict(user=user.pw_uid,group=user.pw_gid,extra_groups=[])
        def update(progress, message):
            job.update(progress=progress, message=message);write_status(root, job)
        def run(args, limit=300):
            subprocess.run(args, cwd=work, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=max(1,min(limit,deadline-time.monotonic())), check=True, **identity)
        def probe(name):
            result = subprocess.run(['ffprobe','-v','error','-show_entries','format=duration:stream=width,height','-of','json',name],
                                    cwd=work,capture_output=True,check=True,timeout=20, **identity)
            return json.loads(result.stdout)
        common=['ffmpeg','-v','error','-nostdin','-y','-threads','1','-filter_threads','1']
        durations=[];scene_cues=[]
        update(5,'Preparing narration / 正在生成配音')
        fitted=opts.get('fit_narration',False) and opts['voice']!='none'
        tempo=1.
        if fitted:
            from narration_timing import synthesize,correct
            original=synthesize(opts['scenes'],opts['voice'],work,identity,deadline)
            durations,tempo=correct(work,original,opts['duration_seconds'],identity)
        for index,line in enumerate(opts['scenes']):
            if opts['voice'] != 'none':
                if not fitted:run([tts_python(),'-m','edge_tts','--voice',VOICES[opts['voice']],'--text',line,'--write-media',f'voice-{index}.mp3','--write-subtitles',f'voice-{index}.srt'],120)
                duration=durations[index] if fitted else float(probe(f'voice-{index}.mp3')['format']['duration'])
                scene_cues.append([(a/tempo,b/tempo,text) for a,b,text in read_cues(work/f'voice-{index}.srt')])
            else:
                duration=max(2,len(line)/6)
                scene_cues.append([])
            if not math.isfinite(duration) or duration<=0: raise ValueError('Narration audio is invalid.')
            if not fitted:durations.append(duration)
            update(5+round((index+1)/len(opts['scenes'])*20),'Preparing narration / 正在生成配音')
        required=sum(durations)+(0 if fitted else .25*len(durations)) if opts['voice']!='none' else opts['duration_seconds']
        if required>60.1: raise ValueError('Narration exceeds 60 seconds. Shorten the script and try again. / 口播超过60秒，请缩短文案。')
        total=max(opts['duration_seconds'],required)
        weights=[d+(0 if fitted else .25) for d in durations]
        times=[round(total*w/sum(weights)*24)/24 for w in weights]
        # Keep total within the advertised 60-second maximum after frame rounding.
        times[-1] += min(60,round(total*24)/24)-sum(times)
        pictures=sorted(work.glob('photo-*'))
        for index,seconds in enumerate(times):
            frames=round(seconds*24)
            if index==0 and opts['clip_id']:
                inputs=['-stream_loop','-1','-i','opening.mp4']
                filters=f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x101827,setsar=1,fps=24'
            else:
                picture=pictures[index%len(pictures)]
                streams=probe(picture.name)['streams']
                if not streams or not 0<streams[0].get('width',0)*streams[0].get('height',0)<=40000000:
                    raise ValueError('Photo exceeds 40 megapixels.')
                inputs=['-loop','1','-framerate','24','-i',picture.name]
                zoom="min(zoom+0.00035,1.06)" if index%2==0 else "if(eq(on,0),1.06,max(1.0,zoom-0.00035))"
                filters=f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x101827,zoompan=z='{zoom}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={width}x{height}:fps=24,setsar=1"
            filters+=f',format=yuv420p,fade=t=in:st=0:d=0.2,fade=t=out:st={max(0,seconds-.2)}:d=0.2'
            run(common+inputs+['-vf',filters,'-frames:v',str(frames),'-an','-c:v','libx264','-preset','veryfast','-crf','23','-threads','1',f'scene-{index}.mp4'])
            audio_in=['-i',f'timed-{index}.wav' if fitted else f'voice-{index}.mp3'] if opts['voice']!='none' else ['-f','lavfi','-i','anullsrc=r=24000:cl=mono']
            run(common+audio_in+['-af','apad','-t',str(seconds),'-ar','24000','-ac','1',f'audio-{index}.wav'])
            update(30+round((index+1)/len(times)*45),f'Editing scene {index+1}/{len(times)} / 正在剪辑分镜')
        for prefix,suffix in [('scene','mp4'),('audio','wav')]:
            (work/(prefix+'.txt')).write_text(''.join(f"file '{prefix}-{i}.{suffix}'\n" for i in range(len(times))))
        (work/'captions.ass').write_text(subtitles(opts,times,width,height,scene_cues),encoding='utf-8')
        update(80,'Adding subtitles / 正在合成字幕')
        run(common+['-f','concat','-safe','1','-i','scene.txt','-f','concat','-safe','1','-i','audio.txt',
                    '-vf','ass=captions.ass','-map','0:v:0','-map','1:a:0','-c:v','libx264','-preset','veryfast','-crf','23',
                    '-threads','1','-c:a','aac','-b:a','128k','-t',str(sum(times)),'-movflags','+faststart','clean.mp4'])
        from video_music import mix_music
        destination=root/(job['id']+'.mp4')
        if opts['music_preset']!='none':
            update(92,'Mixing music / 正在混合配乐')
            mix_music(work/'clean.mp4',work/'final.mp4',opts['music_preset'],opts['music_volume'])
        else: shutil.copyfile(work/'clean.mp4',work/'final.mp4')
        if not 100<(work/'final.mp4').stat().st_size<=80*1024*1024: raise ValueError('Video exceeds output size limit.')
        shutil.copyfile(work/'clean.mp4',root/(job['id']+'.source.mp4'))
        (root/(job['id']+'.source.mp4')).chmod(0o600)
        shutil.copyfile(work/'final.mp4',destination);destination.chmod(0o600)
        job.update(status='completed',progress=100,size=destination.stat().st_size,duration_seconds=sum(times),
                   width=width,height=height,scene_durations=times,narration_seconds=sum(durations),narration_tempo=tempo,download_url='/ext-api/promo-videos/'+job['id']+'/file',
                   message='Economy ad ready: narration, subtitles and music. / 经济广告已生成。')
    except ValueError as error: job.update(status='failed',message=str(error))
    except subprocess.CalledProcessError as error:
        detail=(error.stderr or b'').decode(errors='replace')
        if job.get('progress',0)<=25:
            message='No narration audio received. Check the script language and try again. / 配音服务未返回声音，请检查口播语言后重试。' if 'NoAudioReceived' in detail else 'Narration service could not connect. Try again shortly. / 在线配音暂时不可用，请稍后重试。'
        else:
            message='Video editing failed. Check the selected photos or opening video. / 视频剪辑失败，请检查图片或首镜头视频。'
        job.update(status='failed',message=message)
    except Exception as error:
        job.update(status='failed',message='Economy rendering failed at '+str(job.get('progress',0))+'% ('+type(error).__name__+'). Check narration connectivity and photo formats. / 合成失败，请检查配音服务连接和图片格式。')
    finally:
        with LOCK:
            write_status(root,job);ACTIVE.discard(job['id'])
        shutil.rmtree(work,ignore_errors=True);WORKER.release()


def start(root,payload):
    from promo_videos import WORKER,write_status
    try:
        opts=validate(payload)
        job_id=payload.get('request_id','')
        if not isinstance(job_id,str) or not re.fullmatch('[a-f0-9]{40}',job_id): raise ValueError('A unique request ID is required.')
        with LOCK:
            record=root/(job_id+'.json')
            if record.exists(): return json.loads(record.read_text()),200
            ready=readiness()
            if not ready['renderer'] or (opts['voice']!='none' and not ready['voice']):
                return {'ok':False,'message':'Economy renderer or narration service is not installed.'},503
            if len(list(root.glob('*.json')))>=100 or sum(p.stat().st_size for p in root.glob('*.mp4'))>420*1024*1024:
                raise ValueError('Video storage is full.')
            if not WORKER.acquire(blocking=False): return {'ok':False,'message':'Another video is processing. Please wait.'},409
            work=Path(tempfile.mkdtemp(prefix='cellx-economy-'));work.chmod(0o700)
            try:
                from photo_uploads import LOCK as PHOTO_LOCK
                photos=Path(os.getenv('PHOTO_UPLOAD_DIR',str(Path(__file__).parent/'private-photos')))
                with PHOTO_LOCK:
                    for i,file_id in enumerate(payload['photo_ids']):
                        meta=json.loads((photos/(file_id+'.json')).read_text())
                        extension={'image/png':'png','image/jpeg':'jpg','image/webp':'webp'}.get(meta['mime_type'])
                        if not extension: raise ValueError('Use PNG, JPEG or WebP product photos.')
                        shutil.copyfile(photos/(file_id+'.bin'),work/f'photo-{i:02}.{extension}')
                if opts['clip_id']:
                    clip=json.loads((root/(opts['clip_id']+'.json')).read_text())
                    if clip['status']!='completed': raise ValueError('Opening clip must be completed.')
                    shutil.copyfile(root/(opts['clip_id']+'.mp4'),work/'opening.mp4')
                job=dict(ok=True,id=job_id,provider='economy',options=opts,photo_count=len(payload['photo_ids']),
                         created_at=time.time(),status='rendering',progress=0,message='Starting economy ad / 开始制作经济广告')
                write_status(root,job);ACTIVE.add(job_id)
                threading.Thread(target=render,args=(root,dict(job),work),daemon=True).start()
                return job,202
            except Exception:
                ACTIVE.discard(job_id);shutil.rmtree(work,ignore_errors=True);WORKER.release();raise
    except (ValueError,KeyError,OSError,TypeError) as error:
        return {'ok':False,'message':str(error) if isinstance(error,ValueError) else 'Invalid or missing economy video inputs.'},400


def poll(root,job):
    from promo_videos import write_status
    with LOCK:
        if job['status']=='rendering' and job['id'] not in ACTIVE:
            job.update(status='failed',message='Rendering interrupted by service restart. Generate again.');write_status(root,job)
    return job
