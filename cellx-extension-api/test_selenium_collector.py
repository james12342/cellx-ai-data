import socket
import unittest
from unittest.mock import patch
import selenium_collector as c

class Tests(unittest.TestCase):
    def test_private_dns_and_mixed_answers_denied(self):
        for ips in [['127.0.0.1'],['169.254.169.254'],['10.0.0.1'],['::1'],['224.0.0.1'],['8.8.8.8','192.168.1.1']]:
            answers=[(socket.AF_INET,socket.SOCK_STREAM,6,'',(ip,443)) for ip in ips]
            with patch.object(c.socket,'getaddrinfo',return_value=answers),self.assertRaises(ValueError): c.valid_url('https://example.com')
    def test_schemes_ports_credentials_denied(self):
        for u in ['file:///etc/passwd','http://user:password@example.com','https://example.com:3001']:
            with self.assertRaises(ValueError): c.valid_url(u)
    def test_depth_and_field_limits(self):
        with patch.object(c,'valid_url',return_value='https://example.com'):
            for values in [{'maxDetails':11},{'maxPages':6},{'maxPages':True},{'maxDetails':1},{'fields':['x','x']}]:
                with self.assertRaises(ValueError): c.config(dict(url='https://example.com',fields=['x'],**{k:v for k,v in values.items() if k!='fields'}) if 'fields' not in values else dict(url='https://example.com',**values))
    def test_job_isolation_and_stop_keeps_rows(self):
        import threading,time
        c.JOBS['test']={'id':'test','owner':'alice','state':'running','rows':[{'x':'y'}],'cancel':threading.Event(),'updated':time.time()}
        try:
            self.assertEqual(c.status('test','bob')[1],404)
            result,code=c.status('test','alice',True)
            self.assertEqual(code,200);self.assertEqual(result['rows'],[{'x':'y'}]);self.assertTrue(c.JOBS['test']['cancel'].is_set())
        finally:c.JOBS.pop('test')
    def test_proxy_blocks_private_connect(self):
        import threading
        proxy=c.ProxyServer(('127.0.0.1',0),c.Proxy)
        threading.Thread(target=proxy.serve_forever,daemon=True).start()
        try:
            with socket.create_connection(proxy.server_address,timeout=2) as client:
                client.sendall(b'CONNECT 169.254.169.254:443 HTTP/1.1\r\nHost: 169.254.169.254\r\n\r\n')
                self.assertIn(b'403',client.recv(1024))
        finally:proxy.shutdown();proxy.server_close()
if __name__=='__main__':unittest.main()
