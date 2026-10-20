"use strict";
const $=id=>document.getElementById(id);
const S={user:null,csrf:'',accounts:[],jobs:[],users:[],presets:[],defaultPresetId:'xuezhi_group3_amap',view:'overview',refreshing:false,editAccount:null,confirm:null};
const modes={diagnose:'只读诊断',prepare:'位置检查',checkin:'提交打卡'};
const reasons={need_manual_mfa:'学校要求本人完成二次验证',need_manual_captcha:'学校要求本人完成验证码',login_rejected:'学校登录未成功，请核对凭据',micro_app_unauthorized_after_login:'登录成功，但打卡应用仍未授权',daily_login_limit:'达到当日密码登录次数上限',outside_allowed_location:'配置坐标在允许范围外',outside_checkin_window:'不在学校允许的打卡时段',abnormal_record:'学校记录被标记异常',record_not_confirmed:'未读到学校签到成功记录',another_run_active:'其他任务正在使用打卡数据',worker_interrupted:'任务在服务器重启时中断，请核对学校记录',job_expired:'任务已跨过业务日期，请重新检查',session_rejected:'学校会话失效',network_error:'网络连接失败',timeout:'请求等待超时',tls_error:'学校 HTTPS 连接失败',dns_error:'学校地址解析失败',worker_internal_error:'任务执行失败，请联系管理员',account_disabled:'账号或所属用户已停用'};
function node(tag,cls='',value=null){const n=document.createElement(tag);if(cls)n.className=cls;if(value!==null)n.textContent=String(value);return n;}
function clear(id){$(id).replaceChildren();return $(id);}
function errorAt(id,message){$(id).textContent=message;$(id).hidden=!message;}
function toast(message){$('toast').textContent=message;$('toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').hidden=true,4500);}
function chinaDate(){return new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());}
function fmt(stamp,short=false){if(!stamp)return '—';return new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',...(short?{}:{second:'2-digit'})}).format(new Date(stamp*1000));}
async function api(path,options={}){const headers={'Content-Type':'application/json',...options.headers};if(S.csrf)headers['X-CSRF-Token']=S.csrf;const response=await fetch(path,{credentials:'same-origin',...options,headers});let result;try{result=await response.json();}catch{throw new Error('服务器响应不正确，请稍后重试。');}if(response.status===401){location.replace('/login');throw new Error('登录已过期。');}if(!response.ok){const e=new Error(result.error?.message||'操作失败，请稍后重试。');e.code=result.error?.code;if(e.code==='password_change_required')showView('settings');throw e;}return result;}
function badge(label,color='gray'){return node('span','badge '+color+'-badge',label);}
function stateInfo(jobOrResult){const job=jobOrResult||{};if(job.state==='queued')return ['等待执行','amber'];if(job.state==='running')return ['执行中','blue'];const r=job.result&&typeof job.result==='object'?job.result:job;if(r.result==='confirmed')return ['已确认签到','green'];if(r.result==='already_recorded')return ['学校已有记录','green'];if(r.result==='auth_ready')return ['诊断通过','blue'];if(r.result==='dry_run_ready')return ['位置检查通过','blue'];if(r.result==='submission_unknown')return ['结果待核对','amber'];if(r.result==='record_changed')return ['记录有变化','amber'];if(r.result==='error'||job.state==='failed')return ['需要处理','red'];return ['尚未验证','gray'];}
function detail(result){if(!result)return '尚无执行记录';if(result.reason)return reasons[result.reason]||result.reason;if(result.result==='confirmed')return '已回读学校当天记录确认';if(result.result==='already_recorded')return '当天已有签到、报告或豁免记录';if(result.result==='auth_ready')return '登录和业务授权正常';if(result.result==='dry_run_ready')return result.checkinWindow?.open?'位置与时段检查通过，未提交':'位置检查通过；当前时段未开放，未提交';return '请查看任务结果';}
function empty(container,title,message,symbol='☾'){const box=node('div','empty-state');box.append(node('span','empty-symbol',symbol),node('strong','',title),node('p','',message));container.append(box);}
function table(headers){const wrap=node('div','table-scroll');const t=node('table');const head=node('thead');const row=node('tr');for(const h of headers)row.append(node('th','',h));head.append(row);const body=node('tbody');t.append(head,body);wrap.append(t);return {wrap,body};}
function cell(title,subtitle){const td=node('td');td.append(node('span','cell-title',title));if(subtitle)td.append(node('span','cell-subtitle',subtitle));return td;}
function mini(label,action,cls='',disabled=false){const b=node('button','mini-button '+cls,label);b.type='button';b.disabled=disabled;b.addEventListener('click',event=>{Promise.resolve().then(()=>action(event)).catch(error=>toast(error.message));});return b;}
function pending(id){return S.jobs.some(j=>j.account_id===id&&['queued','running'].includes(j.state));}
function renderAccounts(id,items,compact=false){const container=clear(id);if(!items.length){empty(container,'还没有打卡账号','添加一个学校账号，选择默认位置或手动位置，再从只读诊断开始。','▤');return;}const admin=S.user.role==='admin';const headers=['打卡账号'];if(admin)headers.push('所属用户');headers.push('位置','运行计划','最新状态');if(!compact)headers.push('操作');const {wrap,body}=table(headers);for(const a of items){const tr=node('tr');tr.append(cell(a.label,a.student_id));if(admin)tr.append(cell(a.owner_name,a.owner_username));tr.append(cell(a.locationName||'自定义位置',a.inputCoordinateSystem==='wgs84'?'WGS-84 → GCJ-02':'GCJ-02'));tr.append(cell(a.automatic&&a.enabled?'每日 '+a.run_at:'手动运行',a.enabled?(a.automatic?'自动计划已开启':'自动计划未开启'):'账号已停用'));const td=node('td');const active=S.jobs.find(j=>j.account_id===a.id&&['queued','running'].includes(j.state));const [label,color]=a.enabled?stateInfo(active||a.last_result):['已停用','gray'];td.append(badge(label,color));if(a.last_run_at)td.append(node('span','cell-subtitle',fmt(a.last_run_at,true)));tr.append(td);if(!compact){const actions=node('div','actions');const busy=pending(a.id);actions.append(mini('只读诊断',()=>queue(a,'diagnose'),'',!a.enabled||busy),mini('位置检查',()=>queue(a,'prepare'),'',!a.enabled||busy),mini('提交打卡',()=>confirmSubmit(a),'submit-action',!a.enabled||busy),mini('编辑',()=>openAccount(a),'muted-action',busy),mini('删除',()=>confirmDeleteAccount(a),'danger-action',busy));const ac=node('td');ac.append(actions);tr.append(ac);}body.append(tr);}container.append(wrap);}
function submissionInfo(job){
  if(job.mode!=='checkin')return ['未提交','gray'];
  const action=job.diagnostics?.action;
  if(action==='first_submit')return ['首次提交','blue'];
  if(action==='recheck')return ['仅复查','amber'];
  if(action==='not_submitted')return ['未提交','gray'];
  return [['queued','running'].includes(job.state)?'待执行':'旧记录未区分','gray'];
}
function responseSummary(value){
  if(!value)return '';
  return [value.httpStatus!==undefined?'HTTP '+value.httpStatus:'',value.apiCode!==undefined?'学校业务码 '+value.apiCode:''].filter(Boolean).join(' · ');
}
function renderJobs(){
  const container=clear('jobs-table');
  if(!S.jobs.length){empty(container,'还没有运行记录','保存账号后，可先执行只读诊断。系统不会因为打开网页或保存配置而提交打卡。','◷');return;}
  const {wrap,body}=table(['时间','打卡账号','操作','执行方式','提交行为','状态','结果说明','详情']);
  for(const job of S.jobs){
    const tr=node('tr');tr.append(cell(fmt(job.created_at),job.business_date),cell(job.label,job.owner_name),cell(modes[job.mode]||job.mode),cell(job.source==='schedule'?'每日自动':'手动操作'));
    const action=node('td');action.append(badge(...submissionInfo(job)));tr.append(action);
    const status=node('td');status.append(badge(...stateInfo(job)));tr.append(status);
    const info=job.diagnostics?.submission||job.diagnostics?.error;
    tr.append(cell(['queued','running'].includes(job.state)?'任务处理中':detail(job.result),responseSummary(info)||job.result?.reason||''));
    const td=node('td');td.append(mini('查看详情',()=>openJob(job.id)));tr.append(td);body.append(tr);
  }
  container.append(wrap);
}
function diagnosticRow(container,label,value){
  const row=node('div','diagnostic-row');row.append(node('span','',label),node('strong','',value===undefined||value===null||value===''?'—':value));container.append(row);
}
async function openJob(id){
  const result=await api('/api/jobs/'+id);const job=result.job;const diag=job.diagnostics;
  $('job-dialog-title').textContent=job.label+' · 运行详情';
  const box=clear('job-diagnostics');
  diagnosticRow(box,'任务时间',fmt(job.created_at));diagnosticRow(box,'任务结果',stateInfo(job)[0]);diagnosticRow(box,'本次行为',submissionInfo(job)[0]);
  if(diag?.action==='recheck')box.append(node('p','diagnostic-note','本次只读取学校记录，没有重新提交打卡。下方首次提交信息属于当天原始尝试。'));
  if(diag?.action==='first_submit')box.append(node('p','diagnostic-note','本次进入首次提交尝试。接口返回成功仍需回读学校当天记录，才能确认签到。'));
  box.append(node('h3','','首次提交信息'));
  const original=diag?.submission;
  if(original){
    diagnosticRow(box,'首次尝试时间',fmt(original.startedAt));
    diagnosticRow(box,'提交响应',{accepted:'学校接口返回成功',rejected:'学校接口返回拒绝',error:'提交响应异常',unknown:'未取得明确响应',attempting:'未记录到响应，需核对学校记录'}[original.outcome]||'—');
    diagnosticRow(box,'HTTP 状态',original.httpStatus);diagnosticRow(box,'学校业务码',original.apiCode);
    diagnosticRow(box,'脱敏错误信息',original.schoolMessage||'学校未提供错误文字，或内容已省略');
    if(original.reason)diagnosticRow(box,'错误类型',original.reason);
    if(original.stage)diagnosticRow(box,'错误阶段',original.stage);
  }else{
    const message=diag?.action==='not_submitted'?'本次没有进入提交尝试。':diag?.action==='recheck'&&diag.priorAttempt===false?'本工具当天没有提交尝试，本次直接读取学校已有记录。':'首次提交信息未留存（旧版记录），无法恢复原始错误。';
    box.append(node('p','diagnostic-note',message));
  }
  if(diag?.error){
    box.append(node('h3','','本次任务错误'));
    diagnosticRow(box,'错误类型',diag.error.reason);diagnosticRow(box,'错误阶段',diag.error.stage);
    diagnosticRow(box,'HTTP 状态',diag.error.httpStatus);diagnosticRow(box,'学校业务码',diag.error.apiCode);
    diagnosticRow(box,'脱敏错误信息',diag.error.schoolMessage);
  }
  box.append(node('h3','','本次记录复查'));
  if(diag?.verification?.length){
    const names={PENDING:'待打卡',CHECKED_IN:'已签到',STUDENT_REPORTED:'学生已报告',INSTRUCTOR_REPORTED:'辅导员已报告',EXEMPT:'已豁免'};
    for(const item of diag.verification){
      const label=(item.attempt===0?'开始时读取':'第 '+item.attempt+' 次复查')+' · '+fmt(item.at);
      diagnosticRow(box,label,item.status?(names[item.status]||item.status):(reasons[item.reason]||item.reason||'读取失败'));
      if(item.apiCode!==undefined||item.httpStatus!==undefined)diagnosticRow(box,'复查响应',responseSummary(item));
      if(item.schoolMessage)diagnosticRow(box,'复查脱敏信息',item.schoolMessage);
    }
  }else box.append(node('p','diagnostic-note','没有保存到本次复查详情。旧记录不会补造过程信息。'));
  $('job-dialog').showModal();
}
function renderRecent(){const box=clear('recent-jobs');if(!S.jobs.length){empty(box,'每一次运行，都会留下记录','先添加账号，再执行只读诊断和位置检查。');return;}for(const job of S.jobs.slice(0,5)){const row=node('div','recent-job');const info=stateInfo(job);row.append(node('span','job-mark',job.mode==='checkin'?'✓':'◷'));const copy=node('div','recent-copy');copy.append(node('strong','',job.label+' · '+(modes[job.mode]||job.mode)),node('p','',job.owner_name+' · '+(job.mode==='checkin'?submissionInfo(job)[0]+' · ':'')+(['queued','running'].includes(job.state)?'队列将依次执行':detail(job.result))));row.append(copy,badge(...info),node('time','',fmt(job.created_at,true)));box.append(row);}}
function renderUsers(){if(S.user.role!=='admin')return;const box=clear('users-table');const {wrap,body}=table(['用户','角色','状态','打卡账号','操作']);for(const user of S.users){const tr=node('tr');tr.append(cell(user.display_name,user.username));const role=node('td');role.append(badge(user.role==='admin'?'管理员':'普通用户',user.role==='admin'?'blue':'gray'));tr.append(role);const active=node('td');active.append(badge(user.active?'已启用':'已停用',user.active?'green':'gray'));if(user.must_change_password)active.append(node('span','cell-subtitle','下次登录需修改密码'));tr.append(active,cell(S.accounts.filter(a=>a.owner_id===user.id).length));const controls=node('div','actions');controls.append(mini('编辑 / 重置密码',()=>openUser(user)));if(user.id!==S.user.id)controls.append(mini('删除',()=>confirmDeleteUser(user),'danger-action'));const td=node('td');td.append(controls);tr.append(td);body.append(tr);}box.append(wrap);}
function render(){const query=$('account-search').value.trim().toLowerCase();const filtered=S.accounts.filter(a=>(a.label+' '+a.student_id).toLowerCase().includes(query));renderAccounts('accounts-table',filtered);renderAccounts('overview-accounts',S.accounts.slice(0,5),true);$('account-count').textContent=S.accounts.length+' 个账号';$('stat-total').textContent=S.accounts.length;const today=chinaDate();const confirmed=new Set(S.jobs.filter(j=>j.result?.businessDate===today&&(j.result?.result==='confirmed'||j.result?.status==='CHECKED_IN')).map(j=>j.account_id));$('stat-confirmed').textContent=S.accounts.filter(a=>a.confirmed_today||confirmed.has(a.id)).length;$('stat-automatic').textContent=S.accounts.filter(a=>a.enabled&&a.automatic).length;$('stat-attention').textContent=S.accounts.filter(a=>a.enabled&&['error','submission_unknown','record_changed'].includes(a.last_result?.result)).length;renderRecent();renderJobs();renderUsers();}
async function refresh(){if(S.refreshing||S.user?.must_change_password)return;S.refreshing=true;try{const values=await Promise.all([api('/api/accounts'),api('/api/jobs'),...(S.user.role==='admin'?[api('/api/users')]:[])]);S.accounts=values[0].accounts;S.jobs=values[1].jobs;if(values[2])S.users=values[2].users;render();errorAt('global-error','');}catch(error){errorAt('global-error',error.message);}finally{S.refreshing=false;}}
function showView(view){if(S.user?.must_change_password&&view!=='settings'){toast('请先修改登录密码。');view='settings';}if(view==='users'&&S.user?.role!=='admin')return;S.view=view;for(const section of document.querySelectorAll('.view'))section.hidden=section.id!=='view-'+view;for(const b of document.querySelectorAll('.nav-item'))b.classList.toggle('active',b.dataset.view===view);$('page-title').textContent={overview:'概览',accounts:'打卡账号',jobs:'运行记录',users:'用户管理',settings:'账户设置'}[view]||'概览';}
async function queue(account,mode){try{await api('/api/accounts/'+account.id+'/jobs',{method:'POST',body:JSON.stringify({mode,confirm:mode==='checkin'})});toast((modes[mode]||'任务')+'已加入队列');showView('jobs');await refresh();}catch(error){toast(error.message);throw error;}}
function confirmAction(title,message,action,submission=false,danger=false){$('confirm-title').textContent=title;$('confirm-message').textContent=message;$('submission-check-label').hidden=!submission;$('submission-check').checked=false;$('confirm-action').disabled=submission;$('confirm-action').classList.toggle('danger',danger);errorAt('confirm-error','');S.confirm=action;$('confirm-dialog').showModal();}
function confirmSubmit(a){confirmAction('确认提交打卡','将使用“'+a.label+'”配置的位置向学校提交今天的打卡记录。若结果不明确，请先核对学校记录。',()=>queue(a,'checkin'),true);}
function confirmDeleteAccount(a){confirmAction('删除打卡账号','确定删除“'+a.label+'”及其在网页中的运行记录？当天防重复提交记录仍会保留。',async()=>{await api('/api/accounts/'+a.id,{method:'DELETE'});toast('打卡账号已删除');await refresh();},false,true);}
function confirmDeleteUser(user){confirmAction('删除用户','确定删除“'+user.display_name+'”及其所有打卡账号？',async()=>{await api('/api/users/'+user.id,{method:'DELETE'});toast('用户已删除');await refresh();},false,true);}
function selectedPreset(){return S.presets.find(p=>p.id===$('location-preset').value);}
function presetPreview(fillAddress=false){
  const preset=selectedPreset();
  $('form-preset-name').textContent=preset?.name||'请选择位置';
  $('form-preset-description').textContent=preset?'经度 '+preset.source.longitude+' · 纬度 '+preset.source.latitude:'';
  $('form-coordinate-note').textContent='高德 GCJ-02 坐标，直接提交，不再转换。';
  if(fillAddress)$('location-address').value=preset?.address||'';
}
function setLocationFields(){
  const fixed=document.querySelector('[name=location-mode]:checked').value==='fixed';
  $('custom-fields').hidden=!fixed;$('preset-fields').hidden=fixed;
  for(const id of ['location-name','longitude','latitude']){$(id).required=fixed;$(id).disabled=!fixed;}
  $('coordinate-system').disabled=!fixed;$('location-preset').disabled=fixed;$('location-preset').required=!fixed;
}
function openAccount(a=null){
  S.editAccount=a;$('account-form').reset();$('edit-account-id').value=a?.id||'';
  $('account-dialog-title').textContent=a?'编辑打卡账号':'添加打卡账号';
  $('account-label').value=a?.label||'';$('student-id').value=a?.student_id||'';
  $('school-password').value='';$('school-password').required=!a;
  $('browser-fingerprint').value='';$('browser-fingerprint').required=!a;
  $('saved-password-hint').textContent=a?'已保存，留空保持原密码':'';
  $('saved-fingerprint-hint').textContent=a?'已保存，留空保持原指纹':'';
  $('user-agent').value=a?.user_agent||navigator.userAgent;
  $('account-enabled').checked=a?.enabled??true;$('account-automatic').checked=a?.automatic??false;
  $('account-automatic').disabled=!a?.ready_for_automation;$('run-at').value=a?.run_at||'22:00';
  $('automation-hint').textContent=a?.ready_for_automation?'该账号已通过首次提交验证，可开启每日自动运行。':'先完成一次经学校确认的手动提交，之后可以开启自动运行。';
  const owner=$('account-owner');owner.replaceChildren();
  for(const u of S.users.filter(u=>u.active)){const option=node('option','',u.display_name+'（'+u.username+'）');option.value=u.id;owner.append(option);}
  owner.value=a?.owner_id||S.user.id;
  const loc=a?.location||{mode:'preset',preset:S.defaultPresetId};
  const presetId=['学知三组团','xuezhi_group3'].includes(loc.preset)?S.defaultPresetId:loc.preset;
  const choices=S.presets;
  $('location-preset').replaceChildren();
  for(const p of choices){const option=node('option','',p.name+(p.id===S.defaultPresetId?'（默认）':''));option.value=p.id;$('location-preset').append(option);}
  $('location-preset').value=loc.mode==='preset'?presetId:S.defaultPresetId;
  document.querySelector('[name=location-mode][value="'+(loc.mode==='fixed'?'fixed':'preset')+'"]').checked=true;
  $('location-name').value=loc.name||'';$('latitude').value=loc.latitude??'';$('longitude').value=loc.longitude??'';
  $('coordinate-system').value=(loc.coordinate_system||'gcj02').toLowerCase().replace(/[-_]/g,'');
  $('location-address').value=loc.reverse_geocode??(loc.mode==='preset'?selectedPreset()?.address||'':'');
  presetPreview();setLocationFields();errorAt('account-error','');$('account-dialog').showModal();
}
$('account-form').addEventListener('submit',async event=>{
  event.preventDefault();errorAt('account-error','');$('save-account').disabled=true;
  try{
    const fixed=document.querySelector('[name=location-mode]:checked').value==='fixed';
    let location;
    if(fixed){location={mode:'fixed',name:$('location-name').value.trim(),latitude:Number($('latitude').value),longitude:Number($('longitude').value),coordinate_system:$('coordinate-system').value,reverse_geocode:$('location-address').value.trim()};}
    else{
      const preset=selectedPreset();if(!preset)throw new Error('请选择打卡位置。');
      location={mode:'preset',preset:preset.id};
      if($('location-address').value.trim()!==(preset.address||''))location.reverse_geocode=$('location-address').value.trim();
    }
    const previous=S.editAccount?.location;
    const previousPreset=['学知三组团','xuezhi_group3'].includes(previous?.preset)?S.defaultPresetId:previous?.preset;
    const samePoint=previous?.mode===location.mode&&(location.mode==='preset'?previousPreset===location.preset:previous.latitude===location.latitude&&previous.longitude===location.longitude&&previous.coordinate_system===location.coordinate_system);
    if(samePoint&&previous.request_metadata)location.request_metadata=previous.request_metadata;
    const data={label:$('account-label').value.trim(),student_id:$('student-id').value.trim(),password:$('school-password').value,browser_fingerprint:$('browser-fingerprint').value.trim(),user_agent:$('user-agent').value.trim(),location,enabled:$('account-enabled').checked,automatic:$('account-automatic').checked,run_at:$('run-at').value};
    if(S.user.role==='admin')data.owner_id=Number($('account-owner').value);
    const id=$('edit-account-id').value;
    await api('/api/accounts'+(id?'/'+id:''),{method:id?'PATCH':'POST',body:JSON.stringify(data)});
    $('school-password').value='';$('browser-fingerprint').value='';$('account-dialog').close();toast('账号已保存，未提交打卡');await refresh();
  }catch(error){errorAt('account-error',error.message);}finally{$('save-account').disabled=false;}
});
function openUser(user=null){$('user-form').reset();$('edit-user-id').value=user?.id||'';$('user-dialog-title').textContent=user?'编辑用户':'添加用户';$('user-username').value=user?.username||'';$('user-username').disabled=Boolean(user);$('user-display-name').value=user?.display_name||'';$('user-role').value=user?.role||'user';$('user-active').checked=user?.active??true;$('user-password').value='';$('user-password').required=!user;$('user-password-hint').textContent=user?'留空保持原密码；填写新密码即执行重置。':'至少 12 个字符，首次登录后需修改。';errorAt('user-error','');$('user-dialog').showModal();}
$('user-form').addEventListener('submit',async event=>{event.preventDefault();errorAt('user-error','');$('save-user').disabled=true;try{const id=$('edit-user-id').value;const data={display_name:$('user-display-name').value.trim(),role:$('user-role').value,active:$('user-active').checked};if(!id)data.username=$('user-username').value.trim();if($('user-password').value)data.password=$('user-password').value;await api('/api/users'+(id?'/'+id:''),{method:id?'PATCH':'POST',body:JSON.stringify(data)});$('user-password').value='';$('user-dialog').close();toast('用户已保存');await refresh();}catch(error){errorAt('user-error',error.message);}finally{$('save-user').disabled=false;}});
$('password-form').addEventListener('submit',async event=>{event.preventDefault();errorAt('password-error','');if($('new-password').value!==$('confirm-password').value){errorAt('password-error','两次新密码不一致。');return;}const button=event.submitter;button.disabled=true;try{await api('/api/me/password',{method:'POST',body:JSON.stringify({current_password:$('current-password').value,new_password:$('new-password').value})});$('password-form').reset();location.replace('/login');}catch(error){errorAt('password-error',error.message);button.disabled=false;}});
$('confirm-action').addEventListener('click',async()=>{$('confirm-action').disabled=true;try{await S.confirm?.();$('confirm-dialog').close();}catch(error){errorAt('confirm-error',error.message);}finally{$('confirm-action').disabled=false;}});
$('submission-check').addEventListener('change',()=>$('confirm-action').disabled=!$('submission-check').checked);
for(const b of document.querySelectorAll('.close-dialog'))b.addEventListener('click',()=>b.closest('dialog').close());
for(const b of document.querySelectorAll('[data-view]'))b.addEventListener('click',()=>showView(b.dataset.view));
for(const b of document.querySelectorAll('.add-account-button'))b.addEventListener('click',()=>openAccount());
for(const radio of document.querySelectorAll('[name=location-mode]'))radio.addEventListener('change',()=>{
  if(radio.value==='fixed'&&$('location-address').value===(selectedPreset()?.address||''))$('location-address').value='';
  if(radio.value==='preset')presetPreview(true);
  setLocationFields();
});
$('location-preset').addEventListener('change',()=>presetPreview(true));
$('add-user').addEventListener('click',()=>openUser());$('account-search').addEventListener('input',render);$('refresh-jobs').addEventListener('click',refresh);$('show-help').addEventListener('click',()=>$('help-dialog').showModal());$('fingerprint-help').addEventListener('click',()=>$('help-dialog').showModal());
$('logout').addEventListener('click',async()=>{try{await api('/api/logout',{method:'POST',body:'{}'});}catch{}finally{location.replace('/login');}});
function tick(){$('clock').textContent=new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',month:'long',day:'numeric',weekday:'short',hour:'2-digit',minute:'2-digit'}).format(new Date());}tick();setInterval(tick,30000);
(async()=>{try{const session=await api('/api/session');if(!session.authenticated){location.replace('/login');return;}S.user=session.user;S.csrf=session.csrf_token;$('overview-account-heading').textContent=S.user.role==='admin'?'全部打卡账号':'我的打卡账号';$('current-name').textContent=S.user.display_name;$('current-role').textContent=S.user.role==='admin'?'管理员':'普通用户';$('avatar').textContent=Array.from(S.user.display_name)[0]||'U';$('app-version').textContent='v'+session.version;$('http-notice').hidden=session.https;$('password-required').hidden=!S.user.must_change_password;for(const el of document.querySelectorAll('.admin-only'))el.hidden=S.user.role!=='admin';const hour=Number(new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Shanghai',hour:'2-digit',hour12:false}).format(new Date()));$('greeting').textContent=(hour>=18||hour<6?'晚上好':'你好')+'，'+S.user.display_name;if(S.user.must_change_password){showView('settings');return;}const locations=await api('/api/locations');S.presets=locations.locations;S.defaultPresetId=locations.default_preset_id;const preset=S.presets.find(p=>p.id===S.defaultPresetId);$('default-preset-name').textContent=preset?.name||'常用位置';$('preset-address').textContent=preset?'经度 '+preset.source.longitude+' · 纬度 '+preset.source.latitude:'';await refresh();setInterval(()=>{if(document.visibilityState==='visible')refresh();},6000);}catch(error){errorAt('global-error',error.message);}})();
