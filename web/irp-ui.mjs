/** iRp™ v1 client: inert SVG renderer and explicit simulation approval. */
import {validateBlueprint,SAMPLE_BLUEPRINT,sceneFromBlueprint,previewExecution,executeApproved,IRP_MAX_BYTES} from "./irp.mjs";

const SVG="http://www.w3.org/2000/svg";
const shades={
  civic:["#7bfff1","#0b949a"],energy:["#5be9fa","#1274b0"],health:["#a0fce8","#398b93"],
  agriculture:["#7ef3a9","#1b906b"],habitat:["#b5edff","#337d9f"],transport:["#50dded","#195d91"]
};
function S(tag,attrs={},text) {
  const node=document.createElementNS(SVG,tag);
  for(const [k,v] of Object.entries(attrs))node.setAttribute(k,String(v));
  if(text!==undefined)node.textContent=String(text);
  return node;
}
const el=id=>document.getElementById(id);

function background(svg,theme) {
  const colors={ocean:["#03111d","#0c3c4c","#1c7a81"],forest:["#041a19","#0d473c","#227b5b"],
    desert:["#1b1720","#4b374c","#c29181"],night:["#080d23","#173358","#4679ab"]};
  const [night,haze,water]=colors[theme];
  const defs=S("defs"),sky=S("linearGradient",{id:"irp-sky",x1:0,y1:0,x2:0,y2:1}),
        sea=S("linearGradient",{id:"irp-sea",x1:0,y1:0,x2:1,y2:1});
  sky.append(S("stop",{offset:"0%","stop-color":night}),S("stop",{offset:"100%","stop-color":haze}));
  sea.append(S("stop",{offset:"0%","stop-color":haze}),S("stop",{offset:"100%","stop-color":water}));
  defs.append(sky,sea);svg.append(defs);
  svg.append(S("rect",{x:0,y:0,width:900,height:485,fill:"url(#irp-sky)"}));
  for(let y=0;y<=485;y+=32)svg.append(S("line",{x1:0,y1:y,x2:900,y2:y,stroke:"#6cf5e3","stroke-opacity":".07"}));
  for(let x=0;x<=900;x+=40)svg.append(S("line",{x1:x,y1:0,x2:x,y2:485,stroke:"#6cf5e3","stroke-opacity":".06"}));
  svg.append(S("ellipse",{cx:450,cy:325,rx:393,ry:141,fill:"url(#irp-sea)",stroke:"#53e9de","stroke-opacity":".5","stroke-width":2}));
  svg.append(S("ellipse",{cx:450,cy:327,rx:326,ry:112,fill:"none",stroke:"#baffef","stroke-opacity":".14","stroke-dasharray":"6 11"}));
  svg.append(S("path",{d:"M55 313Q450 -105 846 313",fill:"none",stroke:"#43dfdf","stroke-opacity":".19"}));
  svg.append(S("text",{x:26,y:37,fill:"#abf6ea","font-family":"ui-monospace,monospace","font-size":12,"letter-spacing":2},"iRp™ // SYNTHETIC WORLD"));
  svg.append(S("text",{x:870,y:36,fill:"#7bbac1","font-family":"ui-monospace,monospace","font-size":10,"text-anchor":"end"},"RENDERED FROM BOUNDED DATA"));
}

