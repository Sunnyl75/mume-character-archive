const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..');
const {derive,usable,comparisonRows,columns,evidenceEpoch,evidenceRows,sample,placeholders,wordingDiff,diffMarkup}=require('../site/date-indicators/chronology.js');
const data=JSON.parse(fs.readFileSync(path.join(root,'research/date_indicators.json'),'utf8'));
const clone=value=>JSON.parse(JSON.stringify(value));
const source=(id,end,extra={})=>({id,title:id,date_start:end,date_end:end,date_confidence:'high',calibration:'independent',dependencies:[],...extra});
const marker={id:'shadows',mode:'introduced_by',soft_relation:'after',patterns:['A shadow rises.'],comparison:{section:'Combat & death',label:'Shadows',output:'Shadow',continuity:{confirmed:true,scope:'feature'}},attestations:[{source_id:'january',quote:'A shadow rises.'}]};
const fixture={epochs:data.epochs,sources:[source('january','1995-01-31')],indicators:[marker]};
assert.equal(derive(fixture,marker).label,'By Jan 1995');
assert.equal(derive(fixture,marker).sorting,'Soft after Jan 1995');
fixture.sources.push(source('earlier','1994-12-01'));marker.attestations.push({source_id:'earlier',quote:'A shadow rises.'});
assert.equal(derive(fixture,marker).label,'By Dec 1994');
fixture.sources.push(source('circular','1993-02-01',{dependencies:['shadows']}));marker.attestations.push({source_id:'circular'});
fixture.sources.push(source('second','1992-03-01',{dependencies:['other']}));marker.attestations.push({source_id:'second'});
fixture.sources.push(source('dependent','1992-01-01',{dependencies:['shadows']}));fixture.indicators.push({id:'other',patterns:[],attestations:[{source_id:'dependent'}]});
assert.equal(derive(fixture,marker).label,'By Dec 1994');
assert.equal(usable(fixture.sources[2],marker,fixture),false);
assert.equal(evidenceEpoch(fixture,marker,fixture.sources[3]),null);
assert.equal(derive(data,data.indicators.find(i=>i.id==='clip-clop-removal')).date,null);
const transition=derive(data,data.indicators.find(i=>i.id==='first-kill-punctuation'));
assert.equal(transition.from,'1996-03-31');assert.equal(transition.date,'1996-08-31');

const cols=columns(data),rows=comparisonRows(data),get=id=>rows.find(r=>r.id===id);
assert.deepEqual(cols.map(c=>c.id),['diku','i','ii','iii','iv','v','vi','vii','viii','ix']);
assert.equal(cols[0].range,'Jul 1991');assert.equal(cols[5].range,'Aug 1994–Feb 1996');
const shadows=get('guardian-shadows');
assert.equal(shadows.cells.iv,undefined);assert.equal(shadows.cells.v.kind,'observed');
assert.equal(shadows.cells.vi.kind,'observed');
for(const id of ['vii','viii','ix'])assert.equal(shadows.cells[id].kind,'continued');
for(const row of rows.filter(r=>r.id!=='guardian-shadows'))assert.ok(Object.values(row.cells).every(c=>c.kind!=='continued'));
// An earlier dated shadow moves the first occupied epoch and extends only later epochs.
const moved=clone(fixture);moved.sources.push(source('old','1994-05-01'));moved.indicators[0].attestations.push({source_id:'old'});
const movedRow=comparisonRows(moved)[0];assert.equal(movedRow.cells.iv.kind,'observed');assert.equal(movedRow.cells.vi.kind,'continued');assert.equal(movedRow.cells.iii,undefined);
assert.equal(evidenceEpoch(data,data.indicators[0],source('cross','1996-04-01',{date_start:'1996-02-01'})),null);
assert.equal(evidenceEpoch(data,data.indicators[0],source('unbounded','1998-06-01',{date_start:null,date_label:'Before Jun 1998'})),null);
assert.equal(evidenceEpoch(data,data.indicators[0],source('broad',null,{date_start:null,date_label:'Early 1995'})).approx,true);
assert.equal(get('say-self').diku.output,'Ok.');
assert.equal(get('death-victim').diku.output,'You are dead!  Sorry...');
assert.match(get('incapacitated').diku.output,/incapacitated an will/);
assert.equal(rows.length,38);

