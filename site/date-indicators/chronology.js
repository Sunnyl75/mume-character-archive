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
  const rowNames={
    'tell-incoming':['Tell','Received'],'tell-outgoing':['Tell','Sent'],'tell-target-missing':['Tell','Unavailable'],
    'say-observer':['Say','Observer'],'say-self':['Say','Speaker'],'death-victim':['Death','Victim'],'death-room':['Death','Room'],
    'first-kill-punctuation':['First kill',''],'spell-diku-fireball':['Fireball — NPC',''],
    'spell-fireball-words':['Fireball',''],'spell-lightning-words':['Lightning bolt',''],
    'spell-blindness-words':['Blindness',''],'spell-call-words':['Call lightning','']
  };
  // Display recorded excerpts; normalize variable actors/messages only for
  // comparing wording. Punctuation and spelling remain part of the signature.
  function sample(indicator,quote){
    if(!quote)return null;
    let output=String(quote).trim().replace(/^[^']*>\s*/,'');
    const id=indicator.id;
    if(id==='elrond-diku-line'){
      const found=output.match(/^[^']+ screams '(PROTECT THE INNOCENT![^']*)'/);
      if(!found)return null;output=found[1];
    }
    if(['tell-incoming','say-observer','narrate'].includes(id)){
      output=output.replace(/\s+<[-=]{2,}[\s\S]*$/,'');
      if(!output.endsWith("'"))return null; // Incomplete speech is not a wording change.
    }
    if(id==='tell-incoming'&&(!/^[\p{L}\w-]+ tells you '/u.test(output)))return null;
    if(id==='armour-percent'){const found=output.match(/Armour:\s*\d+%/);if(!found)return null;output=found[0];}
    if(id==='fragment-damage'){const found=output.match(/\breduce[sd]?\b[^.]*small fragments\.?/);if(!found)return null;output=found[0];}
    if(id==='shatter-damage'){const found=output.match(/\bshatters? it\.?/);if(!found)return null;output=found[0];}
    if(id==='literal-spell-names'||/^spell-.*-words$/.test(id)){
      const found=output.match(/^(.+? utters the words, '[^']*')/);if(!found)return null;output=found[1];
      if(id==='literal-spell-names'&&!/'(?:harm|lightning bolt)'/.test(output))return null;
    }
    let signature=output;
    if(['tell-incoming','say-observer','narrate'].includes(id))signature=signature.replace(/^.*? (tells you|says|narrates) '[\s\S]*'$/, "<ACTOR> $1 '…'");
    if(id==='guardian-shadows')signature=signature.replace(/(above the corpse of ).*\.$/,'$1<TARGET>.');
    if(id==='horse-clip-clop')signature=output.match(/^Clip-clop\.*(?=[A-Z*]|the |$)/)?.[0]||'Clip-clop...';
    if(id==='follower-coudln')signature=signature.replace(/^ACK!! .*?( coudln't follow you)/,'ACK!! <ACTOR>$1');
    if(id==='raisen-hand')signature=signature.replace(/(raisen hand of ).*?(\. You panic!)/,'$1<ACTOR>$2');
    if(id==='armour-percent')signature=signature.replace(/\d+/g,'<N>');
    if(id==='istar-clock')signature=signature.replace(/(Council is ).*\.$/,'$1<ACTOR>.');
    if(id==='death-room')signature=signature.replace(/^.*?( is dead!)/,'<TARGET>$1');
    if(id==='literal-spell-names')signature=signature.replace(/^.*? utters the words, '[^']*'/,"<ACTOR> utters the words, '<SPELL>'");
    if(/^spell-.*-words$/.test(id))signature=signature.replace(/^.*?( utters the words, )/,'<ACTOR>$1');
    return {output,signature};
  }
  function evidenceRows(catalogue){
    const result=[],grouped=new Map(),cols=columns(catalogue);
    const indicators=new Map(catalogue.indicators.map(i=>[i.id,i]));
    for(const variant of comparisonRows(catalogue)){
      const indicator=indicators.get(variant.id)||catalogue.indicators.find(i=>variant.id.startsWith(i.id+'-'));
      const config=indicator.comparison||{},defaults=rowNames[indicator.id]||[config.label||indicator.title,''];
      const label=config.row||defaults[0],context=config.context??defaults[1],key=variant.section+'|'+label;
      let row=grouped.get(key);
      if(!row){row={id:indicator.id,section:variant.section,label,cells:{}};grouped.set(key,row);result.push(row);}
      function add(column,item){(row.cells[column]??=[]).push({...item,lane:indicator.id,context});}
      if(variant.diku){
        const output=variant.diku.output;
        // Source-code templates already substitute variable actors/messages.
        const signature=indicator.id==='literal-spell-names'?"<ACTOR> utters the words, '<SPELL>'":output;
        add('diku',{kind:'output',output,signature,entries:[{source:{id:'diku:'+variant.diku.url,title:'Diku Alfa source',url:variant.diku.url,date_label:month(variant.diku.date)},baseline:true}]});
      }
      for(const [epoch,value] of Object.entries(variant.cells)){
        if(value.kind==='continued'){
          add(epoch,{kind:'feature',output:label+' (continued)',signature:null,entries:[{continued:true,basis:config.continuity.basis||'Confirmed feature continuation. No wording sample is attached for this epoch.'}]});
          continue;
        }
        const buckets=new Map();
        for(const entry of value.observations){
          const text=entry.documented?{output:config.output||indicator.title,signature:config.output||indicator.title}:sample(indicator,entry.attestation.quote);
          if(!text)continue;
          let bucket=buckets.get(text.signature);
          if(!bucket){bucket={kind:entry.documented?'feature':'output',...text,entries:[]};buckets.set(text.signature,bucket);}
          bucket.entries.push(entry);
        }
        for(const bucket of buckets.values()){
          // The footnote must support the actual displayed quotation. Other
          // examples of the same form remain in the retained catalogue.
          bucket.entries=[bucket.entries[0]];
          add(epoch,bucket);
        }
      }
    }
    for(const row of result){
      // Order each epoch's own samples before assigning shades. Configuration
      // order (including old/new variant lists) must not determine chronology.
      // Bounds order overlapping/approximate dates without inventing a cutoff;
      // the original date ranges remain visible in the source footnotes.
      for(const items of Object.values(row.cells))items.sort((a,b)=>{
        const first=item=>item.entries[0];
        const end=item=>first(item).end||first(item).source?.date_end||'';
        const start=item=>first(item).start||first(item).source?.date_start||'';
        return end(a).localeCompare(end(b))||start(a).localeCompare(start(b));
      });
      const lanes=new Map();
      for(const col of cols)for(const item of row.cells[col.id]||[]){
        if(item.signature===null)continue;
        let forms=lanes.get(item.lane);if(!forms){forms=new Map();lanes.set(item.lane,forms);}
        if(!forms.has(item.signature))forms.set(item.signature,forms.size);
        item.shade=forms.get(item.signature)%6;
      }
    }
    return result;
  }
  function init(root,catalogue){
    const host=root.querySelector('.mdi-app'),rows=evidenceRows(catalogue),cols=columns(catalogue);
    const groups=[...new Set([...(catalogue.comparison?.sections||sections),...rows.map(r=>r.section)])].filter(section=>rows.some(r=>r.section===section));
    const prefix='mdi-'+(document.querySelectorAll('.bree-mume-dates').length>1?[...document.querySelectorAll('.bree-mume-dates')].indexOf(root):'page');
    let active=groups[0];
    host.innerHTML=`<header class="mdi-heading"><h1>MUME wording & date indicators</h1><small>Updated ${esc(catalogue.updated_at)}</small></header><p class="mdi-key">— no evidence · Matching wording keeps its shade; colours only draw attention to changes.</p><div class="mdi-layout"><nav class="mdi-tabs" role="tablist" aria-label="Output categories" aria-orientation="vertical">${groups.map((section,n)=>`<button type="button" role="tab" id="${prefix}-tab-${n}" aria-controls="${prefix}-panel" data-section="${esc(section)}">${esc(section)}</button>`).join('')}</nav><section id="${prefix}-panel" class="mdi-panel" role="tabpanel" tabindex="0"></section></div>`;
    const panel=host.querySelector('.mdi-panel');
    function render(){
      const index=groups.indexOf(active),notes=[],noteMap=new Map();
      host.querySelectorAll('[role="tab"]').forEach(button=>{const selected=button.dataset.section===active;button.setAttribute('aria-selected',String(selected));button.tabIndex=selected?0:-1;});
      panel.setAttribute('aria-labelledby',prefix+'-tab-'+index);
      function reference(entry){
        const key=entry.continued?'continuity:'+entry.basis:entry.source.id||[entry.source.url,entry.source.date_label,entry.documented?'documented':''].join('|');
        if(!noteMap.has(key)){noteMap.set(key,notes.length+1);notes.push(entry);}
        const n=noteMap.get(key),id=prefix+'-'+index+'-note-'+n;
        return `<a class="mdi-note-ref" href="#${id}" aria-label="Source note ${n}">${n}</a>`;
      }
      function cell(row,column){
        const items=row.cells[column.id];
        if(!items?.length)return `<td class="mdi-unknown${column.id==='diku'?' mdi-diku':''}">—</td>`;
        return `<td class="${[column.id==='diku'?'mdi-diku':'',items.length>1?'mdi-multiple':''].filter(Boolean).join(' ')}">${items.map(item=>`<div class="mdi-sample${item.shade!==undefined?' mdi-shade-'+item.shade:''}">${item.context?`<small class="mdi-context">${esc(item.context)}</small>`:''}<code>${esc(item.output)}</code><sup>${item.entries.map(reference).join(', ')}</sup></div>`).join('')}</td>`;
      }
      const table=`<div class="mdi-table-wrap" tabindex="0" aria-label="${esc(active)} comparison; scroll horizontally for later epochs"><table><thead><tr><th scope="col">Output / indicator</th>${cols.map(c=>`<th scope="col" ${c.id==='diku'?'class="mdi-diku"':''}>${esc(c.title)}<small>${esc(c.range)}</small></th>`).join('')}</tr></thead><tbody>${rows.filter(row=>row.section===active).map(row=>`<tr id="${prefix}-${esc(row.id)}"><th scope="row">${esc(row.label)}</th>${cols.map(column=>cell(row,column)).join('')}</tr>`).join('')}</tbody></table></div>`;
      function note(entry){
        if(entry.continued)return esc(entry.basis)+' Feature presence is continued; exact wording is unverified.';
        const s=entry.source,date=s.date_label||(entry.start===entry.end?calendarDay(entry.end):month(entry.start)+'–'+month(entry.end));
        const qualifiers=[entry.approx?'approximate date':'',entry.baseline?'source-code template':'',entry.documented?'documented feature; no game-output sample':''].filter(Boolean).join('; ');
        return `${esc(date)} — ${link(s.url,s.title||'Source')}${s.url?'':' (URL not recorded)'}${qualifiers?' · '+esc(qualifiers):''}`;
      }
      panel.innerHTML=table+`<div class="mdi-footnotes" aria-label="Dates and sources"><ol>${notes.map((entry,n)=>`<li id="${prefix}-${index}-note-${n+1}">${note(entry)}</li>`).join('')}</ol><p class="mdi-epoch-source">Epoch dates: ${link('https://mume.org/about/history','MUME history')} · ${link(catalogue.comparison?.baseline?.source||'https://dikumud.com/history/','Diku history')}</p></div>`;
    }
    host.querySelectorAll('[role="tab"]').forEach(button=>{
      button.addEventListener('click',()=>{active=button.dataset.section;render();if(panel.getBoundingClientRect().top<0)root.scrollIntoView({block:'start'});});
      button.addEventListener('keydown',event=>{
        const current=groups.indexOf(active);let next;
        if(event.key==='ArrowDown'||event.key==='ArrowRight')next=(current+1)%groups.length;
        if(event.key==='ArrowUp'||event.key==='ArrowLeft')next=(current-1+groups.length)%groups.length;
        if(event.key==='Home')next=0;if(event.key==='End')next=groups.length-1;
        if(next!==undefined){event.preventDefault();active=groups[next];render();host.querySelector('#'+prefix+'-tab-'+next).focus();}
      });
    });
    render();
  }
  global.MumeDateIndicators={derive,usable,init,comparisonRows,columns,evidenceEpoch,evidenceRows,sample};
  if(typeof module!=='undefined')module.exports={derive,usable,comparisonRows,columns,evidenceEpoch,evidenceRows,sample};
  if(typeof document!=='undefined')document.querySelectorAll('.bree-mume-dates').forEach(root=>{
    try{const inline=root.querySelector('.mdi-data');init(root,inline?JSON.parse(inline.textContent):global.MUME_DATE_INDICATORS);}catch(error){root.innerHTML='<p>The dating catalogue could not be loaded.</p>';}
  });
})(typeof window!=='undefined'?window:globalThis);