function building(svg,d) {
  const [bright,shadow]=shades[d.sector],x=d.px,y=d.py,w=d.width,h=d.rise,top=y-h;
  const g=S("g",{"data-district":d.id});
  g.append(
    S("ellipse",{cx:x+w*.55,cy:y+6,rx:w*.9,ry:8,fill:"#00ffeb","fill-opacity":".15"}),
    S("polygon",{points:[x+","+(top), (x+w*.56)+","+(top-10),(x+w+10)+","+(top-1),(x+w*.45)+","+(top+11)].join(" "),fill:bright,"fill-opacity":".72",stroke:bright,"stroke-width":".8"}),
    S("polygon",{points:[x+","+top,(x+w*.45)+","+(top+11),(x+w*.45)+","+(y+11),x+","+y].join(" "),fill:shadow,stroke:bright,"stroke-opacity":".7","stroke-width":".8"}),
    S("polygon",{points:[(x+w*.45)+","+(top+11),(x+w+10)+","+(top-1),(x+w+10)+","+(y-11),(x+w*.45)+","+(y+11)].join(" "),fill:"#062c42",stroke:bright,"stroke-opacity":".45","stroke-width":".8"})
  );
  for(let q=0;q<Math.min(5,d.height+1);q++){
    const step=h/(d.height+2);
    g.append(S("path",{d:"M"+(x+4)+" "+(top+18+q*step)+" l"+(w*.35)+" 5",stroke:bright,"stroke-opacity":".52",fill:"none","stroke-width":1}));
  }
  g.append(S("line",{x1:x+w*.55,y1:top-15,x2:x+w*.55,y2:top-2,stroke:bright,"stroke-width":1.7}));
  const labelX=x+w/2+5,labelY=y+26;
  g.append(S("line",{x1:labelX,y1:y+10,x2:labelX,y2:labelY-9,stroke:bright,"stroke-opacity":".65"}));
  g.append(S("circle",{cx:labelX,cy:y+10,r:2.5,fill:bright}));
  g.append(S("text",{x:labelX,y:labelY,fill:"#e5fffc","font-size":11,"font-family":"ui-sans-serif,system-ui","font-weight":650,"text-anchor":"middle",stroke:"#031219","stroke-width":2.4,"paint-order":"stroke"},d.name));
  svg.append(g);
}

export function renderIrpScene(svg,scene) {
  svg.replaceChildren();
  svg.setAttribute("viewBox","0 0 900 485");
  svg.setAttribute("role","img");
  svg.setAttribute("aria-label","Vector city for "+scene.title+", with "+scene.buildings.length+" fictional districts");
  background(svg,scene.theme);
  for(const district of scene.buildings)building(svg,district);
  svg.append(S("text",{x:25,y:455,fill:"#9be6de","font-family":"ui-monospace,monospace","font-size":10},"VECTOR SCENE · NO PHYSICAL CONTROLS"));
  svg.append(S("text",{x:875,y:455,fill:"#9be6de","font-family":"ui-monospace,monospace","font-size":10,"text-anchor":"end"},"iNNOVULiS / iRp v1"));
}

