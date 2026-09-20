"""Build the user's photo-based house introduction with the existing renderer."""
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

BASE = Path(__file__).resolve().parents[1]
OUT = BASE / 'outputs' / 'luxury-house-introduction'
OUT.mkdir(parents=True, exist_ok=True)
names = ['NP26155120_2_5.jpg', 'NP26155120_3_5.jpg', 'NP26155120_9_4.jpg', 'NP26155120_17_4.jpg', 'NP26155120_23_4.jpg', 'NP26155120_29_4.jpg', 'IMG_7286.JPG']
lines = [
    '把度假的松弛感，带回自己的家。今天，带你欣赏这栋泳池豪宅。',
    '泳池、凉亭与宽敞露台相映成趣，让傍晚的相聚，多一份从容。',
    '走进室内，挑高客厅与开阔楼梯，带来明亮通透的空间感。',
    '拱形高窗引入自然光，让每一顿饭，都有好风景相伴。',
    '厨房与休闲区相邻，聊天、聚会，让生活自然发生。',
    '在壁炉旁坐一坐，望向窗外的绿意，享受属于自己的安静时光。',
    '我是你的房产顾问。想了解这套房源的详细信息，欢迎联系我，预约看房。',
]
options = dict(narration='\n'.join(lines), voice='zh-male', duration_seconds=45, aspect_ratio='16:9', brand='泳池豪宅 · 生活美学', cta='', music_preset='piano', music_volume=.10)
(OUT / 'narration.txt').write_text(options['narration'], encoding='utf-8')
(OUT / 'options.json').write_text(json.dumps(options, ensure_ascii=False, indent=2), encoding='utf-8')
assets = OUT / 'photos'
assets.mkdir(exist_ok=True)
for i, name in enumerate(names):
    shutil.copyfile(Path('C:/Users/hibre/Downloads') / name, assets / f'{i+1:02}_{name}')
guide = '''# 豪宅介绍｜页面填写素材

## 页面填写
- 产品／房源名称：泳池豪宅 · 生活美学
- 特色描述：黄昏庭院、泳池与凉亭、宽敞露台、挑高客厅、拱形高窗餐厅、明亮休闲区及壁炉。
- 视频方式：经济广告／照片合成
- 比例：16:9；目标时长：45秒（会按配音长度调整）
- 配音：中文男声；配乐：Piano，音量10%
- 首镜头使用已生成视频：关闭
- 图片顺序：photos文件夹01至07，最后一张为经纪人照片。
- 行动引导：联系我，预约看房
- 口播：复制 narration.txt 的全部内容，每行对应一张照片。

## 短视频发布文案
把度假的松弛感，带回自己的家。泳池庭院、挑高客厅、明亮餐厅与温暖壁炉，一起欣赏这栋住宅的生活细节。想了解房源详情，欢迎联系我预约看房。

## 使用说明
这是照片展示加合成中文男声旁白的样片，经纪人照片在结尾出镜；不包含人物对口型或本人声音克隆。房屋图片保留原始水印。
当前未加入地址、售价、面积、卧室数或联系方式。正式发布时填写已核实的房源资料和自己的经纪人信息。
'''
(OUT / '页面填写与发布文案.md').write_text(guide, encoding='utf-8')
key = 'C:/Users/hibre/Downloads/LightsailDefaultKey-us-west-2.pem'
host = 'ubuntu@44.240.97.37'
ssh = ['ssh', '-o', 'BatchMode=yes', '-i', key, host]
remote = subprocess.check_output(ssh + ['mktemp -d /tmp/luxury-house-XXXXXXXX'], text=True).strip()
(OUT / 'render-location.txt').write_text(remote, encoding='utf-8')
for i, name in enumerate(names):
    subprocess.run(['scp', '-q', '-i', key, str(assets / f'{i+1:02}_{name}'), f'{host}:{remote}/photo-{i:02}.jpg'], check=True)
code = '''import sys, pathlib, json, tempfile, shutil
sys.path.insert(0,'/opt/cellx-extension-api')
import economy_videos as eco
import promo_videos as promo
root=pathlib.Path(REMOTE)
work=pathlib.Path(tempfile.mkdtemp(prefix='luxury-house-work-'))
for p in root.glob('photo-*'): shutil.copyfile(p,work/p.name)
source=pathlib.Path(eco.__file__).read_text()
# Keep original image edges/watermarks inside the frame throughout motion.
source=source.replace('scale={width}:{height}:force_original_aspect_ratio=decrease,pad=', 'scale={int(width*.90)//2*2}:{int(height*.90)//2*2}:force_original_aspect_ratio=decrease,pad=')
exec(compile(source,eco.__file__,'exec'),eco.__dict__)
original_subtitles=eco.subtitles
def subtitles(opts,times,width,height,scene_cues=None):
    s=original_subtitles(opts,times,width,height,scene_cues)
    start=eco.stamp(sum(times[:-1])); end=eco.stamp(sum(times))
    s+=f'Dialogue: 2,{start},{end},CTA,,0,0,0,,{{\\\\an4\\\\pos(60,330)}}房产顾问\\\\N联系我 · 预约看房\\n'
    return s
eco.subtitles=subtitles
opts=eco.validate(dict(photo_ids=['a'*40]*7,options=OPTIONS))
job=dict(id='f'*40,provider='economy',options=opts,photo_count=7,created_at=0,status='rendering',progress=0)
promo.WORKER.acquire();eco.ACTIVE.add(job['id']);eco.render(root,job,work)
print(json.dumps(job,ensure_ascii=False),flush=True)
assert job['status']=='completed',job
subprocess=__import__('subprocess')
video=str(root/(job['id']+'.mp4'))
for label,second in [('opening',3),('interior',sum(job['scene_durations'][:2])+2),('agent',sum(job['scene_durations'][:-1])+2)]:
    subprocess.run(['ffmpeg','-v','error','-y','-ss',str(second),'-i',video,'-frames:v','1',str(root/(label+'.png'))],check=True)
subprocess.run(['ffmpeg','-v','error','-y','-i',str(root/(job['id']+'.source.mp4')),'-vn','-c:a','copy',str(root/'narration.m4a')],check=True)
'''.replace('REMOTE', repr(remote)).replace('OPTIONS', repr(options))
result = subprocess.run(ssh + ['sudo python3 -'], input=code, text=True, encoding='utf-8', capture_output=True)
print(result.stdout, flush=True)
print(result.stderr, flush=True)
result.check_returncode()
for src, dest in [('f'*40+'.mp4','豪宅介绍_中文男声.mp4'),('narration.m4a','中文口播.m4a'),('opening.png','opening.png'),('interior.png','interior.png'),('agent.png','agent.png')]:
    (OUT / dest).write_bytes(subprocess.check_output(ssh + ['sudo cat '+remote+'/'+src]))
with zipfile.ZipFile(OUT / '豪宅介绍素材包.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in [OUT/'narration.txt',OUT/'options.json',OUT/'页面填写与发布文案.md',*assets.iterdir()]:
        z.write(p,p.relative_to(OUT))
print('OUTPUT='+str(OUT),flush=True)
