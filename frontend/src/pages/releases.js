import {releases,datasets as datasetsApi} from '../api/entities.js';
import {workspace} from '../stores/workspace.js';
import {session} from '../stores/session.js';
import {heading} from '../components/common/shell.js';
import {esc,fmt,date,notify} from '../utils/dom.js';
import {submit} from '../hooks/forms.js';
import {ReleaseStatus,CheckStatus} from '../constants/enums.js';

const isAdmin=()=>session.user.role==='admin';

function versionBadge(v){
 return '<span class="engine-badge">'+esc(v||'v1')+'</span>';
}

function statusPill(s){
 return '<span class="release-pill '+esc(s)+'">'+esc(ReleaseStatus[s]||s)+'</span>';
}

function checkPill(s){
 return '<span class="check-pill '+esc(s)+'">'+esc(CheckStatus[s]||s)+'</span>';
}

function enginePanel(versions){
 return '<section class="panel"><div class="section-title"><h2>计算版本登记</h2><span>接单瞬间固定 · 排队与重启沿用</span></div>'
  +versions.map(v=>'<article class="engine-row"><div><strong>'+esc(v.version)+' · '+esc(v.title)+'</strong>'
   +(v.is_default?'<span class="default-tag">当前默认</span>':'')
   +(v.retired?'<span class="retired-tag">已退役</span>':'')
   +'<p>'+esc(v.description)+'</p><small class="method-line">'+esc(v.method)+'</small></div>'
   +'<div class="engine-side"><span>在途任务 <strong>'+v.in_flight+'</strong> 单</span>'
   +(isAdmin()&&!v.is_default&&!v.retired?'<button class="button small" data-retire="'+esc(v.version)+'">退役版本</button>':'')
   +(v.retired?'<span class="muted">退役后不可接新单</span>':'')+'</div></article>').join('')
  +'<p class="hint">退役保护：版本仍有排队/计算中任务时拒绝退役；回滚只影响新单，在途任务沿用旧版直到结束。</p></section>';
}

function createForm(dsList,versions){
 const candidates=versions.filter(v=>!v.is_default&&!v.retired);
 return '<section class="panel"><div class="section-title"><h2>建立试发布</h2><span>锁定批次 · 参数 · 基线改善量与容差</span></div>'
  +'<form id="release-form">'
  +'<label>试发布名称<input name="name" required minlength="2" value="候选算法双算核验 · '+(new Date().toLocaleDateString())+'"></label>'
  +'<label>候选版本<select name="candidate_version" required>'+candidates.map(v=>'<option value="'+esc(v.version)+'">'+esc(v.version+' · '+v.title)+'</option>').join('')+'</select></label>'
  +'<label>锁定历史批次（可多选）<div class="check-list">'+dsList.map(d=>'<label class="check-item"><input type="checkbox" name="dataset_ids" value="'+d.id+'" checked> '+esc(d.name)+' · '+d.rows+' 条 <small>'+esc(d.checksum.slice(0,16))+'…</small></label>').join('')+'</div></label>'
  +'<div class="parameter-grid">'
  +'<label>核验窗口（小时）<input type="number" name="validity_hours" value="168" min="1" max="720" required></label>'
  +'<label>改善量绝对容差/秒<input type="number" step="any" name="tol_diff_abs" value="0.6" min="0" required></label>'
  +'<label>区间界容差/秒<input type="number" step="any" name="tol_bound_abs" value="0.9" min="0" required></label>'
  +'<label>改善量相对容差<input type="number" step="any" name="tol_diff_rel" value="0.25" min="0" required></label>'
  +'<label>p 值容差<input type="number" step="any" name="tol_p_abs" value="0.02" min="0" required></label>'
  +'</div>'
  +'<p class="hint">参数组合固定为全部班次/早班/晚班 × 90%/95%/99% 共 9 组，逐批次双算。每个批次×参数一条对照，重试不新增条目。</p>'
  +'<button type="submit" class="primary" '+(isAdmin()&&candidates.length?'':'disabled')+'>锁定并开始核验 ↗</button>'
  +(isAdmin()?'':'<p class="hint">仅业务负责人可发起试发布。</p>')+'</form></section>';
}

function comparisonBlock(c){
 const cmp=c.comparison||{};
 if(c.status==='pending')return '<p class="muted">未算批次：核验中断后从这里恢复。</p>';
 const rows=[];
 if(typeof cmp.baseline_diff==='number'){
  rows.push(['改善量 A−B（秒）',fmt(cmp.baseline_diff),fmt(cmp.candidate_diff),fmt(cmp.diff_delta)]);
  rows.push(['区间下界（秒）',fmt(cmp.baseline_low),fmt(cmp.candidate_low),fmt(cmp.low_delta)]);
  rows.push(['区间上界（秒）',fmt(cmp.baseline_high),fmt(cmp.candidate_high),fmt(cmp.high_delta)]);
  rows.push(['双侧 p 值',fmt(cmp.baseline_p),fmt(cmp.candidate_p),fmt((cmp.candidate_p||0)-(cmp.baseline_p||0))]);
 }
 return '<table class="mini-table"><thead><tr><th>指标</th><th>基线版本</th><th>候选版本</th><th>差值</th></tr></thead><tbody>'
  +rows.map(r=>'<tr>'+r.map(x=>'<td>'+esc(x)+'</td>').join('')+'</tr>').join('')+'</tbody></table>'
  +(c.last_error?'<p class="warning">'+esc(c.last_error)+'</p>':'');
}

