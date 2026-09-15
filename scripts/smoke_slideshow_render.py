"""Run beside candidate modules on AWS with synthetic photos, not customer data."""
import base64
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import time
import zlib
import promo_videos as videos
from photo_uploads import photo_request

def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
def png(color):
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',64,64,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+bytes(color)*64)*64))+chunk(b'IEND',b'')

with tempfile.TemporaryDirectory(prefix='cellx-video-qa-') as tmp:
    os.environ['PHOTO_UPLOAD_DIR']=tmp+'/photos';os.environ['PROMO_VIDEO_DIR']=tmp+'/videos'
    colors=[(220,30,30),(30,210,30),(30,30,220),(220,180,20),(200,30,200),(30,200,200)]
    ids=[]
    for i,color in enumerate(colors):
        body,status=photo_request('POST','/photo-uploads',{}, {'name':f'test-{i}.png','data':base64.b64encode(png(color)).decode()},lambda **kw:(True,None,200),'')
        assert status==201;ids.append(body['file']['id'])
    for aspect,count,duration,music in [('9:16',6,10,'default'),('16:9',1,5,'none'),('1:1',2,5,'default')]:
        job,status=videos.video_request('POST','/promo-videos',{'photo_ids':ids[:count],'options':{'duration_seconds':duration,'aspect_ratio':aspect,'music_preset':music}})
        assert status==202,job
        route='/promo-videos/'+job['id'];deadline=time.time()+220
        while job['status']=='rendering' and time.time()<deadline:
            time.sleep(.5);job,status=videos.video_request('GET',route,{})
        assert job['status']=='completed',job
        file,status=videos.video_request('GET',route+'/file',{})
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(file)]))
        video=next(s for s in probe['streams'] if s['codec_type']=='video')
        assert (video['width'],video['height'])==videos.SIZES[aspect]
        assert video['codec_name']=='h264'
        assert abs(float(probe['format']['duration'])-duration)<.15
        assert any(s['codec_type']=='audio' for s in probe['streams'])==(music!='none')
        for i,color in enumerate(colors[:count]):
            rgb=subprocess.check_output(['ffmpeg','-v','error','-ss',str((i+.5)*duration/count),'-i',str(file),'-vf','crop=2:2:(iw-2)/2:(ih-2)/2,scale=1:1','-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','pipe:1'])
            assert len(rgb)==3 and max(abs(a-b) for a,b in zip(rgb,color))<40,(aspect,i,list(rgb),color)
        assert videos.video_request('DELETE',route,{})[1]==200
        print('PASS:',aspect,count,'photos;',duration,'seconds; H.264, audio, frame colors/order and deletion verified.',flush=True)