const evidence=evidenceRows(data),findEvidence=id=>evidence.find(r=>r.id===id||r.id.startsWith(id+'-'));
assert.equal(evidence.length,48);
const tell=findEvidence('tell-incoming'),sent=findEvidence('tell-outgoing'),unavailable=findEvidence('tell-target-missing');
assert.equal(tell.label,'Tell');assert.equal(tell.viewpoint,'Target');assert.equal(sent.viewpoint,'Actor');
assert.equal(unavailable.cells.vi[0].output,'No-one by that name here...');
assert.equal(unavailable.cells.vi[0].shade,1);assert.equal(tell.cells.vi[0].shade,0);
assert.equal(tell.cells.vi[0].output,"<Actor> tells you '<Message>'");
for(const row of evidence)for(const items of Object.values(row.cells))for(const item of items){
 assert.equal(item.viewpoint,row.viewpoint);assert.equal(item.detail,row.detail);
 assert.doesNotMatch(item.output,/<(?:ACTOR|TARGET|SPELL|N)>/);
 assert.doesNotMatch(item.output,/Dragomil|Maedhros|Morceleb|Grease|Gonshi|Golfimbul|Tergrim|HolyElf|Radorac/);
}
assert.equal(findEvidence('death-victim').viewpoint,'Target');assert.equal(findEvidence('death-room').viewpoint,'Room');
assert.notEqual(findEvidence('death-victim').id,findEvidence('death-room').id);
assert.notEqual(findEvidence('say-self').id,findEvidence('say-observer').id);
const nod=findEvidence('nod');assert.equal(nod.cells.diku[0].shade,nod.cells.vi[0].shade);
for(const epoch of ['i','ii','iii','iv','v']){assert.equal(nod.cells[epoch][0].kind,'inferred');assert.equal(nod.cells[epoch][0].entries.length,0);assert.equal(nod.cells[epoch][0].shade,nod.cells.vi[0].shade);assert.equal(nod.cells[epoch][0].change,undefined);}
assert.equal(nod.cells.vii,undefined); // A single endpoint cannot extend wording forward.
const firstKill=findEvidence('first-kill-punctuation');assert.equal(firstKill.cells.vi.length,2);
assert.notEqual(firstKill.cells.vi[0].shade,firstKill.cells.vi[1].shade);
// Reversing configured variants must not reverse the dated order inside an
// epoch. Earlier/later samples retain shades matching adjacent observed epochs.
const reordered=clone(data),reorderedKill=reordered.indicators.find(i=>i.id==='first-kill-punctuation');
reorderedKill.comparison.variants.reverse();
reordered.sources.push(source('following-new','2000-01-02'));
reorderedKill.attestations.push({source_id:'following-new',group:'new',quote:"Congratulations! This is the first time you've killed it!"});
const ordered=evidenceRows(reordered).find(r=>r.id==='first-kill-punctuation-actor');
assert.equal(ordered.cells.vi.length,2);
assert.match(ordered.cells.vi[0].output,/Congratulations!!/);
assert.match(ordered.cells.vi[1].output,/Congratulations! This/);
assert.equal(ordered.cells.vi[0].shade,ordered.cells.v[0].shade);
assert.equal(ordered.cells.vi[1].shade,ordered.cells.vii[0].shade);
assert.equal(ordered.cells.v.length,1);assert.equal(ordered.cells.viii,undefined);
for(const [epoch,items]of Object.entries(ordered.cells))for(const item of items){
 assert.ok(item.entries.every(entry=>entry.epoch===epoch));
}
const simulated=clone(data),simNod=simulated.indicators.find(i=>i.id==='nod');
for(const [id,date]of [['later','2000-04-02'],['latest','2005-04-02']]){
 simulated.sources.push(source(id,date));simNod.attestations.push({source_id:id,quote:'You nod your head solemnly.'});
}
const laterNod=evidenceRows(simulated).find(r=>r.id==='nod-actor');
assert.equal(laterNod.cells.vii[0].shade,1);assert.equal(laterNod.cells.viii[0].shade,1);
assert.equal(laterNod.cells.vi[0].shade,0);
assert.equal(sample({id:'tell-incoming'},"Elegil says 'Someone tells you 'hi''"),null);
assert.equal(sample({id:'tell-incoming'},"Bob narrates 'HP:Fine> Alice tells you 'hi''"),null);
assert.equal(sample({id:'elrond-diku-line'},'>> Mood: aggressive << #### BANZAI!!!!!'),null);
assert.equal(sample({id:'narrate'},"Person narrates 'hello' <--- comment").signature,"<Actor> narrates '<Message>'");
assert.equal(sample({id:'narrate'},"Person narrates 'incomplete"),null);
assert.equal(sample({id:'tell-incoming'},"Someone tells you 'other message'").signature,tell.cells.vi[0].signature);

