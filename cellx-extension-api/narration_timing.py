"""Shared Edge speech measurement and small, pitch-preserving timing correction."""
from concurrent.futures import ThreadPoolExecutor
import json
import math
from pathlib import Path
import re
import subprocess
import time

SPEEDS = {'zh-female': 4.2, 'zh-male': 4.1, 'en-female': 2.4, 'en-male': 2.3}
MIN_TEMPO, MAX_TEMPO = .88, 1.12


def units(text, language):
    return len(re.findall(r'[\u4e00-\u9fff]', text)) if language == 'zh-CN' else len(re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*", text))


def budget(duration, voice, count):
    # Small per-scene allowance for the natural pauses already present in Edge audio.
    return max(count * 4, round(max(1, duration - count * .4) * SPEEDS[voice]))


def probe(path, identity=None):
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', str(path)],
                            capture_output=True, check=True, timeout=15, **(identity or {}))
    value = float(json.loads(result.stdout)['format']['duration'])
    if not math.isfinite(value) or value <= 0: raise ValueError('Narration audio is invalid.')
    return value


def synthesize(lines, voice, work, identity=None, deadline=None):
    from economy_videos import VOICES, tts_python
    work = Path(work)
    def one(item):
        index, text = item
        timeout = max(1, min(65, (deadline or time.monotonic()+65)-time.monotonic()))
        subprocess.run([tts_python(), '-m', 'edge_tts', '--voice', VOICES[voice], '--text', text,
                        '--write-media', str(work/f'voice-{index}.mp3'), '--write-subtitles', str(work/f'voice-{index}.srt')],
                       stdin=subprocess.DEVNULL, capture_output=True, check=True, timeout=timeout, **(identity or {}))
        return probe(work/f'voice-{index}.mp3', identity)
    with ThreadPoolExecutor(max_workers=3) as pool:
        return list(pool.map(one, enumerate(lines)))


def correct(work, durations, target, identity=None, tolerance=0):
    """Return measured WAV lengths and tempo; never add silence or cut off speech."""
    ratio = min(MAX_TEMPO, max(MIN_TEMPO, sum(durations) / target))
    if abs(sum(durations)/ratio-target) > tolerance + 1e-6:
        raise ValueError('Narration is too short or long for this duration. Regenerate the storyboard or edit the script. / 口播与目标时长差距较大，请重新生成分镜或调整文案。')
    measured = []
    for index in range(len(durations)):
        destination = Path(work)/f'timed-{index}.wav'
        subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-i', str(Path(work)/f'voice-{index}.mp3'),
                        '-af', f'atempo={ratio:.8f}', '-ar', '24000', '-ac', '1', str(destination)],
                       stdin=subprocess.DEVNULL, capture_output=True, check=True, timeout=20, **(identity or {}))
        measured.append(probe(destination, identity))
    return measured, ratio
