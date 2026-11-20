import {initIrpUi} from "./irp-ui.mjs";
import {advance, initialWorld, summarizeJournalText, MAX_JOURNAL_BYTES} from "./civilization.mjs";

const el = id => document.getElementById(id);
const state = {world:{...initialWorld}, history:[{...initialWorld}], activeSector:"Population"};

function fmt(v) {return Number(v).toFixed(2)}
function setMetric(name, value, percent) {
  el(name).textContent = value;
  el(name+"-meter").style.width = Math.min(100,Math.max(0,percent))+"%";
}

function updateChart() {
  const history = state.history.slice(-60);
  const yOf = record => 122 - record.community_wellbeing_index * 1.0;
  const points = history.length === 1
    ? [[0,yOf(history[0])],[320,yOf(history[0])]]
    : history.map((item,i)=>[i*320/(history.length-1),yOf(item)]);
  const line = points.map((p,i)=>(i ? "L" : "M")+p[0].toFixed(2)+" "+p[1].toFixed(2)).join(" ");
  const first=points[0], last=points[points.length-1];
  el("chart-line").setAttribute("d",line);
  el("chart-fill").setAttribute("d",line+" L"+last[0].toFixed(2)+" 136 L"+first[0].toFixed(2)+" 136Z");
  el("chart-current").textContent = fmt(state.world.community_wellbeing_index);
}

function render() {
  const w=state.world;
  setMetric("wellbeing",fmt(w.community_wellbeing_index),w.community_wellbeing_index);
  setMetric("crisis",fmt(w.crisis_index),w.crisis_index);
  setMetric("supply",String(w.supply_units),w.supply_units);
  setMetric("communications",w.communications_online ? "ONLINE" : "DISRUPTED",w.communications_online?100:0);
  el("tick").textContent=String(w.tick);
  el("map-tick").textContent=String(w.tick).padStart(4,"0");
  updateChart();
}

function parameters() {
  return {
    aid_units:Number(el("aid").value),
    diplomacy:Number(el("diplomacy").value),
    communications_disrupted:el("disruption").checked
  };
}

function setAnnouncement(message) {el("announcement").textContent=message}

el("aid").addEventListener("input",()=>{el("aid-value").textContent=el("aid").value});
el("diplomacy").addEventListener("input",()=>{el("diplomacy-value").textContent=Number(el("diplomacy").value).toFixed(2)});

el("run-step").addEventListener("click",()=>{
  try {
    state.world=advance(state.world,parameters());
    state.history.push({...state.world});
    if(state.history.length>500)state.history.shift();
    render();
    setAnnouncement("Tick "+state.world.tick+" committed to browser memory · synthetic and unsigned.");
  } catch {
    setAnnouncement("Invalid scenario input. No state change applied.");
  }
});

el("reset").addEventListener("click",()=>{
  state.world={...initialWorld};
  state.history=[{...initialWorld}];
  el("aid").value="4";
  el("diplomacy").value="0.5";
  el("disruption").checked=false;
  el("aid-value").textContent="4";
  el("diplomacy-value").textContent="0.50";
  render();
  setAnnouncement("Scenario reset. No external action was performed.");
});

for(const button of document.querySelectorAll(".sector-option")) {
  button.addEventListener("click",()=>{
    for(const candidate of document.querySelectorAll(".sector-option")) {
      const active=candidate===button;
      candidate.classList.toggle("active",active);
      candidate.setAttribute("aria-pressed",String(active));
    }
    const sector=button.dataset.sector;
    state.activeSector=sector;
    el("world-map").dataset.sector=sector;
    el("selected-sector").textContent=sector;
  });
}

const fileInput=el("journal-file");
fileInput.addEventListener("change",async()=>{
  const file=fileInput.files?.[0];
  const result=el("import-results");
  const rows=el("import-rows");
  rows.replaceChildren();
  if(!file) {
    result.textContent="No local journal selected. Nothing has been verified.";
    return;
  }
  if(file.size>MAX_JOURNAL_BYTES) {
    result.textContent="Journal rejected: larger than 4 MiB. No data loaded.";
    fileInput.value="";
    return;
  }
  try {
    const parsed=summarizeJournalText(await file.text());
    result.textContent=parsed.count+" entries parsed locally · SIGNATURES NOT VERIFIED";
    for(const rec of parsed.latest) {
      const row=document.createElement("div"); row.className="import-row";row.setAttribute("role","listitem");
      const id=document.createElement("span");id.textContent="#"+rec.sequence+" · "+rec.receipt_id;
      const status=document.createElement("span");status.textContent="UNVERIFIED";
      row.append(id,status);
      rows.append(row);
    }
  } catch {
    result.textContent="Cannot parse a Buddy JSONL journal. No rows loaded or verified.";
    rows.replaceChildren();
  } finally {
    fileInput.value="";
  }
});

render();

initIrpUi({
  getWorld:()=>({...state.world}),
  commitWorld:(next,execution)=>{
    if(execution?.evidence_state!=="UNSIGNED_BROWSER_EXECUTION"||
      execution?.tick_before!==state.world.tick||
      next.tick!==state.world.tick+1)
      throw new Error("IRP_EXECUTION_CONTRACT_REJECTED");
    state.world={...next};
    state.history.push({...next});
    if(state.history.length>500)state.history.shift();
    render();
    setAnnouncement("iRp v1 advanced fictional world by one tick; UNSIGNED browser execution.");
  }
});

