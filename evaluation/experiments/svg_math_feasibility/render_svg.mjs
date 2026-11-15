// Optional measured rendering with an existing browser/Node. No network assets.
// Input is a single XML page already accepted by svg_inspector.xml_root.
import {spawn} from 'node:child_process';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {join} from 'node:path';
import assert from 'node:assert/strict';
const [browserPath,inputPath,out]=process.argv.slice(2);assert(browserPath&&inputPath&&out);
await mkdir(out);const input=JSON.parse(await readFile(inputPath,'utf8'));
assert(input.safety_checked&&input.tags.every(t=>['svg','text','tspan','path'].includes(t)),'Render only the checked flat text/path page');
let browser,ws,session,id=0,stderr='';const pending=new Map(),requests=[],errors=[];
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
function call(method,params={},sid=session){return new Promise((resolve,reject)=>{
 const n=++id,timer=setTimeout(()=>{pending.delete(n);reject(Error(method+' timeout'));},10000);
 pending.set(n,{resolve,reject,timer});ws.send(JSON.stringify({id:n,method,params,...(sid?{sessionId:sid}:{})}));
});}
async function evaluate(expression){const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});assert(!r.exceptionDetails,JSON.stringify(r.exceptionDetails));return r.result.value;}
let result={complete:false};
try{
 browser=spawn(browserPath,['--headless=new','--remote-debugging-port=0','--remote-debugging-address=127.0.0.1',
 '--user-data-dir='+join(out,'isolated-profile'),'--no-first-run','--no-default-browser-check','--disable-background-networking',
 '--disable-component-update','--disable-sync','--disable-default-apps','--disable-extensions','--disable-gpu','--disable-breakpad',
 '--disable-client-side-phishing-detection','--metrics-recording-only','--host-resolver-rules=MAP * ~NOTFOUND','about:blank'],{stdio:['ignore','ignore','pipe']});
 browser.stderr.on('data',b=>stderr+=b);
 let marker;
 for(let n=0;n<100;n++){try{marker=await readFile(join(out,'isolated-profile','DevToolsActivePort'),'utf8');break;}catch{await sleep(100);}}
 assert(marker,'Browser did not expose owned debugging endpoint');const [port,path]=marker.trim().split('\n');
 ws=new WebSocket('ws://127.0.0.1:'+port+path);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j;});
 ws.onmessage=e=>{const d=JSON.parse(e.data);if(d.id){const p=pending.get(d.id);if(p){clearTimeout(p.timer);pending.delete(d.id);d.error?p.reject(Error(JSON.stringify(d.error))):p.resolve(d.result);}}else{
  if(d.method==='Network.requestWillBeSent')requests.push(d.params.request.url.startsWith('data:')?'data:local-payload':d.params.request.url);
  if(d.method==='Runtime.exceptionThrown')errors.push(d.params.exceptionDetails);
 }};
 const target=await call('Target.createTarget',{url:'about:blank'},null);session=(await call('Target.attachToTarget',{targetId:target.targetId,flatten:true},null)).sessionId;
 for(const name of ['Page','Runtime','Network','DOM','CSS'])await call(name+'.enable');
 await call('Emulation.setDeviceMetricsOverride',{width:612,height:792,deviceScaleFactor:3,mobile:false});
 const html='<html><head><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; script-src \'none\'; img-src \'none\'; font-src \'none\'"></head><body style="margin:0;background:white">'+Buffer.from(input.svg_base64,'base64').toString('utf8')+'</body></html>';
 await call('Page.navigate',{url:'data:text/html;base64,'+Buffer.from(html).toString('base64')});
 await sleep(500);
 const glyphs=await evaluate(`(()=>{const root=document.querySelector('svg'),all=[];
 function visit(e,path){if(e.tagName==='tspan'&&e.textContent){let offsets=0;const chars=Array.from(e.textContent);for(let i=0;i<chars.length;i++){
  const p=e.getStartPositionOfChar(offsets),b=e.getExtentOfChar(offsets),m=e.getCTM();const tr=(x,y)=>[m.a*x+m.c*y+m.e,m.b*x+m.d*y+m.f];
  const corners=[tr(b.x,b.y),tr(b.x+b.width,b.y),tr(b.x,b.y+b.height),tr(b.x+b.width,b.y+b.height)];
  all.push({id:path+':u'+i,text:chars[i],anchor:tr(p.x,p.y),bbox:[Math.min(...corners.map(p=>p[0])),Math.min(...corners.map(p=>p[1])),Math.max(...corners.map(p=>p[0])),Math.max(...corners.map(p=>p[1]))]});offsets+=chars[i].length;}}
  [...e.children].forEach((c,i)=>visit(c,path+'/'+i));}visit(root,'svg');return all;})()`);
 const {root}=await call('DOM.getDocument');const {nodeIds}=await call('DOM.querySelectorAll',{nodeId:root.nodeId,selector:'svg text'});
 const replacementIndices=await evaluate("[...document.querySelectorAll('svg text')].map((t,i)=>t.textContent.includes('�')?i:-1).filter(i=>i>=0)");
 const fonts=[];for(const n of [...new Set([0,1,...replacementIndices])])fonts.push({text_index:n,...await call('CSS.getPlatformFontsForNode',{nodeId:nodeIds[n]})});
 const image=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await writeFile(join(out,'svg-page4.png'),Buffer.from(image.data,'base64'));
 assert(requests.every(r=>r==='data:local-payload'),'External page request');assert.equal(errors.length,0);
 result={complete:true,browser:await call('Browser.getVersion',{},null),viewport:[612,792],device_scale:3,glyphs,fonts,requests,errors};
}catch(e){result.error=e.stack;process.exitCode=1;}
finally{
 if(ws?.readyState===WebSocket.OPEN){try{await call('Browser.close',{},null);}catch{}ws.close();}
 if(browser&&browser.exitCode===null)await Promise.race([new Promise(r=>browser.once('exit',r)),sleep(5000)]);
 await writeFile(join(out,'render.json'),JSON.stringify(result,null,2)+'\n');await writeFile(join(out,'browser.stderr.log'),stderr);
 console.log(JSON.stringify({complete:result.complete,error:result.error,glyphs:result.glyphs?.length}));
}
