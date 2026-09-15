"""One-time structured annotation of the Agent Builder static UI."""
from html.parser import HTMLParser
from html import escape, unescape
from pathlib import Path
import json

target = Path('cellx-extension-ui/index.html')
source = target.read_text(encoding='utf-8')
lines = source.splitlines(keepends=True)
offsets = [0]
for line in lines:
    offsets.append(offsets[-1] + len(line))
edits = []
keys = set()
skip_ids = {'workflowTitle', 'workflowDescription', 'apiStatus', 'dbStatus', 'templateLibraryStatus', 'templateManagerStatus', 'managedTemplateCount', 'managedScriptCount', 'managedTimerCount', 'marketplaceStatus', 'marketplaceAccountStatus', 'aiVoiceDraftMeta', 'aiVoiceStatus'}

class Annotator(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.stack = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        start = offsets[self.getpos()[0] - 1] + self.getpos()[1]
        raw = self.get_starttag_text()
        additions = ''
        for name in ('placeholder', 'title', 'aria-label'):
            text = attributes.get(name, '')
            if text and any(c.isalpha() for c in text) and not text.startswith(('/ext-api', 'you@', 'developer@')):
                additions += ' data-i18n-' + name + '="' + escape(text, quote=True) + '"'
                keys.add(text)
        if tag == 'option' and 'value' not in attributes:
            end = source.index('</option>', start)
            value = unescape(source[start + len(raw):end])
            additions += ' value="' + escape(value, quote=True) + '"'
        if additions:
            edits.append((start + len(raw) - 1, start + len(raw) - 1, additions))
        if tag not in ('meta', 'link', 'input', 'img', 'br', 'hr'):
            self.stack.append((tag, attributes, start, raw))

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1][0] == tag:
            self.stack.pop()

    def handle_data(self, data):
        if not self.stack or not data.strip() or not any(c.isalpha() for c in data):
            return
        tag, attrs, opening, raw = self.stack[-1]
        if any(t in ('script', 'style', 'pre', 'textarea') or a.get('id') in skip_ids for t, a, _, _ in self.stack):
            return
        text = data.strip()
        if text in ('Cell AI Data', 'CellX', 'API') or 'data-i18n' in attrs:
            return
        # Entity-containing text is annotated manually after this one-time pass.
        start = offsets[self.getpos()[0] - 1] + self.getpos()[1]
        if '&' in source[opening + len(raw):source.find('</', opening + len(raw))]:
            return
        keys.add(text)
        if tag in ('option', 'title'):
            edits.append((opening + len(raw) - 1, opening + len(raw) - 1, ' data-i18n="' + escape(text, quote=True) + '"'))
        else:
            left = len(data) - len(data.lstrip())
            right = len(data.rstrip())
            edits.append((start + left, start + right, '<span data-i18n="' + escape(text, quote=True) + '">' + data[left:right] + '</span>'))

parser = Annotator()
parser.feed(source)
for start, end, value in sorted(edits, reverse=True):
    source = source[:start] + value + source[end:]
target.write_text(source, encoding='utf-8')
Path('outputs/agent-static-i18n-keys.json').write_text(json.dumps(sorted(keys), ensure_ascii=False, indent=2), encoding='utf-8')
print('Annotated', len(keys), 'static messages')
