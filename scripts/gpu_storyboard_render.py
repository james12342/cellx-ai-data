"""Portrait opening + every remaining image; executed only on the Windows GPU host."""
import json
import math
import re
from pathlib import Path
from PIL import Image,ImageOps
from narration_timing import probe,correct
from gpu_storyboard_limits import MAX_SECONDS, tolerance as timing_tolerance
from economy_videos import read_cues,subtitles

class StoryboardTimingError(ValueError):
    def __init__(self, message, timing=None):
        super().__init__(message)
        self.timing=timing or {}


def split_cues(cues,limit):
    """Keep long Edge sentence cues to roughly two readable subtitle lines."""
    output=[]
    for start,end,text in cues:
        chunks=[];chunk='';weight=0
        for token in re.findall(r'[\u2e80-\uffff]|[^\u2e80-\uffff\s]+\s*|\s+',text):
            parts=[token] if len(token)<=limit else [token[i:i+limit] for i in range(0,len(token),limit)]
            for part in parts:
                size=sum(2 if ord(c)>=0x2e80 else 1 for c in part)
                if chunk and weight+size>limit:chunks.append(chunk.strip());chunk='';weight=0
                chunk+=part;weight+=size
                if re.search(r'[。！？!?；;]$',part):chunks.append(chunk.strip());chunk='';weight=0
        if chunk.strip():chunks.append(chunk.strip())
        total=sum(map(len,chunks));cursor=start
        for i,part in enumerate(chunks):
            finish=end if i==len(chunks)-1 else cursor+(end-start)*len(part)/total
            output.append((cursor,finish,part));cursor=finish
    return output


