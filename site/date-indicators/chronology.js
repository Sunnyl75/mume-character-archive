(function(global){
  'use strict';
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
  const sections=['Social interactions','Combat & death','Spells','Mounts & followers','Stats & equipment','World & NPCs','Calendar & features'];
  const oldSections={'Death and protection':'Combat & death','Mounts':'Mounts & followers','Text and spelling':'Combat & death','Combat':'Combat & death','Calendar and characters':'Calendar & features','World and entities':'World & NPCs','Lineage':'World & NPCs','Documented versions':'Calendar & features'};
  function columns(catalogue){
    return [{id:'diku',title:catalogue.comparison?.baseline?.title||'Diku Alfa',range:catalogue.comparison?.baseline?.date_label||'Jul 1991',source:catalogue.comparison?.baseline?.source||'https://dikumud.com/history/'},...catalogue.epochs.map(e=>{
      const last=e.end?new Date(new Date(e.end+'T00:00:00Z').getTime()-86400000).toISOString().slice(0,10):null;
      return {id:e.id,title:e.title,range:month(e.start)+'–'+(last?month(last):'present'),source:e.source};
    })];
  }
  function evidenceEpoch(catalogue,indicator,source){
    if(!source||dependsOn(catalogue,source,indicator.id))return null;
    let start=source.date_start,end=source.date_end,approx=false;
    if(!start||!end){
      // A broad single-year label may still identify an epoch; it does not
      // become a precise date or calibrate the shared introduction anchor.
      const years=[...new Set(String(source.date_label||'').match(/\b(?:19|20)\d{2}\b/g)||[])];
      if(years.length!==1||/before|after|alternative|disputed/i.test(source.date_label||''))return null;
      start=years[0]+'-01-01';end=years[0]+'-12-31';approx=true;
    }
    const epoch=catalogue.epochs.find(e=>start>=e.start&&(!e.end||end<e.end));
    return epoch?{epoch:epoch.id,start,end,approx:approx||source.calibration!=='independent'||String(source.date_confidence).startsWith('low')}:null;
  }
  function comparisonRows(catalogue){
    const sourceMap=new Map(catalogue.sources.map(s=>[s.id,s]));
    const result=[];
    for(const indicator of catalogue.indicators){
      const config=indicator.comparison||{section:oldSections[indicator.category]||indicator.category,label:indicator.title,output:indicator.patterns[0]||indicator.title};
      const variants=config.variants||(indicator.mode==='transition'?[{id:'old',group:'old',label:indicator.title+' — older',output:indicator.patterns[0]},{id:'new',group:'new',label:indicator.title+' — newer',output:indicator.patterns[1]}]:[{}]);
      for(const variant of variants){
        const row={id:indicator.id+(variant.id?'-'+variant.id:''),section:config.section,label:variant.label||config.label,output:variant.output||config.output||indicator.patterns[0]||indicator.title,diku:variant.diku||config.diku,cells:{}};
        const observed={};
        for(const a of indicator.attestations){
          if(variant.group&&a.group!==variant.group)continue;
          const source=sourceMap.get(a.source_id),placed=evidenceEpoch(catalogue,indicator,source);
          if(placed)(observed[placed.epoch]??=[]).push({...placed,source,attestation:a});
        }
        if(indicator.mode==='documented'){
          const e=catalogue.epochs.find(e=>e.id===indicator.epoch_id);
          if(e)observed[e.id]=[{start:indicator.documented_date,end:indicator.documented_date,approx:true,source:{url:indicator.source_url,date_label:month(indicator.documented_date)},documented:true}];
        }
        const indexes=catalogue.epochs.map((e,index)=>observed[e.id]?.length?index:-1).filter(index=>index>=0);
        const continuous=config.continuity?.confirmed===true&&config.continuity.scope==='feature';
        const first=indexes.length?Math.min(...indexes):-1;
        const presence=catalogue.epochs.map((e,index)=>!!observed[e.id]?.length||(continuous&&first>=0&&index>first&&(!config.continuity.until||e.start<config.continuity.until)));
        catalogue.epochs.forEach((epoch,index)=>{
          const candidates=observed[epoch.id];
          if(candidates?.length){
            candidates.sort((a,b)=>a.end.localeCompare(b.end));
            const firstEdge=index===0||!presence[index-1],lastEdge=index===presence.length-1||!presence[index+1];
            row.cells[epoch.id]={kind:'observed',first:firstEdge,last:lastEdge,observations:candidates};
          }else if(presence[index])row.cells[epoch.id]={kind:'continued'};
        });
        result.push(row);
      }
    }
    return result;
  }
  function calendarDay(value){return new Intl.DateTimeFormat('en-GB',{day:'numeric',month:'short',year:'numeric',timeZone:'UTC'}).format(new Date(value+'T00:00:00Z'));}
  function marker(entry,edge){
    let term,dateText;
    if(edge==='first'&&!entry.approx){term='by';dateText=month(entry.end);}
    else if(entry.approx){term='around';dateText=entry.start.slice(0,4)===entry.end.slice(0,4)&&entry.start.endsWith('01-01')&&entry.end.endsWith('12-31')?entry.start.slice(0,4):month(entry.end);}
    else if(entry.start===entry.end){term='at';dateText=calendarDay(entry.end);}
    else if(entry.start.slice(0,7)===entry.end.slice(0,7)){term='around';dateText=month(entry.end);}
    else{term='between';dateText=month(entry.start)+'–'+month(entry.end);}
    const date=entry.source.url?link(entry.source.url,dateText):esc(dateText)+'<sup title="Original online source URL has not been recorded">†</sup>';
    return `<span class="mdi-presence-date">(present ${term} ${date})</span>`;
  }
  function cell(row,column){
    if(column.id==='diku'){
      if(!row.diku)return '<td class="mdi-unknown mdi-diku">—</td>';
      return `<td class="mdi-observed mdi-diku">${row.diku.output!==row.output?`<code>${esc(row.diku.output)}</code>`:''}<span class="mdi-presence-date">(present at ${link(row.diku.url,month(row.diku.date))})</span></td>`;
    }
    const value=row.cells[column.id];if(!value)return '<td class="mdi-unknown">—</td>';
    if(value.kind==='continued')return '<td class="mdi-continued">Present<sup>*</sup></td>';
    const observations=value.observations;
    let text='Present';
    if(value.first)text=marker(observations[0],'first');
    if(value.last&&(!value.first||observations.at(-1).end!==observations[0].end))text=(value.first?text:'')+marker(observations.at(-1),'last');
    return `<td class="mdi-observed">${text}</td>`;
  }
  function init(root,catalogue){
    const host=root.querySelector('.mdi-app'),rows=comparisonRows(catalogue),cols=columns(catalogue);
    const groups=[...new Set([...(catalogue.comparison?.sections||sections),...rows.map(r=>r.section)])].filter(section=>rows.some(r=>r.section===section));
    let active=groups[0];
    host.innerHTML=`<header class="mdi-heading"><h1>MUME wording & date indicators</h1><small>Updated ${esc(catalogue.updated_at)}</small></header><p class="mdi-key">— no evidence · <sup>*</sup> continued feature · <sup>†</sup> source URL unavailable. Dates link to sources.</p><div class="mdi-layout"><nav class="mdi-tabs" role="tablist" aria-label="Output categories" aria-orientation="vertical">${groups.map((section,n)=>`<button type="button" role="tab" id="mdi-tab-${n}" aria-controls="mdi-panel" data-section="${esc(section)}">${esc(section)}</button>`).join('')}</nav><section id="mdi-panel" role="tabpanel" tabindex="0"></section></div>`;
    const panel=host.querySelector('#mdi-panel');
    function render(){
      const index=groups.indexOf(active);
      host.querySelectorAll('[role="tab"]').forEach(button=>{const selected=button.dataset.section===active;button.setAttribute('aria-selected',String(selected));button.tabIndex=selected?0:-1;});
      panel.setAttribute('aria-labelledby','mdi-tab-'+index);
      panel.innerHTML=`<div class="mdi-table-wrap" tabindex="0" aria-label="${esc(active)} comparison; scroll horizontally for later epochs"><table><thead><tr><th scope="col" class="mdi-output-heading">Output / indicator</th>${cols.map(c=>`<th scope="col" ${c.id==='diku'?'class="mdi-diku"':''}>${esc(c.title)}<small>${link(c.source,c.range)}</small></th>`).join('')}</tr></thead><tbody>${rows.filter(row=>row.section===active).map(row=>`<tr id="mdi-${esc(row.id)}"><th scope="row"><b>${esc(row.label)}</b><code>${esc(row.output)}</code></th>${cols.map(column=>cell(row,column)).join('')}</tr>`).join('')}</tbody></table></div>`;
    }
    host.querySelectorAll('[role="tab"]').forEach(button=>{
      button.addEventListener('click',()=>{active=button.dataset.section;render();});
      button.addEventListener('keydown',event=>{
        const current=groups.indexOf(active);let next;
        if(event.key==='ArrowDown'||event.key==='ArrowRight')next=(current+1)%groups.length;
        if(event.key==='ArrowUp'||event.key==='ArrowLeft')next=(current-1+groups.length)%groups.length;
        if(event.key==='Home')next=0;if(event.key==='End')next=groups.length-1;
        if(next!==undefined){event.preventDefault();active=groups[next];render();host.querySelector('#mdi-tab-'+next).focus();}
      });
    });
    render();
  }
  global.MumeDateIndicators={derive,usable,init,comparisonRows,columns,evidenceEpoch};
  if(typeof module!=='undefined')module.exports={derive,usable,comparisonRows,columns,evidenceEpoch};
  if(typeof document!=='undefined')document.querySelectorAll('.bree-mume-dates').forEach(root=>{
    try{const inline=root.querySelector('.mdi-data');init(root,inline?JSON.parse(inline.textContent):global.MUME_DATE_INDICATORS);}catch(error){root.innerHTML='<p>The dating catalogue could not be loaded.</p>';}
  });
})(typeof window!=='undefined'?window:globalThis);
