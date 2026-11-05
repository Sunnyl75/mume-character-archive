'use strict';
const steps = [
  ['Add sources', 'Start with the evidence', 'Load an existing research package, or prepare a webpage or one gameplay log using the forms below.'],
  ['Preview & import', 'See what will change', 'Preview the selected source, check the proposed additions, then import it into your local archive.'],
  ['Review player links', 'Keep identities deliberate', 'Choose which player–character links to accept. Uncertain links can stay pending while you continue.'],
  ['Collect Whois', 'Fill in the character details', 'Build the existing queue, then collect it in Mudlet. You can skip collection and keep working with historical evidence.'],
  ['Import captures', 'Bring the Whois back', 'Choose the latest Mudlet archive. Preview new captures before importing them into the character archive.'],
  ['Build & preview', 'Inspect the actual Deck', 'Rebuild the Deck on your computer. Check player decks, colour Whois, log references and trophy snapshots before publishing.'],
  ['Publish', 'Put the reviewed Deck online', 'Connect to your WordPress plugin, then publish the prepared data when you are ready.']
];
const hash = new URLSearchParams(location.hash.slice(1));
let token = hash.get('token') || sessionStorage.getItem('deck-workbench-token') || '';
if (token) sessionStorage.setItem('deck-workbench-token', token);
history.replaceState(null, '', location.pathname);
let state = {}, current = 0, seenJob = '', sourceTab = 'package', candidates = [], selectedLinks = new Set(), review = null;
let sourceDraft = {title:'',url:'',date:'',start:'',end:'',observer:'',characters:'',groups:'',text:'',selected:[]};
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
    (report?`<div class="panel"><h2>Proposed archive changes</h2><div class="progress-list">${Object.entries(report.changes||{}).map(([name,count])=>`<div class="stat-change"><span>${esc(name.replaceAll('_',' '))}</span><b>${count}</b></div>`).join('')||'<p>No new records or changes. This source is already represented.</p>'}</div><p class="hint">${report.review?.length||0} review item(s). Player links will be reviewed in the next step.</p><details><summary>Other review items</summary><pre>${esc(JSON.stringify((report.review||[]).filter(r=>r.kind!=='player_link'),null,2))}</pre></details><div class="callout">Import saves the original input and adds collection candidates. It leaves new player links awaiting review.</div><div class="actions"><button id="apply-research">Import into my local archive</button><a class="link-button" href="${download('report')}">Save review report</a></div>${state.research_applied?'<p class="step-status">✓ A historical import has been applied in this workspace.</p>':''}</div>`:'');
  bind('preview-research','click',()=>job('preview_research'));
  bind('apply-research','click',()=>job('apply_research'));
}
async function renderLinks() {
  if(!review)review=await api('review');
  $('content').innerHTML=`<div class="panel"><h2>Player–character associations</h2><p>Tick the rows you have checked. Accept them, reject an incorrect assertion, or leave them pending. Existing accepted owners are shown so you can resolve a conflict deliberately.</p><label for="link-filter">Find a character or player</label><input class="review-filter" id="link-filter" placeholder="Search names…"><div class="toolbar"><button id="select-links" class="secondary">Select visible pending links</button><button id="clear-links" class="text-button">Clear selection</button></div><div id="link-table"></div><label for="map-player">Optional: map selected links to an existing player</label><select id="map-player"><option value="">Keep each proposed player</option>${review.players.map(p=>`<option value="${esc(p.player_id)}">${esc(p.known_by||p.main_handle)} · ${esc(p.player_id)}</option>`).join('')}</select><div class="toolbar"><button id="accept-links">Accept selected</button><button id="reject-links" class="secondary">Reject selected</button><button id="pending-links" class="secondary">Keep selected pending</button></div><p class="hint">Accepted links appear in player decks after rebuilding. A conflicting accepted owner will stop the change and explain which character needs attention.</p></div>`;
  let filter='';
  function update(){
    const links=review.links.filter(r=>`${r.character_name} ${r.main_handle}`.toLowerCase().includes(filter));
    $('link-table').innerHTML=links.length?`<div class="table-wrap"><table><thead><tr><th>Choose</th><th>Character</th><th>Proposed player</th><th>Review state</th><th>Evidence</th></tr></thead><tbody>${links.map(r=>`<tr><td><input class="link-check" type="checkbox" data-id="${esc(r.link_id)}" ${selectedLinks.has(r.link_id)?'checked':''} aria-label="Review ${esc(r.character_name)}"></td><td><b>${esc(r.character_name)}</b></td><td>${esc(r.main_handle)}${r.other_owners.length?`<small class="error-text">Accepted owner: ${esc(r.other_owners.join(', '))}</small>`:''}</td><td>${esc(r.status.replaceAll('_',' '))}<small>${esc(r.confidence)} confidence</small></td><td><details><summary>Source details</summary><small>${esc(r.source_location)}<br>${esc(r.notes)}</small><code>${esc(r.primary_evidence_id)}</code></details></td></tr>`).join('')}</tbody></table></div>`:'<div class="empty">No matching historical player links. You can continue to collection or build.</div>';
    $('link-table').querySelectorAll('.link-check').forEach(e=>e.onchange=()=>e.checked?selectedLinks.add(e.dataset.id):selectedLinks.delete(e.dataset.id));
  }
  update();
  bind('link-filter','input',()=>{filter=$('link-filter').value.toLowerCase();update();});
  bind('select-links','click',()=>{review.links.filter(r=>r.status==='needs_review'&&`${r.character_name} ${r.main_handle}`.toLowerCase().includes(filter)).forEach(r=>selectedLinks.add(r.link_id));update();});
  bind('clear-links','click',()=>{selectedLinks.clear();update();});
  async function save(status){if(!selectedLinks.size)throw Error('Select at least one player link.');const decisions=[...selectedLinks].map(link_id=>({link_id,status,player_id:$('map-player').value}));await job('save_review',{decisions});selectedLinks.clear();}
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
