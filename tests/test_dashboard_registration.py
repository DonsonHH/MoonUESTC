"""Public signup and real cryptographic ALTCHA proofs; no school requests."""
import base64
import copy
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from altcha import Challenge,Payload,solve_challenge
from dashboard_helpers import WebCase,ORIGIN,USER_PASS,FAST_HASHER
from moonuestc.web_app import create_app
from moonuestc.web_errors import WebError


class DashboardRegistration(WebCase):
    def setUp(self):
        super().setUp()
        self.client=self.app.test_client()
        self.captcha=self.app.extensions['moon_captcha']

    def post(self,data,ip='127.0.0.1',origin=ORIGIN):
        return self.client.post('/api/register',base_url=ORIGIN,headers={'Origin':origin},json=data,environ_overrides={'REMOTE_ADDR':ip})

    def proof(self,ip='127.0.0.1'):
        response=self.client.get('/api/registration/challenge',base_url=ORIGIN,environ_overrides={'REMOTE_ADDR':ip})
        self.assertEqual(response.status_code,200,response.get_json())
        challenge=Challenge.from_dict(response.get_json())
        solution=solve_challenge(challenge,timeout=5)
        self.assertIsNotNone(solution)
        return Payload(challenge,solution).to_base64()

    def fields(self,username='new.student',**extra):
        return {'username':username,'password':USER_PASS,'altcha':self.proof(),**extra}

    def test_signup_needs_no_email_and_always_creates_ready_ordinary_user(self):
        with patch('moonuestc.transport.Transport.request',side_effect=AssertionError('no external requests')):
            response=self.post(self.fields())
        self.assertEqual(response.status_code,201,response.get_json())
        user=response.get_json()['user']
        self.assertEqual(user['role'],'user');self.assertTrue(user['active'])
        self.assertFalse(user['must_change_password'])
        self.assertEqual(user['display_name'],'new.student')
        self.assertNotIn('password',user)
        self.assertNotIn(USER_PASS,response.get_data(as_text=True))
        self.assertNotIn('Set-Cookie',response.headers)
        with self.store.db() as db:
            stored=db.execute('SELECT * FROM web_users WHERE id=?',(user['id'],)).fetchone()
            self.assertTrue(stored['password_hash'].startswith('$argon2id$'))
            self.assertNotEqual(stored['password_hash'],USER_PASS)
            self.assertEqual(db.execute("SELECT count(*) FROM web_audit WHERE event='user_registered' AND actor_id=?",(user['id'],)).fetchone()[0],1)
        client,token=self.login_client('new.student',USER_PASS)
        self.assertEqual(self.req(client,token,'/api/accounts').get_json()['accounts'],[])
        self.assertEqual(self.req(client,token,'/api/users').status_code,403)
        self.assertEqual(self.calls,[])

    def test_self_registered_user_cannot_read_existing_accounts(self):
        account=self.add_account()
        self.assertEqual(self.post(self.fields()).status_code,201)
        client,token=self.login_client('new.student',USER_PASS)
        self.assertEqual(self.req(client,token,'/api/accounts/'+account['id']).status_code,404)
        response=self.req(client,token,'/api/accounts','POST',self.account_fields(student='202300000009'))
        self.assertEqual(response.status_code,201,response.get_json())
        self.assertEqual(len(self.req(self.ac,self.at,'/api/accounts').get_json()['accounts']),2)
        self.assertEqual(self.calls,[])

    def test_role_active_display_name_or_email_cannot_be_injected(self):
        for extra in ({'role':'admin'},{'active':False},{'display_name':'admin'},{'email':'x@example.test'}):
            response=self.post(self.fields(**extra))
            self.assertEqual(response.status_code,400,response.get_json())
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM web_users').fetchone()[0],3)

    def test_case_insensitive_duplicate_is_rejected_and_requires_fresh_proof(self):
        fields=self.fields(username='New.Student')
        self.assertEqual(self.post(fields).status_code,201)
        fields['username']='another'
        self.assertEqual(self.post(fields).get_json()['error']['code'],'captcha_used')
        response=self.post(self.fields(username='new.student'))
        self.assertEqual(response.status_code,409)
        self.assertEqual(response.get_json()['error']['code'],'username_exists')

    def test_invalid_username_short_password_and_missing_fields_rejected(self):
        for data in ({'username':'ab'},{'username':'bad name'},{'password':'short'},{'password':'x'*129},{'username':None}):
            response=self.post(self.fields(**data))
            self.assertEqual(response.status_code,400,response.get_json())
        response=self.post({'username':'example','altcha':self.proof()})
        self.assertEqual(response.status_code,400,response.get_json())

    def test_captcha_required_invalid_or_oversized_never_creates_user(self):
        for value in (None,'','!',[],{},'A'*4097,base64.b64encode(b'{}').decode()):
            response=self.post({'username':'testuser','password':USER_PASS,'altcha':value})
            self.assertEqual(response.status_code,403,response.get_json())
        with self.store.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM web_users').fetchone()[0],3)

    def test_challenge_tampering_wrong_solution_and_unknown_signature_rejected(self):
        valid=json.loads(base64.b64decode(self.proof()))
        cases=[]
        altered=copy.deepcopy(valid);altered['challenge']['parameters']['cost']=0;cases.append(altered)
        altered=copy.deepcopy(valid);altered['challenge']['parameters']['keyPrefix']='';cases.append(altered)
        altered=copy.deepcopy(valid);altered['challenge']['signature']='0'*64;cases.append(altered)
        altered=copy.deepcopy(valid);altered['solution']['derivedKey']='0'*64;cases.append(altered)
        altered=copy.deepcopy(valid);altered['solution']['counter']=-1;cases.append(altered)
        altered=copy.deepcopy(valid);altered['solution']['counter']={};cases.append(altered)
        for value in cases:
            proof=base64.b64encode(json.dumps(value).encode()).decode()
            response=self.post({'username':'testuser','password':USER_PASS,'altcha':proof})
            self.assertEqual(response.status_code,403,response.get_json())
        proof=base64.b64encode(json.dumps(valid).encode()).decode()
        self.assertEqual(self.post({'username':'testuser','password':USER_PASS,'altcha':proof}).status_code,201)

    def test_proof_is_bound_to_ip_and_failed_cross_ip_does_not_consume_it(self):
        fields=self.fields()
        response=self.post(fields,ip='192.0.2.14')
        self.assertEqual(response.status_code,403)
        self.assertEqual(self.post(fields).status_code,201)
        with self.store.db() as db:
            row=db.execute('SELECT remote_digest FROM web_registration_challenges').fetchone()
            self.assertNotIn('127.0.0.1',row['remote_digest'])

    def test_expired_proof_rejected(self):
        fields=self.fields()
        with self.store.db(True) as db:db.execute('UPDATE web_registration_challenges SET expires_at=?',(time.time()-1,))
        response=self.post(fields)
        self.assertEqual(response.status_code,403)
        self.assertEqual(response.get_json()['error']['code'],'captcha_expired')

    def test_only_one_concurrent_consumer_can_use_a_valid_proof(self):
        proof=self.proof()
        def consume(_):
            try:self.captcha.consume(proof,'127.0.0.1');return 'ok'
            except WebError as e:return e.code
        with ThreadPoolExecutor(max_workers=2) as executor:result=list(executor.map(consume,range(2)))
        self.assertEqual(sorted(result),['captcha_used','ok'])

    def test_registration_disabled_covers_page_challenge_and_api(self):
        self.app.config['MOON_REGISTRATION_ENABLED']=False
        for path in ('/register','/api/registration/challenge'):
            self.assertEqual(self.client.get(path,base_url=ORIGIN).status_code,403)
        self.assertEqual(self.post({}).status_code,403)
        self.assertFalse(self.client.get('/api/session',base_url=ORIGIN).get_json()['registration_enabled'])
        self.assertEqual(self.client.get('/login',base_url=ORIGIN).status_code,200)

    def test_registration_cannot_bootstrap_first_admin(self):
        app=create_app(self.root/'empty',ORIGIN,hasher=FAST_HASHER)
        client=app.test_client()
        try:
            self.assertEqual(client.get('/register',base_url=ORIGIN).status_code,503)
            self.assertEqual(client.get('/api/registration/challenge',base_url=ORIGIN).status_code,503)
            response=client.post('/api/register',base_url=ORIGIN,headers={'Origin':ORIGIN},json={'username':'admin','password':USER_PASS})
            self.assertEqual(response.status_code,403)
            self.assertFalse(app.extensions['moon_store'].initialized())
        finally:app.extensions['moon_worker'].stop()

    def test_signup_origin_json_and_body_limits(self):
        fields=self.fields()
        self.assertEqual(self.post(fields,origin='https://evil.example').status_code,403)
        self.assertEqual(self.client.post('/api/register',base_url=ORIGIN,headers={'Origin':ORIGIN},data='x').status_code,415)
        self.assertEqual(self.post({'x':'z'*33000}).status_code,413)
        self.assertEqual(self.post(fields).status_code,201)

    def test_registration_ip_and_global_quotas_apply_before_hashing(self):
        for scope,identity,count,ip in [('registration_ip','127.0.0.1',20,'127.0.0.1'),('registration_global','all',60,'192.0.2.14')]:
            with self.subTest(scope=scope):
                proof=self.proof(ip)
                with self.store.db(True) as db:
                    db.execute('DELETE FROM web_login_limits')
                    db.execute('INSERT INTO web_login_limits VALUES(?,?,?)',(self.store.vault.digest(scope,identity),count,time.time()+900))
                with patch.object(type(self.store.hasher),'hash',side_effect=AssertionError('must rate limit before hashing')):
                    response=self.post({'username':'testuser','password':USER_PASS,'altcha':proof},ip=ip)
                self.assertEqual(response.status_code,429,response.get_json())
                self.assertEqual(response.get_json()['error']['code'],'registration_rate_limited')
                self.assertIn('Retry-After',response.headers)

    def test_challenge_ip_and_global_quotas_and_expired_cleanup(self):
        for scope,identity,count in [('captcha_issue_ip','127.0.0.1',60),('captcha_issue_global','all',240)]:
            with self.store.db(True) as db:
                db.execute('DELETE FROM web_login_limits')
                db.execute('INSERT INTO web_login_limits VALUES(?,?,?)',(self.store.vault.digest(scope,identity),count,time.time()+900))
            response=self.client.get('/api/registration/challenge',base_url=ORIGIN)
            self.assertEqual(response.status_code,429,response.get_json())
        with self.store.db(True) as db:db.execute('UPDATE web_login_limits SET reset_at=?',(time.time()-1,))
        proof=self.proof()
        self.captcha.consume(proof,'127.0.0.1')

    def test_registration_page_assets_work_with_strict_same_origin_csp(self):
        response=self.client.get('/register',base_url=ORIGIN)
        self.assertEqual(response.status_code,200)
        self.assertIn("worker-src 'self'",response.headers['Content-Security-Policy'])
        self.assertNotIn('unsafe-inline',response.headers['Content-Security-Policy'])
        self.assertIn('no-store',response.headers['Cache-Control'])
        for file in ('register.js','vendor/altcha-3.4.1.min.js','vendor/altcha-3.4.1.css','vendor/altcha-sha-3.4.1.worker.js','vendor/altcha-zh-cn-3.4.1.js'):
            self.assertEqual(self.client.get('/static/'+file,base_url=ORIGIN).status_code,200,file)

    def test_locations_api_has_eight_choices_and_old_references_normalize_on_save(self):
        response=self.req(self.c1,self.t1,'/api/locations').get_json()
        self.assertEqual(len(response['locations']),8)
        self.assertEqual(response['default_preset_id'],'xuezhi_group3_amap')
        self.assertNotIn('legacy_locations',response)
        for reference in ('xuezhi_group3','学知三组团'):
            account=self.add_account(student='202300000001' if reference=='xuezhi_group3' else '202300000008',location={'mode':'preset','preset':reference})
            self.assertEqual(account['location'],{'mode':'preset','preset':'xuezhi_group3_amap'})
            self.assertEqual(account['inputCoordinateSystem'],'gcj02')
