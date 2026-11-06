'use strict';
const steps = [
  ['Add sources', 'Start with the evidence', 'Load a research package, webpage or one gameplay log. Adding it saves evidence for review; it does not accept its claims.'],
  ['Review findings', 'Read, decide and complete', 'Read the source and accept, revise, reject or add findings here. Leave uncertainty pending.'],
  ['Whois', 'Collect and enrich characters', 'Build the queue for Mudlet, then bring back its captures. This optional step preserves historical player links.'],
  ['Build & export', 'Check the update', 'Build a concise list of Deck changes, and export accepted response evidence for the epoch comparison.'],
  ['Publish', 'Put the reviewed Deck online', 'Publish the prepared Deck data to WordPress when you are ready.']
];
const hash = new URLSearchParams(location.hash.slice(1));
let token = hash.get('token') || sessionStorage.getItem('deck-workbench-token') || '';
if (token) sessionStorage.setItem('deck-workbench-token', token);
history.replaceState(null, '', location.pathname);
let state = {}, current = 0, seenJob = '', sourceTab = 'package', candidates = [], review = null;
let sourceDraft = {title:'',url:'',date:'',start:'',end:'',observer:'',characters:'',groups:'',text:'',selected:[]};
let previewFilters = {table:'all',action:'all',q:'',offset:0};
let previewRequest = 0;
let previewDetailRequest = 0;
let selectedClaimGroups = new Set();
let activeSourceReview=null;
const sourceReviewFilters=new Map();
const previewNames = {characters:'Characters',players:'Players',player_character_links:'Player links',logs:'Logs',historical_events:'Deaths & trophy snapshots',log_appearances:'Log appearances',whois_queue:'Whois queue',sources:'Source files',evidence:'Evidence claims',historical_log_index:'Log index entries'};
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const when = value => value ? new Date(value * 1000).toLocaleString() : 'Not yet';
const running = () => state.job?.status === 'running';
const download = kind => `/download/${kind}?token=${encodeURIComponent(token)}`;

