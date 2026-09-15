"""Exercise music synthesis and remixing on AWS with disposable media."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import wave
from array import array

sys.path.insert(0, sys.argv[1] if len(sys.argv)>1 else '/opt/cellx-extension-api')
from video_music import PRESETS, make_music
from promo_videos import video_request, write_status

with tempfile.TemporaryDirectory(prefix='cellx-music-check-') as temporary:
    root = Path(temporary)
    os.environ['PROMO_VIDEO_DIR'] = temporary
    hashes = set()
    for preset in PRESETS:
        track = root / (preset + '.wav')
        make_music(track, 2, preset, .35)
        with wave.open(str(track)) as audio:
            samples = array('h', audio.readframes(audio.getnframes()))
            assert len(samples) == 44100 and max(samples) > 100
            hashes.add(hash(samples.tobytes()))
    assert len(hashes) == 6
    for original_audio in [False, True]:
        job_id = ('a' if original_audio else 'b') * 40
        source = root / (job_id + '.mp4')
        args = ['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=white:s=160x160:r=24']
        if original_audio:
            args += ['-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=22050']
        args += ['-t', '2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(source)]
        subprocess.run(args, check=True)
        before = source.read_bytes()
        write_status(root, {'id':job_id, 'ok':True, 'status':'completed', 'options':{}})
        job, status = video_request('POST', '/promo-videos/' + job_id + '/music', {'music_preset':'upbeat', 'music_volume':.35})
        assert status == 201, job
        assert source.read_bytes() == before and job['id'] != job_id
        probe = subprocess.check_output(['ffprobe','-v','error','-show_entries','stream=codec_type','-of','json',str(root/(job['id']+'.mp4'))])
        assert any(s['codec_type']=='audio' for s in json.loads(probe)['streams'])
        restored, code = video_request('POST', '/promo-videos/' + job['id'] + '/music', {'music_preset':'none'})
        assert code == 201 and (root/(restored['id']+'.mp4')).read_bytes() == before
    assert video_request('POST', '/promo-videos/' + 'b'*40 + '/music', {'music_preset':'invalid'})[1] == 400
print('PASS: six distinct audible tracks, silent/video-audio mixing, preserved originals, no stacking on repeated edits, and invalid input rejected. No Runway generation.')