// Normalize actual output templates while preserving the difference in POV.
assert.equal(placeholders("<ACTOR> hits <TARGET>'s <BODY>."),"<Actor> hits <Target>'s <BodyPart>.");
const actorHit=sample({id:'shatter-damage'},"You lightly pierce *Mammoth the Orc*'s right leg and shatter it.");
const victimHit=sample({id:'shatter-damage'},"*Tergrim the Hobbit* barely pierces your left arm and shatters it.");
const roomHit=sample({id:'shatter-damage'},"Alice lightly pierces Bob's right leg and shatters it.");
assert.equal(actorHit.viewpoint,'Actor');assert.equal(victimHit.viewpoint,'Target');assert.equal(roomHit.viewpoint,'Room');
assert.equal(actorHit.output,"You lightly pierce <Target>'s <BodyPart> and shatter it.");
assert.equal(victimHit.output,"<Actor> barely pierces your <BodyPart> and shatters it.");
assert.equal(roomHit.output,"<Actor> lightly pierces <Target>'s <BodyPart> and shatters it.");
assert.equal(sample({id:'shatter-damage'},"You slash Bob's left leg very hard and shatter it.").viewpoint,'Actor');
assert.equal(sample({id:'tell-incoming'},"Alice tells you 'hello'").output,sample({id:'tell-incoming'},"Bob tells you 'different words'").output);
assert.equal(sample({id:'smile'},'You smile at Alice.').output,'You smile at <Target>.');
assert.equal(sample({id:'smile'},'Bob smiles at you.').viewpoint,'Target');
assert.equal(sample({id:'smile'},'Bob smiles at Alice.').output,'<Actor> smiles at <Target>.');
assert.equal(sample({id:'istar-clock'},'The present Tan Istar, Lord of the Istari Council is not defined.').output,'The present Tan Istar, Lord of the Istari Council is not defined.');
const perspectives=clone(data),perspectiveIndicator=perspectives.indicators.find(i=>i.id==='shatter-damage');
perspectives.sources.push(source('three-views','1997-12-01'));
for(const quote of ["You lightly pierce Bob's right leg and shatter it.","Bob barely pierces your left arm and shatters it.","Alice lightly pierces Bob's right leg and shatters it."]){
 perspectiveIndicator.attestations.push({source_id:'three-views',quote});
}
const perspectiveRows=evidenceRows(perspectives).filter(r=>r.label==='Shatter'&&r.detail==='Pierce');
assert.deepEqual(new Set(perspectiveRows.map(r=>r.viewpoint)),new Set(['Actor','Target','Room']));
assert.ok(perspectiveRows.every(r=>r.cells.vi.every(item=>item.viewpoint===r.viewpoint)));
const before=JSON.stringify(data);evidenceRows(data);assert.equal(JSON.stringify(data),before);

