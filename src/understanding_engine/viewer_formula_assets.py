"""Opt-in formula panel: fixed assets, text-only model display, crop-only overlay."""

CSS = r'''
#formula-explorer{border-bottom:2px solid #c5d8de;padding-bottom:20px;margin-bottom:22px}
#formula-explorer h2{font-size:18px}#formula-explorer .formula-actions{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}
#formula-latex{padding:12px;background:#f1f5fa;font-size:12px;border-radius:5px;white-space:pre-wrap}
#formula-latex mark{background:#ffe086;color:#142a39;outline:1px solid #bd870a}
#formula-tree{font-size:11px;border-left:2px solid #dce6eb;padding-left:8px;max-height:300px;overflow:auto}
#formula-tree details{margin:5px 0 5px 10px}#formula-tree summary{line-height:1.4}
#formula-tree button{padding:3px 5px;font-size:11px;text-align:left;border-color:transparent}
#formula-tree button[aria-pressed="true"]{background:#fff0bd;border-color:#c69b32}
#formula-node pre{font-size:10px;max-height:240px;overflow:auto}
#formula-status{font-size:12px;font-weight:600}#formula-error{color:#8b3219;background:#fff0ec;padding:8px}
.formula-crop-box{fill:#0e948815;stroke:#087f75;stroke-width:2;stroke-dasharray:7 3;vector-effect:non-scaling-stroke}
.formula-crop-box.active{fill:#0e948825;stroke-dasharray:none}
'''

