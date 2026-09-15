"""Exercise the runner against intercepted fixture pages; never contact Instagram."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
from playwright.sync_api import sync_playwright
import instagram_runner as runner

markup = '''<html><head><meta charset="utf-8"></head><body><main></main><script>
for(let n=1;n<=8;n++){
 const a=document.createElement('article'); a.style.height='500px';
 a.innerHTML='<a href="/p/Test'+n+'/">Post '+n+'</a><button aria-label="Like">Like</button><button aria-label="Comment">Comment</button>';
 a.querySelector('[aria-label="Like"]').onclick=e=>{e.target.setAttribute('aria-label','Unlike');e.target.textContent='Unlike';};
 a.querySelector('[aria-label="Comment"]').onclick=()=>{
  const d=document.createElement('div');d.setAttribute('role','dialog');
  d.style.cssText='position:fixed;inset:20px;background:white;z-index:10';
  d.innerHTML='<textarea aria-label="Add a comment\u2026"></textarea><button>Post</button><button>Close</button>';
  d.querySelector('button').onclick=()=>{const p=document.createElement('p');p.textContent=d.querySelector('textarea').value;d.append(p);d.querySelector('textarea').value='';};
  d.querySelectorAll('button')[1].onclick=()=>d.remove();document.body.append(d);
 };document.querySelector('main').append(a);
}</script></body></html>'''


class FixturePW:
    def __enter__(self):
        self.manager = sync_playwright()
        self.real = self.manager.__enter__()
        return SimpleNamespace(chromium=SimpleNamespace(launch_persistent_context=self.launch))

    def launch(self, profile, **options):
        options['headless'] = True
        context = self.real.chromium.launch_persistent_context(profile, **options)
        context.route('**/*', lambda route: route.fulfill(status=200, content_type='text/html', body=markup))
        return context

    def __exit__(self, *args):
        return self.manager.__exit__(*args)


with tempfile.TemporaryDirectory(prefix='cellx-instagram-fixture-') as directory:
    with patch.dict(os.environ, {'LOCALAPPDATA': directory}), patch('playwright.sync_api.sync_playwright', FixturePW):
        first = runner.run({'minPosts': 2, 'maxPosts': 2, 'commentText': 'Editable test comment'}, True)
        assert first['ok'], first
        assert len(first['output']['rows']) == 2
        assert all(row['like'] == 'liked' and row['comment'] == 'posted' for row in first['output']['rows'])
        second = runner.run({'minPosts': 1, 'maxPosts': 1}, True)
        assert second['ok'], second
        assert second['output']['rows'][0]['post_url'] not in {row['post_url'] for row in first['output']['rows']}
print(json.dumps({'ok': True, 'checks': ['like verification', 'editable public comment', 'bounded stop', 'cross-run deduplication'], 'real_posts_modified': 0}))