async function api(route, payload) {
  const response = await fetch('/api/' + route, {method:payload === undefined ? 'GET':'POST',
    headers:{'X-Workbench-Token':token,...(payload === undefined ? {}:{'Content-Type':'application/json'})},
    ...(payload === undefined ? {}:{body:JSON.stringify(payload)})});
  const result = await response.json();
  if (!response.ok) throw Error(result.error || 'The operation could not be completed.');
  return result;
}
function notice(message, error=false) {
  $('notice').textContent = message;
  $('notice').className = error ? 'error':'';
  $('notice').hidden = !message;
}
function bind(id, event, handler) {
  const element = $(id);
  if (element) element.addEventListener(event, async e => {try {await handler(e);} catch(error) {notice(error.message,true);}});
}
async function job(action, extra={}) {
  notice('');
  await api('job', {action,...extra});
  $('activity').open = true;
  await refresh();
}
function completion(index) {
  return [!!state.research_applied,!!state.links_reviewed,!!state.whois_imported,!!state.build_current,!!state.published_at&&!!state.build_current][index];
}
function chrome() {
  $('archive-path').textContent = state.root || '';
  $('count-characters').textContent = (state.counts?.characters || 0).toLocaleString();
  $('count-captures').textContent = (state.counts?.captures || 0).toLocaleString();
  $('count-pending').textContent = (state.counts?.pending || 0).toLocaleString();
  $('connection-badge').textContent = state.connection?.configured ? 'Publishing connected':'Local workspace';
  $('steps').innerHTML = steps.map((step,index) => `<button class="step-link ${index===current?'active':''} ${completion(index)?'complete':''}" data-step="${index}" ${index===current?'aria-current="step"':''}><span class="step-circle">${completion(index)?'✓':index+1}</span><span>${step[0]}</span></button>`).join('');
  $('steps').querySelectorAll('button').forEach(b => b.addEventListener('click',() => go(Number(b.dataset.step))));
  $('step-number').textContent = `STEP ${current + 1} / ${steps.length}`;
  $('step-title').textContent = steps[current][1];
  $('step-description').textContent = steps[current][2];
  $('step-position').textContent = `${current+1} of ${steps.length}`;
  $('back').disabled = current===0;
  $('next').disabled = current===steps.length-1;
  $('backup-note').textContent = state.last_backup ? `Last archive backup: ${state.last_backup.split('/').pop()}`:'Working tables are backed up before imports and edits.';
  $('restore-button').disabled = !state.last_backup || running();
  const status = state.job?.status;
  $('job-status').textContent = status === 'running' ? 'Working…' : status === 'done' ? 'Completed' : status === 'error' ? 'Needs attention':'';
  $('job-status').className = status === 'running' ? 'busy' : status === 'error' ? 'error-text':'';
  $('activity-title').textContent = state.job ? 'Activity · ' + state.job.action.replaceAll('_',' ') : 'Activity log';
  if (state.job) $('job-log').textContent = state.job.log.join('\n') || 'Starting…';
  $('content').querySelectorAll('button,input,select,textarea').forEach(e => {if (!e.dataset.keepDisabled) e.disabled=running();});
  if ($('publish')) $('publish').disabled = running() || !state.build_current || !state.connection?.configured;
  if ($('import-whois')) $('import-whois').disabled = running() || !state.whois_preview;
}
async function go(step) {
  current = Math.max(0, Math.min(steps.length-1,step));
  await api('step',{step:current});
  notice('');
  await render();
  window.scrollTo({top:0,behavior:'smooth'});
}
async function refresh() {
  state = await api('state');
  chrome();
  const signature = state.job ? state.job.id + state.job.status : '';
  if (signature && signature !== seenJob) {
    const changedJob = seenJob;
    seenJob = signature;
    if (state.job.status !== 'running') {
      if (changedJob) notice(state.job.status === 'done' ? 'Step completed. You can review the result and continue.':state.job.error,state.job.status === 'error');
      review=null;
      if(state.job.action==='stage_research'&&state.job.status==='done'){
        current=1;activeSourceReview=null;selectedClaimGroups.clear();
      }
      await render();
    }
  }
}
async function bytes64(file) {
  if (file.size > 25*1024*1024) throw Error('Choose a file under 25 MiB.');
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary='';
  for (let i=0;i<bytes.length;i+=8192) binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
  return btoa(binary);
}
async function upload(input,kind) {
  const file=$(input).files[0];
  if (!file) throw Error('Choose a file first.');
  await api('upload',{kind,filename:file.name,data:await bytes64(file)});
  if(kind==='research'){activeSourceReview=null;selectedClaimGroups.clear();}
  state=await api('state');
  notice(`${file.name} is ready for preview.`);
  await render();
}
function sourceFields() {
  return `<div class="inline-fields"><div><label for="source-title">Source title</label><input id="source-title" placeholder="e.g. Rogrog at the Ford"></div><div><label for="source-url">Original or archived URL (optional)</label><input id="source-url" placeholder="https://web.archive.org/…"></div></div>
  <div class="inline-fields triple"><div><label for="source-date">Event date label</label><input id="source-date" placeholder="e.g. Late 1996, or date uncertain"></div><div><label for="source-start">Earliest date, if known</label><input id="source-start" type="date"></div><div><label for="source-end">Latest date, if known</label><input id="source-end" type="date"></div></div>
  <small>Use the date of the gameplay, if established. A webpage posting date does not automatically date the event.</small>
  <label for="source-text">Original webpage text or one log</label><textarea id="source-text" rows="8" placeholder="Paste the source here, or load a text/HTML file below."></textarea>
  <label for="raw-file">Load a saved source</label><input id="raw-file" type="file" accept=".txt,.log,.html,.htm,text/plain,text/html">
  <div class="inline-fields"><div><label for="source-observer">Observer / trophy-displaying character</label><input id="source-observer" placeholder="e.g. Cadfael"><small>Use the observer of this specific log perspective.</small></div><div><label for="source-characters">Other confirmed player characters</label><input id="source-characters" placeholder="NameOne, NameTwo"><small>Only list characters you can establish from the source.</small></div></div>
  <label for="source-groups">Explicit same-player groups (optional)</label><textarea id="source-groups" rows="3" placeholder="pDorien: Dorien, Utgbald, Rogrog&#10;pHordak: Hordak, Ward, Gubbe"></textarea>
  <small>One public player handle per line. Enter an association only when the source supports common ownership.</small>
  <div class="actions"><button id="detect" class="secondary">Detect death & trophy lines</button></div>
  <div id="extraction"></div>
  <div class="actions"><button id="prepare-source">Add this source to review →</button></div>`;
}
function extractionTable() {
  if (!candidates.length) {$('extraction').innerHTML='<p class="hint">No standard death or trophy lines detected. You can still enter confirmed names and player groups.</p>';return;}
  $('extraction').innerHTML=`<div class="callout">Confirm which detected names are player characters. Nothing is included until selected. Anonymous races and mobile descriptions are excluded by the detector; an unfamiliar one-word name still needs your review.</div><div class="toolbar"><button id="select-all-entries" class="secondary">Select all named entries</button><button id="clear-entries" class="text-button">Clear selection</button></div><div class="table-wrap"><table><thead><tr><th>Keep</th><th>Type</th><th>Character</th><th>Count</th><th>Source line</th></tr></thead><tbody>${candidates.map((c,i)=>`<tr><td><input type="checkbox" class="entry-check" data-index="${i}" aria-label="Keep ${esc(c.character)} ${esc(c.kind)}" ${sourceDraft.selected.includes(i)?'checked':''}></td><td>${esc(c.kind)}</td><td>${esc(c.character)}</td><td>${c.count}</td><td><div class="extract-raw">${esc(c.raw)}</div><small>Line ${c.line}</small></td></tr>`).join('')}</tbody></table></div>`;
  $('extraction').querySelectorAll('.entry-check').forEach(c=>c.onchange=()=>{sourceDraft.selected=Array.from(document.querySelectorAll('.entry-check:checked')).map(e=>Number(e.dataset.index));});
  bind('select-all-entries','click',()=>{sourceDraft.selected=candidates.map((_,i)=>i);extractionTable();});
  bind('clear-entries','click',()=>{sourceDraft.selected=[];extractionTable();});
}
async function renderSource() {
  $('content').innerHTML=`<div class="tabs"><button id="tab-package" class="${sourceTab==='package'?'active':''}">Research JSON / ZIP</button><button id="tab-text" class="${sourceTab==='text'?'active':''}">Webpage / gameplay log</button></div>`+
    (sourceTab==='package'?`<div class="panel"><h2>Use research you already have</h2><p>Load the July historical research bundle, a player-link JSON, or another supported structured research file. Keep the ZIP intact; the workbench extracts it for you.</p><label for="research-file">Research file</label><div class="upload-row"><input id="research-file" type="file" accept=".json,.zip"><button id="load-research">Add research to review</button></div><small>Accepts our historical corpus, same-player candidate files, website player lists and curated log indexes.</small></div>`:
    `<div class="panel"><h2>Prepare a source yourself</h2><p>Paste what the source says, enter any explicit player groups, and review the standard game lines the helper detects. You do not need to write JSON.</p>${sourceFields()}</div>`)+
    (state.research_path?`<div class="callout success"><b>A research input is selected.</b><div class="file-picked">${esc(state.research_path)}</div><button id="source-next" class="text-button">Review findings →</button></div>`:'');
  bind('tab-package','click',async()=>{sourceTab='package';await render();});
  bind('tab-text','click',async()=>{sourceTab='text';await render();});
  bind('load-research','click',async()=>{await upload('research-file','research');await job('stage_research');});
  bind('source-next','click',()=>state.research_applied?go(1):job('stage_research'));
  const fieldMap={title:'source-title',url:'source-url',date:'source-date',start:'source-start',end:'source-end',observer:'source-observer',characters:'source-characters',groups:'source-groups',text:'source-text'};
  for (const [key,id] of Object.entries(fieldMap)) {
    if (!$(id)) continue;
    $(id).value=sourceDraft[key];
    $(id).oninput=()=>{sourceDraft[key]=$(id).value;if (key==='text'||key==='observer') {candidates=[];sourceDraft.selected=[];$('extraction').innerHTML='';}};
  }
  bind('raw-file','change',async()=>{
    const file=$('raw-file').files[0];if(!file)return;
    if(file.size>8*1024*1024)throw Error('Use one source under 8 MiB at a time.');
    const bytes=await file.arrayBuffer();let text;
    try{text=new TextDecoder('utf-8',{fatal:true}).decode(bytes);}catch{text=new TextDecoder('windows-1252').decode(bytes);}
    sourceDraft.text=text;sourceDraft.original_filename=file.name;sourceDraft.original_data=await bytes64(file);
    if(!sourceDraft.title)sourceDraft.title=file.name;
    candidates=[];sourceDraft.selected=[];await render();
  });
  bind('detect','click',async()=>{candidates=(await api('analyse',sourceDraft)).entries;sourceDraft.selected=[];extractionTable();notice(`Detected ${candidates.length} named observations. Select the player entries to include.`);});
  bind('prepare-source','click',async()=>{await api('prepare',sourceDraft);activeSourceReview=null;state=await api('state');await job('stage_research');});
  if(candidates.length)extractionTable();
}
async function technicalRecords() {
  const target=$('technical-records');
  if(!target||!state.research_report)return;
  target.innerHTML=`<p class="hint">Storage rows from the latest source load. Review decisions are made above.</p><a href="${download('report')}">Download import report</a><div class="inline-fields"><div><label for="preview-table">Record type</label><select id="preview-table"><option value="all">All record types</option>${Object.entries(previewNames).map(([v,l])=>`<option value="${v}">${l}</option>`).join('')}</select></div><div><label for="preview-action">Change</label><select id="preview-action"><option value="all">Additions and updates</option><option value="added">Additions</option><option value="updated">Updates</option></select></div></div><label for="preview-search">Search supporting rows</label><input id="preview-search"><div id="preview-records"></div><div class="preview-pagination"><button id="preview-prev" class="secondary">Previous</button><span id="preview-page"></span><button id="preview-next" class="secondary">More</button></div><div id="preview-detail"></div>`;
  $('preview-table').value=previewFilters.table;$('preview-action').value=previewFilters.action;$('preview-search').value=previewFilters.q;
  for(const id of ['preview-table','preview-action','preview-search'])bind(id,id==='preview-search'?'input':'change',async()=>{
    previewFilters={table:$('preview-table').value,action:$('preview-action').value,q:$('preview-search').value,offset:0};await loadPreviewRecords();
  });
  bind('preview-prev','click',async()=>{previewFilters.offset=Math.max(0,previewFilters.offset-25);await loadPreviewRecords();});
  bind('preview-next','click',async()=>{previewFilters.offset+=25;await loadPreviewRecords();});
  await loadPreviewRecords();
}
function confidenceBadge(rating){return `<span class="confidence confidence-${esc(rating)}">${esc(rating==='unknown'?'Unrated':rating[0].toUpperCase()+rating.slice(1))} confidence</span>`;}
async function renderClaimGroups(scope,target){
  const data=review;
  if(!$(target))return;
  const groups=data.groups||[], summary=data.summary||{};
  let filter=groups.some(g=>g.needs_judgement&&g.pending)?'attention':'all', search='';
  $(target).innerHTML=`<div class="triage-summary"><div><b>${summary.needs_judgement||0}</b><span>source groups needing judgement</span></div><div><b>${summary.supported||0}</b><span>high-confidence groups</span></div></div>
  <p class="hint">High = explicit source-supported claims with a retained original and no detected conflict. Medium = a summary/transcription or interpretation. Low = weak attribution or conflict. Unrated = no usable assessment. These are evidence-based rules, not probabilities or a fresh AI reading.</p>
  <div class="actions"><button id="accept-supported" ${!groups.some(g=>g.safe_to_accept&&g.pending)?'disabled data-keep-disabled="true"':''}>Accept all pending high-confidence claims</button></div>
  <div class="tabs claim-tabs"><button data-filter="attention">Needs judgement</button><button data-filter="supported">High confidence</button><button data-filter="all">All source groups</button></div>
  <label for="${target}-search">Find a character, player or source</label><input id="${target}-search" type="search" placeholder="Search source groups…">
  <div id="${target}-groups"></div><div id="${target}-original"></div>`;
  function update(){
    const visible=groups.filter(g=>(filter==='all'||filter==='supported'&&g.safe_to_accept||filter==='attention'&&g.needs_judgement)&&(!search||[g.title,g.source,...g.names].join(' ').toLocaleLowerCase().includes(search)));
    document.querySelectorAll(`#${target} .claim-tabs button`).forEach(b=>b.classList.toggle('active',b.dataset.filter===filter));
    $(target+'-groups').innerHTML=visible.map(g=>`<article class="claim-group"><div class="claim-title">${scope==='archive'?`<input type="checkbox" class="claim-group-check" data-id="${esc(g.id)}" aria-label="Review ${esc(g.title)}" ${selectedClaimGroups.has(g.id)?'checked':''}>`:''}<h3>${esc(g.title)}</h3>${confidenceBadge(g.confidence)}</div>
      <p class="group-source">Source: ${esc(g.source)} · ${g.pending} pending claim(s) · ${g.original_attached?'Original attached':'Original not retained'}</p><p>${esc(g.reasons[0]||'No assessment available.')}</p>
      ${g.concerns.map(reason=>`<p class="group-concern">${esc(reason)}</p>`).join('')}
      ${g.date_notes.map(reason=>`<p class="hint">${esc(reason)}</p>`).join('')}
      <p class="group-names">${esc(g.names.join(', '))}</p>
      <details><summary>Why this rating / individual claims</summary><ul>${g.reasons.map(reason=>`<li>${esc(reason)}</li>`).join('')}</ul><ul>${g.members.map(m=>`<li>${esc(m.character)}${m.other_character?' → '+esc(m.other_character):''}${m.count?' · '+esc(m.count):''} · ${esc(m.status.replaceAll('_',' '))}</li>`).join('')}</ul></details>
      <div class="actions"><button class="secondary open-original" data-group="${esc(g.id)}">Read original source</button><button class="secondary open-source-facts" data-group="${esc(g.id)}">View source & all claims</button>${scope==='archive'?`<select class="group-decision" data-group="${esc(g.id)}" aria-label="Decision for ${esc(g.title)}"><option value="">Choose a decision…</option><option value="accepted">Accept group as written</option><option value="revise">Review / revise individual claims</option><option value="rejected">Reject group</option><option value="needs_review">Keep group pending</option></select>`:''}</div></article>`).join('')||`<div class="empty">${groups.length?'No source groups match this filter.':'No claim groups yet. Add a source, or open a retained source below to inspect all findings.'}</div>`;
    $(target+'-groups').querySelectorAll('.claim-group-check').forEach(e=>e.onchange=()=>e.checked?selectedClaimGroups.add(e.dataset.id):selectedClaimGroups.delete(e.dataset.id));
    $(target+'-groups').querySelectorAll('.open-original').forEach(b=>b.onclick=()=>openOriginal(scope,b.dataset.group,target+'-original').catch(e=>notice(e.message,true)));
    $(target+'-groups').querySelectorAll('.open-source-facts').forEach(b=>b.onclick=()=>openSourceReview(scope,{group:b.dataset.group},target+'-original').catch(e=>notice(e.message,true)));
    $(target+'-groups').querySelectorAll('.group-decision').forEach(b=>b.onchange=async()=>{const choice=b.value;b.value='';try{
      if(choice==='revise')await openSourceReview(scope,{group:b.dataset.group},target+'-original');
      else if(choice)await job('review_claims',{groups:[b.dataset.group],status:choice});
    }catch(e){notice(e.message,true);}});
  }
  document.querySelectorAll(`#${target} .claim-tabs button`).forEach(b=>b.onclick=()=>{filter=b.dataset.filter;update();});
  bind(target+'-search','input',()=>{search=$(target+'-search').value.trim().toLocaleLowerCase();update();});
  update();
  bind('accept-supported','click',()=>job('review_supported'));
}
function sourceLink(value){try{const u=new URL(value);return ['http:','https:'].includes(u.protocol)?`<a href="${esc(u.href)}" target="_blank" rel="noopener noreferrer">Open archived / original webpage ↗</a>`:'';}catch{return '';}}
function factStatement(fact){
  if(fact.kind==='response')return `${fact.response?.label||'Response'} · ${fact.response?.viewpoint||'Unspecified'}: ${fact.value}`;
  if(fact.kind==='death')return `${fact.subject}: ${fact.value} death observation(s)`;
  if(fact.kind==='trophy')return `${fact.subject}: trophy snapshot of ${fact.value} × ${fact.object}`;
  if(fact.kind==='link')return `${fact.subject} → player ${fact.object}`;
  return `${fact.label||fact.kind}: ${fact.value}`;
}
async function openSourceReview(scope,query,target,scroll=true){
  const request=new URLSearchParams({scope,...(query.group?{group:query.group}:{source_id:query.source_id,log_id:query.log_id||''})});
  const data=await api('source-facts?'+request);
  if(!$(target))return;
  activeSourceReview={scope,source_id:data.source_id,log_id:data.log_id,target};
  $(target).innerHTML=`<section class="source-review"><span class="eyebrow">SOURCE REVIEW</span><h2>${esc(data.log?.title||data.source.title)}</h2>
    <p><b>${data.facts.length} attached claims and findings.</b> This includes every retained extraction field, named appearance and reviewed claim. Unreviewed context is shown alongside pending, accepted and rejected claims. This list cannot establish that the original extraction missed nothing; add missing findings below.</p>
    <div class="inline-fields"><div><label for="source-scope">Source scope</label><select id="source-scope"><option value="">Entire imported source collection / page</option>${data.logs.map(log=>`<option value="${esc(log.id)}" ${data.log_id===log.id?'selected':''}>${esc(log.title)}</option>`).join('')}</select></div><div><label for="source-fact-search">Find in attached claims</label><input id="source-fact-search" type="search" placeholder="Name, fact, status or evidence…"></div></div>
    <p class="hint">Choose a decision beside a claim. Revise opens a form; accepting keeps its content and confidence. Decisions retain revision history.</p><button id="add-source-fact" class="secondary">+ Add a missing finding</button>
    ${scope==='archive'&&data.log_id?'<button id="scan-responses" class="secondary">Find epoch response lines</button><p class="hint">Creates pending wording findings from this log. Repeating the scan preserves decisions. Check gameplay boundaries, context and dates before acceptance.</p>':''}
    <div class="source-review-columns"><div><label for="source-fact-kind-filter">Show findings</label><select id="source-fact-kind-filter"><option value="all">All attached findings</option><option value="death">Deaths</option><option value="response">Epoch responses</option><option value="link">Player links</option><option value="pending">Pending / unreviewed</option></select><div id="source-facts-list"></div><div id="source-fact-editor"></div></div>
    <aside><h3>Original source</h3><div id="source-review-original"></div></aside></div></section>`;
  if(scroll)$(target).scrollIntoView({behavior:'smooth',block:'start'});
  const filterKey=data.source_id+'|'+data.log_id, remembered=sourceReviewFilters.get(filterKey);
  if(remembered){$('source-fact-search').value=remembered.search;$('source-fact-kind-filter').value=remembered.kind;}
  function list(){
    const search=$('source-fact-search').value.trim().toLocaleLowerCase();
    const kind=$('source-fact-kind-filter').value;
    sourceReviewFilters.set(filterKey,{search:$('source-fact-search').value,kind});
    const visible=data.facts.filter(f=>(kind==='all'||kind==='pending'&&['needs_review','unreviewed'].includes(f.status)||f.kind===kind)&&(!search||[factStatement(f),f.subject,f.kind,f.basis,f.status].join(' ').toLocaleLowerCase().includes(search)));
    $('source-facts-list').innerHTML=`<p class="hint">Showing ${visible.length} of ${data.facts.length} attached claims / findings.</p>`+visible.map(f=>`<article class="attached-fact" data-fact="${esc(f.id)}"><div class="claim-title"><h3>${esc(factStatement(f))}</h3>${confidenceBadge(f.confidence)}</div><p class="hint">${esc(f.kind)} · ${esc(f.status.replaceAll('_',' '))}${f.revised?' · human reviewed':''}</p><p>${esc(f.basis)}</p>${f.kind==='death'?`<div class="death-context"><b>Victim: ${esc(f.subject)}</b>${['attacker','killer','location'].map(kind=>{const attached=data.facts.filter(a=>a.about===f.id&&a.kind===kind);return `<p>${kind==='killer'?'Final killer':kind==='attacker'?'Attackers':'Location'}: ${attached.length?attached.map(a=>`${esc(a.value)} (${esc(a.status.replaceAll('_',' '))}, ${esc(a.confidence)})`).join(', '):'Not recorded'}</p>`;}).join('')}</div>`:''}${f.kind==='response'?`<p class="hint">${esc(f.response?.date_label||'Date unresolved')} · ${esc(f.response?.date_confidence||'unknown')} date confidence · ${esc(f.response?.calibration||'unresolved')} dating</p>`:''}${f.citation?.quote?`<blockquote>${esc(f.citation.quote)}</blockquote><small>${esc(f.citation.file||'Source')} ${f.citation.start?'· lines '+esc(f.citation.start)+'–'+esc(f.citation.end||f.citation.start):''}</small>${f.citation.start?`<button class="text-button read-fact-passage" data-fact="${esc(f.id)}">Read cited passage</button>`:''}`:''}
      ${f.notes?`<p>${esc(f.notes)}</p>`:''}${scope==='archive'?`<label>Decision <select class="fact-decision" data-fact="${esc(f.id)}" aria-label="Decision for ${esc(factStatement(f))}"><option value="">Choose a decision…</option><option value="accept">Accept as written</option><option value="revise">Revise…</option><option value="reject">Reject</option><option value="pending">Keep pending</option></select></label>`:''}
      ${f.history?.length?`<details><summary>Revision history (${f.history.length})</summary>${f.history.map(h=>`<div class="fact-history"><b>${esc(h.action)} · ${esc(new Date(h.at).toLocaleString())}</b><p>Before: ${esc(h.before?factStatement(h.before)+' · '+h.before.status+' · '+h.before.confidence:'No earlier finding')}</p><p>After: ${esc(factStatement(h.after))} · ${esc(h.after.status)} · ${esc(h.after.confidence)}</p><p>${esc(h.after.basis)}</p>${h.after.citation?.quote?`<blockquote>${esc(h.after.citation.quote)}</blockquote>`:''}</div>`).join('')}</details>`:''}</article>`).join('');
    $('source-facts-list').querySelectorAll('.read-fact-passage').forEach(b=>b.onclick=()=>{const fact=data.facts.find(f=>f.id===b.dataset.fact);openOriginal(scope,{source_id:data.source_id,log_id:fact.log_id,fact_id:fact.id},'source-review-original',false).catch(e=>notice(e.message,true));});
    $('source-facts-list').querySelectorAll('.fact-decision').forEach(select=>select.onchange=async()=>{
      const action=select.value;select.value='';const fact=data.facts.find(f=>f.id===select.dataset.fact);
      try{if(action==='revise')editSourceFact(data,fact);else if(action)await job('save_facts',{decisions:[{source_id:data.source_id,log_id:fact.log_id,id:fact.id,version:fact.version,action}]});}catch(e){notice(e.message,true);}
    });
  }
  bind('source-fact-search','input',list);bind('source-fact-kind-filter','change',list);list();
  bind('source-scope','change',()=>openSourceReview(scope,{source_id:data.source_id,log_id:$('source-scope').value},target,false));
  bind('add-source-fact','click',()=>editSourceFact(data,null));
  bind('scan-responses','click',()=>job('scan_responses',{source_id:data.source_id,log_id:data.log_id}));
  if(data.log_id||!data.logs.length)await openOriginal(scope,{source_id:data.source_id,log_id:data.log_id},'source-review-original',false);
  else $('source-review-original').innerHTML='<p class="hint">Select a particular log to read its retained original beside these claims.</p>';
  chrome();
}
const responseSections=['Social interactions','Combat & death','Spells','Mounts & followers','Stats & equipment','World & NPCs','Calendar & features'];
function responseFields(meta,log){
  meta={date_start:log?.date_range_start||'',date_end:log?.date_range_end||'',date_label:log?.display_date||'',...meta};
  const select=(id,values,value)=>`<select id="${id}">${values.map(v=>`<option value="${esc(v)}" ${v===value?'selected':''}>${esc(v)}</option>`).join('')}</select>`;
  return `<h3>Epoch comparison details</h3><div class="inline-fields"><div><label for="response-category">Category</label>${select('response-category',responseSections,meta.category||responseSections[0])}</div><div><label for="response-label">Response name (e.g. Tell or Nod)</label><input id="response-label" value="${esc(meta.label||'')}"></div></div><div class="inline-fields"><div><label for="response-view">Point of view</label>${select('response-view',['Actor','Target','Room','Unspecified'],meta.viewpoint||'Unspecified')}</div><div><label for="response-detail">Condition / attack type (optional)</label><input id="response-detail" value="${esc(meta.detail||'')}"></div></div>
  <p class="hint">Use &lt;Actor&gt;, &lt;Target&gt; and &lt;Message&gt; consistently in the normalized output above. Keep the original names in the quotation below. Separate different perspectives.</p><label for="response-date-label">Gameplay date label</label><input id="response-date-label" value="${esc(meta.date_label)}"><div class="inline-fields"><div><label for="response-start">Earliest gameplay date</label><input id="response-start" type="date" value="${esc(meta.date_start)}"></div><div><label for="response-end">Latest gameplay date</label><input id="response-end" type="date" value="${esc(meta.date_end)}"></div></div><div class="inline-fields"><div><label for="response-date-confidence">Confidence in the date</label>${select('response-date-confidence',['unknown','low','medium','high'],meta.date_confidence||'unknown')}</div><div><label for="response-calibration">Date support</label>${select('response-calibration',['unresolved','independent','other-indicators'],meta.calibration||'unresolved')}</div></div><label for="response-date-basis">Evidence for the gameplay date</label><textarea id="response-date-basis" rows="2">${esc(meta.date_basis||'')}</textarea><label for="response-dependencies">Dating indicator IDs used (if any; comma separated)</label><input id="response-dependencies" value="${esc((meta.dependencies||[]).join(', '))}"><p class="hint">A webpage posting date alone does not date gameplay. Only independently dated observations within one epoch enter this export; other findings remain available for review.</p>`;
}
function readResponseFields(){return {category:$('response-category').value,label:$('response-label').value.trim(),viewpoint:$('response-view').value,detail:$('response-detail').value.trim(),date_start:$('response-start').value,date_end:$('response-end').value,date_label:$('response-date-label').value.trim(),date_confidence:$('response-date-confidence').value,calibration:$('response-calibration').value,date_basis:$('response-date-basis').value.trim(),dependencies:$('response-dependencies').value.split(',').map(s=>s.trim()).filter(Boolean)};}
function editSourceFact(data,fact){
  const adding=!fact;
  fact=fact||{kind:'other',subject:'',object:'',value:'',confidence:'unknown',basis:'',notes:'',about:'',citation:{}};
  const canonical=!!fact.record_key;
  $('source-fact-editor').innerHTML=`<form id="fact-form" class="fact-editor"><h3>${adding?'Add a missing finding':'Revise this claim'}</h3>
    ${canonical?'':`<label for="fact-kind">Finding type</label><select id="fact-kind">${['observer','attacker','killer','participant','location','date','response',...(adding?['death','trophy','link']:[]),'other'].map(kind=>`<option value="${kind}" ${fact.kind===kind?'selected':''}>${kind==='killer'?'Final killer (only if supported)':kind}</option>`).join('')}</select>`}
    <div class="inline-fields"><div><label for="fact-subject">${fact.kind==='trophy'?'Trophy owner':'Subject character (if applicable)'}</label><input id="fact-subject" value="${esc(fact.subject)}"></div><div><label for="fact-value">${fact.kind==='death'||fact.kind==='trophy'?'Observation count':'Finding / normalized response output'}</label><input id="fact-value" value="${esc(fact.value)}" ${fact.kind==='link'?'disabled data-keep-disabled="true"':''}></div></div>
    ${adding?`<label for="fact-object">Related character / player ID (trophy or player link)</label><input id="fact-object" list="fact-player-options" placeholder="Trophy victim, or existing player ID"><datalist id="fact-player-options">${data.players.map(p=>`<option value="${esc(p.player_id)}">${esc(p.known_by||p.main_handle)}</option>`).join('')}</datalist><small>For a new death or trophy, enter the observation count in Value. For a player link, use an existing player ID here.</small>`:fact.kind==='link'?`<label for="fact-object">Player</label><select id="fact-object">${data.players.map(p=>`<option value="${esc(p.player_id)}" ${fact.object===p.player_id?'selected':''}>${esc(p.known_by||p.main_handle)}</option>`).join('')}</select>`:fact.kind==='trophy'?`<label for="fact-object">Trophy victim</label><input id="fact-object" value="${esc(fact.object)}">`:''}
    ${canonical?'':`<label for="fact-about">Attach to a specific observation (optional)</label><select id="fact-about"><option value="">Source / log only</option>${data.facts.filter(f=>f.kind==='death'||f.kind==='trophy').map(f=>`<option value="${esc(f.id)}" ${fact.about===f.id?'selected':''}>${esc(factStatement(f))}</option>`).join('')}</select><small>Use this to attach each attacker or location to the correct death. Add one named character per role finding.</small>`}
    <div id="response-editor" ${fact.kind==='response'?'':'hidden'}>${responseFields(fact.response||{},data.log)}${data.log_id?'<label><input id="response-all-dates" type="checkbox"> Apply these dates to the other unrejected response findings in this log</label><small>This changes their dating fields only; pending findings remain pending.</small>':''}</div>
    <label for="fact-confidence">Confidence in this particular claim</label><select id="fact-confidence">${['high','medium','low','unknown'].map(level=>`<option value="${level}" ${fact.confidence===level?'selected':''}>${level==='unknown'?'Unrated':level}</option>`).join('')}</select>
    <label for="fact-basis">Evidence / reason</label><textarea id="fact-basis" rows="3" required>${esc(fact.basis)}</textarea>
    <label for="fact-quote">Exact supporting quotation</label><textarea id="fact-quote" rows="3">${esc(fact.citation?.quote||'')}</textarea>
    <div class="inline-fields triple"><div><label for="fact-file">Source file / passage label</label><input id="fact-file" value="${esc(fact.citation?.file||'')}"></div><div><label for="fact-line-start">First line (optional)</label><input id="fact-line-start" type="number" min="1" value="${esc(fact.citation?.start||'')}"></div><div><label for="fact-line-end">Last line (optional)</label><input id="fact-line-end" type="number" min="1" value="${esc(fact.citation?.end||'')}"></div></div>
    <label for="fact-url">Source URL (optional)</label><input id="fact-url" type="url" value="${esc(fact.citation?.url||data.log?.source_url||data.source.url||'')}">
    <label for="fact-notes">Private review notes (optional)</label><textarea id="fact-notes" rows="2">${esc(fact.notes)}</textarea>
    <div class="actions"><button type="submit">Save & accept ${adding?'finding':'revision'}</button><button id="fact-save-pending" type="button" class="secondary">Save pending</button><button id="fact-cancel" type="button" class="text-button">Cancel</button></div><p class="hint">The retained source and original extraction stay preserved. Attacker and final-killer claims are separate from confirming a death.</p></form>`;
  $('source-fact-editor').scrollIntoView({behavior:'smooth',block:'start'});
  async function save(status){
    const start=$('fact-line-start').value,end=$('fact-line-end').value;
    const changes={subject:$('fact-subject').value.trim(),value:$('fact-value').value.trim(),confidence:$('fact-confidence').value,
      basis:$('fact-basis').value.trim(),notes:$('fact-notes').value.trim(),citation:{quote:$('fact-quote').value,file:$('fact-file').value.trim(),start:start?Number(start):null,end:end?Number(end):null,url:$('fact-url').value.trim()}};
    if($('fact-object'))changes.object=$('fact-object').value.trim();
    if(!canonical){changes.kind=$('fact-kind').value;changes.about=$('fact-about').value;}
    if((changes.kind||fact.kind)==='response')changes.response=readResponseFields();
    const attached=data.facts.find(f=>f.id===changes.about);
    const decisions=[{id:adding?'':fact.id,version:fact.version,source_id:data.source_id,log_id:fact.log_id||attached?.log_id||data.log_id,action:adding?'add':'revise',status,changes}];
    if(changes.response&&$('response-all-dates')?.checked){
      const dates=Object.fromEntries(['date_start','date_end','date_label','date_confidence','date_basis','calibration','dependencies'].map(k=>[k,changes.response[k]]));
      for(const other of data.facts.filter(f=>f.kind==='response'&&f.id!==fact.id&&f.log_id===data.log_id&&f.status!=='rejected')){
        decisions.push({id:other.id,version:other.version,source_id:data.source_id,log_id:other.log_id,action:'revise',status:other.status,changes:{response:{...other.response,...dates},basis:other.basis}});
      }
    }
    await job('save_facts',{decisions});
  }
  bind('fact-kind','change',()=>{$('response-editor').hidden=$('fact-kind').value!=='response';});
  bind('fact-form','submit',async e=>{e.preventDefault();await save('accepted');});
  bind('fact-save-pending','click',()=>save('needs_review'));
  bind('fact-cancel','click',()=>{$('source-fact-editor').innerHTML='';});
  chrome();
}
async function openOriginal(scope,group,target,scroll=true){
  const source=await api('original?'+new URLSearchParams({scope,...(typeof group==='string'?{group}:group)}));
  if(!$(target))return;
  $(target).innerHTML=`<section class="original-reader"><h3>Original source: ${esc(source.group.title)}</h3>${sourceLink(source.url)}
    ${source.message?`<div class="callout">${esc(source.message)}</div>`:''}
    ${source.documents.length?`<label for="original-file">Retained original file</label><select id="original-file">${source.documents.length>1?'<option value="">Choose a retained source copy</option>':''}${source.documents.map(d=>`<option value="${esc(d.ref)}">${esc(d.path)}</option>`).join('')}</select><div class="upload-row"><input id="original-find" placeholder="Find a name or phrase in the original"><button id="original-search" class="secondary">Find in original</button></div><p class="hint" id="original-position"></p><div id="original-lines" class="source-lines"></div><div class="preview-pagination"><button id="original-prev" class="secondary">← Previous lines</button><button id="original-next" class="secondary">Next lines →</button></div>`:''}</section>`;
  if(scroll)$(target).scrollIntoView({behavior:'smooth',block:'start'});
  if(!source.documents.length)return;
  let currentSource=null, requestId=0;
  async function read(start,q){
    const ref=$('original-file')?.value;if(!ref)return;
    const serial=++requestId;
    const query=new URLSearchParams({ref,...(start?{start}:{}),...(q?{q}:{})});
    const data=await api('source-text?'+query);
    if(serial!==requestId||!$('original-lines'))return;
    currentSource=data;
    $('original-position').textContent=`${data.name}: lines ${data.start}–${data.end} of ${data.total}. `+
      (data.citation[0]&&!data.html_as_text?`Referenced lines ${data.citation[0]}–${data.citation[1]} are highlighted.`:'No exact line citation is available; use Find in original.')+
      (data.html_as_text?' Original HTML is displayed as readable text.':'')+(data.search?` ${data.matches} matching line(s).`:'');
    $('original-lines').innerHTML=data.lines.map(line=>`<div class="source-line ${line.highlight?'cited-line':''}"><span>${line.number}</span><code>${esc(line.text)||' '}</code></div>`).join('');
    $('original-prev').disabled=data.start<=1;$('original-prev').dataset.keepDisabled='true';
    $('original-next').disabled=data.end>=data.total;$('original-next').dataset.keepDisabled='true';
  }
  bind('original-file','change',()=>read());bind('original-search','click',()=>read(null,$('original-find').value));
  bind('original-prev','click',()=>read(Math.max(1,(currentSource?.start||1)-250)));
  bind('original-next','click',()=>read((currentSource?.end||0)+1));
  if(source.documents.length===1)await read();
}

