import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
import server as app

class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=app.DATA;app.DATA=Path(self.tmp.name);app.init()
        self.httpd=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler);self.thread=threading.Thread(target=self.httpd.serve_forever,daemon=True);self.thread.start()
        self.url='http://127.0.0.1:'+str(self.httpd.server_port)
    def tearDown(self):
        self.httpd.shutdown();self.httpd.server_close();self.thread.join();app.DATA=self.old;self.tmp.cleanup()
    def request(self,path,data=None,headers=None):
        h={'Content-Type':'application/json',**(headers or {})}
        req=urllib.request.Request(self.url+path,data=json.dumps(data).encode() if data is not None else None,headers=h)
        return urllib.request.urlopen(req,timeout=5)
    def test_assets_and_state(self):
        for path in ['/','/app.js','/branding.js','/style.css','/favicon.svg']:
            with self.request(path) as r:self.assertEqual(r.status,200);self.assertTrue(r.read())
        with self.request('/api/state') as r:state=json.load(r)
        self.assertEqual(state['version'],1);self.assertEqual(state['records']['orders'],[])
    def test_cross_origin_write_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as error:self.request('/api/clients',{'name':'Indevido'},{'Origin':'https://outro-site.example'})
        self.assertEqual(error.exception.code,403)
        with self.request('/api/state') as r:self.assertEqual(json.load(r)['records']['clients'],[])
    def test_invalid_host_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as error:self.request('/api/state',headers={'Host':'outro-site.example'})
        self.assertEqual(error.exception.code,403)
    def test_backup_download(self):
        with self.request('/api/backup') as r:
            self.assertIn('attachment',r.headers['Content-Disposition']);backup=json.load(r)
        with self.request('/api/clients',{'name':'Cliente HTTP'}) as r:self.assertEqual(json.load(r)['name'],'Cliente HTTP')
        with self.request('/api/restore',{'backup':backup}) as r:self.assertTrue(json.load(r)['ok'])
        with self.request('/api/state') as r:self.assertEqual(json.load(r)['records']['clients'],[])