// Bounded continuity is derived from the nearest observed forms in this row;
// another response in the gap blocks inference across it. No new evidence is made.
function series(points){
 const cat={epochs:data.epochs,sources:[],indicators:[{id:'nod',title:'Nod',category:'Social interactions',mode:'observed_by',soft_relation:'none',patterns:[],comparison:{section:'Social interactions',label:'Nod'},attestations:[]}]};
 points.forEach(([date,quote],n)=>{const id='series-'+n;cat.sources.push(source(id,date));cat.indicators[0].attestations.push({source_id:id,quote});});
 return cat;
}
const a='You nod solemnly.',b='You nod your head solemnly.',c='You nod in agreement.';
const gapData=series([['1993-01-01',a],['1997-01-01',a]]),gapBefore=JSON.stringify(gapData);
const gap=evidenceRows(gapData).find(r=>r.id==='nod-actor');
assert.equal(gap.cells.i,undefined);assert.equal(gap.cells.vii,undefined);
for(const epoch of ['iii','iv','v']){const item=gap.cells[epoch][0];assert.equal(item.kind,'inferred');assert.equal(item.output,a);assert.equal(item.shade,gap.cells.ii[0].shade);assert.deepEqual(item.entries,[]);assert.equal(item.change,undefined);}
assert.equal(derive(gapData,gapData.indicators[0]).usable,2);assert.equal(JSON.stringify(gapData),gapBefore);
const blocked=evidenceRows(series([['1993-01-01',a],['1994-05-01',b],['1997-01-01',a]])).find(r=>r.id==='nod-actor');
assert.equal(blocked.cells.iii,undefined);assert.equal(blocked.cells.v,undefined);
const shared=evidenceRows(series([['1993-01-01',a],['1993-01-02',b],['1997-01-01',b],['1997-01-02',c]])).find(r=>r.id==='nod-actor');
for(const epoch of ['iii','iv','v']){assert.equal(shared.cells[epoch].length,1);assert.equal(shared.cells[epoch][0].output,b);assert.equal(shared.cells[epoch][0].shade,shared.cells.ii.find(item=>item.output===b).shade);}
// Only a new form's first observed appearance gets a diff; later repetitions
// keep the shade, and both inserted/deleted text preserve the current response.
assert.equal(laterNod.cells.vii[0].change.parts.filter(p=>p.changed).map(p=>p.text).join('').trim(),'your head');
assert.equal(laterNod.cells.viii[0].change,undefined);
assert.equal(nod.cells.diku[0].change,undefined);assert.equal(nod.cells.vi[0].change,undefined);
const punctuation=wordingDiff('No-one by that name here..','No-one by that name here...');
assert.equal(punctuation.filter(p=>p.changed).map(p=>p.text).join(''),'...');
const deletion=wordingDiff('You nod very solemnly.','You nod solemnly.');
assert.ok(deletion.some(p=>p.changed&&!p.text&&p.removed.includes('very')));
for(const [beforeText,afterText]of [[a,b],['one two','one'],['','new'],['old',''],['a '.repeat(600),'a '.repeat(300)+'b '+'a '.repeat(299)]]){
 const parts=wordingDiff(beforeText,afterText);assert.equal(parts.map(p=>p.text).join(''),afterText);
}
const markup=new JSDOM('<code>'+diffMarkup({output:'You nod solemnly.',change:{parts:deletion}})+'</code>');
assert.equal(markup.window.document.querySelector('code').textContent,'You nod solemnly.');
assert.match(markup.window.document.querySelector('.mdi-deletion').getAttribute('aria-label'),/very/);markup.window.close();
const escapedDiff=new JSDOM('<code>'+diffMarkup({output:'<img src=x>',change:{parts:wordingDiff('safe','<img src=x>')}})+'</code>');
assert.equal(escapedDiff.window.document.querySelectorAll('img').length,0);assert.equal(escapedDiff.window.document.querySelector('code').textContent,'<img src=x>');escapedDiff.window.close();

