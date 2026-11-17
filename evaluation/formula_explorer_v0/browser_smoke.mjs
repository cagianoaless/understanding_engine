// Existing Chromium/Node only. Browser-plugin execution tool was unavailable.
// Owned temporary profile/server; no model calls, package installs or personal profile.
import {spawn} from 'node:child_process';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {join,resolve} from 'node:path';
import assert from 'node:assert/strict';
const args=Object.fromEntries(process.argv.slice(2).reduce((a,v,i,x)=>i%2?a:[...a,[v.slice(2),x[i+1]]],[]));
for(const k of ['browser','python','launch','work'])assert(args[k],`Missing --${k}`);
const launch=JSON.parse(await readFile(args.launch,'utf8')),graph=JSON.parse(await readFile(launch.formula_graph,'utf8'));
const work=resolve(args.work);await mkdir(work);
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
let browser,server,ws,session,id=0,serverOut='',serverErr='',browserErr='';
const pending=new Map(),requests=[],errors=[];
const report={schema_version:'formula-explorer-browser-smoke.1',prediction_id:graph.provenance.prediction_id,formula_id:graph.id,
  pdf_sha256:graph.provenance.pdf_sha256,complete:false,checks:[],browser_surface:'Installed Chromium-compatible browser, isolated headless profile; CDP fallback',
  manual_human_verification:false,new_inference_calls:0};
