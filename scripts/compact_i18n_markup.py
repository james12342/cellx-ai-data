"""Mechanical cleanup: put a sole translated child's annotation on its parent."""
from pathlib import Path
import re
path = Path('cellx-extension-ui/index.html')
html = path.read_text(encoding='utf-8')
pattern = re.compile(r'<(button|strong|h1|p|a|div|span|label)([^<>]*)>\s*<span (data-i18n="[^"]*")>([^<>]*)</span>\s*</\1>')
html = pattern.sub(lambda m: '<' + m[1] + m[2] + ' ' + m[3] + '>' + m[4] + '</' + m[1] + '>', html)
path.write_text(html, encoding='utf-8')
