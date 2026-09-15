"""Original synthesized backing tracks and local video mixing."""
from array import array
import json
import math
from pathlib import Path
import subprocess
import tempfile
import wave

PRESETS = {
    'default': (80, [261.63, 329.63, 392, 523.25, 220, 261.63, 329.63, 440], False),
    'upbeat': (124, [392, 493.88, 587.33, 783.99, 440, 523.25, 659.25, 880], True),
    'piano': (68, [261.63, 392, 523.25, 329.63, 220, 329.63, 440, 523.25], False),
    'cinematic': (60, [146.83, 220, 293.66, 349.23, 130.81, 196, 261.63, 329.63], False),
    'playful': (112, [523.25, 659.25, 783.99, 659.25, 587.33, 698.46, 880, 698.46], True),
    'electronic': (128, [220, 220, 329.63, 440, 196, 196, 293.66, 392], True),
}

def settings(value, default='none'):
    preset = value.get('music_preset', default)
    volume = value.get('music_volume', .35)
    if preset not in {'none', *PRESETS}:
        raise ValueError('Choose a background music preset.')
    if isinstance(volume, bool) or not isinstance(volume, (int, float)) or not math.isfinite(volume) or not 0 <= volume <= 1:
        raise ValueError('Music volume must be between 0 and 100 percent.')
    return {'music_preset': preset, 'music_volume': volume}

def make_music(path, duration, preset='default', volume=1):
    bpm, notes, drums = PRESETS[preset]
    rate, beat = 22050, 60 / bpm
    samples = array('h')
    for i in range(int(rate * duration)):
        t = i / rate
        phase = t % beat
        freq = notes[int(t / beat) % len(notes)]
        decay = 7 if preset in {'piano', 'playful'} else 3
        env = min(1, phase / .015) * math.exp(-phase * decay)
        tone = math.sin(2 * math.pi * freq * t) + .22 * math.sin(4 * math.pi * freq * t)
        if preset == 'electronic':
            tone += .2 * math.sin(6 * math.pi * freq * t)
        bass = .3 * math.sin(math.pi * notes[(int(t / (beat * 4)) * 4) % len(notes)] * t)
        kick = .65 * math.sin(2 * math.pi * (55 * phase + 1.5 * (1 - math.exp(-phase * 30)))) * math.exp(-phase * 18) if drums else 0
        fade = max(0, min(1, t / .15, (duration - t) / .6))
        samples.append(int(11000 * volume * fade * (env * tone + bass + kick) / 2))
    with wave.open(str(path), 'wb') as handle:
        handle.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
        handle.writeframes(samples.tobytes())

def mix_music(source, destination, preset, volume):
    probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_type', '-of', 'json', str(source)], capture_output=True, timeout=15, check=True)
    info = json.loads(probe.stdout)
    duration = float(info['format']['duration'])
    if not math.isfinite(duration) or not 0 < duration <= 120:
        raise ValueError('Unsupported video duration for background music.')
    has_audio = any(s.get('codec_type') == 'audio' for s in info['streams'])
    with tempfile.TemporaryDirectory(prefix='music-', dir=destination.parent) as temporary:
        track, output = Path(temporary) / 'music.wav', Path(temporary) / 'output.mp4'
        make_music(track, duration, preset, volume)
        args = ['ffmpeg', '-v', 'error', '-nostdin', '-y', '-threads', '1', '-i', str(source), '-i', str(track)]
        if has_audio:
            args += ['-filter_complex', '[0:a:0][1:a:0]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]', '-map', '0:v:0', '-map', '[a]']
        else:
            args += ['-map', '0:v:0', '-map', '1:a:0']
        args += ['-c:v', 'copy', '-c:a', 'aac', '-b:a', '128k', '-t', str(duration), '-movflags', '+faststart', str(output)]
        subprocess.run(args, capture_output=True, timeout=90, check=True)
        if output.stat().st_size > 80 * 1024 * 1024:
            raise ValueError('Mixed video exceeds storage limit.')
        output.chmod(0o600)
        output.replace(destination)
