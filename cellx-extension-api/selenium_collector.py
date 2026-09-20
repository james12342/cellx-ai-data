"""Bounded Selenium jobs. Public web only, isolated browser, validated egress proxy."""
import copy
import hashlib
import ipaddress
import json
import os
import select
import shutil
import socket
import socketserver
import tempfile
import threading
import time
import uuid
from urllib.parse import urlsplit, urljoin

JOBS = {}
LOCK = threading.RLock()
ACTIVE = threading.Semaphore(1)
TERMINAL = {'completed', 'stopped', 'failed', 'paused'}

def public_addresses(host, port):
    answers = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not answers or any(not ipaddress.ip_address(a[4][0]).is_global or ipaddress.ip_address(a[4][0]).is_multicast or ipaddress.ip_address(a[4][0]).is_reserved for a in answers):
        raise ValueError('Only public website addresses are allowed.')
    return answers

def valid_url(url):
    u = urlsplit(str(url))
    if u.scheme not in ('http', 'https') or not u.hostname or u.username or u.password or u.port not in (None, 80, 443):
        raise ValueError('Enter a public HTTP or HTTPS URL using a standard port.')
    public_addresses(u.hostname, u.port or (443 if u.scheme == 'https' else 80))
    return u._replace(fragment='').geturl()

class Proxy(socketserver.StreamRequestHandler):
    def handle(self):
        remote = None
        try:
            self.connection.settimeout(20)
            line = self.rfile.readline(8193).decode('ascii')
            method, target, version = line.strip().split(' ')
            headers = []
            for _ in range(100):
                h = self.rfile.readline(8193)
                if h in (b'\r\n', b'\n', b''): break
                headers.append(h)
            if method == 'CONNECT':
                u = urlsplit('https://' + target)
                if u.port != 443: raise ValueError('Port blocked')
            else:
                valid_url(target)
                u = urlsplit(target)
                if u.scheme != 'http': raise ValueError('Scheme blocked')
            port = u.port or (443 if method == 'CONNECT' else 80)
            # Connect to the validated numeric address, avoiding a second DNS lookup.
            for family, kind, proto, _, addr in public_addresses(u.hostname, port):
                try:
                    remote = socket.socket(family, kind, proto)
                    remote.settimeout(15)
                    remote.connect(addr)
                    break
                except OSError:
                    remote.close()
                    remote = None
            if remote is None: raise OSError('Connection failed')
            if method == 'CONNECT':
                self.connection.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
            else:
                if method not in ('GET', 'HEAD'): raise ValueError('Read-only browsing')
                path = u.path or '/'
                if u.query: path += '?' + u.query
                clean = [h for h in headers if not h.lower().startswith((b'proxy-', b'connection:', b'host:'))]
                remote.sendall(f'{method} {path} HTTP/1.1\r\nHost: {u.netloc}\r\nConnection: close\r\n'.encode() + b''.join(clean) + b'\r\n')
            end = time.monotonic() + 120
            while time.monotonic() < end:
                ready, _, _ = select.select([self.connection, remote], [], [], 2)
                for src in ready:
                    data = src.recv(65536)
                    if not data: return
                    (remote if src is self.connection else self.connection).sendall(data)
        except Exception:
            try: self.connection.sendall(b'HTTP/1.1 403 Forbidden\r\nConnection: close\r\nContent-Length: 0\r\n\r\n')
            except OSError: pass
        finally:
            if remote: remote.close()

class ProxyServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

SNAPSHOT = """return {url:location.href,title:document.title,text:(document.body?.innerText||'').slice(0,60000),truncated:(document.body?.innerText||'').length>60000,links:[...document.querySelectorAll('a[href]')].filter(a=>a.getClientRects().length).slice(0,500).map(a=>({text:a.innerText.trim().slice(0,200),url:a.href.slice(0,3000)}))};"""

def config(payload):
    fields = payload.get('fields')
    if not isinstance(fields, list) or not 1 <= len(fields) <= 12 or any(not isinstance(f, str) or not f.strip() or len(f)>60 for f in fields) or len(set(fields)) != len(fields):
        raise ValueError('Enter 1–12 unique field names.')
    def bounded(name, default, low, high):
        value = payload.get(name, default)
        if isinstance(value, bool) or str(value) != str(int(value)) or not low <= int(value) <= high: raise ValueError('Invalid ' + name)
        return int(value)
    result = {'url':valid_url(payload.get('url','')), 'fields':fields, 'maxPages':bounded('maxPages',1,1,5), 'maxDetails':bounded('maxDetails',0,0,10)}
    for key in ('nextSelector','detailSelector'):
        result[key] = str(payload.get(key,'')).strip()
        if len(result[key]) > 500: raise ValueError('Selector too long')
    if result['maxDetails'] and not result['detailSelector']: raise ValueError('Specify a CSS selector for detail links.')
    return result

