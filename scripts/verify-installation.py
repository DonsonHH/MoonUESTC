#!/usr/bin/env python3
"""Run on a Linux Docker host. Uses only isolated, disposable synthetic data."""
import argparse,datetime,hashlib,http.client,json,os,pty,re,secrets,selectors,shutil,socket,subprocess,tempfile,time,urllib.request
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--image',default='ghcr.io/horoscope963852/moonuestc:0.5.1');p.add_argument('--output',required=True);a=p.parse_args()
source=Path(__file__).resolve().parents[1]
checks=[]
def check(name,ok):
    if not ok:raise AssertionError(name)
    checks.append(name)
with tempfile.TemporaryDirectory(prefix='moonuestc-acceptance-') as temp:
    work=Path(temp)
    for name in ['compose.yaml','install.sh']:shutil.copy2(source/name,work/name)
    bad=subprocess.run(['bash','install.sh','--unknown'],cwd=work,capture_output=True)
    check('unknown_options_fail',bad.returncode!=0 and not (work/'.env').exists())
    missing=subprocess.run(['bash','install.sh','--yes','--skip-pull'],cwd=work,capture_output=True)
    check('noninteractive_missing_config_fails',missing.returncode!=0 and not (work/'.env').exists())
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    project='moonuestc-accept-'+secrets.token_hex(5)
    env='\n'.join(['MOON_IMAGE='+a.image,'PUID=10001','PGID=10001','MOON_PORT='+str(port),'MOON_BIND_ADDRESS=127.0.0.1','MOON_PUBLIC_URL=http://127.0.0.1:'+str(port),'MOON_ALLOW_INSECURE_HTTP=1','MOON_DATA_DIR=./data','MOON_CONFIG_DIR=./config','COMPOSE_PROJECT_NAME='+project])+'\n'
    (work/'.env').write_text(env);(work/'.env').chmod(0o600)
    env_digest=hashlib.sha256((work/'.env').read_bytes()).hexdigest()
    password=secrets.token_urlsafe(24)
    master,slave=pty.openpty()
    process=subprocess.Popen(['bash','install.sh','--yes','--skip-pull'],cwd=work,stdin=slave,stdout=slave,stderr=slave,start_new_session=True)
    os.close(slave);os.set_blocking(master,False)
    seen=b'';sent=0;deadline=time.monotonic()+150
    prompts=[('管理员用户名：','releaseadmin\n'),('新的登录密码（至少12字符）：',password+'\n'),('再次输入密码：',password+'\n')]
    try:
        while process.poll() is None and time.monotonic()<deadline:
            try:chunk=os.read(master,65536)
            except (BlockingIOError,OSError):chunk=b''
            if chunk:seen=(seen+chunk)[-100000:]
            if sent<len(prompts) and prompts[sent][0].encode() in seen:
                os.write(master,prompts[sent][1].encode());sent+=1;seen=b''
            time.sleep(.05)
        if process.poll() is None:process.terminate();process.wait(timeout=10)
        check('interactive_first_install',process.returncode==0 and sent==3)
        check('configuration_not_overwritten',hashlib.sha256((work/'.env').read_bytes()).hexdigest()==env_digest)
        with urllib.request.urlopen('http://127.0.0.1:'+str(port)+'/healthz',timeout=5) as r:check('new_instance_healthy',r.status==200)
        conn=http.client.HTTPConnection('127.0.0.1',port,timeout=10)
        body=json.dumps({'username':'releaseadmin','password':password}).encode()
        conn.request('POST','/api/login',body,{'Content-Type':'application/json','Origin':'http://127.0.0.1:'+str(port)})
        response=conn.getresponse();data=json.loads(response.read());check('new_admin_login',response.status==200 and data['user']['role']=='admin');conn.close()
        key_before=hashlib.sha256((work/'data/dashboard.key').read_bytes()).hexdigest()
        db_inode=(work/'data/dashboard.sqlite3').stat().st_ino
        second=subprocess.run(['bash','install.sh','--yes','--skip-pull'],cwd=work,capture_output=True,timeout=100)
        check('repeat_install_without_reinitialization',second.returncode==0)
        check('existing_key_preserved',hashlib.sha256((work/'data/dashboard.key').read_bytes()).hexdigest()==key_before)
        check('existing_database_preserved',(work/'data/dashboard.sqlite3').stat().st_ino==db_inode)
        check('repeat_keeps_configuration',hashlib.sha256((work/'.env').read_bytes()).hexdigest()==env_digest)
        metadata=json.loads(subprocess.check_output(['docker','compose','ps','--format','json'],cwd=work))
        check('only_isolated_project_used',metadata['Project']==project)
        inspect=json.loads(subprocess.check_output(['docker','inspect',metadata['ID']]))[0]
        check('non_root_runtime',inspect['Config']['User']=='10001:10001')
        check('loopback_listener',inspect['HostConfig']['PortBindings']=={'8080/tcp':[{'HostIp':'127.0.0.1','HostPort':str(port)}]})
        check('private_data_permissions',os.stat(work/'data').st_mode&0o777==0o700)
        code='from moonuestc.web_store import WebStore; s=WebStore("/data"); assert len(s.users())==1; assert s.users()[0]["username"]=="releaseadmin"; print("preserved")'
        preserved=subprocess.run(['docker','compose','exec','-T','moonuestc','python','-c',code],cwd=work,capture_output=True)
        check('administrator_preserved',preserved.returncode==0)
    finally:
        os.close(master)
        if process.poll() is None:process.terminate();process.wait(timeout=10)
        subprocess.run(['docker','compose','down','--remove-orphans'],cwd=work,capture_output=True,timeout=70)
result={'passed':True,'checks':checks,'count':len(checks),'platform':'linux/amd64','school_requests':0,'fixture':'isolated synthetic admin; no school accounts','finished_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'passed':True,'checks':len(checks),'school_requests':0}))
