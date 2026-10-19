import './vendor/altcha-3.4.1.min.js';
import './vendor/altcha-zh-cn-3.4.1.js';

const $=id=>document.getElementById(id);
const form=$('register-form');
const widget=$('registration-captcha');
globalThis.$altcha.algorithms.set('SHA-256',()=>new Worker(new URL('./vendor/altcha-sha-3.4.1.worker.js',import.meta.url),{type:'module'}));
await customElements.whenDefined('altcha-widget');
widget.configure({challenge:'/api/registration/challenge',language:'zh-cn',workers:2,auto:'off',minDuration:500});
function error(message){$('register-error').textContent=message;$('register-error').hidden=!message;}
if(!window.isSecureContext){error('注册验证需要 HTTPS 连接。请使用管理员配置的 HTTPS 地址，或通过 localhost 访问测试环境。');$('register-submit').disabled=true;}
fetch('/api/session',{credentials:'same-origin'}).then(r=>r.json()).then(data=>{
  if(data.authenticated){location.replace('/');return;}
  $('register-version').textContent='v'+data.version;
  if(!data.registration_enabled){error('管理员已关闭自助注册，或尚未初始化。');$('register-submit').disabled=true;}
}).catch(()=>{error('无法连接服务器，请刷新重试。');});
form.addEventListener('submit',async event=>{
  event.preventDefault();error('');
  if($('password').value!==$('confirm-password').value){error('两次密码不一致。');return;}
  if(!window.isSecureContext)return;
  $('register-submit').disabled=true;
  try{
    if(!new FormData(form).get('altcha'))await widget.verify();
    const proof=new FormData(form).get('altcha');
    if(typeof proof!=='string'||!proof)throw new Error('请完成注册验证后重试。');
    const response=await fetch('/api/register',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:$('username').value.trim(),password:$('password').value,altcha:proof})});
    const result=await response.json();
    if(!response.ok)throw new Error(result.error?.message||'注册失败，请稍后重试。');
    $('password').value='';$('confirm-password').value='';
    location.replace('/login?registered=1');
  }catch(e){error(e.message||'验证未完成，请稍后重试。');widget.reset();}
  finally{$('register-submit').disabled=false;}
});
