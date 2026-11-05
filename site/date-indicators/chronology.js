(function(global){
  'use strict';
  const categories=['Death and protection','Mounts','Text and spelling','Combat','Stats and equipment','Calendar and characters','World and entities','Lineage','Documented versions'];
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function month(value){
    if(!value)return 'Date unresolved';
    return new Intl.DateTimeFormat('en-GB',{month:'short',year:'numeric',timeZone:'UTC'}).format(new Date(value+'T00:00:00Z'));
  }
  function link(url,label){
    try{const value=new URL(url);if(!['http:','https:'].includes(value.protocol))return esc(label);return `<a href="${esc(value.href)}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>`;}catch{return esc(label);}
  }
  function dependsOn(catalogue,source,target,seen=new Set()){
    for(const id of source?.dependencies||[]){
      if(id===target)return true;
      if(seen.has(id))continue;seen.add(id);
      const marker=catalogue?.indicators.find(i=>i.id===id);
      if(marker?.attestations.some(a=>dependsOn(catalogue,catalogue.sources.find(s=>s.id===a.source_id),target,seen)))return true;
    }
    return false;
  }
  function usable(source,indicator,catalogue){
    return source&&['independent','other-indicators'].includes(source.calibration)&&source.date_end&&
      !dependsOn(catalogue,source,indicator.id)&&!String(source.date_confidence||'').toLowerCase().startsWith('low');
  }
  function derive(catalogue,indicator){
    const sources=new Map(catalogue.sources.map(s=>[s.id,s]));
    const seen=indicator.attestations.map(a=>({attestation:a,source:sources.get(a.source_id)}));
    const dated=seen.filter(a=>usable(a.source,indicator,catalogue));
    let date=null,from=null,label='Date unresolved',reason='No usable independent date boundary is established.',relation=indicator.soft_relation;
    if(indicator.mode==='documented'){
      date=indicator.documented_date;label=month(date);reason='Official version chronology; grouping uses the month-level version heading.';
    }else if(indicator.mode==='transition'){
      const old=dated.filter(a=>a.attestation.group==='old'),next=dated.filter(a=>a.attestation.group==='new');
      from=old.length?old.map(a=>a.source.date_end).sort().at(-1):null;
      date=next.length?next.map(a=>a.source.date_end).sort()[0]:null;
      if(date){label=from?`${month(from)} – ${month(date)}`:`By ${month(date)}`;reason='Provisional transition window from the last older form and earliest usable newer-form attestation. It is not an exact change date.';}
    }else if(['introduced_by','observed_by'].includes(indicator.mode)&&dated.length){
      date=dated.map(a=>a.source.date_end).sort()[0];label=`By ${month(date)}`;
      reason=indicator.mode==='introduced_by'?'Earliest usable dated appearance currently places introduction by this date. The sorting anchor can move when earlier evidence is added.':'Earliest usable dated occurrence of this wording or feature. This does not establish its introduction or removal date.';
    }
    if(indicator.mode==='lineage'){date=null;label='Lineage clue';reason='An inherited response needs a documented change before it can supply a chronological boundary.';}
    let epoch=catalogue.epochs.find(e=>date&&date>=e.start&&(!e.end||date<e.end));
    if(indicator.mode==='documented'&&indicator.epoch_id)epoch=catalogue.epochs.find(e=>e.id===indicator.epoch_id)||epoch;
    const sorting=date?(relation==='after'?`Soft after ${month(date)}`:relation==='before'?`Soft before ${month(date)}`:relation==='during'?`Provisional window: ${label}`:`Observed by ${month(date)}`):'No chronological cutoff assigned';
    return {date,from,label,reason,sorting,epoch:epoch?.id||'unresolved',usable:dated.length,evidence:seen};
  }
  function init(root,catalogue){
    const host=root.querySelector('.mdi-app');
    let filters={search:'',epoch:'all',category:'all',status:'all',order:'oldest'};
    const results=catalogue.indicators.map(indicator=>({indicator,date:derive(catalogue,indicator)}));
    host.innerHTML=`<header class="mdi-hero"><div class="mdi-kicker">BREE LEGENDS · RESEARCH CHRONOLOGY</div><h1>MUME dating indicators</h1><p class="mdi-lead">The changing clues we use to place player logs in history.</p><p>Exact phrases, game features and character observations, organised by the epoch they currently point to.</p><div class="mdi-edition"><span>${esc(catalogue.edition)}</span><span>Updated ${esc(catalogue.updated_at)}</span></div></header>
      <section class="mdi-explainer"><b>A working chronology</b><p><strong>“By Jan 1995”</strong> describes the evidence. <strong>“Soft after Jan 1995”</strong> is a provisional sorting preference for an undated log. Stronger independent evidence can place the log earlier and move the indicator with it. Epoch placement is a research aid, not proof of an introduction date.</p><details><summary>How dates and conflicts are handled</summary><p>Features can be introduced before their first surviving observation. Absence of a conditional feature is weak evidence. A log dated using this same indicator cannot independently move its anchor. Version headings follow ${link(catalogue.provenance.epoch_source,'the official MUME history')}; their feature lists do not establish exact deployment dates for every addition.</p><p>This catalogue records what the research currently supports, including unresolved removal dates and calendar hypotheses. Original quotations retain their spelling and punctuation.</p></details></section>
      <div class="mdi-counts"><div><b>${results.length}</b><span>indicators</span></div><div><b>${results.filter(r=>r.date.date).length}</b><span>placed in epochs</span></div><div><b>${results.filter(r=>!r.date.date).length}</b><span>awaiting a date</span></div><div><b>${catalogue.sources.length}</b><span>source records</span></div></div>
      <form class="mdi-filters" role="search"><label>Find an indicator<input name="search" type="search" placeholder="Shadows, Clip-clop, a typo…"></label><label>Epoch<select name="epoch"><option value="all">All epochs</option>${catalogue.epochs.map(e=>`<option value="${esc(e.id)}">${esc(e.title)}</option>`).join('')}<option value="unresolved">Date unresolved</option></select></label><label>Evidence family<select name="category"><option value="all">All families</option>${categories.map(c=>`<option>${esc(c)}</option>`).join('')}</select></label><label>Standing<select name="status"><option value="all">All indicators</option><option value="documented">Documented version markers</option><option value="provisional">Provisional research</option><option value="unresolved">Unresolved boundaries</option></select></label><label>Order<select name="order"><option value="oldest">Oldest first</option><option value="newest">Newest first</option></select></label><button type="reset">Reset</button></form>
      <div class="mdi-result-count" aria-live="polite"></div><main class="mdi-timeline"></main><footer class="mdi-foot"><b>A catalogue that can improve.</b><p>Each new dated observation can refine the shared anchor. The WordPress editor can add evidence or upload a revised catalogue; the page then recalculates its chronology from the stored data.</p><button class="mdi-download" type="button">Download current catalogue</button><p>Unresolved entries remain visible. Documented changes, dated appearances and proposed interpretations retain distinct labels.</p></footer>`;
    const form=host.querySelector('form'),timeline=host.querySelector('.mdi-timeline');
    function card({indicator:i,date:d}){
      const evidence=d.evidence.map(({attestation:a,source:s})=>`<li><div class="mdi-evidence-title">${link(s?.url,s?.title||a.source_id)}</div><p>${esc(s?.date_label||'Date unresolved')} · ${usable(s,i,catalogue)?'usable date evidence':'not used to move this anchor'}</p><blockquote>${esc(a.quote)}</blockquote><small>${esc(a.file||'Source passage')}${a.line_start?` · lines ${a.line_start}–${a.line_end||a.line_start}`:''}</small><details><summary>Date basis</summary><p>${esc(s?.date_basis||'No independent date basis recorded.')}</p>${s?.dependencies?.length?`<p>Depends on: ${esc(s.dependencies.join(', '))}</p>`:''}</details></li>`).join('');
      return `<article class="mdi-indicator" id="mdi-${esc(i.id)}"><div class="mdi-date"><b>${esc(d.label)}</b><span>${esc(d.sorting)}</span></div><div class="mdi-body"><div class="mdi-badges"><span>${esc(i.category)}</span><span class="mdi-status mdi-${esc(i.status)}">${esc(i.status==='documented'?'Documented version marker':i.status==='unresolved'?'Unresolved boundary':'Provisional research')}</span></div><h3><a href="#mdi-${esc(i.id)}">${esc(i.title)}</a></h3><p>${esc(i.summary)}</p>${i.patterns.length?`<div class="mdi-patterns">${i.patterns.map(p=>`<code>${esc(p)}</code>`).join('')}</div>`:''}<p class="mdi-note">${esc(i.notes)}</p><details><summary>Why this date? · ${i.attestations.length} source observation${i.attestations.length===1?'':'s'}</summary><p>${esc(d.reason)}</p>${i.source_url?`<p>${link(i.source_url,'Official source')}</p>`:''}${evidence?`<ol class="mdi-evidence">${evidence}</ol>`:'<p>No independently dated original passage is attached yet.</p>'}${i.history?.length?`<h4>Research updates</h4><ul>${i.history.map(h=>`<li>${esc(h.date)} — ${esc(h.note)}</li>`).join('')}</ul>`:''}</details></div></article>`;
    }
    function render(){
      const selected=results.filter(({indicator:i,date:d})=>(filters.epoch==='all'||d.epoch===filters.epoch)&&(filters.category==='all'||i.category===filters.category)&&(filters.status==='all'||i.status===filters.status)&&(!filters.search||[i.title,i.summary,i.notes,...i.patterns,...d.evidence.map(e=>e.source?.title||'')].join(' ').toLowerCase().includes(filters.search)));
      const epochs=[...catalogue.epochs];if(filters.order==='newest')epochs.reverse();epochs.push({id:'unresolved',title:'Date unresolved',start:null});
      timeline.innerHTML=epochs.map(epoch=>{
        const items=selected.filter(r=>r.date.epoch===epoch.id).sort((a,b)=>(a.date.date||'').localeCompare(b.date.date||'')*(filters.order==='newest'?-1:1)||a.indicator.title.localeCompare(b.indicator.title));
        return items.length?`<section class="mdi-epoch"><header><span>${epoch.start?month(epoch.start):'Awaiting independent anchors'}</span><h2>${esc(epoch.title)}</h2><small>${items.length} indicator${items.length===1?'':'s'}</small></header>${items.map(card).join('')}</section>`:'';
      }).join('')||'<p class="mdi-empty">No indicators match these filters. Reset the filters to return to the full chronology.</p>';
      host.querySelector('.mdi-result-count').textContent=`Showing ${selected.length} of ${results.length} indicators`;
    }
    form.addEventListener('submit',e=>e.preventDefault());
    const updateFilter=e=>{if(e.target.name){filters[e.target.name]=e.target.name==='search'?e.target.value.trim().toLowerCase():e.target.value;render();}};
    form.addEventListener('input',updateFilter);form.addEventListener('change',updateFilter);
    form.addEventListener('reset',()=>{filters={search:'',epoch:'all',category:'all',status:'all',order:'oldest'};render();});
    host.querySelector('.mdi-download').addEventListener('click',()=>{
      const href=URL.createObjectURL(new Blob([JSON.stringify(catalogue,null,2)+'\n'],{type:'application/json'}));
      const a=document.createElement('a');a.href=href;a.download='mume-date-indicators.json';a.click();setTimeout(()=>URL.revokeObjectURL(href),1000);
    });
    render();
  }
  global.MumeDateIndicators={derive,usable,init};
  if(typeof module!=='undefined')module.exports={derive,usable};
  if(typeof document!=='undefined')document.querySelectorAll('.bree-mume-dates').forEach(root=>{
    try{const inline=root.querySelector('.mdi-data');init(root,inline?JSON.parse(inline.textContent):global.MUME_DATE_INDICATORS);}catch(error){root.innerHTML='<p>The dating catalogue could not be loaded. Please check the uploaded data.</p>';}
  });
})(typeof window!=='undefined'?window:globalThis);
