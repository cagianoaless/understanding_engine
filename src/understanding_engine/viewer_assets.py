"""Packaged, fixed local assets: no build system or runtime file-serving root."""

HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Understanding Engine · Local PDF Viewer</title><link rel="stylesheet" href="/viewer.css"><link rel="icon" href="/favicon.svg" type="image/svg+xml">
<script type="module" src="/viewer.js"></script></head><body>
<header><div><span class="eyebrow">UNDERSTANDING ENGINE · OFFLINE</span><h1>Source inspection</h1></div>
<p>Original PDF characters. Structural labels are hypotheses.</p></header>
<div id="loading" role="status">Loading verified local document…</div>
<main id="workspace" hidden><section class="reader" aria-label="PDF page">
<nav><button id="previous" aria-label="Previous page">←</button><label>Page <select id="page"></select></label><button id="next" aria-label="Next page">→</button>
<label>Zoom <select id="zoom"><option value="fit">Fit width</option><option value="75">75%</option><option value="100">100%</option><option value="125">125%</option><option value="150">150%</option><option value="200">200%</option></select></label>
<span id="page-mode" class="badge"></span></nav>
<div id="stage"><div id="paper"><img id="page-image" alt="Verified original PDF page" draggable="false"><svg id="overlay" preserveAspectRatio="none" aria-hidden="true"></svg></div></div>
<p class="legend"><span class="char-key">■ Source units</span> <span class="structure-key">□ Structure 0.2</span> <span class="docling-key">□ Docling</span> · All matching regions are outlined.</p>
</section><aside aria-label="Selection inspection"><h2>Inspect a source element</h2>
<p id="hint">Click the page to discover every matching source unit and region. No candidate is chosen automatically.</p>
<p class="notice">Source text follows backend extraction order, not verified human reading order. Reading-order hypotheses may be unresolved. Formula labels are not verified LaTeX transcriptions.</p>
<p id="error" role="alert" hidden></p><div id="selection" hidden>
<div id="badges"></div><h3>Original source text</h3><pre id="source-text"></pre><p id="selection-count"></p>
<details><summary>Original characters and source IDs</summary><div id="characters"></div><button id="more-characters">Show more source units</button></details>
<h3 id="candidate-count"></h3><div id="candidates"></div><button id="more-candidates">Show more candidates</button>
<details id="raw-details"><summary>Complete compact SelectionResult (nothing omitted)</summary><pre id="raw-json"></pre></details>
</div></aside></main></body></html>'''

CSS = r''':root{font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#152a39;background:#edf1f3;font-size:14px}*{box-sizing:border-box}[hidden]{display:none!important}body{margin:0}header{display:flex;align-items:center;justify-content:space-between;gap:24px;background:#fff;padding:18px 26px;border-bottom:1px solid #d4dfe4}h1{font-size:23px;margin:4px 0 0;font-weight:650}header p{max-width:400px;color:#516674}.eyebrow{font-size:10px;letter-spacing:.14em;color:#536d78}#loading{padding:40px;line-height:1.6}main{display:grid;grid-template-columns:minmax(320px,1fr) 410px;gap:18px;padding:18px;height:calc(100dvh - 109px)}.reader{min-width:0;display:flex;flex-direction:column}nav{display:flex;align-items:center;gap:10px;padding:10px 12px;background:#fff;border:1px solid #d4dfe4;border-radius:8px 8px 0 0;flex-wrap:wrap}button,select{font:inherit;border:1px solid #bacbd4;border-radius:5px;background:#fff;color:#152a39;padding:6px 10px}button{cursor:pointer}button:hover{background:#eef5f8}button:disabled{opacity:.4;cursor:default}label{display:flex;align-items:center;gap:6px}#stage{overflow:auto;flex:1;min-height:0;padding:18px;background:#dce3e7;border:1px solid #c5d2d9;border-top:0}#paper{position:relative;margin:0 auto;background:white;box-shadow:0 2px 9px #18374826}#page-image{display:block;width:100%;height:auto;padding:0;border:0;cursor:crosshair;user-select:none;transform:none}#overlay{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;overflow:hidden}.unit-box{fill:#fff07888;stroke:#9c7300;stroke-width:.6;vector-effect:non-scaling-stroke}.region-box{fill:none;stroke-width:1.5;vector-effect:non-scaling-stroke}.region-box.structure{stroke:#275fbe;stroke-dasharray:4 2}.region-box.docling{stroke:#b04a15}.legend{font-size:11px;color:#526875;margin:9px 0 0}.char-key{color:#846100}.structure-key{color:#275fbe}.docling-key{color:#b04a15}aside{background:white;border:1px solid #d4dfe4;border-radius:8px;padding:20px;overflow:auto;min-width:0}h2{font-size:19px;margin:0 0 10px}h3{font-size:13px;margin:20px 0 8px}p{line-height:1.5}.notice{font-size:12px;line-height:1.5;padding:10px 12px;background:#fff8e9;border-left:3px solid #c49a35;color:#665224}.badge{display:inline-block;border-radius:20px;background:#e9f0f4;color:#385769;font-size:11px;padding:4px 8px;margin:2px}.warning{background:#fff0d8;color:#78520d}.candidate{border-top:1px solid #dce4e8;padding:10px 0}.candidate summary{cursor:pointer;font-size:12px;font-weight:600;line-height:1.6}.candidate pre{font-size:10px}details{margin:12px 0}details>summary{cursor:pointer;line-height:1.6}pre{font:11px/1.6 ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre-wrap;overflow-wrap:anywhere;max-width:100%}#source-text{font-size:15px;padding:12px;background:#f2f6f8;border-radius:5px;min-height:40px}#error{background:#fff0ec;color:#8b3219;padding:12px;border-radius:5px}.unit{padding:8px 0;border-bottom:1px solid #e8edef;font:10px/1.5 ui-monospace,monospace;overflow-wrap:anywhere}.buttons{display:flex;gap:6px;margin:8px 0}.buttons button{font-size:11px}#selection-count,#hint{font-size:12px;color:#526875}#raw-json{font-size:10px}@media(max-width:900px){main{grid-template-columns:1fr;height:auto}.reader{height:80dvh}aside{max-height:85dvh}header{align-items:flex-start}header p{display:none}}'''

COORDINATES_JS = r'''
function finite(v,n){if(!Array.isArray(v)||v.length!==n||!v.every(x=>typeof x==="number"&&Number.isFinite(x)))throw Error("Invalid coordinate vector");}
function frame(geometry){
  const {width:w,height:h}=geometry;
  if(!Number.isFinite(w)||!Number.isFinite(h)||w<=0||h<=0||geometry.rotation!==0||geometry.raw_rotation!==0||geometry.user_unit!==1)throw Error("Unsupported source frame");
  for(const key of ["bbox","mediabox","cropbox","raw_mediabox","pdfminer_layout_bbox"]){finite(geometry[key],4);if(geometry[key].some((v,i)=>v!==[0,0,w,h][i]))throw Error("Unsupported crop/media frame");}
  if(geometry.raw_cropbox!==null&&geometry.raw_cropbox.some((v,i)=>v!==[0,0,w,h][i]))throw Error("Unsupported raw crop");
}
export function pointerToPdf(geometry,pixels,rect,pointer){
  frame(geometry);finite(pixels,2);finite(rect,4);finite(pointer,2);
  const {width:w,height:h}=geometry;
  if(!pixels.every(v=>Number.isInteger(v)&&v>0&&v<=8192)||rect[2]<=0||rect[3]<=0)throw Error("Invalid image dimensions");
  const x=pointer[0]-rect[0],y=pointer[1]-rect[1];
  if(x<0||y<0||x>rect[2]||y>rect[3])throw Error("Pointer outside image");
  return [(x*pixels[0]/rect[2])*w/pixels[0],(y*pixels[1]/rect[3])*h/pixels[1]];
}
export function boxToCss(geometry,box,rect){
  frame(geometry);finite(box,4);finite(rect,4);
  if(rect[2]<=0||rect[3]<=0||box[0]>box[2]||box[1]>box[3])throw Error("Invalid overlay box");
  return [rect[0]+box[0]*rect[2]/geometry.width,rect[1]+box[1]*rect[3]/geometry.height,
    (box[2]-box[0])*rect[2]/geometry.width,(box[3]-box[1])*rect[3]/geometry.height];
}
'''

JS = r'''
import {pointerToPdf} from "/coordinates.js";
import {createFormulaExplorer} from "/formula-explorer.js";
const $=id=>document.getElementById(id),token=new URLSearchParams(location.hash.slice(1)).get("token");
history.replaceState(null,"",location.pathname);
let formulaExplorer=null;
let documentInfo=null,current=null,result=null,generation=0,selectionSerial=0,blobURL=null,charLimit=20,candidateLimit=12;
function error(message){$("error").hidden=false;$("error").textContent=message;}
async function api(path,body){
  const response=await fetch(path,{method:body?"POST":"GET",headers:{Authorization:"Bearer "+token,...(body?{"Content-Type":"application/json"}:{})},body:body?JSON.stringify(body):undefined,cache:"no-store",credentials:"omit"});
  if(!response.ok){let d;try{d=await response.json();}catch{d={error:"Local request failed"};}throw Error(d.error);}
  return response;
}
function zoom(){if(!current)return;const z=$("zoom").value;$("paper").style.width=(z==="fit"?Math.min(current.render.width,Math.max(1,$("stage").clientWidth-36)):current.render.width*Number(z)/100)+"px";}
function clear(){selectionSerial++;formulaExplorer?.reset(false);result=null;$("selection").hidden=true;$("overlay").replaceChildren();$("error").hidden=true;$("hint").hidden=false;$("raw-json").textContent="";}
async function page(number){
  const gen=++generation;selectionSerial++;current=null;clear();$("loading").hidden=false;$("loading").textContent="Rendering verified page "+number+"…";
  try{
    const meta=await (await api("/api/page/"+number)).json();
    const blob=await (await api("/api/page/"+number+"/image")).blob();
    if(gen!==generation)return;
    const url=URL.createObjectURL(blob),old=blobURL;blobURL=url;$("page-image").src=url;await $("page-image").decode();if(old)URL.revokeObjectURL(old);
    if(gen!==generation)return;
    if(meta.pdf_sha256!==documentInfo.pdf_sha256||meta.source_canonical_sha256!==documentInfo.source_canonical_sha256||$("page-image").naturalWidth!==meta.render.width||$("page-image").naturalHeight!==meta.render.height)throw Error("Rendered image identity/dimensions differ");
    current=meta;$("overlay").setAttribute("viewBox",`0 0 ${meta.geometry.width} ${meta.geometry.height}`);
    $("page").value=String(number);$("page-mode").textContent=meta.source_only?"Source only":"Layout hypotheses available";
    $("previous").disabled=number===1;$("next").disabled=number===documentInfo.page_count;
    zoom();$("stage").scrollTop=0;$("stage").scrollLeft=0;$("loading").hidden=true;drawSelectionOverlay();
  }catch(e){if(gen===generation){$("loading").hidden=true;error(e.message);}}
}
function rect(box,kind,title){
  const node=document.createElementNS("http://www.w3.org/2000/svg","rect");
  for(const [k,v] of Object.entries({x:box[0],y:box[1],width:box[2]-box[0],height:box[3]-box[1],class:kind}))node.setAttribute(k,v);
  const t=document.createElementNS(node.namespaceURI,"title");t.textContent=title;node.append(t);return node;
}
function show(data){
  result=data;charLimit=20;candidateLimit=12;$("selection").hidden=false;$("hint").hidden=true;$("error").hidden=true;
  $("source-text").textContent=data.source_text;
  $("selection-count").textContent=data.characters.length+" original source units · "+data.text_role+(data.query.basis?" · basis: "+data.query.basis:"");
  $("badges").replaceChildren();
  for(const [key,value] of Object.entries(data.status))if(value===true){const b=document.createElement("span");b.className="badge warning";b.textContent=key;$("badges").append(b);}
  if(data.status.source_only){const b=document.createElement("p");b.textContent="No available layout on this page. Original source selection remains available.";$("badges").append(b);}
  drawSelectionOverlay();
  characters();candidates();$("raw-json").textContent="";if($("raw-details").open)raw();
}
function drawSelectionOverlay(){
  const overlay=$("overlay");overlay.replaceChildren();
  if(result&&!formulaExplorer?.active){
    for(const h of result.hypotheses)for(const r of h.regions)overlay.append(rect(r.bbox,"region-box "+(h.provider==="docling"?"docling":"structure"),h.provider+" · predicted "+r.label));
    for(const c of result.characters)overlay.append(rect(c.bbox,"unit-box",c.id+" · "+c.text));
  }
  formulaExplorer?.draw(overlay);
}
function characters(){
  $("characters").replaceChildren();
  for(const c of result.characters.slice(0,charLimit)){const d=document.createElement("div");d.className="unit";d.textContent=JSON.stringify(c.text)+" · "+c.id+"\nbox "+JSON.stringify(c.bbox);$("characters").append(d);}
  $("more-characters").hidden=charLimit>=result.characters.length;
}
function candidates(){
  const all=result.hypotheses.flatMap(h=>h.regions.map(r=>({h,r})));$("candidates").replaceChildren();
  $("candidate-count").textContent=all.length+" structural candidates (all outlined)";
  for(const {h,r} of all.slice(0,candidateLimit)){
    const d=document.createElement("details"),s=document.createElement("summary");d.className="candidate";
    s.textContent=h.provider+" "+h.provider_version+" · predicted "+r.label+" · "+r.association_status;d.append(s);
    const buttons=document.createElement("div");buttons.className="buttons";
    for(const basis of ["geometric","native"]){const b=document.createElement("button");b.textContent=basis==="geometric"?"Inspect region":"Native membership";b.onclick=()=>region(h.evidence_id,r.region_id,basis);buttons.append(b);}
    const pre=document.createElement("pre");d.ontoggle=()=>{if(d.open&&!pre.textContent)pre.textContent=JSON.stringify({region:r,hierarchy:h.hierarchy,reading_order:h.reading_order},null,2);};d.append(buttons,pre);$("candidates").append(d);
  }
  $("more-candidates").hidden=candidateLimit>=all.length;
}
function raw(){if(result)$("raw-json").textContent=JSON.stringify(result,null,2);}
function identity(){return {pdf_sha256:current.pdf_sha256,source_canonical_sha256:current.source_canonical_sha256};}
async function region(evidenceId,regionId,basis){
  if(!current)return;const gen=generation,serial=++selectionSerial,number=current.page_number;
  try{const d=await(await api("/api/select",{...identity(),query:{kind:"region",page_number:number,evidence_id:evidenceId,region_id:regionId,basis}})).json();if(gen===generation&&serial===selectionSerial&&d.page_number===number)show(d);}catch(e){if(gen===generation&&serial===selectionSerial)error(e.message);}
}
$("page-image").addEventListener("click",async event=>{
  if(!current)return;const gen=generation,serial=++selectionSerial,meta=current,bounds=event.currentTarget.getBoundingClientRect();
  const display=[bounds.left,bounds.top,bounds.width,bounds.height],pointer=[event.clientX,event.clientY],pixels=[event.currentTarget.naturalWidth,event.currentTarget.naturalHeight];
  try{
    const localPoint=pointerToPdf(meta.geometry,pixels,display,pointer);
    const d=await(await api("/api/click",{...identity(),page_number:meta.page_number,render_sha256:meta.render.sha256,image_pixels:pixels,display_rect:display,pointer})).json();
    if(gen!==generation||serial!==selectionSerial||d.page_number!==meta.page_number)return;
    if(d.query.point.some((v,i)=>Math.abs(v-localPoint[i])>1e-9))throw Error("Browser/PDF coordinate verification failed");
    show(d);formulaExplorer?.click(localPoint);
  }catch(e){if(gen===generation&&serial===selectionSerial)error(e.message);}
});
$("page").onchange=()=>page(Number($("page").value));$("previous").onclick=()=>current&&page(current.page_number-1);$("next").onclick=()=>current&&page(current.page_number+1);
$("zoom").onchange=zoom;window.addEventListener("resize",zoom);
$("more-characters").onclick=()=>{charLimit+=50;characters();};$("more-candidates").onclick=()=>{candidateLimit+=20;candidates();};$("raw-details").ontoggle=()=>{$("raw-details").open&&raw();};
async function initialize(){
  if(!token){$("loading").textContent="Open the session URL printed by the local Python server. The token is kept only in page memory; reopening that URL is required after a reload.";return;}
  try{
    const d=await(await api("/api/status")).json();$("loading").textContent=d.phase+"…";
    if(d.state==="failed")throw Error(d.error);
    if(d.state!=="ready"){setTimeout(initialize,500);return;}
    documentInfo=d;
    if(d.formula_demo)formulaExplorer=await createFormulaExplorer({api,documentInfo:d,getPage:()=>current,navigate:page,onChange:drawSelectionOverlay,onReset:clear,rect});
    for(const p of d.pages){const option=document.createElement("option");option.value=p.page_number;option.textContent=p.page_number+(p.source_only?" · source only":" · layout");option.disabled=!p.spatial_supported;$("page").append(option);}
    $("workspace").hidden=false;await page(d.initial_page);
  }catch(e){$("loading").textContent=e.message;}
}
initialize();
'''

ASSETS = {
    '/': ('text/html; charset=utf-8', HTML.encode()),
    '/viewer.css': ('text/css; charset=utf-8', CSS.encode()),
    '/viewer.js': ('text/javascript; charset=utf-8', JS.encode()),
    '/coordinates.js': ('text/javascript; charset=utf-8', COORDINATES_JS.encode()),
    '/favicon.svg': ('image/svg+xml', b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><rect x="3" y="2" width="18" height="20" rx="3" fill="#245970"/><path d="M7 8h10M7 12h10M7 16h6" stroke="white" stroke-width="2"/></svg>'),
}

# Formula code is a fixed local asset; it is activated only after an opted-in context reports it.
from .viewer_formula_assets import CSS as FORMULA_CSS, JS as FORMULA_JS
ASSETS['/viewer.css'] = ('text/css; charset=utf-8', (CSS+FORMULA_CSS).encode())
ASSETS['/formula-explorer.js'] = ('text/javascript; charset=utf-8', FORMULA_JS.encode())