function releaseCard(r){
 const cc=r.checks_count||{pending:0,passed:0,failed:0,total:0};
 const expired=Date.now()/1000>r.expires_at;
 return '<article class="release-card '+esc(r.status)+'">'
  +'<div class="release-head"><div><strong>'+esc(r.name)+'</strong> '+statusPill(r.status)
  +(expired&&r.status!=='published'&&r.status!=='rolled_back'?'<span class="expired-tag">核验已过期</span>':'')+'</div>'
  +'<small>#'+r.id+' · 候选 '+esc(r.candidate_version)+' → 基线 '+esc(r.baseline_version)+' · 起始默认 '+esc(r.start_default_version)+'</small></div>'
  +'<div class="check-progress"><span class="check-pill passed">通过 '+cc.passed+'</span><span class="check-pill pending">未算 '+cc.pending+'</span><span class="check-pill failed">超差/缺项 '+cc.failed+'</span><span class="muted">共 '+cc.total+' 条</span></div>'
  +'<details class="check-details"><summary>查看锁定快照与逐条对照（容差 '+esc(JSON.stringify(r.tolerance))+'）</summary>'
  +'<div class="lock-grid"><div><p class="eyebrow">锁定批次</p>'+r.dataset_ids.map(id=>'<small>#'+id+' '+esc((r.dataset_checksums||{})[String(id)]?.slice(0,24)||'')+'…</small>').join('<br>')+'</div>'
  +'<div><p class="eyebrow">锁定参数（'+r.locked_params.length+' 组）</p><small>'+esc(r.locked_params.map(p=>(p.shift||'全部')+'/'+((p.confidence*100)|0)+'%').join('，'))+'</small></div>'
  +'<div><p class="eyebrow">核验窗口</p><small>'+date(r.expires_at)+'</small></div></div>'
  +'<div class="check-list-rows">'+(r.checks||[]).map(c=>'<div class="check-row"><div>'+checkPill(c.status)+' <small>批次#'+c.dataset_id+' · '+esc(c.params.shift)+' · '+esc((c.params.confidence*100)|0)+'% · 尝试 '+c.attempts+' 次</small></div>'+comparisonBlock(c)+'</div>').join('')+'</div>'
  +(r.failure_reason?'<p class="warning">'+esc(r.failure_reason)+'</p>':'')+'</details>'
  +'<div class="release-actions">'
  +(isAdmin()&&(r.status==='pending'||r.status==='rejected')?'<button class="button" data-verify="'+r.id+'">核验/恢复未算批次 ↻</button>':'')
  +(isAdmin()&&r.status==='ready'?'<button class="primary" data-publish="'+r.id+'">全部通过 · 切换默认版本 ↗</button>':'')
  +(isAdmin()&&r.status==='published'?'<button class="button" data-rollback="'+r.id+'">回滚到 '+esc(r.baseline_version)+'</button>':'')
  +(r.published_at?'<small class="muted">上线于 '+date(r.published_at)+'</small>':'')
  +(r.rolled_back_at?'<small class="muted">回滚于 '+date(r.rolled_back_at)+'（仅影响新单）</small>':'')
  +'</div></article>';
}

export async function releasesPage(){
 const [list,versions,dsList]=await Promise.all([releases.list(),releases.versions(),datasetsApi.list()]);
 workspace.releases=list;
 return heading('06 / RELEASE CANARY','计算版本试发布与双算对照','候选算法按全样本班别构成校正均值差；锁定历史批次、参数、基线改善量与区间容差，缺项或超差拒绝上线，全部通过才切换默认版本。')
  +'<div class="release-grid">'+enginePanel(versions)+createForm(dsList,versions)+'</div>'
  +'<section class="panel"><div class="section-title"><h2>试发布单</h2><span>待核验 · 超差 · 可上线 · 已上线</span></div>'
  +'<div class="release-list">'+(list.length?list.map(releaseCard).join(''):'<p class="empty">尚无试发布单。建立后系统对每个锁定批次执行基线/候选双算。</p>')+'</div></section>';
}

export function bindReleases(refresh){
 submit(document.querySelector('#release-form'),async f=>{
  const ids=[...f.getAll('dataset_ids')].map(Number);
  if(!ids.length)throw new Error('至少选择一个历史批次');
  const data={name:f.get('name'),candidate_version:f.get('candidate_version'),dataset_ids:ids,
   validity_hours:Number(f.get('validity_hours')),
   tolerance:{diff_abs:Number(f.get('tol_diff_abs')),bound_abs:Number(f.get('tol_bound_abs')),
              diff_rel:Number(f.get('tol_diff_rel')),p_abs:Number(f.get('tol_p_abs'))}};
  await releases.create(data);notify('试发布已锁定，开始双算核验');await refresh();
 });
 document.querySelectorAll('[data-verify]').forEach(b=>b.onclick=async()=>{try{await releases.verify(b.dataset.verify);notify('已推进核验，未算批次继续对照');await refresh();}catch(e){notify(e.message,true);}});
 document.querySelectorAll('[data-publish]').forEach(b=>b.onclick=async()=>{try{await releases.publish(b.dataset.publish);notify('默认版本已切换，新单将使用候选版本');await refresh();}catch(e){notify(e.message,true);}});
 document.querySelectorAll('[data-rollback]').forEach(b=>b.onclick=async()=>{try{await releases.rollback(b.dataset.rollback);notify('已回滚，仅影响新单；在途任务沿用旧版');await refresh();}catch(e){notify(e.message,true);}});
 document.querySelectorAll('[data-retire]').forEach(b=>b.onclick=async()=>{try{await releases.retire(b.dataset.retire);notify('版本已退役');await refresh();}catch(e){notify(e.message,true);}});
}