const html=fs.readFileSync(path.join(root,'releases/MUME_Date_Indicators.html'),'utf8');
const dom=new JSDOM(html,{runScripts:'dangerously',url:'https://preview.example.org/'});
const d=dom.window.document;
assert.equal(d.querySelectorAll('script[src],link[rel="stylesheet"]').length,0);
const tabs=[...d.querySelectorAll('[role="tab"]')];
assert.equal(tabs.length,7);assert.equal(d.querySelectorAll('table').length,1);
assert.equal(d.querySelectorAll('tbody tr').length,8);
assert.equal(d.querySelectorAll('thead th').length,11);
assert.equal(d.querySelectorAll('form,details,.mdi-indicator,.mdi-observed,.mdi-continued').length,0);
assert.equal(d.querySelector('#mdi-page-tell-incoming-target-received th b').textContent,'Tell');
assert.match(d.querySelector('#mdi-page-tell-incoming-target-received .mdi-viewpoint').textContent,/Target/);
assert.match(d.querySelector('#mdi-page-tell-target-missing-actor-unavailable').textContent,/No-one by that name here\.\.\./);
assert.doesNotMatch(d.querySelector('tbody').textContent,/present by|199[0-9]/);
assert.ok(d.querySelector('.mdi-footnotes a[href*="github.com"]'));
for(const ref of d.querySelectorAll('.mdi-note-ref'))assert.ok(d.getElementById(ref.getAttribute('href').slice(1)));
const nodSamples=[...d.querySelectorAll('#mdi-page-nod-actor .mdi-sample')];
assert.equal(nodSamples.length,7);assert.ok(nodSamples.every(c=>c.classList.contains('mdi-shade-0')));
assert.equal(d.querySelectorAll('#mdi-page-nod-actor .mdi-inferred').length,5);
assert.equal(d.querySelectorAll('#mdi-page-nod-actor .mdi-sample:not(.mdi-inferred)').length,2);
assert.equal(d.querySelectorAll('#mdi-page-nod-actor .mdi-change').length,0);
assert.match(d.querySelector('.mdi-footnotes').textContent,/Assumed unchanged between Diku Alfa and MUME VI; no direct evidence/);
tabs[1].click();assert.equal(tabs[1].getAttribute('aria-selected'),'true');
assert.equal(d.querySelectorAll('[role="tab"][aria-selected="true"]').length,1);
assert.match(d.querySelector('#mdi-page-guardian-shadows-room').textContent,/A shadow slowly rises/);
assert.match(d.querySelector('#mdi-page-guardian-shadows-room').textContent,/continued/);
assert.equal(d.querySelector('#mdi-page-guardian-shadows-room td').textContent,'—');
assert.ok(d.querySelector('.mdi-footnotes a[href*="radorac.txt"]'));
assert.equal(d.querySelectorAll('tbody a[href^="http"]').length,0);
const mixedCell=d.querySelector('#mdi-page-first-kill-punctuation-actor td:nth-of-type(7)');
assert.ok(mixedCell.classList.contains('mdi-multiple'));
const stacked=[...mixedCell.querySelectorAll('.mdi-sample')];
assert.equal(stacked.length,2);assert.match(stacked[0].textContent,/Congratulations!!/);
assert.match(stacked[1].textContent,/Congratulations! This/);
assert.equal(stacked[0].querySelectorAll('.mdi-change,.mdi-deletion').length,0);
assert.equal(stacked[1].querySelector('.mdi-change').textContent,'!');
assert.match(stacked[1].querySelector('.mdi-deletion').getAttribute('title'),/one space/);
tabs[1].dispatchEvent(new dom.window.KeyboardEvent('keydown',{key:'End',bubbles:true}));
assert.equal(tabs[6].getAttribute('aria-selected'),'true');
assert.equal(d.querySelectorAll('table').length,1);
// Official feature notes with different dates must not be collapsed together.
const featureNotes=d.querySelector('.mdi-footnotes').textContent;
assert.match(featureNotes,/Mar 1996/);assert.match(featureNotes,/Apr 1999/);assert.match(featureNotes,/Jan 2002/);
tabs[6].dispatchEvent(new dom.window.KeyboardEvent('keydown',{key:'Home',bubbles:true}));
assert.equal(tabs[0].getAttribute('aria-selected'),'true');
// Malicious labels, quotations and non-web source URLs remain inert.
const malicious=clone(data);malicious.indicators[0].comparison.row='<img src=x onerror=alert(1)>';
malicious.indicators[0].attestations[0].quote='<script>alert(1)</script>';
for(const s of malicious.sources)s.url='javascript:alert(1)';
const isolated=new JSDOM('<div class="bree-mume-dates"><div class="mdi-app"></div></div>',{runScripts:'outside-only'});
isolated.window.MUME_DATE_INDICATORS=malicious;
isolated.window.eval(fs.readFileSync(path.join(root,'site/date-indicators/chronology.js'),'utf8'));
isolated.window.document.querySelectorAll('[role="tab"]')[1].click();
assert.equal(isolated.window.document.querySelectorAll('img,script,a[href^="javascript:"]').length,0);
assert.match(isolated.window.document.body.textContent,/<img src/);
// Legacy catalogue files still render without comparison metadata.
const legacy=clone(data);delete legacy.comparison;for(const i of legacy.indicators)delete i.comparison;
assert.equal(comparisonRows(legacy).length,38);assert.ok(evidenceRows(legacy).length>0);
dom.window.close();isolated.window.close();
console.log('Date indicator checks passed: anchors, circular evidence, epoch ranges, bounded inferred continuity, first-appearance text diffs, placeholders, separate viewpoints, source footnotes, tabs and escaping.');