export function initIrpUi({getWorld,commitWorld}) {
  let blueprint=null,approval=null,busy=false;
  const scene=el("irp-scene"),status=el("irp-status"),run=el("irp-execute"),
        preview=el("irp-preview"),exportBtn=el("irp-export");
  const notify=message=>{status.textContent=message};
  function setBusy(flag){
    busy=flag;el("irp-generate").disabled=flag;el("irp-sample").disabled=flag;
    preview.disabled=flag||!blueprint;run.disabled=flag||!approval;
    exportBtn.disabled=flag||!blueprint;
  }
  function stage(untrusted,source){
    const clean=validateBlueprint(untrusted),compiled=sceneFromBlueprint(clean);
    blueprint=clean;approval=null;
    renderIrpScene(scene,compiled);
    el("irp-title").textContent=clean.title;
    el("irp-summary").textContent=clean.summary;
    el("irp-source").textContent=source;
    el("irp-theme").textContent=clean.theme.toUpperCase();
    el("irp-count").textContent=String(clean.districts.length);
    el("irp-plan").textContent="Aid "+clean.plan.aid_units+" · Diplomacy "+clean.plan.diplomacy.toFixed(2)+" · Comms "+(clean.plan.communications_disrupted?"disrupted":"online");
    el("irp-projection").textContent="Blueprint validated. Preview the fictional state change before executing.";
    const list=el("irp-district-list");list.replaceChildren();
    for(const d of clean.districts){
      const row=document.createElement("div");row.className="irp-district-row";
      const name=document.createElement("strong");name.textContent=d.name;
      const detail=document.createElement("span");detail.textContent=d.sector+" · height "+d.height;
      row.append(name,detail);list.append(row);
    }
    run.disabled=true;preview.disabled=false;exportBtn.disabled=false;
    notify("Validated "+clean.districts.length+" fictional districts · "+source+". Nothing executed.");
  }
  el("irp-sample").addEventListener("click",()=>{try{stage(SAMPLE_BLUEPRINT,"BUILT-IN DEMO BLUEPRINT")}catch{notify("Could not load demo blueprint.")}});
  el("irp-import").addEventListener("change",async event=>{
    const file=event.target.files?.[0];if(!file)return;
    try{if(file.size>IRP_MAX_BYTES)throw Error("Blueprint larger than 16 KiB");
      stage(JSON.parse(await file.text()),"LOCAL IMPORT · UNATTESTED");
    }catch(err){notify("Blueprint rejected: "+String(err.message).slice(0,120));}
    finally{event.target.value="";}
  });
  el("irp-generate").addEventListener("click",async()=>{
    if(busy)return;
    const prompt=el("irp-prompt").value.trim();
    if(prompt.length<8||prompt.length>600){notify("Enter an 8–600 character fictional world description.");return;}
    setBusy(true);notify("Requesting CODED local model. No real-world action.");
    try{
      const res=await fetch("./api/irp/generate",{
        method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({prompt}),
        credentials:"same-origin",redirect:"error",signal:AbortSignal.timeout(150000)
      });
      const result=await res.json().catch(()=>null);
      if(!res.ok)throw Error(result?.error||"LOCAL_MODEL_HTTP_"+res.status);
      if(result?.schema!=="innovulis.irp.generation.v1" ||
        result.provenance!=="UNATTESTED_LOCAL_MODEL_OUTPUT" ||
        !["advancedistroadmin/CODED:v1.0.0","advancedistroadmin/CODED:latest"].includes(result.source_model))
        throw Error("UNEXPECTED_GENERATOR_METADATA");
      stage(result.blueprint,"CODED MODEL PROPOSAL · UNATTESTED");
    }catch(err){
      notify("Local model unavailable or rejected: "+String(err.message).slice(0,90)+
        ". Load the demo or import JSON; start the opt-in iRp server for model inference.");
    }finally{setBusy(false);}
  });
  preview.addEventListener("click",()=>{
    try{
      const proposed=previewExecution(getWorld(),blueprint);
      approval={tick:getWorld().tick,blueprint:JSON.stringify(blueprint)};
      el("irp-projection").textContent=
        "Projected tick "+proposed.after.tick+": wellbeing "+proposed.after.community_wellbeing_index.toFixed(2)+
        " (was "+proposed.before.community_wellbeing_index.toFixed(2)+"), crisis "+
        proposed.after.crisis_index.toFixed(2)+" (was "+proposed.before.crisis_index.toFixed(2)+
        "), supply "+proposed.after.supply_units+". Synthetic only.";
      run.disabled=false;
      notify("Preview ready. Approve the exact plan to execute one synthetic tick.");
    }catch{approval=null;run.disabled=true;notify("Preview rejected. Nothing executed.");}
  });
  run.addEventListener("click",()=>{
    if(!approval||busy||!blueprint||approval.tick!==getWorld().tick||
      approval.blueprint!==JSON.stringify(blueprint)){
      approval=null;run.disabled=true;notify("Preview expired; re-preview required.");return;
    }
    try{
      const executed=executeApproved(getWorld(),blueprint,true);
      commitWorld(executed.world,executed.execution);
      approval=null;run.disabled=true;
      notify("Executed synthetic tick "+executed.execution.tick_after+
        " in browser memory. UNSIGNED. No physical action or blockchain receipt.");
    }catch{approval=null;run.disabled=true;notify("Execution refused. Nothing executed.");}
  });
  exportBtn.addEventListener("click",()=>{
    if(!blueprint)return;
    const file=new Blob([JSON.stringify(blueprint,null,2)+"\n"],{type:"application/json"});
    const url=URL.createObjectURL(file),a=document.createElement("a");
    a.href=url;a.download="iRp_Civilization_Blueprint_v1.json";document.body.append(a);a.click();a.remove();
    URL.revokeObjectURL(url);
  });
  stage(SAMPLE_BLUEPRINT,"BUILT-IN DEMO BLUEPRINT");
}