function previewLabel(record) {
  const row=record.after;
  if(record.table==='player_character_links')return `${row.character_name} → ${row.main_handle || row.player_id}`;
  if(record.table==='historical_events')return row.event_type==='trophy'?`${row.character_name} → ${row.other_character_name}`:row.character_name;
  return row.name || row.character_name || row.known_by || row.main_handle || row.title || row.subject_id_or_name || row.claim || record.id;
}
function previewSummary(record) {
  const row=record.after;
  if(record.table==='historical_events')return row.event_type==='trophy'?`Trophy snapshot: at least ${row.count} kill(s), recorded ${row.display_date||'date uncertain'}`:`${row.count} death observation(s) · ${row.display_date||'date uncertain'}`;
  if(record.table==='player_character_links')return `${(row.status||'').replaceAll('_',' ')} · ${row.confidence||'unknown'} confidence`;
  if(record.table==='logs'||record.table==='historical_log_index')return row.display_date||'Date uncertain';
  if(record.table==='whois_queue')return 'Awaiting Whois collection';
  if(record.table==='evidence')return row.evidence_type?.replaceAll('_',' ')||'Source evidence';
  if(record.table==='log_appearances')return `${row.event_type||'Appearance'} in a historical log`;
  return record.action==='updated'?`Changed: ${record.changed_fields.map(f=>f.replaceAll('_',' ')).join(', ')}`:row.notes||'New archive record';
}
async function loadPreviewRecords() {
  const serial=++previewRequest;
  const query=new URLSearchParams({...previewFilters,limit:25});
  const result=await api('preview?'+query);
  if(serial!==previewRequest||current!==1||!$('preview-records'))return;
  $('preview-detail').innerHTML='';
  $('preview-records').innerHTML=!result.available?'<div class="callout">This older report lacks row details. Add the source to review again to refresh them; existing decisions are preserved.</div>':
    result.records.length?`<div class="table-wrap"><table><thead><tr><th>Record</th><th>Type / change</th><th>Details</th><th>Inspect</th></tr></thead><tbody>${result.records.map(r=>`<tr><td><b>${esc(previewLabel(r))}</b></td><td>${esc(previewNames[r.table]||r.table)}<small>${esc(r.action)}</small></td><td>${esc(previewSummary(r))}</td><td><button class="secondary preview-inspect" data-key="${esc(r.key)}" aria-label="Inspect ${esc(previewLabel(r))}">Inspect</button></td></tr>`).join('')}</tbody></table></div>`:'<div class="empty">No changes match these filters.</div>';
  $('preview-page').textContent=result.total?`${result.offset+1}–${Math.min(result.offset+result.limit,result.total)} of ${result.total} records`:'0 records';
  for(const [id,disabled] of [['preview-prev',result.offset===0],['preview-next',result.offset+result.limit>=result.total]]){
    $(id).dataset.keepDisabled='true';$(id).disabled=disabled||running();
  }
  document.querySelectorAll('.preview-inspect').forEach(button=>button.onclick=()=>inspectPreviewRecord(button.dataset.key).catch(e=>notice(e.message,true)));
}
function prettyRaw(value) {
  try{return JSON.stringify(JSON.parse(value),null,2);}catch{return value||'';}
}
async function inspectPreviewRecord(key) {
  const selection=++previewDetailRequest, list=previewRequest;
  const result=await api('preview-record?'+new URLSearchParams({key}));
  if(current!==1||!$('preview-detail')||selection!==previewDetailRequest||list!==previewRequest)return;
  const r=result.record,row=r.after,fields=r.changed_fields;
  const sources=new Map(result.sources.map(source=>[source.source_id,source]));
  $('preview-detail').innerHTML=`<section class="record-detail"><h3>${esc(previewLabel(r))}</h3><p class="hint">${esc(previewNames[r.table]||r.table)} · ${esc(r.action)}. ${r.before?'Compare the existing and proposed values below.':'This record does not yet exist in the archive.'}</p>
    <div class="table-wrap"><table><thead><tr><th>Field</th>${r.before?'<th>Currently in archive</th>':''}<th>${state.research_report?.applied?'Imported':'Proposed'} value</th></tr></thead><tbody>${fields.map(field=>`<tr><th>${esc(field.replaceAll('_',' '))}</th>${r.before?`<td class="field-value">${esc(r.before[field]||'—')}</td>`:''}<td class="field-value">${field==='raw_text'?`<pre>${esc(prettyRaw(row[field]))}</pre>`:esc(row[field]||'—')}</td></tr>`).join('')}</tbody></table></div>
    <h3>Supporting source evidence</h3>${result.sources.map(source=>`<div class="source-reference"><b>${esc(source.title||source.source_id)}</b>${source.input_file?`<small>Input file: ${esc(source.input_file)}</small>`:''}${source.url?`<small class="field-value">${esc(source.url)}</small>`:''}</div>`).join('')}
    ${result.evidence.map(e=>`<details class="source-excerpt"><summary>${esc(sources.get(e.source_id)?.title||'Source claim')} · ${esc(e.location_in_source||e.evidence_id)}</summary><p>${esc(e.claim)}</p><small>Confidence: ${esc(e.confidence||'unknown')} · ${esc(e.date_range_start||'')} ${esc(e.date_range_end||'')}</small><pre>${esc(prettyRaw(e.raw_text))}</pre></details>`).join('')||'<p class="hint">No separate claim is attached to this record. Its source metadata and full record are available here and in the detailed report.</p>'}
    <details class="source-excerpt"><summary>Full record and identifiers</summary><pre>${esc(JSON.stringify({before:r.before,after:row,evidence_ids:r.evidence_ids,source_ids:r.source_ids},null,2))}</pre></details></section>`;
}
async function renderReview() {
  if(!review)review=await api('review');
  if(current!==1)return;
  $('content').innerHTML=`<div class="panel"><h2>Review source groups</h2><p>Evidence is saved locally. Accepting a claim makes it eligible for the next build; publishing is a later step.</p><div id="archive-claims"></div>
    <label for="map-player">Map selected player groups to an existing player (optional)</label><select id="map-player"><option value="">Keep each proposed player</option>${review.players.map(p=>`<option value="${esc(p.player_id)}">${esc(p.known_by||p.main_handle)}</option>`).join('')}</select>
    <div class="toolbar"><button id="select-links" class="secondary">Select all pending groups</button><button id="clear-links" class="text-button">Clear selection</button><button id="accept-links">Accept selected</button><button id="reject-links" class="secondary">Reject selected</button><button id="pending-links" class="secondary">Keep pending</button></div></div>
    <div class="panel"><h2>Open any source and all its findings</h2><p class="hint">Includes sources without death, trophy or player-link groups. Deaths show their attached attackers, final killer and location, each with its own review status.</p><label for="review-source">Source</label><select id="review-source"><option value="">Choose a source…</option>${review.sources.map(s=>`<option value="${esc(s.id)}">${esc(s.title)}</option>`).join('')}</select><label for="review-log">Log / page</label><select id="review-log"><option value="">Whole source / page</option></select><button id="open-review-source" class="secondary">View source & all claims</button><p class="hint">${review.death_context_missing} death observations have no accepted attacker or final-killer finding. Missing details remain unknown; confirming a death does not establish its killer.</p><div id="retained-source-review"></div></div>
    <details class="advanced-records"><summary>Optional: supporting rows from the latest source load</summary><div id="technical-records"></div></details>`;
  await renderClaimGroups('archive','archive-claims');
  const old=activeSourceReview;
  if(old?.scope==='archive'&&!running())await openSourceReview('archive',old,$(old.target)?old.target:'retained-source-review',false);
  bind('review-source','change',()=>{const source=review.sources.find(s=>s.id===$('review-source').value);$('review-log').innerHTML='<option value="">Whole source / page</option>'+(source?.logs||[]).map(l=>`<option value="${esc(l.id)}">${esc(l.title)}</option>`).join('');if(source?.logs.length===1)$('review-log').value=source.logs[0].id;});
  bind('open-review-source','click',()=>openSourceReview('archive',{source_id:$('review-source').value,log_id:$('review-log').value},'retained-source-review'));
  bind('select-links','click',async()=>{review.groups.filter(g=>g.pending).forEach(g=>selectedClaimGroups.add(g.id));await renderClaimGroups('archive','archive-claims');chrome();});
  bind('clear-links','click',async()=>{selectedClaimGroups.clear();await renderClaimGroups('archive','archive-claims');chrome();});
  async function save(status){if(!selectedClaimGroups.size)throw Error('Select at least one source group.');await job('review_claims',{groups:[...selectedClaimGroups],status,player_id:$('map-player').value});selectedClaimGroups.clear();}
  bind('accept-links','click',()=>save('accepted'));bind('reject-links','click',()=>save('rejected'));bind('pending-links','click',()=>save('needs_review'));
  const details=$('technical-records').parentElement;details.ontoggle=()=>{if(details.open)technicalRecords().catch(e=>notice(e.message,true));};
}
async function renderWhois() {
  const commands=`mha setrepo ${state.root}\nmha queue load\nmha queue status\nmha queue delay 5\nmha queue batch 500`;
  $('content').innerHTML=`<div class="split"><div class="panel"><h2>Prepare the collection list</h2><p><b>${(state.counts?.pending||0).toLocaleString()}</b> names currently await collection. Rebuilding exports the unchecked names to the file your collector already reads.</p><div class="actions"><button id="build-queue">Build Whois queue</button><a class="link-button" href="${download('queue')}">Save queue file</a></div><p class="hint">Already checked names are skipped. Player links and source evidence stay in the archive.</p></div><div class="panel"><h2>Then switch to Mudlet</h2><p>With the <b>mha</b> collector enabled, paste these commands into Mudlet in order.</p><pre class="commands">${esc(commands)}</pre><button id="copy-queue" class="secondary">Copy Mudlet commands</button><small>Return here after collection and select the capture archive below.</small></div></div><div class="callout">Whois collection is optional. You can move straight to Build & export if you only want to publish historical evidence.</div>`;
  await renderCaptures();
  bind('build-queue','click',()=>job('queue'));bind('copy-queue','click',async()=>{await navigator.clipboard.writeText(commands);notice('Commands copied. Paste them into Mudlet, one line at a time.');});
}
async function renderCaptures() {
  $('content').insertAdjacentHTML('beforeend',`<div class="panel"><h2>Select the latest capture archive</h2>${state.profiles?.length?`<label for="mudlet-profile">Mudlet profiles found on this computer</label><div class="upload-row"><select id="mudlet-profile">${state.profiles.map(p=>`<option value="${esc(p.path)}">${esc(p.profile)} · saved ${esc(when(p.modified))}</option>`).join('')}</select><button id="use-profile">Use this profile</button></div>`:'<p class="hint">No standard Mudlet archive was found automatically. Choose its JSON file below.</p>'}<label for="whois-file">Or choose mume_whois_archive.json</label><div class="upload-row"><input type="file" id="whois-file" accept=".json"><button id="load-whois" class="secondary">Use selected file</button></div>${state.whois_path?`<p class="file-picked">Selected: ${esc(state.whois_path)}</p>`:''}<div class="actions"><button id="preview-whois">Preview new captures</button><button id="import-whois" class="secondary">Import captures</button></div><p class="hint">Preview shows new records, duplicate captures, not-found responses and possible corruption in the activity log. Import preserves the existing historical links.</p></div><div class="callout">If collection is still running, let the current batch finish before importing. Select the local profile to use its latest saved archive, or choose the file again after further collection.</div>`);
  if(state.whois_path&&$('mudlet-profile'))$('mudlet-profile').value=state.whois_path;
  bind('use-profile','click',async()=>{await api('select-profile',{path:$('mudlet-profile').value});state=await api('state');notice('Local Mudlet archive selected.');await render();});
  bind('load-whois','click',()=>upload('whois-file','whois'));
  bind('preview-whois','click',()=>job('preview_whois'));bind('import-whois','click',()=>job('import_whois'));
}
async function renderBuild() {
  $('content').innerHTML=`<div class="panel"><h2>Build the Deck update</h2><p>Build accepted claims and imported Whois into the website data. Pending and rejected claims remain in the research archive.</p><div class="actions"><button id="build">Rebuild Deck of Chars</button><button id="validate" class="secondary">Check archive only</button></div><p class="hint">Last build: ${esc(when(state.built_at))}. ${state.built_at&&!state.build_current?'The archive changed; rebuild before publishing.':''}</p><div id="build-changes"></div></div>
    <div class="panel"><h2>Export to the epoch comparison</h2><p>Export accepted response findings with normalized wording, separate points of view, original quotations and citations. Independent date bounds must fit one epoch; unclear dates are listed for follow-up.</p>
    <label for="epoch-base">Current comparison catalogue (optional)</label><div class="upload-row"><input id="epoch-base" type="file" accept=".json"><button id="load-epoch-base" class="secondary">Use this catalogue</button></div><p class="hint">${state.epoch_base?'Your supplied comparison catalogue will be preserved and extended.':'Uses the bundled comparison as its base.'} If you have edited the website comparison, download its current catalogue from WordPress → Tools → MUME Dating Indicators and load it here first.</p><button id="export-epochs">Export epoch comparison</button>
    ${state.epoch_export_current?`<p class="step-status">${state.epoch_export.exported} accepted response findings exported; ${state.epoch_export.deferred.length} accepted findings deferred for dating.</p><div class="actions"><a class="link-button" href="${download('epoch-page')}">Download comparison for review</a><a class="link-button" href="${download('epochs')}">Download comparison catalogue</a><a href="${download('epoch-report')}">Dating follow-up report</a><a href="${download('epoch-plugin')}">Comparison plugin update</a></div>${state.epoch_export.deferred.length?`<details><summary>Findings needing clearer dates</summary><ul>${state.epoch_export.deferred.map(d=>`<li><b>${esc(d.title)}</b>: ${esc(d.output)} — ${esc(d.reason)} <button class="text-button review-deferred" data-source="${esc(d.source_id)}" data-log="${esc(d.log_id)}">Review this source</button></li>`).join('')}</ul></details>`:''}<p class="hint">Open the downloaded HTML to review the table. To update the website, upload its JSON catalogue in WordPress → Tools → MUME Dating Indicators → Replace the catalogue. Updating the comparison renderer requires the latest comparison plugin.</p>`:'<p class="hint">Export again after changing evidence or review decisions.</p>'}</div>
    <details class="panel"><summary>Installation and manual data downloads</summary><p>For interface updates, upload the rebuilt Deck plugin through WordPress → Plugins → Add New → Upload Plugin.</p><div class="actions"><a class="link-button" href="${download('plugin')}">Download Deck plugin</a><a class="link-button" href="${download('data')}">Download Deck data</a></div></details>`;
  bind('build','click',()=>job('build'));bind('validate','click',()=>job('validate'));
  bind('export-epochs','click',()=>job('export_epochs'));
  bind('load-epoch-base','click',async()=>{const file=$('epoch-base').files[0];if(!file)throw Error('Choose the current comparison catalogue first.');await api('epoch-base',{data:await bytes64(file)});state=await api('state');await render();notice('Comparison catalogue selected. Its existing evidence will be retained.');});
  document.querySelectorAll('.review-deferred').forEach(b=>b.onclick=async()=>{activeSourceReview={scope:'archive',source_id:b.dataset.source,log_id:b.dataset.log,target:'retained-source-review'};await go(1);});
  if(state.built_at)await showBuildChanges();
}
async function showBuildChanges(offset=0,q=''){
  const data=await api('build-changes?'+new URLSearchParams({offset,q}));
  if(!$('build-changes'))return;
  $('build-changes').innerHTML=`<h3>Changes to characters</h3><p class="hint">Compared with: ${esc(data.baseline)}. Manual website uploads cannot be tracked here.</p><div class="triage-summary">${['added','updated','removed'].map(k=>`<div><b>${data.summary[k]||0}</b><span>${k}</span></div>`).join('')}</div><label for="build-search">Find changed characters</label><input id="build-search" value="${esc(q)}"><div class="table-wrap"><table><thead><tr><th>Character</th><th>Change</th><th>Fields</th></tr></thead><tbody>${data.records.map(r=>`<tr><td>${esc(r.name)}</td><td>${esc(r.action)}</td><td>${esc(r.details?.length?r.details.join('; '):r.fields.map(f=>f==='history'?'Historical evidence':f.replace(/([A-Z])/g,' $1').toLowerCase()).join(', '))}</td></tr>`).join('')}</tbody></table></div><div class="preview-pagination"><button id="build-prev" class="secondary" ${offset?'':'disabled data-keep-disabled="true"'}>Previous</button><span>${data.total} changed characters</span><button id="build-next" class="secondary" ${offset+40<data.total?'':'disabled data-keep-disabled="true"'}>More</button></div>`;
  bind('build-search','change',()=>showBuildChanges(0,$('build-search').value));
  bind('build-prev','click',()=>showBuildChanges(Math.max(0,offset-40),q));bind('build-next','click',()=>showBuildChanges(offset+40,q));
}
async function renderPublish() {
  $('content').innerHTML=`<div class="panel"><h2>Connect the website once</h2><p>In WordPress, open <b>Tools → Deck of Chars → Create publishing key</b>. Enter the website address and paste that key below. The workbench checks the connection and keeps the key private on this computer.</p><div class="inline-fields"><div><label for="site">Website address</label><input id="site" value="${esc(state.connection?.site||'https://breelegends.com')}"></div><div><label for="publishing-key">Deck publishing key</label><input id="publishing-key" type="password" autocomplete="off" placeholder="48-character key from WordPress"></div></div><div class="actions"><button id="connect">Verify & save connection</button><button id="test-connection" class="secondary">Test saved connection</button></div><p class="hint">Connection checks do not upload character data. Reconnect here if you revoke or replace the key in WordPress.</p></div><div class="panel"><h2>Publish the prepared data</h2><p>${state.build_current?'<span class="step-status">✓ The prepared Deck matches the current archive.</span>':'Build and check the update in the previous step before publishing.'}</p><p>Destination: <b>${esc(state.connection?.site||'Website not connected')}</b></p><div class="actions"><button id="publish">Publish Deck data</button><a class="link-button" href="${download('data')}">Download for manual upload</a></div><p class="hint">If the website blocks the connection, upload the downloaded JSON through Tools → Deck of Chars. Data publication updates characters and evidence; it does not install changed interface files.</p>${state.published_at?`<p class="step-status">Last successful publication: ${esc(when(state.published_at))}</p>`:''}</div>`;
  bind('connect','click',async()=>{const key=$('publishing-key').value;$('publishing-key').value='';await job('connect',{site:$('site').value,key});});
  bind('test-connection','click',()=>job('test_connection'));
  bind('publish','click',async()=>{if(confirm(`Publish the prepared Deck data to ${state.connection.site}? This updates the live character archive on the website.`))await job('publish',{confirm:true});});
}
async function render() {
  await [renderSource,renderReview,renderWhois,renderBuild,renderPublish][current]();
  chrome();
}
bind('back','click',()=>go(current-1));bind('next','click',()=>go(current+1));
bind('help-button','click',()=>$('guide').showModal());bind('close-guide','click',()=>$('guide').close());
bind('restore-button','click',async()=>{if(confirm('Restore the working archive tables from the last pre-operation backup? The current tables will be backed up first. Rebuild the queue and Deck afterwards.'))await job('restore',{confirm:true});});
(async()=>{try{state=await api('state');current=Math.max(0,Math.min(steps.length-1,state.step||0));await render();setInterval(async()=>{try{await refresh();}catch(error){notice('The local workbench is disconnected. Reopen its launcher to continue.',true);}},1500);}catch(error){notice(error.message,true);}})();