def start(payload, owner):
    try: cfg = config(payload)
    except (ValueError,TypeError,OverflowError,OSError) as e: return {'ok':False,'message':str(e)},400
    if not os.getenv('OPENAI_API_KEY'): return {'ok':False,'message':'OpenAI extraction is not configured.'},503
    with LOCK:
        for key in list(JOBS):
            if JOBS[key]['state'] in TERMINAL and time.time()-JOBS[key]['updated']>3600: del JOBS[key]
        if any(j['state'] not in TERMINAL for j in JOBS.values()): return {'ok':False,'message':'The browser is busy. Try again after the current collection finishes.'},409
        if len(JOBS)>=100: return {'ok':False,'message':'Job storage is full. Try later.'},429
        key=uuid.uuid4().hex
        JOBS[key]={'id':key,'owner':owner,'state':'queued','message':'Queued','rows':[],'fields':cfg['fields'],'sources':[],'warnings':[],'updated':time.time(),'cancel':threading.Event()}
    threading.Thread(target=run,args=(key,cfg),daemon=True).start()
    return {'ok':True,'jobId':key},202

def status(key,owner,stop=False):
    with LOCK:
        job=JOBS.get(key)
        if not job or job['owner']!=owner: return {'ok':False,'message':'Collection not found or expired.'},404
        if stop and job['state'] not in TERMINAL:
            job['cancel'].set();job['message']='Stopping; completed rows will be kept.'
        return {'ok':True,**copy.deepcopy({k:v for k,v in job.items() if k not in ('owner','cancel')})},200

