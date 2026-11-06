import http.cookiejar
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch
import security
import server as app

class SecurityTests(unittest.TestCase):
    password='A-test-password-25-characters'
    @classmethod
    def setUpClass(cls):cls.encoded=security.password_hash(cls.password)
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=app.DATA;app.DATA=Path(self.tmp.name);app.init()
        self.httpd=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        self.url='http://127.0.0.1:'+str(self.httpd.server_port)
        self.httpd.access=security.AccessConfig(True,self.url,'tiago',self.encoded)
        self.thread=threading.Thread(target=self.httpd.serve_forever,daemon=True);self.thread.start()
        self.jar=http.cookiejar.CookieJar();self.client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
    def tearDown(self):
        self.httpd.shutdown();self.httpd.server_close();self.thread.join();app.DATA=self.old;self.tmp.cleanup()
    def request(self,path,data=None,headers=None,method=None):
        request=urllib.request.Request(self.url+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json',**(headers or {})},method=method)
        return self.client.open(request,timeout=10)
    def enter(self):
        with self.request('/api/auth/login',{'username':'tiago','password':self.password}) as response:
            cookie=response.headers['Set-Cookie'];self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=Strict',cookie)
            self.assertNotIn('token',json.load(response))
    def test_anonymous_users_cannot_read_or_write_business_data(self):
        for path,data,method in [('/api/state',None,None),('/api/backup',None,None),('/api/backup/previous',None,None),('/api/clients',{'name':'Blocked'},None),('/api/clients/missing',{},'DELETE')]:
            with self.assertRaises(urllib.error.HTTPError) as error:self.request(path,data,method=method)
            self.assertEqual(error.exception.code,401)
        with self.request('/') as response:self.assertTrue(response.geturl().endswith('/login'));self.assertIn(b'loginform',response.read())
        with app.transaction() as c:self.assertEqual(app.all_rows(c,'clients'),[])
    def test_login_logout_and_backup_exclude_authentication_secrets(self):
        self.enter()
        with self.request('/api/clients',{'name':'Cliente autenticado'}) as response:self.assertEqual(json.load(response)['name'],'Cliente autenticado')
        with self.request('/api/state') as response:self.assertTrue(json.load(response)['auth']['enabled'])
        with self.request('/api/backup') as response:
            backup=json.load(response);self.assertEqual(set(backup['records']),app.ENTITIES)
            self.assertNotIn('auth',backup);self.assertNotIn(self.encoded,json.dumps(backup))
        with self.request('/api/auth/logout',{}) as response:self.assertTrue(json.load(response)['ok'])
        with self.assertRaises(urllib.error.HTTPError) as error:self.request('/api/state')
        self.assertEqual(error.exception.code,401)
    def test_wrong_password_does_not_set_session(self):
        with self.assertRaises(urllib.error.HTTPError) as error:self.request('/api/auth/login',{'username':'tiago','password':'wrong'})
        self.assertEqual(error.exception.code,401);self.assertEqual(len(list(self.jar)),0)
    def test_repeated_failures_are_rate_limited(self):
        for _ in range(5):
            with self.assertRaises(urllib.error.HTTPError) as error:self.request('/api/auth/login',{'username':'tiago','password':'wrong'})
            self.assertEqual(error.exception.code,401)
        with self.assertRaises(urllib.error.HTTPError) as error:self.request('/api/auth/login',{'username':'tiago','password':self.password})
        self.assertEqual(error.exception.code,429)
    def test_expired_session_is_rejected(self):
        self.enter()
        with app.transaction() as c:c.execute('UPDATE auth_sessions SET expires=0')
        with self.assertRaises(urllib.error.HTTPError) as error:self.request('/api/state')
        self.assertEqual(error.exception.code,401)
    def test_password_rotation_revokes_previous_sessions(self):
        self.enter();self.httpd.access=security.AccessConfig(True,self.url,'tiago',security.password_hash('A-new-owner-password-123'))
        with self.assertRaises(urllib.error.HTTPError) as error:self.request('/api/state')
        self.assertEqual(error.exception.code,401)
    def test_cross_origin_requests_are_rejected_even_with_session(self):
        self.enter()
        with self.assertRaises(urllib.error.HTTPError) as error:self.request('/api/clients',{'name':'Blocked'},{'Origin':'https://outside.example'})
        self.assertEqual(error.exception.code,403)
    def test_health_and_login_assets_remain_available(self):
        for path in ['/healthz','/login','/login.js','/style.css','/favicon.svg']:
            with self.request(path) as response:self.assertEqual(response.status,200)
    def test_public_deployment_fails_closed_without_credentials(self):
        with patch.dict('os.environ',{'LOJINHA_MODE':'production','LOJINHA_PUBLIC_URL':'https://shop.example','LOJINHA_ADMIN_PASSWORD_HASH':''},clear=True):
            with self.assertRaises(ValueError):security.AccessConfig.from_environment('0.0.0.0')
        secure=security.AccessConfig(True,'https://shop.example','tiago',self.encoded)
        self.assertIn('Secure',secure.cookie('some-token'));self.assertTrue(secure.cookie_name.startswith('__Host-'))
        self.assertTrue(secure.host_allowed('shop.example',10000));self.assertFalse(secure.host_allowed('attacker.example',10000))
    def test_cloud_configuration_never_falls_back_to_local_disk(self):
        with patch.dict('os.environ',{'LOJINHA_REQUIRE_POSTGRES':'1','LOJINHA_DATABASE_URL':''},clear=True):
            with self.assertRaisesRegex(RuntimeError,'LOJINHA_DATABASE_URL'):app.connect()

if __name__=='__main__':unittest.main()
