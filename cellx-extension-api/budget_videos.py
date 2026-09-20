"""Budget image-to-video catalog and durable fal queue integration."""
import json
import os
import re
import time
import urllib.request

MODELS = {
    'product_ad': dict(name='Runway Product Ad', provider='runway', durations=list(range(4, 16)), photos=10, audio=True, pricing_url='https://docs.dev.runwayml.com/guides/pricing/'),
    'wan_turbo': dict(name='Wan 2.2 Turbo · 720p', provider='fal', durations=[5], fixed_duration=True, photos=1, audio=False, endpoint='fal-ai/wan/v2.2-a14b/image-to-video/turbo'),
    'hailuo_fast': dict(name='Hailuo 2.3 Fast · 768p', provider='fal', durations=[6, 10], photos=1, audio=False, image_ratio=True, endpoint='fal-ai/minimax/hailuo-2.3-fast/standard/image-to-video'),
    'kling_turbo': dict(name='Kling 2.5 Turbo Pro', provider='fal', durations=[5, 10], photos=1, audio=False, image_ratio=True, endpoint='fal-ai/kling-video/v2.5-turbo/pro/image-to-video'),
    'gen4_turbo': dict(name='Runway Gen-4 Turbo · 720p', provider='runway', durations=[5, 10], photos=1, audio=False, pricing_url='https://docs.dev.runwayml.com/guides/pricing/'),
}


def price(model, duration):
    if model == 'product_ad': return 200 + 36 * (duration - 4)
    if model == 'wan_turbo': return 10
    if model == 'hailuo_fast': return {6: 19, 10: 32}[duration]
    if model == 'kling_turbo': return duration * 7
    if model == 'gen4_turbo': return duration * 5
    raise ValueError('Unknown video model.')


def catalog(runway_configured):
    return [{**spec, 'id': key, 'configured': runway_configured if spec['provider'] == 'runway' else bool(os.getenv('FAL_KEY', '').strip()),
             'prices_cents': {str(d): price(key, d) for d in spec['durations']},
             'pricing_url': spec.get('pricing_url', 'https://fal.ai/models/' + spec.get('endpoint', ''))}
            for key, spec in MODELS.items()]


def fal_request(url, body=None):
    from runway_videos import NoRedirect
    from urllib.parse import urlsplit
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.netloc != 'queue.fal.run' or not parsed.path.startswith('/fal-ai/'):
        raise ValueError('Unexpected fal queue URL.')
    request = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization': 'Key ' + os.environ['FAL_KEY'], 'Content-Type': 'application/json'})
    with urllib.request.build_opener(NoRedirect).open(request, timeout=45) as response:
        return json.load(response)


def fal_task(root, job, images):
    from promo_videos import write_status
    from runway_videos import STYLES
    opts = job['options']
    model = opts['model']
    spec = MODELS[model]
    if not job.get('task_id'):
        body = {'image_url': images[0]['uri'], 'prompt': STYLES[opts['style']] + ' Preserve the product appearance. No text overlays. ' + opts['product_info'] + '. ' + opts['concept']}
        if model == 'wan_turbo':
            body.update(resolution='720p', aspect_ratio=opts['aspect_ratio'])
        else:
            body['duration'] = str(opts['duration_seconds'])
        receipt = fal_request('https://queue.fal.run/' + spec['endpoint'], body)
        request_id = receipt.get('request_id', '')
        if not re.fullmatch(r'[a-zA-Z0-9-]{1,100}', request_id):
            raise OSError('Missing fal receipt; submission outcome uncertain.')
        job.update(task_id=request_id, fal_status_url=receipt['status_url'], fal_response_url=receipt['response_url'])
        write_status(root, job)
    deadline = time.monotonic() + 1800
    while time.monotonic() < deadline:
        status = fal_request(job['fal_status_url'])
        if status['status'] == 'COMPLETED':
            if status.get('error'):
                raise ValueError('fal generation failed. Check the request in fal history.')
            result = fal_request(job['fal_response_url'])
            return {'id': job['task_id'], 'output': [result['video']['url']]}
        if status['status'] not in {'IN_QUEUE', 'IN_PROGRESS'}:
            raise ValueError('Unexpected fal task status. Check provider history.')
        time.sleep(5)
    raise TimeoutError('fal task is still processing.')
