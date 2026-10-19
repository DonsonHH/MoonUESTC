"""Self-hosted ALTCHA registration challenges; no remote verification service."""
import base64
import binascii
import hmac
import json
import re
import time

from altcha import create_challenge,verify_solution
from .web_errors import WebError


class RegistrationCaptcha:
    TTL=120

    def __init__(self,store):
        self.store=store
        self.key=bytes.fromhex(store.vault.digest('captcha_signing','altcha-v2'))
        with store.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS web_registration_challenges(signature TEXT PRIMARY KEY,challenge_json TEXT NOT NULL,remote_digest TEXT NOT NULL,expires_at REAL NOT NULL,used_at REAL)')
            db.execute('CREATE INDEX IF NOT EXISTS web_registration_challenges_expiry ON web_registration_challenges(expires_at)')

    def issue(self,remote_ip):
        stamp=time.time()
        buckets=[(self.store.vault.digest('captcha_issue_ip',str(remote_ip)),60),
                 (self.store.vault.digest('captcha_issue_global','all'),240)]
        with self.store.db(True) as db:
            if not db.execute("SELECT 1 FROM web_users WHERE role='admin' AND active=1 LIMIT 1").fetchone():
                raise WebError(503,'not_initialized','管理员尚未初始化，请联系管理员。')
            db.execute('DELETE FROM web_login_limits WHERE reset_at<=?',(stamp,))
            db.execute('DELETE FROM web_registration_challenges WHERE expires_at<=?',(stamp,))
            for bucket,limit in buckets:
                row=db.execute('SELECT count FROM web_login_limits WHERE bucket=?',(bucket,)).fetchone()
                if row and row['count']>=limit:
                    raise WebError(429,'captcha_rate_limited','验证请求过多，请稍后重试。')
            for bucket,_ in buckets:
                db.execute('INSERT INTO web_login_limits VALUES(?,1,?) ON CONFLICT(bucket) DO UPDATE SET count=count+1',(bucket,stamp+900))
        # Signed, fixed-cost SHA-256 parameters. Only one hash is needed to verify.
        challenge=create_challenge('SHA-256',1,key_prefix='000',expires_at=int(stamp)+self.TTL,hmac_secret=self.key).to_dict()
        with self.store.db(True) as db:
            db.execute('INSERT INTO web_registration_challenges VALUES(?,?,?,?,NULL)',
                       (challenge['signature'],json.dumps(challenge,sort_keys=True,separators=(',',':')),
                        self.store.vault.digest('captcha_remote',str(remote_ip)),stamp+self.TTL))
        return challenge

    def consume(self,encoded,remote_ip):
        if not isinstance(encoded,str) or not encoded or len(encoded)>4096:
            raise WebError(403,'captcha_required','请先完成注册验证。')
        try:
            data=json.loads(base64.b64decode(encoded,validate=True).decode('utf-8'))
            if not isinstance(data,dict) or set(data)!={'challenge','solution'}:
                raise ValueError()
            challenge=data['challenge'];solution=data['solution']
            if not isinstance(challenge,dict) or not isinstance(solution,dict):raise ValueError()
            signature=challenge.get('signature')
            if not isinstance(signature,str) or not re.fullmatch(r'[a-f0-9]{64}',signature):raise ValueError()
        except (ValueError,TypeError,UnicodeError,binascii.Error,RecursionError):
            raise WebError(403,'captcha_invalid','验证信息无效，请重新验证。') from None
        with self.store.db() as db:
            row=db.execute('SELECT * FROM web_registration_challenges WHERE signature=?',(signature,)).fetchone()
        if not row:raise WebError(403,'captcha_invalid','验证信息无效，请重新验证。')
        if row['expires_at']<=time.time():raise WebError(403,'captcha_expired','验证已过期，请重新验证。')
        if row['used_at'] is not None:raise WebError(403,'captcha_used','验证信息已使用，请重新验证。')
        if not hmac.compare_digest(row['remote_digest'],self.store.vault.digest('captcha_remote',str(remote_ip))):
            raise WebError(403,'captcha_invalid','验证来源不匹配，请重新验证。')
        if challenge!=json.loads(row['challenge_json']):
            raise WebError(403,'captcha_invalid','验证信息已改变，请重新验证。')
        try:
            result=verify_solution(encoded,self.key)
            valid=result.verified is True
        except (ValueError,TypeError,KeyError,OverflowError,RecursionError):
            valid=False
        if not valid:raise WebError(403,'captcha_invalid','验证未通过，请重新验证。')
        stamp=time.time()
        with self.store.db(True) as db:
            changed=db.execute('UPDATE web_registration_challenges SET used_at=? WHERE signature=? AND used_at IS NULL AND expires_at>?',
                               (stamp,signature,stamp)).rowcount
            if changed!=1:raise WebError(403,'captcha_used','验证信息已使用或过期，请重新验证。')
