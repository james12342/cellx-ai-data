"""Run staged, reviewed static asset deployment on the existing AWS host."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import tempfile

stage = Path(__file__).resolve().parent
manifest = json.loads((stage / 'manifest.json').read_text())
allowed = {Path('/var/www/cellx-extension-ui'), Path('/var/www/rdp-marketing-site'), Path('/var/www/cellx-data-ui')}
for entry in manifest:
    target = Path(entry['target'])
    assert target.parent in allowed and not target.is_symlink(), 'Unexpected deployment path'
    actual = hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
    assert actual == entry['before'], 'Live file changed: ' + str(target)
    assert hashlib.sha256((stage / entry['file']).read_bytes()).hexdigest() == entry['after']
backup = Path(tempfile.mkdtemp(prefix='cellx-before-i18n-'))
(backup / 'manifest.json').write_text(json.dumps(manifest, indent=2))
for entry in manifest:
    target = Path(entry['target'])
    if target.exists():
        shutil.copy2(target, backup / entry['file'])
try:
    Path('/var/www/cellx-data-ui').mkdir(exist_ok=True)
    for entry in sorted(manifest, key=lambda item: item['target'].endswith('.html')):
        target = Path(entry['target'])
        temporary = target.with_name(target.name + '.i18n-staging')
        shutil.copyfile(stage / entry['file'], temporary)
        os.chmod(temporary, 0o644)
        os.replace(temporary, target)
except Exception:
    for entry in manifest:
        target = Path(entry['target'])
        old = backup / entry['file']
        if old.exists():
            shutil.copy2(old, target)
        elif entry['before'] is None:
            target.unlink(missing_ok=True)
    raise
print('Published', len(manifest), 'static files. Backup:', backup)
