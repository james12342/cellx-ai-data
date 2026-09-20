"""Run on Linux staging host. Synthetic photos; no paid LLM/video calls."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(1,'/opt/cellx-extension-api')
import economy_videos as eco
import promo_videos as promo

root=Path(tempfile.mkdtemp(prefix='economy-smoke-output-'))
work=Path(tempfile.mkdtemp(prefix='economy-smoke-work-'))
for i,color in enumerate(['0x365575','0x886245']):
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',f'color=c={color}:s=720x1280','-frames:v','1','-threads','1',str(work/f'photo-{i:02}.png')],check=True)
payload=dict(photo_ids=['b'*40,'c'*40],options=dict(narration='给生活留一点美好的时间。\n用自己的商品图片，制作属于你的广告。',voice='zh-female',duration_seconds=15,aspect_ratio='9:16',brand='CELL AI · DEMO',cta='了解更多',music_preset='default',music_volume=.15))
if len(sys.argv)>1:
    import shutil
    shutil.copyfile(sys.argv[1],work/'opening.mp4')
    payload['options'].update(clip_id='c'*40,voice='none',aspect_ratio='16:9')
job=dict(id='e'*40,provider='economy',options=eco.validate(payload),photo_count=2,created_at=0,status='rendering',progress=0)
assert promo.WORKER.acquire(blocking=False)
eco.ACTIVE.add(job['id']);eco.render(root,job,work)
print(json.dumps(job,ensure_ascii=False))
assert job['status']=='completed',job['message']
video=root/(job['id']+'.mp4')
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(video)]))
assert any(s['codec_type']=='audio' for s in probe['streams'])
expected=promo.SIZES[payload['options']['aspect_ratio']]
assert any((s.get('width'),s.get('height'))==expected for s in probe['streams'])
assert 14.9<=float(probe['format']['duration'])<=60.1
subprocess.run(['ffmpeg','-v','error','-ss','3','-i',str(video),'-frames:v','1',str(root/'frame.png')],check=True)
print('SMOKE_OUTPUT='+str(root))