def run(key,cfg):
    driver=proxy=None
    profile=tempfile.mkdtemp(prefix='cellx-collector-')
    job=JOBS[key]
    deadline=time.monotonic()+600
    def update(**values):
        with LOCK: job.update(values,updated=time.time())
    def cancelled():
        if job['cancel'].is_set(): raise InterruptedError('Stopped by user.')
        if time.monotonic()>deadline: raise TimeoutError('Collection time limit reached.')
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from browser_collector import extract
        cancelled()
        update(state='running',message='Starting isolated Chrome browser...')
        proxy=ProxyServer(('127.0.0.1',0),Proxy)
        threading.Thread(target=proxy.serve_forever,daemon=True).start()
        opts=webdriver.ChromeOptions()
        for arg in ['--headless=new','--disable-dev-shm-usage','--disable-quic','--disable-background-networking','--disable-extensions','--disable-sync','--disable-features=OptimizationHints','--force-webrtc-ip-handling-policy=disable_non_proxied_udp','--window-size=1440,1000','--proxy-bypass-list=<-loopback>',f'--proxy-server=http://127.0.0.1:{proxy.server_address[1]}','--user-data-dir='+profile]: opts.add_argument(arg)
        opts.add_experimental_option('prefs',{'profile.default_content_setting_values.notifications':2,'profile.managed_default_content_settings.images':2,'download_restrictions':3})
        if os.getenv('COLLECTOR_CHROME_BINARY'): opts.binary_location=os.environ['COLLECTOR_CHROME_BINARY']
        service=Service(executable_path=os.environ['COLLECTOR_CHROMEDRIVER']) if os.getenv('COLLECTOR_CHROMEDRIVER') else Service()
        driver=webdriver.Chrome(service=service,options=opts)
        driver.set_page_load_timeout(35)
        driver.set_script_timeout(10)
        driver.execute_cdp_cmd('Browser.setDownloadBehavior',{'behavior':'deny'})
        seen=set(); seen_rows=set(); detail_links=[]
        def collect(url=None):
            cancelled()
            if url:
                valid_url(url)
                driver.get(url)
            WebDriverWait(driver,15).until(lambda d:d.execute_script('return document.readyState') in ('interactive','complete'))
            time.sleep(1)
            cancelled()
            valid_url(driver.current_url)
            page=driver.execute_script(SNAPSHOT)
            low=(page['title']+' '+page['text'][:2500]).lower()
            if any(v in low for v in ['robots.txt','request blocked','verify you are human','checking your browser','just a moment...','access denied','captcha','sign in to continue','log in to continue']): raise PermissionError('The website requires login or verification. Automated collection paused.')
            fingerprint=hashlib.sha256(page['text'].encode()).hexdigest()
            if fingerprint in seen: return False
            seen.add(fingerprint)
            update(message=f'Extracting page {len(job["sources"])+1}...')
            result,code=extract({'fields':cfg['fields'],'page':page})
            if code!=200: raise RuntimeError('Field extraction failed. Completed results are preserved.')
            warning=str(result.get('warning','')).lower()
            if not result.get('rows') and any(v in warning for v in ['blocked','verification','captcha','login','access denied']): raise PermissionError('The website blocked automated access or requires verification. Use Chrome helper mode for this website.')
            with LOCK:
                for row in result['rows']:
                    fingerprint=json.dumps(row,sort_keys=True)
                    if fingerprint not in seen_rows: seen_rows.add(fingerprint);job['rows'].append(row)
                job['sources'].append(page['url'])
                if result.get('warning'): job['warnings'].append(result['warning'])
                if page.get('truncated') or len(result['rows'])>=100: job['warnings'].append('Page or row limit reached; results may be incomplete.')
            return True
        for i in range(cfg['maxPages']):
            if not collect(cfg['url'] if i==0 else None): break
            if cfg['maxDetails']:
                for el in driver.find_elements(By.CSS_SELECTOR,cfg['detailSelector']):
                    href=el.get_attribute('href')
                    if href and urlsplit(href).hostname==urlsplit(cfg['url']).hostname and href not in detail_links and href not in job['sources']: detail_links.append(href)
                    if len(detail_links)>=cfg['maxDetails']: break
            if i+1>=cfg['maxPages']: break
            selector=cfg['nextSelector'] or 'a[rel="next"],button[aria-label="Next"],a[aria-label="Next"]'
            targets=[el for el in driver.find_elements(By.CSS_SELECTOR,selector) if el.is_displayed() and el.is_enabled() and el.get_attribute('aria-disabled')!='true']
            if not targets:
                with LOCK: job['warnings'].append('No matching next-page control found. Collection ended at the current page.')
                update(message='No next page found.')
                break
            cancelled()
            old=driver.execute_script('return document.body.innerText')
            targets[0].click()
            WebDriverWait(driver,15).until(lambda d:d.execute_script('return document.body.innerText')!=old)
        for href in detail_links[:cfg['maxDetails']]: collect(href)
        cancelled()
        update(state='completed',message=f'Collected {len(job["sources"])} pages and {len(job["rows"])} records. Review warnings for completeness.')
    except InterruptedError as e: update(state='stopped',message=str(e))
    except PermissionError as e: update(state='paused',message=str(e))
    except Exception as e:
        print('Collector failure:',str(e)[:1500],flush=True)
        update(state='failed',message=f'Collection stopped ({type(e).__name__}). Completed rows are preserved. Check the URL, selectors or website access.')
    finally:
        if driver:
            try: driver.quit()
            except Exception: pass
        if proxy: proxy.shutdown();proxy.server_close()
        shutil.rmtree(profile,ignore_errors=True)

def owner_id(headers):
    return hashlib.sha256(headers.get('X-Workflow-Admin-Token','').encode()).hexdigest()

def relay(action,payload,headers):
    from urllib.request import Request,urlopen
    from urllib.error import HTTPError,URLError
    token=os.getenv('COLLECTOR_INTERNAL_TOKEN','')
    if not token: return {'ok':False,'message':'Automatic browser collection is not configured.'},503
    data=json.dumps({'owner':owner_id(headers),'payload':payload}).encode()
    req=Request('http://127.0.0.1:3002/'+action,data=data,headers={'Content-Type':'application/json','X-Collector-Key':token})
    try:
        with urlopen(req,timeout=15) as response: return json.load(response),response.status
    except HTTPError as e: return json.load(e),e.code
    except (URLError,TimeoutError): return {'ok':False,'message':'The automatic browser service is unavailable.'},503

if __name__=='__main__':
    from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
    import hmac
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_POST(self):
            if not os.getenv('COLLECTOR_INTERNAL_TOKEN') or not hmac.compare_digest(self.headers.get('X-Collector-Key',''),os.environ['COLLECTOR_INTERNAL_TOKEN']):
                self.send_error(403);return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=32768: raise ValueError('Request too large')
                data=json.loads(self.rfile.read(length))
                payload,owner=data['payload'],data['owner']
                if self.path=='/start': body,code=start(payload,owner)
                elif self.path in ('/status','/stop'): body,code=status(str(payload.get('jobId','')),owner,self.path=='/stop')
                else: body,code={'ok':False,'message':'Not found'},404
            except Exception: body,code={'ok':False,'message':'Invalid collector request.'},400
            raw=json.dumps(body).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    ThreadingHTTPServer(('127.0.0.1',3002),Handler).serve_forever()
