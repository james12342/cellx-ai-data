"""Verify the deployed public photo workflow without paid generation."""
import base64
import json
import sys
from urllib.request import urlopen
import smoke_photo_uploads_aws as photos

photos.base = 'https://app.cellaidata.com/ext-api'
raw = b'GIF89a' + b'\0' * (6 * 1024 * 1024)
status, body = photos.request('/photo-uploads', 'POST', {
    'name': 'deployment-size-check.gif', 'mime_type': 'image/gif',
    'data': base64.b64encode(raw).decode(),
})
assert status == 201, body.get('message')
path = '/photo-uploads/' + body['file']['id']
try:
    assert body['file']['size'] == len(raw)
    assert body['file']['mime_type'] == 'image/gif'
finally:
    assert photos.request(path, 'DELETE')[0] == 200
print('PASS: public HTTPS upload accepts GIF payload above 5 MB; test file removed.')
code, info = photos.request('/promo-videos/providers')
assert code == 200 and info.get('sdk') == 'runwayml'
print('Runway key configured:', info['runway_configured'])
for path, expected in [
    ('/agent/', 'workflow-photos.js?v=20260915-ad-presets-v2'),
    ('/agent/workflow-templates/manifest.json', 'runway-product-ad-video-test.json'),
    ('/agent/workflow-templates/runway-product-ad-video-test.json', 'Video Generation'),
]:
    with urlopen('https://app.cellaidata.com' + path, timeout=20) as response:
        assert expected in response.read().decode()
sys.path.insert(0, '/opt/cellx-extension-api/runway-sdk')
from runwayml import RunwayML
client = RunwayML(api_key='readiness-placeholder')
assert callable(client.recipes.product_ad)
client.close()
print('PASS: public page, template catalog, video template and SDK recipe available. No paid task submitted.')
