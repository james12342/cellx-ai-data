from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parent.parent
old = root / 'outputs/i18n-before/nginx.conf'
source = old.read_text(encoding='utf-8')
assert 'location ^~ /data/' not in source
anchor = '    location ^~ /agent/ {'
assert source.count(anchor) == 1
block = '''    location = /data {
        return 308 /data/$is_args$args;
    }

    location ^~ /data/ {
        alias /var/www/cellx-data-ui/;
        index index.html;
        try_files $uri $uri/ /data/index.html;
    }

'''
stage = root / 'outputs/i18n-deploy'
(stage / 'nginx.conf').write_text(source.replace(anchor, block + anchor), encoding='utf-8')
(stage / 'nginx-manifest.json').write_text(json.dumps({'before': hashlib.sha256(old.read_bytes()).hexdigest(), 'after': hashlib.sha256((stage / 'nginx.conf').read_bytes()).hexdigest()}))
