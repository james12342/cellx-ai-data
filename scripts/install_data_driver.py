"""Install the hash-pinned pure Python wheel without requiring system pip."""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from urllib.request import urlopen
import zipfile

expected = '62169ce6d5510f08e140c5e7990ee884a9764024e4a9a27b2cc11f1099322ae0'
root = Path('/opt/cellx-extension-api')
assert not (root / 'pymysql').exists(), 'Driver directory already exists; inspect before replacing'
metadata = json.load(urlopen('https://pypi.org/pypi/PyMySQL/1.2.0/json', timeout=20))
wheel = next(item for item in metadata['urls'] if item['filename'] == 'pymysql-1.2.0-py3-none-any.whl')
assert wheel['digests']['sha256'] == expected
assert wheel['url'].startswith('https://files.pythonhosted.org/')
data = urlopen(wheel['url'], timeout=20).read(200000)
assert hashlib.sha256(data).hexdigest() == expected
stage = Path(tempfile.mkdtemp(prefix='data-driver-', dir=root))
with zipfile.ZipFile(io.BytesIO(data)) as archive:
    for name in archive.namelist():
        path = PurePosixPath(name)
        assert not path.is_absolute() and '..' not in path.parts
        assert path.parts[0] in {'pymysql', 'pymysql-1.2.0.dist-info'}
    archive.extractall(stage)
for folder in stage.iterdir():
    assert not (root / folder.name).exists()
    shutil.move(str(folder), str(root / folder.name))
stage.rmdir()
print('Installed verified PyMySQL 1.2.0 wheel into application directory only.')
