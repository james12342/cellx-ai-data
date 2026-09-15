"""Stage only reviewed frontend assets with pre-deployment hash guards."""
from pathlib import Path
import hashlib
import json
import shutil

root = Path(__file__).resolve().parent.parent
stage = root / 'outputs/i18n-deploy'
stage.mkdir(exist_ok=True)
sites = {
    'agent': ('cellx-extension-ui', '/var/www/cellx-extension-ui', ['app.js', 'i18n.js', 'i18n.css', 'i18n-static-zh.js', 'i18n-zh.js', 'index.html']),
    'marketing': ('rdp-marketing-site', '/var/www/rdp-marketing-site', ['app.js', 'analytics.js', 'workflow-motion.js', 'i18n.js', 'i18n.css', 'i18n-zh.js', 'index.html', 'analytics.html']),
    'data': ('cellx-data-ui', '/var/www/cellx-data-ui', ['app.js', 'styles.css', 'logo.png', 'i18n.js', 'i18n.css', 'i18n-zh.js', 'index.html']),
}
manifest = []
for site, (local, remote, files) in sites.items():
    for shared in ('i18n.js', 'i18n.css'):
        assert (root / local / shared).read_bytes() == (root / 'shared' / shared).read_bytes(), 'Run sync_i18n_assets.ps1 before staging'
    for filename in files:
        source = root / local / filename
        baseline = root / 'outputs/i18n-before' / site / filename
        data = source.read_bytes()
        if site == 'agent' and filename == 'app.js':
            # Preserve the existing live portable-edition link, unrelated to localization.
            data = data.replace(b'href="http://127.0.0.1:3001/agent/"', b'href="http://127.0.0.1:3001/workflow/"')
        target = stage / f'{site}-{filename}'
        target.write_bytes(data)
        manifest.append({
            'file': target.name,
            'target': remote + '/' + filename,
            'before': hashlib.sha256(baseline.read_bytes()).hexdigest() if baseline.exists() else None,
            'after': hashlib.sha256(data).hexdigest(),
        })
(stage / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
shutil.copyfile(root / 'scripts/install_i18n_deploy.py', stage / 'install.py')
print('Staged', len(manifest), 'static files; no API, registry or scheduler changes.')
