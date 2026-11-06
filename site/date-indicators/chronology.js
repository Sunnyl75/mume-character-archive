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
  const responseInfo={
    'tell-incoming':['Tell','Target','Received'],'tell-outgoing':['Tell','Actor','Sent'],
    'tell-target-missing':['Tell','Actor','Unavailable'],'say-observer':['Say','Room',''],
    'say-self':['Say','Actor',''],'death-victim':['Death','Target',''],'death-room':['Death','Room',''],
    'first-kill-punctuation':['First kill','Actor',''],'fragment-damage':['Fragments','Unspecified',''],
    'shatter-damage':['Shatter','Unspecified',''],'guardian-shadows':['Guardian shadows','Room',''],
    'shadow-disappearance':['Shadow disappearance','Room',''],'horse-clip-clop':['Horse movement','Room',''],
    'follower-coudln':['Follower-loss typo','Target','Leader'],'raisen-hand':['Icy-wind typo','Target',''],
    'armour-percent':['Armour metric','Actor',''],'trophy-schema':['Trophy columns','Actor',''],
    'istar-clock':['Tan Istar field','Actor',''],'elrond-diku-line':['Guard battle cry','Room',''],
    'literal-spell-names':['Literal spell display','Room',''],'incapacitated':['Incapacitated','Target',''],
    'narrate':['Narrate','Room',''],'smile':['Smile','Actor',''],'nod':['Nod','Actor',''],
    'spell-diku-fireball':['Fireball — NPC','Room',''],'spell-fireball-words':['Fireball','Room',''],
    'spell-lightning-words':['Lightning bolt','Room',''],'spell-blindness-words':['Blindness','Room',''],
    'spell-call-words':['Call lightning','Room','']
  };
  const placeholderNames={ACTOR:'Actor',TARGET:'Target','TARGET-POSS':'TargetPossessive','ACTOR-POSS':'ActorPossessive',
    'ACTOR-OBJ':'ActorObject','TARGET-OBJ':'TargetObject',CHARACTER:'Character',MESSAGE:'Message',SPELL:'Spell',
    N:'Number',NUMBER:'Number',BODY:'BodyPart',BODYPART:'BodyPart',DIRECTION:'Direction',MOUNT:'Mount',PRONOUN:'Pronoun'};
  function placeholders(text){return String(text).replace(/<([^<>]+)>/g,(all,name)=>placeholderNames[name.toUpperCase()]?'<'+placeholderNames[name.toUpperCase()]+'>':all);}
  function viewpoint(value){
    const aliases={actor:'Actor',speaker:'Actor',sender:'Actor',self:'Actor',target:'Target',victim:'Target',recipient:'Target',
      room:'Room',observer:'Room',feature:'Feature',system:'Actor',unspecified:'Unspecified'};
    return aliases[String(value||'').toLowerCase()]||'Unspecified';
  }
  function cleanOutput(quote){
    let text=String(quote).trim();
    const end=text.indexOf('>');
    if(end>=0){const prefix=text.slice(0,end);if(!/['"]/.test(prefix)&&((/HP:|Mana:/.test(prefix)&&prefix.length<120)||/^[0-9*oRWC\s]*$/.test(prefix)))text=text.slice(end+1).trim();}
    return text.replace(/\s+<[-=]{2,}.*$/,'').trimEnd();
  }
  function combatSample(output){
    const found=output.match(/^(You|.+?) ((?:barely |lightly |strongly |swiftly |firmly )?)(hits?|slash(?:es)?|pierces?|crush(?:es)?|smites?|pounds?|cleaves?|stabs?|bites?|claws?|mauls?|whips?|shoots?) (your|.+?'s) ((?:(?:left|right) )?(?:arm|leg|hand|foot|wing|foreleg|hindleg)|head|body|neck|chest|back|tail|stomach) (.+)$/);
    if(!found)return null;
    const [,actor,adverb,verb,target,,effect]=found;
    const view=actor==='You'?'Actor':target==='your'?'Target':'Room';
    const stem={hits:'Hit',hit:'Hit',slashes:'Slash',slash:'Slash',pierces:'Pierce',pierce:'Pierce',crushes:'Crush',crush:'Crush',
      smites:'Smite',smite:'Smite',pounds:'Pound',pound:'Pound',cleaves:'Cleave',cleave:'Cleave',stabs:'Stab',stab:'Stab',
      bites:'Bite',bite:'Bite',claws:'Claw',claw:'Claw',mauls:'Maul',maul:'Maul',whips:'Whip',whip:'Whip',shoots:'Shoot',shoot:'Shoot'};
    return {output:`${actor==='You'?'You':'<Actor>'} ${adverb}${verb} ${target==='your'?'your':"<Target>'s"} <BodyPart> ${effect}`,viewpoint:view,detail:stem[verb]||verb};
  }
  // Display templates consistently. The attestation retains its unmodified raw
  // quotation; names and perspective never become apparent wording changes.
  function sample(indicator,quote){
    if(!quote)return null;
    const id=indicator.id,config=indicator.comparison||{},info=responseInfo[id];
    let output=cleanOutput(quote),view=config.viewpoint?viewpoint(config.viewpoint):info?.[1]||'Unspecified',detail=config.detail??info?.[2]??'';
    const done=()=>({output:placeholders(output),signature:placeholders(output),viewpoint:view,detail});
    if(['tell-incoming','say-observer','narrate'].includes(id)){
      const verb={'tell-incoming':'tells you','say-observer':'says',narrate:'narrates'}[id];
      const found=output.match(new RegExp("^[^']+? "+verb+" '(.*)'([.!?]*)$"));
      if(!found)return null;
      output=`<Actor> ${verb} '<Message>'${found[2]}`;return done();
    }
    if(id==='elrond-diku-line'){
      const found=output.match(/^[^']+ screams '(PROTECT THE INNOCENT![^']*)'/);
      if(!found)return null;output=`<Actor> screams '${found[1]}'`;return done();
    }
    if(id==='guardian-shadows')output=output.replace(/(above the corpse of ).*\.$/,'$1<Target>.');
    if(id==='horse-clip-clop'){
      const found=output.match(/^(Clip-clop\.+)(.+?) (has arrived from|have arrived from|leaves|leave) (.+)$/);
      if(!found)return null;
      const [,sound,,verb,tail]=found;
      const riding=tail.match(/^(.*?) riding (.+?)(\.)?$/);
      output=`${sound}<Actor> ${verb} <Direction>${riding?' riding <Mount>':''}${output.endsWith('.')?'.':''}`;
      detail=/arrived/.test(verb)?'Arrival':'Departure';return done();
    }
    if(id==='follower-coudln')output=output.replace(/^ACK!! .*? ((?:coudln|couldn)'t follow you, you lost) (?:him|her|it)\.$/,'ACK!! <Actor> $1 <Pronoun>.');
    if(id==='raisen-hand')output=output.replace(/(hand of ).*?(\. You panic!)/,'$1<Actor>$2');
    if(id==='armour-percent'){
      const found=output.match(/Armour:\s*\d+%/);if(!found)return null;output=found[0].replace(/\d+/g,'<Number>');
    }
    if(['fragment-damage','shatter-damage'].includes(id)){
      const combat=combatSample(output);if(combat)return {...combat,signature:combat.output};
      view='Unspecified';return done();
    }
    if(id==='istar-clock')output=output.replace(/(Council is )(?!not defined\.).*\.$/,'$1<Character>.');
    if(id==='death-room'){const found=output.match(/^.*? is dead! R\.I\.P\./);if(!found)return null;output='<Target> is dead! R.I.P.';view='Room';}
    if(['nod','smile'].includes(id)){
      if(output.startsWith('You '))view='Actor';
      else{
        const found=output.match(/^(.+?) (nods|smiles)(.*)$/);
        if(found){view=/\bat you\b/.test(found[3])?'Target':'Room';output=`<Actor> ${found[2]}${found[3]}`;}
        else view='Unspecified';
      }
      output=output.replace(/( at )(?!you(?:rself)?\b)([^.!?]+)([.!?]*)$/,'$1<Target>$3');
    }
    if(id==='literal-spell-names'||/^spell-.*-words$/.test(id)){
      const found=output.match(/^[^']+? utters the words, '([^']*)'([.!?]*)/);if(!found)return null;
      if(id==='literal-spell-names'&&!/^(?:harm|lightning bolt)$/.test(found[1]))return null;
      output=`<Actor> utters the words, '${id==='literal-spell-names'?'<Spell>':found[1]}'${found[2]}`;view='Room';
    }
    return done();
  }
  function baselineSample(indicator,baseline){
    const config=indicator.comparison||{},info=responseInfo[indicator.id];
    let output=placeholders(baseline.output);
    if(['tell-incoming','say-observer'].includes(indicator.id))output=output.replace(/'…'/,"'<Message>'");
    if(indicator.id==='literal-spell-names')output="<Actor> utters the words, '<Spell>'";
    if(indicator.id==='spell-diku-fireball')output="<Actor> utters the words 'tuborg'.";
    if(indicator.id==='elrond-diku-line')output=`<Actor> screams '${output}'`;
    return {output,signature:output,viewpoint:viewpoint(baseline.viewpoint||config.viewpoint||info?.[1]),detail:config.detail??info?.[2]??''};
  }
  function wordingDiff(before,after){
    if(before===after)return [];
    const tokenize=text=>text.match(/<[^<>]+>|\s+|[\p{L}\p{N}_]+|[^\s\p{L}\p{N}_<>]+|[<>]/gu)||[];
    const a=tokenize(before),b=tokenize(after),parts=[];
    // Bound work for unusually large uploaded excerpts.
    if(a.length*b.length>250000){
      let start=0,end=0;
      while(start<a.length&&start<b.length&&a[start]===b[start])start++;
      while(end<a.length-start&&end<b.length-start&&a.at(-1-end)===b.at(-1-end))end++;
      return [{text:b.slice(0,start).join('')},
        {text:b.slice(start,b.length-end).join(''),changed:true,removed:a.slice(start,a.length-end).join('')},
        {text:b.slice(b.length-end).join('')}].filter(p=>p.text||p.changed);
    }
    const matrix=Array.from({length:a.length+1},()=>new Uint16Array(b.length+1));
    for(let i=a.length-1;i>=0;i--)for(let j=b.length-1;j>=0;j--)matrix[i][j]=a[i]===b[j]?matrix[i+1][j+1]+1:Math.max(matrix[i+1][j],matrix[i][j+1]);
    let i=0,j=0,added='',removed='';
    function flush(){if(added||removed){parts.push({text:added,changed:true,removed});added='';removed='';}}
    while(i<a.length||j<b.length){
      if(i<a.length&&j<b.length&&a[i]===b[j]){
        flush();const last=parts.at(-1);if(last&&!last.changed)last.text+=b[j];else parts.push({text:b[j]});i++;j++;
      }else if(i<a.length&&(j===b.length||matrix[i+1][j]>=matrix[i][j+1]))removed+=a[i++];
      else added+=b[j++];
    }
    flush();return parts;
  }
  function diffMarkup(item){
    if(!item.change)return esc(item.output);
    const describe=text=>/^\s+$/.test(text)?(text.length===1?'one space':text.length+' spaces'):text;
    return item.change.parts.map(part=>{
      if(!part.changed)return esc(part.text);
      const title=part.removed?'Previously: '+describe(part.removed):'Added wording';
      if(part.text)return `<mark class="mdi-change" title="${esc(title)}">${esc(part.text)}</mark>`;
      const label='Removed: '+describe(part.removed);
      return `<span class="mdi-deletion" role="img" aria-label="${esc(label)}" title="${esc(label)}"></span>`;
    }).join('');
  }
  function bridgeGaps(row,cols){
    // Only original, comparable response evidence supplies endpoints. Derived
    // continuity never becomes an attestation or a new calibration source.
    const observed=cols.map((col,index)=>({col,index,items:(row.cells[col.id]||[]).filter(item=>item.kind==='output'&&item.signature!==null)})).filter(c=>c.items.length);
    for(let n=1;n<observed.length;n++){
      const left=observed[n-1],right=observed[n];if(right.index-left.index<2)continue;
      const rightForms=new Map(right.items.map(item=>[item.signature,item]));
      const shared=[...new Map(left.items.filter(item=>rightForms.has(item.signature)).map(item=>[item.signature,item])).values()];
      for(let index=left.index+1;index<right.index;index++){
        const column=cols[index];if(row.cells[column.id]?.length)continue;
        if(!shared.length)continue;
        row.cells[column.id]=shared.map(item=>({kind:'inferred',output:item.output,signature:item.signature,
          viewpoint:row.viewpoint,detail:row.detail,shade:item.shade,lane:item.lane,entries:[],
          inference:{inferred:true,key:[row.id,left.col.id,right.col.id,item.signature].join('|'),
            from:{column:left.col,entry:item.entries[0]},to:{column:right.col,entry:rightForms.get(item.signature).entries[0]}}}));
      }
    }
  }
  function evidenceRows(catalogue){
    const result=[],grouped=new Map(),cols=columns(catalogue);
    const indicators=new Map(catalogue.indicators.map(i=>[i.id,i]));
    const slug=value=>String(value).toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');
    for(const variant of comparisonRows(catalogue)){
      const indicator=indicators.get(variant.id)||catalogue.indicators.find(i=>variant.id.startsWith(i.id+'-'));
      const config=indicator.comparison||{},info=responseInfo[indicator.id]||[config.label||indicator.title,indicator.mode==='documented'?'Feature':'Unspecified',''];
      const label=config.row||info[0],defaultView=viewpoint(config.viewpoint||info[1]),defaultDetail=config.detail??info[2];
      function ensure(view,detail){
        const key=[variant.section,label,view,detail].join('|');let row=grouped.get(key);
        if(!row){row={id:indicator.id+'-'+slug(view)+(detail?'-'+slug(detail):''),section:variant.section,label,viewpoint:view,detail,cells:{}};grouped.set(key,row);result.push(row);}
        return row;
      }
      let added=false;
      function add(column,item){
        const view=item.viewpoint||defaultView,detail=item.detail??defaultDetail;
        const row=ensure(view,detail);(row.cells[column]??=[]).push({...item,lane:indicator.id,viewpoint:view,detail});added=true;
      }
      if(variant.diku){
        const text=baselineSample(indicator,variant.diku);
        add('diku',{kind:'output',...text,entries:[{source:{id:'diku:'+variant.diku.url,title:'Diku Alfa source',url:variant.diku.url,date_label:month(variant.diku.date)},baseline:true}]});
      }
      for(const [epoch,value] of Object.entries(variant.cells)){
        if(value.kind==='continued'){
          add(epoch,{kind:'feature',output:label+' (continued)',signature:null,entries:[{continued:true,basis:config.continuity.basis||'Confirmed feature continuation. No wording sample is attached for this epoch.'}]});continue;
        }
        const buckets=new Map();
        for(const entry of value.observations){
          let text=entry.documented?{output:config.output||indicator.title,signature:config.output||indicator.title,viewpoint:'Feature',detail:''}:sample(indicator,entry.attestation.quote);
          if(!text)continue;
          if(entry.attestation?.viewpoint)text={...text,viewpoint:viewpoint(entry.attestation.viewpoint)};
          const key=[text.viewpoint,text.detail,text.signature].join('|');let bucket=buckets.get(key);
          if(!bucket){bucket={kind:entry.documented?'feature':'output',...text,entries:[]};buckets.set(key,bucket);}
          bucket.entries.push(entry);
        }
        for(const bucket of buckets.values()){
          // The citation backs the original line from which this display
          // template was made. Names remain available in that attestation.
          bucket.entries=[bucket.entries[0]];add(epoch,bucket);
        }
      }
      if(!added)ensure(defaultView,defaultDetail);
    }
    const groupOrder=new Map();for(const row of result){const key=row.section+'|'+row.label;if(!groupOrder.has(key))groupOrder.set(key,groupOrder.size);}
    const ranks={Actor:0,Target:1,Room:2,Feature:3,Unspecified:4};
    result.sort((a,b)=>groupOrder.get(a.section+'|'+a.label)-groupOrder.get(b.section+'|'+b.label)||ranks[a.viewpoint]-ranks[b.viewpoint]||a.detail.localeCompare(b.detail));
    for(const row of result){
      for(const items of Object.values(row.cells))items.sort((a,b)=>{
        const first=item=>item.entries[0];const end=item=>first(item).end||first(item).source?.date_end||'';
        const start=item=>first(item).start||first(item).source?.date_start||'';
        return end(a).localeCompare(end(b))||start(a).localeCompare(start(b));
      });
      const forms=new Map();let previous=null;
      for(const col of cols)for(const item of row.cells[col.id]||[]){
        if(item.signature===null)continue;
        if(!forms.has(item.signature)){
          forms.set(item.signature,forms.size);
          if(item.kind==='output'&&previous?.kind==='output')item.change={before:previous.output,parts:wordingDiff(previous.output,item.output)};
        }
        item.shade=forms.get(item.signature)%6;
        if(item.kind==='output')previous=item;
      }
      bridgeGaps(row,cols);
    }
    return result;
  }
  function init(root,catalogue){
    const host=root.querySelector('.mdi-app'),rows=evidenceRows(catalogue),cols=columns(catalogue);
    const groups=[...new Set([...(catalogue.comparison?.sections||sections),...rows.map(r=>r.section)])].filter(section=>rows.some(r=>r.section===section));
    const prefix='mdi-'+(document.querySelectorAll('.bree-mume-dates').length>1?[...document.querySelectorAll('.bree-mume-dates')].indexOf(root):'page');
    let active=groups[0];
    host.innerHTML=`<header class="mdi-heading"><h1>MUME wording & date indicators</h1><small>Updated ${esc(catalogue.updated_at)}</small></header><p class="mdi-key">— unknown · Dashed = inferred continuity · Red = first wording difference · Names use &lt;Actor&gt; / &lt;Target&gt;.</p><div class="mdi-layout"><nav class="mdi-tabs" role="tablist" aria-label="Output categories" aria-orientation="vertical">${groups.map((section,n)=>`<button type="button" role="tab" id="${prefix}-tab-${n}" aria-controls="${prefix}-panel" data-section="${esc(section)}">${esc(section)}</button>`).join('')}</nav><section id="${prefix}-panel" class="mdi-panel" role="tabpanel" tabindex="0"></section></div>`;
    const panel=host.querySelector('.mdi-panel');
    function render(){
      const index=groups.indexOf(active),notes=[],noteMap=new Map();
      host.querySelectorAll('[role="tab"]').forEach(button=>{const selected=button.dataset.section===active;button.setAttribute('aria-selected',String(selected));button.tabIndex=selected?0:-1;});
      panel.setAttribute('aria-labelledby',prefix+'-tab-'+index);
      function reference(entry){
        const key=entry.inferred?'inferred:'+entry.key:entry.continued?'continuity:'+entry.basis:entry.source.id||[entry.source.url,entry.source.date_label,entry.documented?'documented':''].join('|');
        if(!noteMap.has(key)){noteMap.set(key,notes.length+1);notes.push(entry);}
        const n=noteMap.get(key),id=prefix+'-'+index+'-note-'+n;
        return `<a class="mdi-note-ref" href="#${id}" aria-label="Source note ${n}">${n}</a>`;
      }
      function cell(row,column){
        const items=row.cells[column.id];
        if(!items?.length)return `<td class="mdi-unknown${column.id==='diku'?' mdi-diku':''}">—</td>`;
        return `<td class="${[column.id==='diku'?'mdi-diku':'',items.length>1?'mdi-multiple':''].filter(Boolean).join(' ')}">${items.map(item=>`<div class="mdi-sample${item.shade!==undefined?' mdi-shade-'+item.shade:''}${item.kind==='inferred'?' mdi-inferred':''}">${item.kind==='inferred'?'<small class="mdi-assumption">Inferred</small>':''}<code>${diffMarkup(item)}</code><sup>${item.kind==='inferred'?reference(item.inference):item.entries.map(reference).join(', ')}</sup></div>`).join('')}</td>`;
      }
      const table=`<div class="mdi-table-wrap" tabindex="0" aria-label="${esc(active)} comparison; scroll horizontally for later epochs"><table><thead><tr><th scope="col">Output / indicator</th>${cols.map(c=>`<th scope="col" ${c.id==='diku'?'class="mdi-diku"':''}>${esc(c.title)}<small>${esc(c.range)}</small></th>`).join('')}</tr></thead><tbody>${rows.filter(row=>row.section===active).map(row=>`<tr id="${prefix}-${esc(row.id)}"><th scope="row"><b>${esc(row.label)}</b><small class="mdi-viewpoint">${esc(row.viewpoint)}${row.detail?' · '+esc(row.detail):''}</small></th>${cols.map(column=>cell(row,column)).join('')}</tr>`).join('')}</tbody></table></div>`;
      function note(entry){
        if(entry.inferred){
          const endpoint=bound=>{const s=bound.entry.source;return esc(s.date_label||bound.column.range)+' — '+link(s.url,s.title||bound.column.title)+(s.url?'':' (URL not recorded)');};
          return `Assumed unchanged between ${esc(entry.from.column.title)} and ${esc(entry.to.column.title)}; no direct evidence from the intervening epochs. ${endpoint(entry.from)}; ${endpoint(entry.to)}.`;
        }
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
  global.MumeDateIndicators={derive,usable,init,comparisonRows,columns,evidenceEpoch,evidenceRows,sample,placeholders,wordingDiff,diffMarkup};
  if(typeof module!=='undefined')module.exports={derive,usable,comparisonRows,columns,evidenceEpoch,evidenceRows,sample,placeholders,wordingDiff,diffMarkup};
  if(typeof document!=='undefined')document.querySelectorAll('.bree-mume-dates').forEach(root=>{
    try{const inline=root.querySelector('.mdi-data');init(root,inline?JSON.parse(inline.textContent):global.MUME_DATE_INDICATORS);}catch(error){root.innerHTML='<p>The dating catalogue could not be loaded.</p>';}
  });
})(typeof window!=='undefined'?window:globalThis);
