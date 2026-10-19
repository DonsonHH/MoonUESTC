"""Authenticated dashboard. Database ownership is checked on every operation."""
import functools
import hmac
import ipaddress
import os
from pathlib import Path
import sqlite3
import urllib.parse

from flask import Flask,g,jsonify,redirect,request,send_from_directory
from werkzeug.exceptions import HTTPException

from . import __version__
from .captcha import RegistrationCaptcha
from .errors import ToolError
from .locations import DEFAULT_PRESET_ID,list_presets
from .web_errors import WebError
from .web_service import WebWorker
from .web_store import WebStore

COOKIE='moon_dashboard_session'


def normalize_origin(value,allow_http=False):
    try:
        parsed=urllib.parse.urlsplit(value)
        port=parsed.port
        host=parsed.hostname
        if (parsed.scheme not in ('http','https') or not host or parsed.username or parsed.password
                or parsed.path not in ('','/') or parsed.query or parsed.fragment): raise ValueError()
        if parsed.scheme=='http':
            try: local=ipaddress.ip_address(host).is_private or ipaddress.ip_address(host).is_loopback
            except ValueError: local=host=='localhost' or host.endswith('.local')
            if not allow_http or not local: raise ValueError()
        host=host.lower()
        if ':' in host: host='['+host+']'
        authority=host+(':'+str(port) if port and port!=(443 if parsed.scheme=='https' else 80) else '')
        return parsed.scheme+'://'+authority
    except (ValueError,TypeError):
        raise ToolError('dashboard_origin_required','web_config') from None