def render(job,run,python,command,download,state,revise=None):
    opts=job['options'];scenes=opts['scenes'];voice={'zh-male':'zh-CN-YunxiNeural','zh-female':'zh-CN-XiaoxiaoNeural','en-male':'en-US-GuyNeural','en-female':'en-US-JennyNeural'}[opts['voice']]
    durations=[]
    for i,scene in enumerate(scenes):
        source=download(i)
        with Image.open(source) as im:
            if im.width*im.height>40_000_000:raise ValueError('Photo exceeds 40 megapixels')
            im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((1024,1024) if i==0 else (1920,1920));im.save(run/f'photo-{i}.png')
        command([python,'-m','edge_tts','--voice',voice,'--text',scene['narration'],'--write-media',str(run/f'voice-{i}.mp3'),'--write-subtitles',str(run/f'voice-{i}.srt')],300)
        durations.append(probe(run/f'voice-{i}.mp3'))
        state['progress']=5+int(15*(i+1)/len(scenes))
    target_seconds=opts['duration_seconds'];tolerance=timing_tolerance(target_seconds)
    for attempt in range(3):
        raw=list(durations);tempo=min(1.12,max(.88,sum(raw)/target_seconds))
        timing={'target_seconds':target_seconds,'opening_seconds':round(raw[0],3),'raw_seconds':round(sum(raw),3),'scene_seconds':raw,'tempo':tempo,'adjusted_seconds':round(sum(raw)/tempo,3),'adjusted_opening_seconds':round(raw[0]/tempo,3),'revisions':attempt}
        (run/'timing-report.json').write_text(json.dumps(timing,indent=2),encoding='utf-8')
        matched=abs(sum(raw)/tempo-target_seconds)<=tolerance and raw[0]/tempo<=20 and sum(raw)/tempo<=MAX_SECONDS+.1
        if matched:break
        if attempt==2 or not opts.get('auto_timing_revision') or not revise:
            raise StoryboardTimingError('Measured narration does not fit target duration',timing)
        try:revised=revise(timing)
        except Exception as error:raise StoryboardTimingError('Automatic revision unavailable; original text kept',timing) from error
        scenes=revised['scenes']
        if [s['photo_id'] for s in scenes]!=job['photo_ids']:raise ValueError('Revised scene order changed')
        durations=[]
        for i,scene in enumerate(scenes):
            command([python,'-m','edge_tts','--voice',voice,'--text',scene['narration'],'--write-media',str(run/f'voice-{i}.mp3'),'--write-subtitles',str(run/f'voice-{i}.srt')],300)
            durations.append(probe(run/f'voice-{i}.mp3'))
    try:durations,tempo=correct(run,durations,target_seconds,tolerance=tolerance)
    except ValueError as error:raise StoryboardTimingError(str(error),timing) from error
    if durations[0]>20 or sum(durations)>MAX_SECONDS+.15:raise StoryboardTimingError('Measured narration exceeds limit',timing)
    command(['ffmpeg','-v','error','-y','-i',str(run/'timed-0.wav'),'-ar','16000','-ac','1',str(run/'opening-speech.wav')],60)
    state['progress']=25
    inference=run/'inference';inference.mkdir(exist_ok=True)
    command([python,'inference.py','--source_image',str(run/'photo-0.png'),'--driven_audio',str(run/'opening-speech.wav'),'--result_dir',str(inference),'--preprocess','full','--still','--size','256','--batch_size','2','--expression_scale','0.65'],1800)
    videos=sorted(inference.glob('*.mp4'),key=lambda p:p.stat().st_mtime)
    if not videos:raise RuntimeError('No talking portrait output')
    width,height={'9:16':(720,1280),'16:9':(1280,720),'1:1':(720,720)}[opts['aspect_ratio']]
    total=min(MAX_SECONDS,round(sum(durations)*25)/25)
    times=[round(d*25)/25 for d in durations];times[-1]+=total-sum(times)
    cues=[[(a/tempo,b/tempo,text) for a,b,text in split_cues(read_cues(run/f'voice-{i}.srt'),50 if width==720 else 90)] for i in range(len(scenes))]
    captions=subtitles({'scenes':[s['narration'] for s in scenes],'brand':'','cta':''},times,width,height,cues).replace('Noto Sans CJK SC','Microsoft YaHei')
    (run/'captions.ass').write_text(captions,encoding='utf-8')
    for i,seconds in enumerate(times):
        inputs=['-i',str(videos[-1])] if i==0 else ['-loop','1','-framerate','25','-i',str(run/f'photo-{i}.png')]
        filters=f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x101827,setsar=1,fps=25,format=yuv420p,fade=t=in:st=0:d=0.12,fade=t=out:st={max(0,seconds-.12)}:d=0.12'
        command(['ffmpeg','-v','error','-nostdin','-y',*inputs,'-i',str(run/f'timed-{i}.wav'),'-map','0:v:0','-map','1:a:0','-vf',filters,'-af','apad','-t',str(seconds),'-c:v','libx264','-preset','fast','-crf','20','-threads','4','-c:a','aac','-ar','48000','-ac','2','-pix_fmt','yuv420p',str(run/f'segment-{i}.mp4')],max(180,int(seconds*5+60)))
        state['progress']=60+int(25*(i+1)/len(scenes))
    (run/'segments.txt').write_text(''.join(f"file 'segment-{i}.mp4'\n" for i in range(len(scenes))),encoding='utf-8')
    target=run/'output.mp4'
    command(['ffmpeg','-v','error','-nostdin','-y','-f','concat','-safe','1','-i','segments.txt','-vf','ass=captions.ass','-c:v','libx264','-preset','fast','-crf','20','-threads','4','-pix_fmt','yuv420p','-maxrate','3M','-bufsize','6M','-c:a','aac','-b:a','128k','-ar','48000','-ac','2','-t',str(total),'-movflags','+faststart',str(target)],max(240,int(total*5+120)),cwd=run)
    actual=probe(target)
    if abs(actual-opts['duration_seconds'])>max(1.5,min(3,opts['duration_seconds']*.02)):raise StoryboardTimingError('Final video duration differs from requested duration')
    metadata={'duration_seconds':actual,'scene_durations':times,'photo_ids':job['photo_ids'],'width':width,'height':height,'narration_tempo':tempo}
    (run/'render-summary.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    state['progress']=95
    return target
