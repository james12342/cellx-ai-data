"""Apply only the Data Explorer integration to the captured live server source."""
import ast
from pathlib import Path
import hashlib
import json
import shutil

root = Path(__file__).resolve().parent.parent
old = (root / 'outputs/i18n-before/api/server.py').read_text(encoding='utf-8')
new = (root / 'cellx-extension-api/server.py').read_text(encoding='utf-8')
new_tree = ast.parse(new)
new_lines = new.splitlines(keepends=True)
handler = next(n for n in new_tree.body if isinstance(n, ast.ClassDef) and n.name == 'Handler')
def segment(node):
    return ''.join(new_lines[node.lineno - 1:node.end_lineno]) + '\n'
def method(name):
    return next(n for n in handler.body if isinstance(n, ast.FunctionDef) and n.name == name)
def once(source, needle, replacement):
    assert source.count(needle) == 1, 'Unexpected integration anchor: ' + needle
    return source.replace(needle, replacement)

request = next(n for n in new_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'data_explorer_request')
staged = once(old, 'def safe_static_path(', segment(request) + '\n\ndef safe_static_path(')
methods = segment(method('serve_data_explorer')) + '\n' + segment(method('do_PUT'))
methods += '\n    do_PATCH = do_PUT\n    do_DELETE = do_PUT\n    do_HEAD = do_PUT\n\n'
staged = once(staged, 'class Handler(BaseHTTPRequestHandler):\n', 'class Handler(BaseHTTPRequestHandler):\n' + methods)
staged = once(staged, '    def log_message(self, fmt, *args):\n', '    def log_message(self, fmt, *args):\n        if normalize_api_path(urlparse(self.path).path).startswith("/data-explorer"):\n            return\n')
staged = once(staged, '        if not raw_path.startswith("/ext-api") and self.serve_ui_static(raw_path):', '        if normalize_api_path(raw_path).startswith("/data-explorer"):\n            return self.serve_data_explorer("GET")\n        if not raw_path.startswith("/ext-api") and self.serve_ui_static(raw_path):')
needle = '    def do_POST(self):\n        path = normalize_api_path(urlparse(self.path).path)\n'
staged = once(staged, needle, needle + '        if path.startswith("/data-explorer"):\n            return self.serve_data_explorer("POST")\n')
ast.parse(staged)

def existing_functions(source):
    tree = ast.parse(source)
    result = {node.name: ast.dump(node) for node in tree.body if isinstance(node, ast.FunctionDef)}
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Handler')
    result.update({'Handler.' + node.name: ast.dump(node) for node in cls.body if isinstance(node, ast.FunctionDef)})
    return result
old_functions, staged_functions = existing_functions(old), existing_functions(staged)
allowed = {'Handler.do_GET', 'Handler.do_POST', 'Handler.log_message'}
assert all(staged_functions[name] == value for name, value in old_functions.items() if name not in allowed)
stage = root / 'outputs/data-api-deploy'
stage.mkdir(exist_ok=True)
(stage / 'server.py').write_text(staged, encoding='utf-8')
for name in ['data_explorer.py', 'test_data_explorer.py']:
    shutil.copyfile(root / 'cellx-extension-api' / name, stage / name)
manifest = {'before_server': hashlib.sha256((root / 'outputs/i18n-before/api/server.py').read_bytes()).hexdigest(),
            'files': {name: hashlib.sha256((stage / name).read_bytes()).hexdigest() for name in ['server.py', 'data_explorer.py']}}
(stage / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print('Staged minimal Data Explorer API; all other existing function ASTs match live baseline.')
