"""Authentication for the hosted, single-owner Lojinha deployment."""
import base64
import hashlib
import hmac
import os
import secrets
import time
from http.cookies import SimpleCookie
from urllib.parse import urlsplit

SESSION_SECONDS=12*60*60
MAX_FAILURES=5
LOCK_SECONDS=15*60

def password_hash(password):
    if not isinstance(password,str) or len(password)<12: raise ValueError('Use uma senha com pelo menos 12 caracteres.')
    salt=secrets.token_bytes(16)
    digest=hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1,dklen=32)
    return 'scrypt$'+base64.urlsafe_b64encode(salt).decode()+'$'+base64.urlsafe_b64encode(digest).decode()

def verify_password(password,encoded):
    try:
        algorithm,salt,digest=encoded.split('$')
        if algorithm!='scrypt' or len(password)>1024: return False
        actual=hashlib.scrypt(password.encode(),salt=base64.urlsafe_b64decode(salt),n=16384,r=8,p=1,dklen=32)
        return hmac.compare_digest(actual,base64.urlsafe_b64decode(digest))
    except (ValueError,TypeError): return False

class AccessConfig:
    def __init__(self,require_auth=False,origin='',username='admin',encoded_password=''):
        self.required=require_auth
        self.origin=origin.rstrip('/')
        self.username=username
        self.encoded_password=encoded_password
        self.secure=self.origin.startswith('https://')
        self.cookie_name='__Host-lojinha_session' if self.secure else 'lojinha_session'
        if origin:
            parsed=urlsplit(self.origin)
            if parsed.scheme not in ['http','https'] or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username: raise ValueError('LOJINHA_PUBLIC_URL deve conter somente a origem da aplicação.')
        if require_auth and (not username or not encoded_password.startswith('scrypt$')): raise ValueError('Configure LOJINHA_ADMIN_USER e LOJINHA_ADMIN_PASSWORD_HASH antes de expor a aplicação.')

    @classmethod
    def from_environment(cls,host):
        production=os.environ.get('LOJINHA_MODE')=='production' or host not in ['127.0.0.1','localhost','::1']
        origin=os.environ.get('LOJINHA_PUBLIC_URL','')
        if not origin and os.environ.get('RENDER_EXTERNAL_HOSTNAME'): origin='https://'+os.environ['RENDER_EXTERNAL_HOSTNAME']
        if production and not origin.startswith('https://'): raise ValueError('A publicação exige uma origem HTTPS em LOJINHA_PUBLIC_URL ou RENDER_EXTERNAL_HOSTNAME.')
        return cls(production,origin,os.environ.get('LOJINHA_ADMIN_USER','admin'),os.environ.get('LOJINHA_ADMIN_PASSWORD_HASH',''))

    def host_allowed(self,host,port):
        allowed={f'127.0.0.1:{port}',f'localhost:{port}'}
        if self.origin: allowed.add(urlsplit(self.origin).netloc)
        return host in allowed

    def origin_allowed(self,origin,port):
        return not origin or origin in {self.origin,f'http://127.0.0.1:{port}',f'http://localhost:{port}'}

    def cookie(self,token='',clear=False):
        return f'{self.cookie_name}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={0 if clear else SESSION_SECONDS}'+('; Secure' if self.secure else '')

def prepare_tables(c):
    c.execute('CREATE TABLE IF NOT EXISTS auth_sessions (token_hash TEXT PRIMARY KEY, username TEXT NOT NULL, expires BIGINT NOT NULL)')
    c.execute('CREATE TABLE IF NOT EXISTS auth_attempts (key TEXT PRIMARY KEY, failures INTEGER NOT NULL, since BIGINT NOT NULL)')
    c.execute('CREATE TABLE IF NOT EXISTS auth_config (id INTEGER PRIMARY KEY CHECK(id=1), fingerprint TEXT NOT NULL)')

def sync_config(c,config):
    prepare_tables(c)
    fingerprint=hashlib.sha256((config.username+'\0'+config.encoded_password).encode()).hexdigest()
    row=c.execute('SELECT fingerprint FROM auth_config WHERE id=1').fetchone()
    if not row or not hmac.compare_digest(row[0],fingerprint):
        c.execute('DELETE FROM auth_sessions');c.execute('DELETE FROM auth_attempts')
        c.execute('INSERT INTO auth_config (id,fingerprint) VALUES(1,?) ON CONFLICT(id) DO UPDATE SET fingerprint=excluded.fingerprint',(fingerprint,))

def cookie_token(header,config):
    cookie=SimpleCookie()
    try: cookie.load(header or '');token=cookie.get(config.cookie_name)
    except Exception: return ''
    value=token.value if token else ''
    return value if 30<=len(value)<=128 else ''

def authenticated(c,header,config):
    if not config.required: return True
    sync_config(c,config)
    token=cookie_token(header,config)
    if not token:return False
    row=c.execute('SELECT username,expires FROM auth_sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
    return bool(row and row[0]==config.username and row[1]>int(time.time()))

def login(c,username,password,peer,config):
    sync_config(c,config);stamp=int(time.time());key=hashlib.sha256(peer.encode()).hexdigest()
    c.execute('DELETE FROM auth_sessions WHERE expires<=?',(stamp,))
    row=c.execute('SELECT failures,since FROM auth_attempts WHERE key=?',(key,)).fetchone()
    if row and stamp-row[1]<LOCK_SECONDS and row[0]>=MAX_FAILURES:return None,'locked'
    # Perform the password check even for an unknown user.
    valid=verify_password(password,config.encoded_password)
    if not (valid and hmac.compare_digest(username.encode(),config.username.encode())):
        failures=row[0]+1 if row and stamp-row[1]<LOCK_SECONDS else 1
        since=row[1] if row and stamp-row[1]<LOCK_SECONDS else stamp
        c.execute('INSERT INTO auth_attempts (key,failures,since) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET failures=excluded.failures,since=excluded.since',(key,failures,since));return None,'invalid'
    c.execute('DELETE FROM auth_attempts WHERE key=?',(key,))
    token=secrets.token_urlsafe(32)
    c.execute('INSERT INTO auth_sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),config.username,stamp+SESSION_SECONDS))
    return token,None

def logout(c,header,config):
    prepare_tables(c);token=cookie_token(header,config)
    if token:c.execute('DELETE FROM auth_sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))
