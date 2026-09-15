"""Print credential presence only, never environment values."""
from pathlib import Path
import subprocess
pid = subprocess.check_output(['systemctl','show','cellx-extension-api','-p','MainPID','--value'],text=True).strip()
env = dict(item.decode().split('=',1) for item in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0') if b'=' in item)
print('Runway API key configured:', bool(env.get('RUNWAYML_API_SECRET') or env.get('RUNWAY_API_KEY')))
