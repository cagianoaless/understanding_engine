// Optional offline UI smoke: existing Chromium-compatible executable + Node >=22.
// No packages, personal browser profile, inference or external page requests.
import {spawn} from 'node:child_process';
import {readFile, writeFile, mkdir} from 'node:fs/promises';
import {join, resolve} from 'node:path';
import assert from 'node:assert/strict';
const args=Object.fromEntries(process.argv.slice(2).reduce((a,v,i,all)=>i%2?a:[...a,[v.slice(2),all[i+1]]],[]));
for(const k of ['browser','python','pdf','extraction','hybrid','manifest','anchors','work'])assert(args[k],`Missing --${k}`);
const work=resolve(args.work);await mkdir(work); // refuse an existing evidence run
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const anchors=JSON.parse(await readFile(args.anchors,'utf8'));
let browser,server,ws,session,id=0;const pending=new Map(),requests=[],errors=[];
let browserLog='',serverOut='',serverErr='';
function command(method,params={},sessionId=session){return new Promise((resolve,reject)=>{
  const n=++id,timer=setTimeout(()=>{pending.delete(n);reject(Error('CDP timeout '+method));},15000);
  pending.set(n,{resolve,reject,timer});ws.send(JSON.stringify({id:n,method,params,...(sessionId?{sessionId}:{})}));
});}
async function evaluate(expression){const r=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});assert(!r.exceptionDetails,JSON.stringify(r.exceptionDetails));return r.result.value;}
async function until(fn,limit=60000){const start=performance.now();while(performance.now()-start<limit){const v=await fn();if(v)return v;await sleep(100);}throw Error('UI wait timed out');}
async function click(x,y){await command('Input.dispatchMouseEvent',{type:'mousePressed',x,y,button:'left',clickCount:1});await command('Input.dispatchMouseEvent',{type:'mouseReleased',x,y,button:'left',clickCount:1});}
async function selection(){await evaluate("document.getElementById('raw-details').open=true");return until(()=>evaluate("(()=>{const t=document.getElementById('raw-json').textContent;return t?JSON.parse(t):null;})()"));}
async function choosePage(number){await evaluate(`document.getElementById('page').value='${number}';document.getElementById('page').dispatchEvent(new Event('change'))`);await until(()=>evaluate(`(()=>{const i=document.getElementById('page-image');return document.getElementById('loading').hidden&&i.complete&&i.naturalWidth&&document.getElementById('page').value==='${number}';})()`));}
async function screenshot(name){const r=await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await writeFile(join(work,name),Buffer.from(r.data,'base64'));}
async function clickAnchor(a,zoom){
  await evaluate(`document.getElementById('zoom').value=${JSON.stringify(zoom)};document.getElementById('zoom').dispatchEvent(new Event('change'));document.getElementById('raw-json').textContent=''`);
  const target=await evaluate(`(()=>{const i=document.getElementById('page-image'),r=i.getBoundingClientRect(),b=${JSON.stringify(a.bbox)},g=${JSON.stringify(a.geometry)};return {x:r.left+(b[0]+b[2])/2*r.width/g.width,y:r.top+(b[1]+b[3])/2*r.height/g.height,rect:[r.left,r.top,r.width,r.height],natural:[i.naturalWidth,i.naturalHeight]};})()`);
  assert(target.x>0&&target.x<1280&&target.y>0&&target.y<1000,'Anchor outside test viewport');
  const before=performance.now();await click(target.x,target.y);const r=await selection();const elapsed=performance.now()-before;
  assert(r.characters.some(c=>c.id===a.id&&c.text===a.text),'Expected original source ID/Unicode absent');
  assert.equal(r.source_text,r.characters.map(c=>c.text).join(''));
  const counts=await evaluate("({units:document.querySelectorAll('.unit-box').length,regions:document.querySelectorAll('.region-box').length})");
  assert.equal(counts.units,r.characters.length);assert.equal(counts.regions,r.hypotheses.reduce((n,h)=>n+h.regions.length,0));
  const overlay=await evaluate(`(()=>{const s=[...document.querySelectorAll('.unit-box')].find(e=>e.querySelector('title').textContent.startsWith(${JSON.stringify(a.id+' · ')}));const b=s.getBoundingClientRect();return [b.left,b.top,b.width,b.height];})()`);
  const b=a.bbox,g=a.geometry,dr=target.rect,expected=[dr[0]+b[0]*dr[2]/g.width,dr[1]+b[1]*dr[3]/g.height,(b[2]-b[0])*dr[2]/g.width,(b[3]-b[1])*dr[3]/g.height];
  const overlayError=Math.max(...expected.map((v,i)=>Math.abs(v-overlay[i])));assert(overlayError<.05,'Scaled highlighting differs');
  const center=[(b[0]+b[2])/2,(b[1]+b[3])/2];
  const pointerError=Math.max(...center.map((v,i)=>Math.abs(v-r.query.point[i])));
  assert(pointerError<=Math.max(g.width/dr[2],g.height/dr[3]),'Pointer error exceeds one CSS pixel');
  return {page:a.page,zoom,expected_id:a.id,unicode:a.text,image_pixels:target.natural,display_rect:target.rect,
    returned_characters:r.characters.length,matching_regions:counts.regions,source_only:r.status.source_only,
    response_json_utf8_bytes:Buffer.byteLength(JSON.stringify(r)),pointer_error_pdf_points:pointerError,
    overlay_max_error_css_pixels:overlayError,interaction_ms:elapsed,result:r};
}
const report={schema_version:'local-viewer-browser-smoke.1',reference_status:'source identities; not quality annotations',checks:[],complete:false};
try{
  browser=spawn(args.browser,['--headless=new','--remote-debugging-port=0','--remote-debugging-address=127.0.0.1',
    '--user-data-dir='+join(work,'isolated-profile'),'--no-first-run','--no-default-browser-check',
    '--disable-background-networking','--disable-component-update','--disable-sync','--disable-default-apps',
    '--disable-extensions','--disable-gpu','--disable-breakpad','--disable-client-side-phishing-detection',
    '--metrics-recording-only','--disk-cache-size=10485760',
    '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1, EXCLUDE localhost','about:blank'],{stdio:['ignore','ignore','pipe']});
  browser.stderr.on('data',b=>{browserLog+=b;});
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
  await command('Emulation.setDeviceMetricsOverride',{width:1280,height:1000,deviceScaleFactor:1,mobile:false});
  report.browser=await command('Browser.getVersion',{},null);
  const started=performance.now();
  server=spawn(args.python,['-B','-m','understanding_engine.viewer','--pdf',args.pdf,'--extraction',args.extraction,
    '--hybrid',args.hybrid,'--manifest',args.manifest,'--page',String(anchors[0].page)],{env:process.env,stdio:['ignore','pipe','pipe']});
  server.stdout.on('data',b=>{serverOut+=b;});server.stderr.on('data',b=>{serverErr+=b;});
  const url=await until(()=>serverOut.match(/Open locally: (http:\/\/127\.0\.0\.1:\d+\/#[^\s]+)/)?.[1],15000);
  const origin=new URL(url).origin;
  await command('Page.navigate',{url});
  const loading=await until(()=>evaluate("(()=>{const e=document.getElementById('loading');return e&&!e.hidden?e.textContent:null;})()"),10000);
  report.visible_initial_loading=loading;await screenshot('loading.png');
  await until(()=>evaluate("(()=>{const e=document.getElementById('workspace'),i=document.getElementById('page-image');return e&&!e.hidden&&document.getElementById('loading').hidden&&i.complete&&i.naturalWidth;})()"));
  report.startup_to_render_ms=performance.now()-started;
  assert.equal(await evaluate('location.hash'),'','Session token still exposed in address bar');
  for(const zoom of ['fit','75','150']){const checked=await clickAnchor(anchors[0],zoom);report.checks.push(checked);await screenshot('page-'+anchors[0].page+'-'+zoom+'.png');}
  const repeated=await clickAnchor(anchors[0],'150');assert.deepEqual(repeated.result,report.checks.at(-1).result);report.deterministic_repeat=true;
  await evaluate("(()=>{const d=[...document.querySelectorAll('.candidate')].find(d=>d.querySelector('summary').textContent.includes('predicted table'));if(!d)throw Error('Missing table candidate');d.open=true;document.getElementById('raw-json').textContent='';d.querySelector('button').click();})()");
  const region=await selection();assert.equal(region.query.kind,'region');
  assert.equal(await evaluate("document.querySelectorAll('.unit').length"),Math.min(20,region.characters.length));
  if(region.characters.length>20)await evaluate("document.getElementById('more-characters').click()");
  assert.equal(await evaluate("document.querySelectorAll('.unit').length"),Math.min(70,region.characters.length));
  report.progressive_region_inspection={characters:region.characters.length,response_json_utf8_bytes:Buffer.byteLength(JSON.stringify(region)),result:region};
  await screenshot('table-region-inspection.png');
  for(const anchor of anchors.slice(1)){
    if(anchor.page!==anchors[0].page)await choosePage(anchor.page);
    if(anchor.id){report.checks.push(await clickAnchor(anchor,'fit'));await screenshot('page-'+anchor.page+'-source-only.png');}
    else{
      const target=await evaluate(`(()=>{const r=document.getElementById('page-image').getBoundingClientRect();document.getElementById('raw-json').textContent='';return [r.left+${anchor.point[0]}*r.width/${anchor.geometry.width},r.top+${anchor.point[1]}*r.height/${anchor.geometry.height}];})()`);
      await click(...target);const r=await selection();assert(r.status.textless_visual&&r.characters.length===0);report.textless_visual_result=r;await screenshot('textless-visual.png');
    }
  }
  assert(requests.every(u=>u.startsWith(origin+'/')||u.startsWith('blob:'+origin+'/')),'Unexpected external page request');
  assert.equal(errors.length,0,'Browser console/network errors: '+JSON.stringify(errors));
  report.page_request_count=requests.length;report.external_page_requests=0;report.browser_errors=errors;report.complete=true;
}catch(e){report.failure=e.stack;process.exitCode=1;}
finally{
  if(server&&server.exitCode===null){server.kill('SIGINT');await Promise.race([new Promise(r=>server.once('exit',r)),sleep(10000)]);}
  if(ws?.readyState===WebSocket.OPEN){try{await command('Browser.close',{},null);}catch{}ws.close();}
  if(browser&&browser.exitCode===null)await Promise.race([new Promise(r=>browser.once('exit',r)),sleep(5000)]);
  report.server_exit_code=server?.exitCode;report.server_signal=server?.signalCode;
  await writeFile(join(work,'browser-smoke.json'),JSON.stringify(report,null,2)+'\n');
  await writeFile(join(work,'browser.stderr.log'),browserLog);await writeFile(join(work,'server.stderr.log'),serverErr);
  // Never persist the secret session URL/token.
  console.log(JSON.stringify({complete:report.complete,checks:report.checks.length,failure:report.failure,work}));
}
