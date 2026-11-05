'use strict';
const steps = [
  ['Add sources', 'Start with the evidence', 'Load an existing research package, or prepare a webpage or one gameplay log using the forms below.'],
  ['Preview & import', 'See what will change', 'Preview the selected source, check the proposed additions, then import it into your local archive.'],
  ['Review claims', 'Decide by source group', 'Accept supported groups together. Concentrate on uncertain claims and conflicting owners; the supporting archive rows do not need individual approval.'],
  ['Collect Whois', 'Fill in the character details', 'Build the existing queue, then collect it in Mudlet. You can skip collection and keep working with historical evidence.'],
  ['Import captures', 'Bring the Whois back', 'Choose the latest Mudlet archive. Preview new captures before importing them into the character archive.'],
  ['Build & preview', 'Inspect the actual Deck', 'Rebuild the Deck on your computer. Check player decks, colour Whois, log references and trophy snapshots before publishing.'],
  ['Publish', 'Put the reviewed Deck online', 'Connect to your WordPress plugin, then publish the prepared data when you are ready.']
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
  return [!!state.research_path,!!state.research_applied,!!state.links_reviewed,!!state.queue_ready,
    !!state.whois_imported,!!state.build_current,!!state.published_at][index];
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
  if ($('apply-research')) $('apply-research').disabled = running() || !state.research_preview;
  if ($('import-whois')) $('import-whois').disabled = running() || !state.whois_preview;
}
async function go(step) {
  current = Math.max(0, Math.min(6,step));
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
      if (current===2) review=null;
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
  <div class="actions"><button id="prepare-source">Prepare this source for import →</button></div>`;
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
    (sourceTab==='package'?`<div class="panel"><h2>Use research you already have</h2><p>Load the July historical research bundle, a player-link JSON, or another supported structured research file. Keep the ZIP intact; the workbench extracts it for you.</p><label for="research-file">Research file</label><div class="upload-row"><input id="research-file" type="file" accept=".json,.zip"><button id="load-research">Load research file</button></div><small>Accepts our historical corpus, same-player candidate files, website player lists and curated log indexes.</small></div>`:
    `<div class="panel"><h2>Prepare a source yourself</h2><p>Paste what the source says, enter any explicit player groups, and review the standard game lines the helper detects. You do not need to write JSON.</p>${sourceFields()}</div>`)+
    (state.research_path?`<div class="callout success"><b>A research input is selected.</b><div class="file-picked">${esc(state.research_path)}</div><button id="source-next" class="text-button">Continue to preview →</button></div>`:'');
  bind('tab-package','click',async()=>{sourceTab='package';await render();});
  bind('tab-text','click',async()=>{sourceTab='text';await render();});
  bind('load-research','click',()=>upload('research-file','research'));
  bind('source-next','click',()=>go(1));
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
  bind('prepare-source','click',async()=>{await api('prepare',sourceDraft);state=await api('state');notice('Source preserved and structured for import.');await go(1);});
  if(candidates.length)extractionTable();
}
async function renderImport() {
  const report=state.research_report;
  $('content').innerHTML=`<div class="panel"><h2>Preview the selected source</h2>${state.research_path?`<p class="file-picked">${esc(state.research_path)}</p>`:'<p>Select a research file or prepare a source in the previous step.</p>'}<div class="actions"><button id="preview-research">Preview proposed changes</button></div></div>`+
    (report?`<div class="panel"><h2>${report.applied?'Imported':'Proposed'} archive changes</h2><p class="hint">Choose a total to inspect its records, or search the detailed list below.</p><div class="progress-list">${Object.entries(report.changes||{}).map(([name,count])=>{const [table,action]=name.split(': ');return `<button class="stat-change preview-category" data-table="${esc(table)}" data-action="${esc(action)}"><span>${esc(previewNames[table]||table)} · ${esc(action)}</span><b>${count}</b></button>`;}).join('')||'<p>No new records or changes. This source is already represented.</p>'}</div><p class="hint">${report.review?.length||0} review item(s). Claim decisions are made in Step 3.</p><details><summary>Other review items</summary><pre>${esc(JSON.stringify((report.review||[]).filter(r=>r.kind!=='player_link'),null,2))}</pre></details></div>
    <div class="panel" id="preview-browser"><h2>Inspect individual records</h2><div class="inline-fields"><div><label for="preview-table">What to inspect</label><select id="preview-table"><option value="all">All record types</option>${Object.entries(previewNames).map(([value,label])=>`<option value="${value}">${label}</option>`).join('')}</select></div><div><label for="preview-action">Change</label><select id="preview-action"><option value="all">Additions and updates</option><option value="added">Additions only</option><option value="updated">Updates only</option></select></div></div><label for="preview-search">Search names, titles or values</label><input id="preview-search" placeholder="e.g. Rogrog, pDorien, a log title…"><div id="preview-records" aria-live="polite"></div><div class="preview-pagination"><button id="preview-prev" class="secondary">← Previous records</button><span id="preview-page"></span><button id="preview-next" class="secondary">More records →</button></div><div id="preview-detail" aria-live="polite"></div></div>
    <div class="panel"><div class="callout">Inspecting records does not import or change them. Import saves the input and collection candidates; new player links, deaths and trophy claims remain pending until approved in Step 3.</div><div class="actions"><button id="apply-research">Import into my local archive</button><a class="link-button" href="${download('report')}">Save full detailed report</a></div>${state.research_applied?'<p class="step-status">✓ A historical import has been applied in this workspace.</p>':''}</div>`:'');
  bind('preview-research','click',()=>job('preview_research'));
  bind('apply-research','click',()=>job('apply_research'));
  if (!report) return;
  // Keep the technical row browser available, but do not make storage rows the
  // user's review workload. Source claims are the primary review unit.
  const technical=document.createElement('details');technical.className='advanced-records';
  technical.innerHTML='<summary>Optional: inspect all supporting archive rows and JSON details</summary>';
  const browser=$('preview-browser'), totals=browser.previousElementSibling;
  totals.before(technical);technical.append(totals,browser);
  const claims=document.createElement('section');claims.className='panel';claims.id='source-claim-review';
  claims.innerHTML='<h2>Review source claims</h2><div id="preview-claims">Loading review groups…</div>';
  technical.before(claims);
  $('preview-table').value=previewFilters.table;
  $('preview-action').value=previewFilters.action;
  $('preview-search').value=previewFilters.q;
  bind('preview-table','change',async()=>{previewFilters.table=$('preview-table').value;previewFilters.offset=0;await loadPreviewRecords();});
  bind('preview-action','change',async()=>{previewFilters.action=$('preview-action').value;previewFilters.offset=0;await loadPreviewRecords();});
  let debounce;
  bind('preview-search','input',()=>{clearTimeout(debounce);previewFilters.q=$('preview-search').value;previewFilters.offset=0;debounce=setTimeout(()=>loadPreviewRecords().catch(e=>notice(e.message,true)),200);});
  bind('preview-prev','click',async()=>{previewFilters.offset=Math.max(0,previewFilters.offset-25);await loadPreviewRecords();});
  bind('preview-next','click',async()=>{previewFilters.offset+=25;await loadPreviewRecords();});
  document.querySelectorAll('.preview-category').forEach(button=>button.onclick=async()=>{
    previewFilters={table:button.dataset.table,action:button.dataset.action,q:'',offset:0};
    $('preview-table').value=previewFilters.table;$('preview-action').value=previewFilters.action;$('preview-search').value='';
    try {await loadPreviewRecords();$('preview-browser').scrollIntoView({behavior:'smooth',block:'start'});}catch(error){notice(error.message,true);}
  });
  await loadPreviewRecords();
  await renderClaimGroups('preview','preview-claims');
}

function confidenceBadge(rating){return `<span class="confidence confidence-${esc(rating)}">${esc(rating==='unknown'?'Unrated':rating[0].toUpperCase()+rating.slice(1))} confidence</span>`;}
async function renderClaimGroups(scope,target){
  const data=scope==='archive'?review:await api('claims?scope=preview');
  const groups=data.groups||[], summary=data.summary||{};
  let filter=groups.some(g=>g.needs_judgement&&g.pending)?'attention':'all', search='';
  $(target).innerHTML=`<div class="triage-summary"><div><b>${summary.needs_judgement||0}</b><span>source groups needing judgement</span></div><div><b>${summary.supported||0}</b><span>high-confidence groups</span></div><div><b>${summary.routine_records??'—'}</b><span>supporting rows · no separate approval</span></div></div>
  <p class="hint">High = explicit source-supported claims with a retained original and no detected conflict. Medium = a summary/transcription or interpretation. Low = weak attribution or conflict. Unrated = no usable assessment. These are evidence-based rules, not probabilities or a fresh AI reading.</p>
  ${scope==='archive'?`<div class="actions"><button id="accept-supported" ${!groups.some(g=>g.safe_to_accept&&g.pending)?'disabled data-keep-disabled="true"':''}>Accept all pending high-confidence claims</button></div>`:'<div class="callout">Import stores the evidence and collection work. New player links, death observations and trophies remain pending until approved in Step 3. You can leave uncertain groups pending indefinitely.</div>'}
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
      <div class="actions"><button class="secondary open-original" data-group="${esc(g.id)}">Read original source</button></div></article>`).join('')||`<div class="empty">${groups.length?'No source groups match this filter.':'No new claim groups are present. Run Preview proposed changes again after updating to generate the assessments.'}</div>`;
    $(target+'-groups').querySelectorAll('.claim-group-check').forEach(e=>e.onchange=()=>e.checked?selectedClaimGroups.add(e.dataset.id):selectedClaimGroups.delete(e.dataset.id));
    $(target+'-groups').querySelectorAll('.open-original').forEach(b=>b.onclick=()=>openOriginal(scope,b.dataset.group,target+'-original').catch(e=>notice(e.message,true)));
  }
  document.querySelectorAll(`#${target} .claim-tabs button`).forEach(b=>b.onclick=()=>{filter=b.dataset.filter;update();});
  bind(target+'-search','input',()=>{search=$(target+'-search').value.trim().toLocaleLowerCase();update();});
  update();
  bind('accept-supported','click',()=>job('review_supported'));
}
function sourceLink(value){try{const u=new URL(value);return ['http:','https:'].includes(u.protocol)?`<a href="${esc(u.href)}" target="_blank" rel="noopener noreferrer">Open archived / original webpage ↗</a>`:'';}catch{return '';}}
async function openOriginal(scope,group,target){
  const source=await api('original?'+new URLSearchParams({scope,group}));
  if(!$(target))return;
  $(target).innerHTML=`<section class="original-reader"><h3>Original source: ${esc(source.group.title)}</h3>${sourceLink(source.url)}
    ${source.message?`<div class="callout">${esc(source.message)}</div>`:''}
    ${source.documents.length?`<label for="original-file">Retained original file</label><select id="original-file">${source.documents.length>1?'<option value="">Choose a retained source copy</option>':''}${source.documents.map(d=>`<option value="${esc(d.ref)}">${esc(d.path)}</option>`).join('')}</select><div class="upload-row"><input id="original-find" placeholder="Find a name or phrase in the original"><button id="original-search" class="secondary">Find in original</button></div><p class="hint" id="original-position"></p><div id="original-lines" class="source-lines"></div><div class="preview-pagination"><button id="original-prev" class="secondary">← Previous lines</button><button id="original-next" class="secondary">Next lines →</button></div>`:''}</section>`;
  $(target).scrollIntoView({behavior:'smooth',block:'start'});
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
  $('preview-records').innerHTML=!result.available?'<div class="callout">This preview was created by the earlier version. Click <b>Preview proposed changes</b> again to load the record details.</div>':
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
async function renderLinks() {
  if(!review)review=await api('review');
  $('content').innerHTML=`<div class="panel"><h2>Review source groups</h2><p>Accept the clear cases in a batch. For uncertain cases, read the original once and decide for the related group. Supporting character, source and queue rows do not require separate decisions.</p><div id="archive-claims"></div>
    <label for="map-player">Optional: map selected player groups to an existing player</label><select id="map-player"><option value="">Keep each proposed player</option>${review.players.map(p=>`<option value="${esc(p.player_id)}">${esc(p.known_by||p.main_handle)} · ${esc(p.player_id)}</option>`).join('')}</select>
    <div class="toolbar"><button id="select-links" class="secondary">Select all pending groups</button><button id="clear-links" class="text-button">Clear selection</button></div><div class="toolbar"><button id="accept-links">Accept selected groups</button><button id="reject-links" class="secondary">Reject selected groups</button><button id="pending-links" class="secondary">Keep selected pending</button></div><p class="hint">Rejected and pending player/death/trophy claims stay out of the public Deck. Their original evidence remains preserved. Existing accepted owners are never silently replaced.</p></div>`;
  await renderClaimGroups('archive','archive-claims');
  bind('select-links','click',async()=>{review.groups.filter(g=>g.pending).forEach(g=>selectedClaimGroups.add(g.id));await renderClaimGroups('archive','archive-claims');chrome();});
  bind('clear-links','click',async()=>{selectedClaimGroups.clear();await renderClaimGroups('archive','archive-claims');chrome();});
  async function save(status){if(!selectedClaimGroups.size)throw Error('Select at least one source group.');await job('review_claims',{groups:[...selectedClaimGroups],status,player_id:$('map-player').value});selectedClaimGroups.clear();}
  bind('accept-links','click',()=>save('accepted'));bind('reject-links','click',()=>save('rejected'));bind('pending-links','click',()=>save('needs_review'));
}
async function renderQueue() {
  const commands=`mha setrepo ${state.root}\nmha queue load\nmha queue status\nmha queue delay 5\nmha queue batch 500`;
  $('content').innerHTML=`<div class="split"><div class="panel"><h2>Prepare the collection list</h2><p><b>${(state.counts?.pending||0).toLocaleString()}</b> names currently await collection. Rebuilding exports the unchecked names to the file your collector already reads.</p><div class="actions"><button id="build-queue">Build Whois queue</button><a class="link-button" href="${download('queue')}">Save queue file</a></div><p class="hint">Already checked names are skipped. Player links and source evidence stay in the archive.</p></div><div class="panel"><h2>Then switch to Mudlet</h2><p>With the <b>mha</b> collector enabled, paste these commands into Mudlet in order.</p><pre class="commands">${esc(commands)}</pre><button id="copy-queue" class="secondary">Copy Mudlet commands</button><small>Return here after collection. The next step reads the captures from your Mudlet profile.</small></div></div><div class="callout">Whois collection is optional. You can move straight to Build & preview if you only want to publish historical evidence.</div>`;
  bind('build-queue','click',()=>job('queue'));bind('copy-queue','click',async()=>{await navigator.clipboard.writeText(commands);notice('Commands copied. Paste them into Mudlet, one line at a time.');});
}
async function renderWhois() {
  $('content').innerHTML=`<div class="panel"><h2>Select the latest capture archive</h2>${state.profiles?.length?`<label for="mudlet-profile">Mudlet profiles found on this computer</label><div class="upload-row"><select id="mudlet-profile">${state.profiles.map(p=>`<option value="${esc(p.path)}">${esc(p.profile)} · saved ${esc(when(p.modified))}</option>`).join('')}</select><button id="use-profile">Use this profile</button></div>`:'<p class="hint">No standard Mudlet archive was found automatically. Choose its JSON file below.</p>'}<label for="whois-file">Or choose mume_whois_archive.json</label><div class="upload-row"><input type="file" id="whois-file" accept=".json"><button id="load-whois" class="secondary">Use selected file</button></div>${state.whois_path?`<p class="file-picked">Selected: ${esc(state.whois_path)}</p>`:''}<div class="actions"><button id="preview-whois">Preview new captures</button><button id="import-whois" class="secondary">Import captures</button></div><p class="hint">Preview shows new records, duplicate captures, not-found responses and possible corruption in the activity log. Import preserves the existing historical links.</p></div><div class="callout">If collection is still running, let the current batch finish before importing. Select the local profile to use its latest saved archive, or choose the file again after further collection.</div>`;
  if(state.whois_path&&$('mudlet-profile'))$('mudlet-profile').value=state.whois_path;
  bind('use-profile','click',async()=>{await api('select-profile',{path:$('mudlet-profile').value});state=await api('state');notice('Local Mudlet archive selected.');await render();});
  bind('load-whois','click',()=>upload('whois-file','whois'));
  bind('preview-whois','click',()=>job('preview_whois'));bind('import-whois','click',()=>job('import_whois'));
}
async function renderBuild() {
  $('content').innerHTML=`<div class="panel"><h2>Build the local Deck</h2><p>The workbench validates the archive, refreshes derived character and player data, adds historical views, preserves colour Whois and creates the website packages.</p><div class="actions"><button id="build">Rebuild Deck of Chars</button><button id="validate" class="secondary">Check archive only</button></div><p class="hint">This can take a little while. Progress appears in the activity log; the interface stays responsive.</p></div><div class="panel"><h2>Preview and install the interface</h2><p>Last successful build: <b>${esc(when(state.built_at))}</b>. ${state.built_at&&!state.build_current?'<span class="error-text">The archive changed afterwards; rebuild before publishing.</span>':''}</p><div class="actions"><a class="link-button" target="_blank" rel="noopener" href="/open-preview?token=${encodeURIComponent(token)}">Open local Deck preview ↗</a><a class="link-button" href="${download('plugin')}">Download WordPress plugin</a><a class="link-button" href="${download('data')}">Download Deck data</a></div><div class="callout"><b>First use of the new Logs and Trophies views:</b> install the rebuilt plugin through WordPress → Plugins → Add New → Upload Plugin. Later data-only publications use the Publish step. Future interface or portrait changes also require a new plugin upload.</div></div>`;
  bind('build','click',()=>job('build'));bind('validate','click',()=>job('validate'));
}
async function renderPublish() {
  $('content').innerHTML=`<div class="panel"><h2>Connect the website once</h2><p>In WordPress, open <b>Tools → Deck of Chars → Create publishing key</b>. Enter the website address and paste that key below. The workbench checks the connection and keeps the key private on this computer.</p><div class="inline-fields"><div><label for="site">Website address</label><input id="site" value="${esc(state.connection?.site||'https://breelegends.com')}"></div><div><label for="publishing-key">Deck publishing key</label><input id="publishing-key" type="password" autocomplete="off" placeholder="48-character key from WordPress"></div></div><div class="actions"><button id="connect">Verify & save connection</button><button id="test-connection" class="secondary">Test saved connection</button></div><p class="hint">Connection checks do not upload character data. Reconnect here if you revoke or replace the key in WordPress.</p></div><div class="panel"><h2>Publish the prepared data</h2><p>${state.build_current?'<span class="step-status">✓ The prepared Deck matches the current archive.</span>':'Rebuild and preview the Deck in the previous step before publishing.'}</p><p>Destination: <b>${esc(state.connection?.site||'Website not connected')}</b></p><div class="actions"><button id="publish">Publish Deck data</button><a class="link-button" href="${download('data')}">Download for manual upload</a></div><p class="hint">If the website blocks the connection, upload the downloaded JSON through Tools → Deck of Chars. Data publication updates characters and evidence; it does not install changed interface files.</p>${state.published_at?`<p class="step-status">Last successful publication: ${esc(when(state.published_at))}</p>`:''}</div>`;
  bind('connect','click',async()=>{const key=$('publishing-key').value;$('publishing-key').value='';await job('connect',{site:$('site').value,key});});
  bind('test-connection','click',()=>job('test_connection'));
  bind('publish','click',async()=>{if(confirm(`Publish the prepared Deck data to ${state.connection.site}? This updates the live character archive on the website.`))await job('publish',{confirm:true});});
}
async function render() {
  await [renderSource,renderImport,renderLinks,renderQueue,renderWhois,renderBuild,renderPublish][current]();
  chrome();
}
bind('back','click',()=>go(current-1));bind('next','click',()=>go(current+1));
bind('help-button','click',()=>$('guide').showModal());bind('close-guide','click',()=>$('guide').close());
bind('restore-button','click',async()=>{if(confirm('Restore the working archive tables from the last pre-operation backup? The current tables will be backed up first. Rebuild the queue and Deck afterwards.'))await job('restore',{confirm:true});});
(async()=>{try{state=await api('state');current=state.step||0;await render();setInterval(async()=>{try{await refresh();}catch(error){notice('The local workbench is disconnected. Reopen its launcher to continue.',true);}},1500);}catch(error){notice(error.message,true);}})();