function command(method,params={},sessionId=session){return new Promise((resolve,reject)=>{
  const n=++id,timer=setTimeout(()=>{pending.delete(n);reject(Error('CDP timeout '+method));},15000);
  pending.set(n,{resolve,reject,timer});ws.send(JSON.stringify({id:n,method,params,...(sessionId?{sessionId}:{})}));
});}
async function evaluate(expression){const r=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});assert(!r.exceptionDetails,JSON.stringify(r.exceptionDetails));return r.result.value;}
async function until(fn,limit=120000){const start=performance.now();while(performance.now()-start<limit){const r=await fn();if(r)return r;await sleep(100);}throw Error('UI wait timed out');}
async function clickAt(x,y){await command('Input.dispatchMouseEvent',{type:'mousePressed',x,y,button:'left',clickCount:1});await command('Input.dispatchMouseEvent',{type:'mouseReleased',x,y,button:'left',clickCount:1});}
async function clickElement(selector){
  const point=await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e)throw Error('Missing target');e.scrollIntoView({block:'nearest',inline:'nearest'});const r=e.getBoundingClientRect();return [r.left+r.width/2,r.top+r.height/2,r.width,r.height];})()`);
  assert(point[2]>0&&point[3]>0,'Target hidden');await clickAt(point[0],point[1]);
}
async function screenshot(name){const r=await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await writeFile(join(work,name),Buffer.from(r.data,'base64'));}
async function overlay(){return evaluate("(()=>{const r=document.getElementById('formula-crop-overlay');return {box:['x','y','width','height'].map(k=>Number(r.getAttribute(k))),scope:r.dataset.pdfScope,rectangles:document.querySelectorAll('#overlay rect').length};})()");}
async function selectNode(node){
  await clickElement(`button[data-node-id="${node.id}"]`);
  await until(()=>evaluate(`document.querySelector('button[data-node-id="${node.id}"]').getAttribute('aria-pressed')==='true'`));
  const data=await evaluate("({highlight:document.getElementById('formula-latex-highlight').textContent,latex:document.getElementById('formula-latex').textContent,details:JSON.parse(document.getElementById('formula-node-details').textContent)})");
  const expected=Array.from(graph.input.latex).slice(...node.character_span).join('');
  assert.equal(data.highlight,expected);assert.equal(data.latex,graph.input.latex);
  assert.deepEqual(data.details.child_roles,node.children);assert.deepEqual(data.details.diagnostics,node.diagnostics);
  assert.equal(data.details.symbol_pdf_alignment,'unavailable');
  report.checks.push({node_id:node.id,type:node.type,character_span:node.character_span,token_span:node.token_span,highlight:data.highlight,overlay:await overlay()});
}
try{
  browser=spawn(args.browser,['--headless=new','--remote-debugging-port=0','--remote-debugging-address=127.0.0.1',
    '--user-data-dir='+join(work,'isolated-profile'),'--no-first-run','--no-default-browser-check',
    '--disable-background-networking','--disable-component-update','--disable-sync','--disable-default-apps',
    '--disable-extensions','--disable-gpu','--disable-breakpad','--disable-client-side-phishing-detection',
    '--metrics-recording-only','--disk-cache-size=10485760',
    '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1, EXCLUDE localhost','about:blank'],{stdio:['ignore','ignore','pipe']});
  browser.stderr.on('data',b=>{browserErr+=b;});
  const marker=await until(async()=>{try{return await readFile(join(work,'isolated-profile','DevToolsActivePort'),'utf8');}catch{return null;}},15000);
  const [port,path]=marker.trim().split('\n');ws=new WebSocket('ws://127.0.0.1:'+port+path);
  await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
  ws.onmessage=event=>{const d=JSON.parse(event.data);if(d.id){const p=pending.get(d.id);if(p){clearTimeout(p.timer);pending.delete(d.id);d.error?p.reject(Error(JSON.stringify(d.error))):p.resolve(d.result);}}else{
    if(d.method==='Network.requestWillBeSent')requests.push(d.params.request.url);
    if(d.method==='Runtime.exceptionThrown')errors.push(d.params.exceptionDetails);
    if(d.method==='Log.entryAdded'&&d.params.entry.level==='error')errors.push(d.params.entry);
    if(d.method==='Network.responseReceived'&&d.params.response.status>=400)errors.push({status:d.params.response.status,url:d.params.response.url});
  }};
  const target=await command('Target.createTarget',{url:'about:blank'},null);
  session=(await command('Target.attachToTarget',{targetId:target.targetId,flatten:true},null)).sessionId;
  for(const name of ['Page','Runtime','Network','Log'])await command(name+'.enable');
  await command('Emulation.setDeviceMetricsOverride',{width:1440,height:1100,deviceScaleFactor:1,mobile:false});
  report.browser=await command('Browser.getVersion',{},null);
  const cli=['-B','-m','understanding_engine.viewer'];
  for(const [key,flag] of [['pdf','pdf'],['extraction','extraction'],['hybrid','hybrid'],['manifest','manifest'],['formula_graph','formula-graph'],['formula_manifest','formula-manifest']])cli.push('--'+flag,launch[key]);
  cli.push('--formula-demo');
  const start=performance.now();server=spawn(args.python,cli,{env:process.env,stdio:['ignore','pipe','pipe']});
  server.stdout.on('data',b=>{serverOut+=b;});server.stderr.on('data',b=>{serverErr+=b;});
  const url=await until(()=>serverOut.match(/Open locally: (http:\/\/127\.0\.0\.1:\d+\/#[^\s]+)/)?.[1],15000),origin=new URL(url).origin;
  await command('Page.navigate',{url});
  await until(()=>evaluate("(()=>{const i=document.getElementById('page-image'),e=document.getElementById('formula-crop-overlay');return e&&i.complete&&i.naturalWidth&&document.getElementById('loading').hidden;})()"));
  report.startup_to_render_ms=performance.now()-start;
  assert.equal(await evaluate('location.hash'),'');
  assert.equal(await evaluate("Number(document.getElementById('page').value)"),graph.provenance.page_number);
  await evaluate("document.getElementById('formula-crop-overlay').scrollIntoView({block:'center',inline:'nearest'})");
  const targetPoint=await evaluate(`(()=>{const i=document.getElementById('page-image').getBoundingClientRect(),g=document.getElementById('overlay').viewBox.baseVal,b=${JSON.stringify(graph.provenance.bbox)};return [i.left+(b[0]+b[2])/2*i.width/g.width,i.top+(b[1]+b[3])/2*i.height/g.height];})()`);
  await clickAt(...targetPoint);
  await until(()=>evaluate("!document.getElementById('formula-content').hidden"));
  report.actual_pointer_click_selected_crop=true;
  report.initial_overlay=await overlay();
  const b=graph.provenance.bbox,expectedBox=[b[0],b[1],b[2]-b[0],b[3]-b[1]];
  assert.deepEqual(report.initial_overlay.box,expectedBox);assert.equal(report.initial_overlay.rectangles,1);
  assert.equal(await evaluate("document.getElementById('formula-latex').textContent"),graph.input.latex);
  report.status_label=await evaluate("document.getElementById('formula-status').textContent");
  report.provenance_warning=await evaluate("document.getElementById('formula-provenance-warning').textContent");
  assert(report.provenance_warning.includes('WHOLE formula crop')&&report.status_label.includes('unverified'));
  if(graph.status.acceptance==='reject'){
    assert(report.status_label.includes('REJECTED AS A COMPLETE FORMULA'));
    await selectNode(graph.nodes.find(n=>n.id===graph.root_id));
    assert(await evaluate("document.getElementById('formula-node').textContent.includes('fragment of REJECTED formula')"));
    await screenshot('rejected-fragments.png');
  }else{
    // Use real pointer actions to reveal, collapse and expand the fraction.
    await clickElement('#formula-expand');
    const fraction=graph.nodes.find(n=>n.type==='fraction');assert(fraction);
    const selector=`details[data-node-type="fraction"]`;
    await evaluate(`document.querySelector(${JSON.stringify(selector)}).open=false`);
    const summaryPoint=await evaluate(`(()=>{const s=document.querySelector(${JSON.stringify(selector+'>summary')});s.scrollIntoView({block:'nearest'});const r=s.getBoundingClientRect();return [r.left+3,r.top+r.height/2];})()`);
    await clickAt(...summaryPoint);
    assert(await evaluate(`document.querySelector(${JSON.stringify(selector)}).open`));report.fraction_expanded=true;
    for(const role of ['numerator','denominator']){
      const id=fraction.children.find(c=>c.role===role).node_id;
      await selectNode(graph.nodes.find(n=>n.id===id));
      await screenshot(role+'.png');
    }
    assert.notEqual(report.checks[0].highlight,report.checks[1].highlight);
  }
  for(const check of report.checks){assert.deepEqual(check.overlay.box,expectedBox);assert.equal(check.overlay.rectangles,1);assert.equal(check.overlay.scope,'whole_formula_crop');}
  await clickElement('#formula-return');assert.deepEqual((await overlay()).box,expectedBox);report.return_to_original_crop=true;
  await clickElement('#formula-reset');
  assert(await evaluate("document.getElementById('formula-content').hidden&&!document.getElementById('formula-latex-highlight')"));report.reset_verified=true;
  assert(requests.every(u=>u.startsWith(origin+'/')||u.startsWith('blob:'+origin+'/')),'External page request');
  assert.equal(errors.length,0,JSON.stringify(errors));report.page_requests=requests.map(u=>u.replace(origin,'$ORIGIN'));report.external_page_requests=0;report.browser_errors=errors;
  const unicode=await evaluate("(async()=>{const m=await import('/formula-explorer.js');return m.latexSlices('𝛼+x',[0,1]);})()");
  assert.deepEqual(unicode,{before:'',selected:'𝛼',after:'+x'});report.browser_non_bmp_span_verified=true;
  report.complete=true;
}catch(e){report.failure=e.stack;process.exitCode=1;}
finally{
  if(server&&server.exitCode===null){server.kill('SIGINT');await Promise.race([new Promise(r=>server.once('exit',r)),sleep(10000)]);}
  if(ws?.readyState===WebSocket.OPEN){try{await command('Browser.close',{},null);}catch{}ws.close();}
  if(browser&&browser.exitCode===null)await Promise.race([new Promise(r=>browser.once('exit',r)),sleep(5000)]);
  if(browser&&browser.exitCode===null)browser.kill('SIGTERM');
  report.server_exit_code=server?.exitCode;report.server_signal=server?.signalCode;report.browser_exit_code=browser?.exitCode;
  await writeFile(join(work,'browser-smoke.json'),JSON.stringify(report,null,2)+'\n');
  await writeFile(join(work,'server.stderr.log'),serverErr);await writeFile(join(work,'browser.stderr.log'),browserErr);
  console.log(JSON.stringify({complete:report.complete,checks:report.checks.length,failure:report.failure,work}));
}