def create_app(directory,public_url,*,allow_http=False,start_worker=False,runner=None,hasher=None,registration_enabled=None):
    origin=normalize_origin(public_url,allow_http)
    secure=origin.startswith('https://')
    os.umask(0o077)
    static=Path(__file__).with_name('web_static')
    pages=Path(__file__).with_name('web_pages')
    app=Flask(__name__,static_folder=str(static),static_url_path='/static')
    app.config.update(MAX_CONTENT_LENGTH=32768,MAX_FORM_MEMORY_SIZE=32768,MAX_FORM_PARTS=10,
                      JSON_SORT_KEYS=False,PROPAGATE_EXCEPTIONS=False)
    app.json.ensure_ascii=False
    store=WebStore(directory,hasher)
    worker=WebWorker(store,runner)
    registration_captcha=RegistrationCaptcha(store)
    app.extensions['moon_store']=store
    app.extensions['moon_worker']=worker
    app.extensions['moon_captcha']=registration_captcha
    app.config['MOON_ORIGIN']=origin
    app.config['MOON_REGISTRATION_ENABLED']=(os.environ.get('MOON_ALLOW_REGISTRATION','1')=='1' if registration_enabled is None else bool(registration_enabled))

    def response_ok(value=None,status=200):
        return jsonify({'ok':True,**(value or {})}),status

    def current():
        if not hasattr(g,'moon_identity'):
            g.moon_identity=store.session(request.cookies.get(COOKIE))
        return g.moon_identity

    def protected(admin=False,allow_password_change=False):
        def decorate(function):
            @functools.wraps(function)
            def wrapped(*args,**kwargs):
                identity=current()
                if not identity: raise WebError(401,'login_required','请先登录。')
                user,csrf=identity
                if request.method not in ('GET','HEAD','OPTIONS'):
                    supplied=request.headers.get('X-CSRF-Token','')
                    if len(supplied)>128 or not hmac.compare_digest(supplied.encode('utf-8'),csrf.encode('ascii')):
                        raise WebError(403,'csrf_failed','请求校验失败，请刷新页面后重试。')
                if user['must_change_password'] and not allow_password_change:
                    raise WebError(403,'password_change_required','首次登录请先修改密码。')
                if admin and user['role']!='admin': raise WebError(403,'admin_required','需要管理员权限。')
                g.moon_user=user
                return function(*args,**kwargs)
            return wrapped
        return decorate

    def body():
        if not request.is_json: raise WebError(415,'json_required','请使用 JSON 请求。')
        value=request.get_json()
        if not isinstance(value,dict): raise WebError(400,'invalid_json','参数格式不正确。')
        return value

    @app.before_request
    def checks():
        if request.path=='/healthz': return None
        try:
            received=normalize_origin(('https' if secure else 'http')+'://'+request.host,not secure)
        except ToolError:
            received=None
        if received!=origin:
            raise WebError(400,'host_not_allowed','请使用配置的访问地址。')
        if request.path.startswith('/api/') and request.method not in ('GET','HEAD','OPTIONS'):
            try:
                sent=normalize_origin(request.headers.get('Origin'),not secure)
            except ToolError:
                sent=None
            if sent!=origin:
                raise WebError(403,'origin_not_allowed','访问来源不匹配，请使用系统配置的地址。')

    @app.after_request
    def headers(response):
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='same-origin'
        response.headers['Permissions-Policy']='geolocation=(), camera=(), microphone=()'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; worker-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'"
        if secure: response.headers['Strict-Transport-Security']='max-age=31536000'
        return response

    @app.errorhandler(WebError)
    def web_error(error):
        response=jsonify({'ok':False,'error':{'code':error.code,'message':error.message}})
        response.status_code=error.status
        if error.status==429: response.headers['Retry-After']='900' if error.code in ('login_rate_limited','registration_rate_limited','captcha_rate_limited') else '20'
        return response

    @app.errorhandler(ToolError)
    def tool_error(error):
        return jsonify({'ok':False,'error':{'code':error.reason,'message':'服务器数据或配置不可用，请联系管理员。'}}),500

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify({'ok':False,'error':{'code':'http_'+str(error.code),'message':'请求地址或格式不正确。'}}),error.code

    @app.errorhandler(Exception)
    def internal_error(error):
        app.logger.error('Dashboard failure type=%s',type(error).__name__)
        return jsonify({'ok':False,'error':{'code':'internal_error','message':'操作失败，请联系管理员。'}}),500

    @app.get('/healthz')
    def health(): return jsonify({'ok':True})

    @app.get('/')
    def index():
        if not current(): return redirect('/login')
        return send_from_directory(pages,'app.html')

    @app.get('/login')
    def login_page():
        if current(): return redirect('/')
        return send_from_directory(pages,'login.html')

    @app.get('/api/session')
    def session_info():
        identity=current()
        if not identity:
            return response_ok({'authenticated':False,'initialized':store.initialized(),'https':secure,'version':__version__,'registration_enabled':app.config['MOON_REGISTRATION_ENABLED'] and store.initialized()})
        user,csrf=identity
        return response_ok({'authenticated':True,'user':user,'csrf_token':csrf,'https':secure,'version':__version__,'registration_enabled':app.config['MOON_REGISTRATION_ENABLED'] and store.initialized()})

    @app.get('/register')
    def register_page():
        if current(): return redirect('/')
        if not app.config['MOON_REGISTRATION_ENABLED']:
            raise WebError(403,'registration_disabled','管理员已关闭自助注册。')
        if not store.initialized():
            raise WebError(503,'not_initialized','管理员尚未初始化，请联系管理员。')
        return send_from_directory(pages,'register.html')

    @app.post('/api/register')
    def register():
        if not app.config['MOON_REGISTRATION_ENABLED']:
            raise WebError(403,'registration_disabled','管理员已关闭自助注册。')
        value=body()
        if set(value)-{'username','password','altcha'}:
            raise WebError(400,'invalid_fields','注册只接受用户名、密码和验证信息。')
        proof=value.pop('altcha',None)
        registration_captcha.consume(proof,request.remote_addr or 'unknown')
        user=store.register_user(value,request.remote_addr or 'unknown')
        return response_ok({'user':user},201)

    @app.get('/api/registration/challenge')
    def registration_challenge():
        if not app.config['MOON_REGISTRATION_ENABLED']:
            raise WebError(403,'registration_disabled','管理员已关闭自助注册。')
        return jsonify(registration_captcha.issue(request.remote_addr or 'unknown'))

    @app.post('/api/login')
    def login():
        value=body()
        if set(value)-{'username','password'}: raise WebError(400,'invalid_fields','登录参数不正确。')
        if not store.initialized(): raise WebError(503,'not_initialized','管理员尚未初始化，请先在服务器执行 init-admin。')
        token,csrf,user=store.login(value.get('username'),value.get('password'),request.remote_addr or 'unknown')
        response=jsonify({'ok':True,'user':user,'csrf_token':csrf})
        response.set_cookie(COOKIE,token,max_age=43200,secure=secure,httponly=True,samesite='Strict',path='/')
        return response

    @app.post('/api/logout')
    @protected(allow_password_change=True)
    def logout():
        store.logout(request.cookies.get(COOKIE))
        response=jsonify({'ok':True})
        response.delete_cookie(COOKIE,path='/',secure=secure,httponly=True,samesite='Strict')
        return response

    @app.post('/api/me/password')
    @protected(allow_password_change=True)
    def change_password():
        value=body()
        if set(value)-{'current_password','new_password'}: raise WebError(400,'invalid_fields','密码参数不正确。')
        store.change_password(g.moon_user,value.get('current_password'),value.get('new_password'))
        response=jsonify({'ok':True})
        response.delete_cookie(COOKIE,path='/',secure=secure,httponly=True,samesite='Strict')
        return response

    @app.get('/api/locations')
    @protected()
    def locations(): return response_ok({'locations':list_presets(),'default_preset_id':DEFAULT_PRESET_ID})

    @app.get('/api/accounts')
    @protected()
    def accounts(): return response_ok({'accounts':store.accounts(g.moon_user)})

    @app.post('/api/accounts')
    @protected()
    def create_account(): return response_ok({'account':store.save_account(g.moon_user,body())},201)

    @app.get('/api/accounts/<account_id>')
    @protected()
    def get_account(account_id): return response_ok({'account':store.account(g.moon_user,account_id)})

    @app.patch('/api/accounts/<account_id>')
    @protected()
    def edit_account(account_id): return response_ok({'account':store.save_account(g.moon_user,body(),account_id)})

    @app.delete('/api/accounts/<account_id>')
    @protected()
    def remove_account(account_id):
        store.delete_account(g.moon_user,account_id)
        return response_ok()

    @app.post('/api/accounts/<account_id>/jobs')
    @protected()
    def create_job(account_id):
        value=body()
        if set(value)-{'mode','confirm'}: raise WebError(400,'invalid_fields','任务参数不正确。')
        if value.get('mode')=='checkin' and value.get('confirm') is not True:
            raise WebError(400,'submission_confirmation_required','请明确确认向学校提交打卡。')
        jid=store.enqueue(g.moon_user,account_id,value.get('mode'))
        return response_ok({'job':store.jobs(g.moon_user,jid)},202)

    @app.get('/api/jobs')
    @protected()
    def jobs(): return response_ok({'jobs':store.jobs(g.moon_user)})

    @app.get('/api/jobs/<job_id>')
    @protected()
    def job(job_id): return response_ok({'job':store.jobs(g.moon_user,job_id)})

    @app.get('/api/users')
    @protected(admin=True)
    def users(): return response_ok({'users':store.users()})

    @app.post('/api/users')
    @protected(admin=True)
    def create_user(): return response_ok({'user':store.create_user(g.moon_user,body())},201)

    @app.patch('/api/users/<int:user_id>')
    @protected(admin=True)
    def edit_user(user_id): return response_ok({'user':store.update_user(g.moon_user,user_id,body())})

    @app.delete('/api/users/<int:user_id>')
    @protected(admin=True)
    def remove_user(user_id):
        store.delete_user(g.moon_user,user_id)
        return response_ok()

    if start_worker: worker.start()
    return app


def serve_dashboard(directory,public_url,*,host='0.0.0.0',port=8080,allow_http=False):
    from waitress import create_server
    from .state import execution_lock
    import signal
    with execution_lock(Path(directory)/'web-instance'):
        app=create_app(directory,public_url,allow_http=allow_http,start_worker=True)
        server=create_server(app,host=host,port=port,threads=4,connection_limit=64,
                             max_request_body_size=32768,clear_untrusted_proxy_headers=True,
                             expose_tracebacks=False)
        previous={}
        def stop(signum,frame): server.close()
        for value in (signal.SIGTERM,signal.SIGINT):
            previous[value]=signal.signal(value,stop)
        try: server.run()
        finally:
            app.extensions['moon_worker'].stop()
            server.close()
            for value,handler in previous.items(): signal.signal(value,handler)
