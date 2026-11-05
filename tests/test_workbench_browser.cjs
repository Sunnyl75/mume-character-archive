// Optional DOM integration test: npm install --prefix /tmp/deck-ui-check jsdom
// NODE_PATH=/tmp/deck-ui-check/node_modules node tests/test_workbench_browser.cjs
const {JSDOM,VirtualConsole}=require('jsdom');
const fs=require('node:fs');
const path=require('node:path');
const os=require('node:os');
const {spawn}=require('node:child_process');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'deck-workbench-ui-'));
const archive=path.join(temp,'archive');
for(const name of ['scripts','site','integrations','reports','data'])fs.cpSync(path.join(root,name),path.join(archive,name),{recursive:true});
fs.mkdirSync(path.join(archive,'exports/mudlet'),{recursive:true});
const server=spawn(process.env.DECK_TEST_PYTHON||'python3',[path.join(root,'scripts/deck_workbench.py'),'--archive-root',archive,'--state-dir',path.join(temp,'state'),'--no-browser'],{stdio:['ignore','pipe','pipe']});
let output='',dom;
server.stdout.on('data',x=>output+=x);
server.stderr.on('data',x=>output+=x);
const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function until(fn,message,timeout=45000){const start=Date.now();while(Date.now()-start<timeout){if(await fn())return;await pause(40);}throw Error(message+'\n'+output);}
(async()=>{
  await until(()=>output.includes('Local interface: '),'Server did not start');
  const address=output.match(/Local interface: (\S+)/)[1];
  const url=new URL(address),token=new URLSearchParams(url.hash.slice(1)).get('token');
  const failures=[];
  const console=new VirtualConsole();console.on('jsdomError',e=>failures.push(e.message));
  dom=await JSDOM.fromURL(address,{resources:'usable',runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:console,beforeParse(w){
    w.scrollTo=()=>{};w.HTMLElement.prototype.scrollIntoView=()=>{};w.confirm=()=>true;
    w.fetch=(target,options={})=>{const address=new URL(target,url.origin);assert.equal(address.origin,url.origin);return fetch(address,{...options,headers:{...options.headers,Origin:url.origin}});};
  }});
  const w=dom.window,d=w.document;
  async function api(route,body){const response=await fetch(url.origin+'/api/'+route,{method:body?'POST':'GET',headers:{'X-Workbench-Token':token,Origin:url.origin,'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});const value=await response.json();assert.ok(response.ok,JSON.stringify(value));return value;}
  async function done(action){await until(async()=>{const s=await api('state');if(s.job?.action!==action||s.job.status==='running')return false;assert.equal(s.job.status,'done',s.job.log.join('\n'));return true;},action+' failed');await w.eval('refresh()');}
  function fill(id,value){d.getElementById(id).value=value;d.getElementById(id).dispatchEvent(new w.Event('input',{bubbles:true}));}
  async function click(id){await until(()=>d.getElementById(id),'Missing '+id);d.getElementById(id).click();}
  await until(()=>d.getElementById('tab-text'),'Sources step did not render');
  await click('tab-text');await until(()=>d.getElementById('source-text'),'Source form missing');
  fill('source-title','Workbench <img src=x onerror=alert(1)> fixture');fill('source-date','1995');fill('source-observer','GuiObserver');
  fill('source-groups','pGuiOwner: GuiObserver, GuiVictim');
  fill('source-text','GuiVictim is dead! R.I.P.\n*** TROPHY *** (Number Killed, Knowledge, Mobile)\n 3, 1%, #GuiTrophy |\n');
  await click('detect');await until(()=>d.querySelectorAll('.entry-check').length===2,'Extraction entries missing');
  await click('select-all-entries');await click('prepare-source');await until(()=>d.getElementById('preview-research'),'Import step missing');
  await click('preview-research');await done('preview_research');
  assert.match(d.body.textContent,/Proposed archive changes/);
  await until(()=>d.querySelectorAll('.preview-inspect').length>0,'Detailed preview did not appear');
  assert.match(d.getElementById('preview-records').textContent,/GuiObserver/);
  assert.equal(d.querySelectorAll('#preview-records img').length,0);
  d.getElementById('preview-table').value='historical_events';
  d.getElementById('preview-table').dispatchEvent(new w.Event('change'));
  await until(()=>d.getElementById('preview-page').textContent.includes('of 2 records'),'Event filter did not show death and trophy');
  assert.match(d.getElementById('preview-records').textContent,/Trophy snapshot: at least 3/);
  const inspect=Array.from(d.querySelectorAll('.preview-inspect')).find(b=>b.getAttribute('aria-label').includes('GuiTrophy'));
  inspect.click();
  await until(()=>d.getElementById('preview-detail').textContent.includes('Supporting source evidence'),'Evidence details missing');
  assert.match(d.getElementById('preview-detail').textContent,/minimum_kill_count/);
  assert.match(d.getElementById('preview-detail').textContent,/raw_line/);
  assert.equal(d.querySelectorAll('#preview-detail img').length,0);
  fill('preview-search','NoSuchNameInThisFixture');
  await until(()=>d.getElementById('preview-records').textContent.includes('No changes match'),'Empty search state missing');
  fill('preview-search','GuiVictim');
  await until(()=>d.querySelectorAll('.preview-inspect').length===1,'Name search did not filter events');
  assert.equal(d.getElementById('preview-next').disabled,true);
  await click('apply-research');await done('apply_research');
  await click('next');await until(()=>d.querySelectorAll('.link-check').length===2,'Review links missing');
  await click('select-links');await click('accept-links');await done('save_review');
  assert.match(fs.readFileSync(path.join(archive,'data/working/player_character_links.csv'),'utf8'),/GuiObserver,pGuiOwner,listed_same_player,accepted/);
  await click('next');await click('build-queue');await done('queue');
  assert.match(fs.readFileSync(path.join(archive,'exports/mudlet/whois_queue.txt'),'utf8'),/GuiObserver/);
  await click('next');
  const whois={version:'0.1.2',records:{guiobserver:{latest:{character_name:'GuiObserver',class:'Warrior'}}},captures:[{query_name:'GuiObserver',captured_at:'2026-11-05',raw_text:'GuiObserver the warrior',parsed:{character_name:'GuiObserver'}}]};
  await api('upload',{kind:'whois',filename:'mume_whois_archive.json',data:Buffer.from(JSON.stringify(whois)).toString('base64')});
  await w.eval('refresh();');await click('preview-whois');await done('preview_whois');
  await click('import-whois');await done('import_whois');
  await click('next');await click('build');await done('build');
  assert.ok((await api('state')).build_current);
  const deck=JSON.parse(fs.readFileSync(path.join(archive,'dist/deck-data.json'),'utf8'));
  const observer=deck.characters.find(c=>c.name==='GuiObserver');
  assert.equal(observer.player,'pGuiOwner');assert.equal(observer.history.trophies[0].count,3);
  assert.equal(deck.characters.find(c=>c.name==='GuiVictim').history.deaths.length,1);
  await click('next');await until(()=>d.getElementById('publish'),'Publish step missing');
  assert.equal(d.getElementById('publish').disabled,true);
  assert.deepEqual(failures,[]);
  process.stdout.write('Workbench DOM flow passed: prepare, preview, import, accept links, queue, Whois import, full rebuild and publication gate.\n');
})().catch(e=>{process.stderr.write(e.stack+'\n');process.exitCode=1;}).finally(()=>{dom?.window.close();server.kill('SIGINT');server.on('exit',()=>fs.rmSync(temp,{recursive:true,force:true}));});