JS = r'''
export function latexSlices(text, span){
  const points=Array.from(text);
  if(!Array.isArray(span)||span.length!==2||!span.every(Number.isInteger)||span[0]<0||span[0]>span[1]||span[1]>points.length)throw Error("Invalid Unicode code-point span");
  return {before:points.slice(0,span[0]).join(""),selected:points.slice(span[0],span[1]).join(""),after:points.slice(span[1]).join("")};
}
function element(tag,text,attributes={}){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;for(const [key,value] of Object.entries(attributes))e.setAttribute(key,value);return e;}
function title(text){return text.replaceAll("_"," ").replace(/^./,c=>c.toUpperCase());}
export async function createFormulaExplorer({api,documentInfo,getPage,navigate,onChange,onReset,rect}){
  const payload=await(await api("/api/formula")).json(),graph=payload.graph,provenance=graph.provenance;
  if(provenance.pdf_sha256!==documentInfo.pdf_sha256||payload.pdf_overlay!=="whole_formula_crop_only")throw Error("Formula/document identity differs");
  const byId=new Map(graph.nodes.map(n=>[n.id,n]));
  let active=false,serial=0;
  const panel=element("section",undefined,{id:"formula-explorer","aria-label":"Formula Explorer"});
  const heading=element("h2","Formula Explorer · syntax hypothesis");
  const warning=element("p","Model LaTeX is an unverified transcription, not authoritative PDF text. PDF highlighting shows the WHOLE formula crop only. No symbol/subexpression PDF alignment is available.",{class:"notice",id:"formula-provenance-warning"});
  const status=element("p",`Parsing: ${graph.status.parsing} · acceptance: ${graph.status.acceptance} · mathematical correctness: ${graph.evidence_status.mathematical_correctness}`,{id:"formula-status"});
  if(graph.status.acceptance==="reject")status.textContent+=" · REJECTED AS A COMPLETE FORMULA; parsed fragments only";
  const introduction=element("p",`${provenance.prediction_id} · ${provenance.model_name} · PDF page ${provenance.page_number}. Select the outlined crop or use Go to formula.`,{id:"formula-introduction"});
  const actions=element("div",undefined,{class:"formula-actions"});
  const go=element("button","Go to formula",{id:"formula-go",type:"button"});
  const resetButton=element("button","Reset selection",{id:"formula-reset",type:"button"});
  actions.append(go,resetButton);
  const error=element("p","",{id:"formula-error",role:"alert"});error.hidden=true;
  const body=element("div",undefined,{id:"formula-content"});body.hidden=true;
  const latex=element("pre",graph.input.latex,{id:"formula-latex","aria-label":"Exact model-generated cleaned LaTeX"});
  const raw=element("details"),rawTitle=element("summary","Original raw model output (diagnostic)");raw.append(rawTitle,element("pre",graph.input.raw_model_output??"Unavailable"));
  const graphDiagnostics=element("details"),diagnosticTitle=element("summary","Whole-expression diagnostics and provenance");
  graphDiagnostics.append(diagnosticTitle,element("pre",JSON.stringify({status:graph.status,diagnostics:graph.diagnostics,evidence_status:graph.evidence_status,provenance},null,2)));
  const treeActions=element("div",undefined,{class:"formula-actions"});
  const expand=element("button","Expand all",{id:"formula-expand",type:"button"}),collapse=element("button","Collapse all",{id:"formula-collapse",type:"button"});treeActions.append(expand,collapse);
  const tree=element("div",undefined,{id:"formula-tree","aria-label":"Formula syntax tree"});
  const nodePanel=element("section",undefined,{id:"formula-node","aria-label":"Selected syntax node"});
  const returnButton=element("button","Return to PDF crop",{id:"formula-return",type:"button"});
  body.append(element("h3","Exact model LaTeX · unverified hypothesis"),latex,raw,graphDiagnostics,treeActions,tree,nodePanel,returnButton);
  panel.append(heading,warning,status,introduction,actions,error,body);
  document.querySelector("aside").prepend(panel);
  function fail(message){error.hidden=false;error.textContent=message;}
  function reset(notify=true){
    serial++;active=false;body.hidden=true;error.hidden=true;latex.textContent=graph.input.latex;nodePanel.replaceChildren(element("p","No syntax node selected."));
    for(const button of tree.querySelectorAll("button"))button.setAttribute("aria-pressed","false");
    if(notify)onChange();
  }
  async function select(identifier){
    if(!active||getPage()?.page_number!==provenance.page_number)return;
    const request=++serial;
    try{
      const data=await(await api("/api/formula/node",{pdf_sha256:documentInfo.pdf_sha256,source_canonical_sha256:documentInfo.source_canonical_sha256,formula_id:graph.id,node_id:identifier})).json();
      if(request!==serial||!active)return;
      if(data.formula_id!==graph.id||data.node.id!==identifier||data.pdf_overlay!=="whole_formula_crop_only")throw Error("Wrong formula node identity");
      const slices=latexSlices(graph.input.latex,data.node.character_span);
      if(slices.selected!==data.latex_substring||slices.selected!==data.node.source_text)throw Error("Exact LaTeX substring differs");
      const mark=element("mark",slices.selected,{id:"formula-latex-highlight"});
      latex.replaceChildren(document.createTextNode(slices.before),mark,document.createTextNode(slices.after));
      for(const button of tree.querySelectorAll("button"))button.setAttribute("aria-pressed",String(button.dataset.nodeId===identifier));
      nodePanel.replaceChildren(element("h3",`Selected: ${title(data.node.type)} · ${data.node.status} syntax · unverified model${graph.status.acceptance==="reject"?" · fragment of REJECTED formula":""}`),
        element("p",`Unicode code points [${data.node.character_span.join(", ")}); tokens [${data.node.token_span.join(", ")}). Substring highlight is in model LaTeX only.`),
        element("pre",data.latex_substring,{id:"formula-node-substring"}),
        element("pre",JSON.stringify({node_id:identifier,child_roles:data.node.children,status:data.node.status,diagnostics:data.node.diagnostics,
          token_span_complete:data.node.token_span_complete,tokens:data.tokens,whole_expression_status:data.whole_expression_status,
          pdf_overlay:data.pdf_overlay,symbol_pdf_alignment:data.symbol_pdf_alignment},null,2),{id:"formula-node-details"}));
      error.hidden=true;onChange();
    }catch(e){if(request===serial)fail(e.message);}
  }
  function entry(identifier,role,depth){
    const node=byId.get(identifier);if(!node)throw Error("Missing formula tree node");
    const details=element("details");details.open=depth<3;details.dataset.nodeType=node.type;
    const summary=element("summary"),button=element("button",`${title(role)} · ${title(node.type)} · ${node.status}`,{type:"button","aria-pressed":"false"});
    button.dataset.nodeId=identifier;button.dataset.nodeType=node.type;button.dataset.childRole=role;
    button.addEventListener("click",event=>{event.preventDefault();event.stopPropagation();select(identifier);});
    summary.append(button);details.append(summary);
    for(const edge of node.children)details.append(entry(edge.node_id,edge.role,depth+1));
    return details;
  }
  tree.append(entry(graph.root_id,"root",0));
  function activate(){if(getPage()?.page_number!==provenance.page_number)return;active=true;body.hidden=false;error.hidden=true;onChange();}
  async function goToCrop(){
    try{
      if(getPage()?.page_number!==provenance.page_number)await navigate(provenance.page_number);
      activate();document.getElementById("formula-crop-overlay")?.scrollIntoView({block:"center",inline:"nearest"});
    }catch(e){fail(e.message);}
  }
  go.addEventListener("click",goToCrop);returnButton.addEventListener("click",goToCrop);
  resetButton.addEventListener("click",()=>{reset(false);onReset();onChange();});
  expand.addEventListener("click",()=>{for(const d of tree.querySelectorAll("details"))d.open=true;});
  collapse.addEventListener("click",()=>{for(const d of tree.querySelectorAll("details"))d.open=false;});
  reset(false);
  return {
    get active(){return active;},reset,
    contains(point){const b=provenance.bbox;return getPage()?.page_number===provenance.page_number&&point[0]>=b[0]&&point[0]<=b[2]&&point[1]>=b[1]&&point[1]<=b[3];},
    click(point){if(this.contains(point))activate();else reset();},
    draw(overlay){
      if(getPage()?.page_number!==provenance.page_number)return;
      const crop=rect(provenance.bbox,"formula-crop-box"+(active?" active":""),"Whole original formula crop; no symbol-level PDF mapping");
      crop.id="formula-crop-overlay";crop.dataset.pdfScope="whole_formula_crop";overlay.append(crop);
    }
  };
}
'''
