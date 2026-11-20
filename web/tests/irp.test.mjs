import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {fileURLToPath} from "node:url";
import {dirname,resolve} from "node:path";
import {initialWorld} from "../civilization.mjs";
import {
  IRP_SCHEMA,IRP_EXECUTION_SCHEMA,SAMPLE_BLUEPRINT,
  SECTORS,THEMES,validateBlueprint,sceneFromBlueprint,
  previewExecution,executeApproved
} from "../irp.mjs";

const clone=()=>JSON.parse(JSON.stringify(SAMPLE_BLUEPRINT));
const here=dirname(fileURLToPath(import.meta.url));

test("sample blueprint is valid and fully cloned",()=>{
  const a=validateBlueprint(SAMPLE_BLUEPRINT),b=validateBlueprint(SAMPLE_BLUEPRINT);
  assert.equal(a.schema,IRP_SCHEMA);assert.equal(a.districts.length,6);
  assert.notEqual(a,b);assert.notEqual(a.districts,b.districts);
});
test("scene deterministic and bounded",()=>{
  const a=sceneFromBlueprint(SAMPLE_BLUEPRINT),b=sceneFromBlueprint(SAMPLE_BLUEPRINT);
  assert.deepEqual(a,b);assert.equal(a.buildings.length,6);
  assert.equal(a.render_scope,"DETERMINISTIC_2D_VECTOR_SYNTHETIC_ONLY");
  for(const x of a.buildings) {
    assert.ok(x.px>=100&&x.px<=800);
    assert.ok(x.py>=100&&x.py<430);
    assert.ok(x.rise>0&&x.rise<=105);
  }
});
test("reject invalid root and injected shell/script/path instructions",()=>{
  for(const extra of [{eval:"console.log(1)"},{script:"alert(1)"},{url:"https://evil.test"},{command:"rm -rf /"}]){
    assert.throws(()=>validateBlueprint({...clone(),...extra}),/ROOT_KEYS/);
  }
  assert.throws(()=>validateBlueprint({}),/ROOT_KEYS/);
  const x=clone();x.schema="other";assert.throws(()=>validateBlueprint(x),/SCHEMA/);
});
test("reject duplicate district identifiers",()=>{
  const x=clone();x.districts[1].id=x.districts[0].id;
  assert.throws(()=>validateBlueprint(x),/DISTRICT_DUPLICATE/);
});
test("reject unsupported sector and theme",()=>{
  let x=clone();x.districts[0].sector="weapons";assert.throws(()=>validateBlueprint(x),/SECTOR/);
  x=clone();x.theme="hacked";assert.throws(()=>validateBlueprint(x),/THEME/);
  assert.deepEqual(SECTORS,["habitat","energy","health","agriculture","transport","civic"]);
  assert.deepEqual(THEMES,["ocean","forest","desert","night"]);
});
test("reject invalid coordinates and heights",()=>{
  for(const val of [-1,99,NaN,Infinity,"54",true]){
    const x=clone();x.districts[0].x=val;assert.throws(()=>validateBlueprint(x));
  }
  for(const val of [0,6,2.5,"4",false]){
    const x=clone();x.districts[0].height=val;assert.throws(()=>validateBlueprint(x));
  }
});
test("reject malformed or oversized text and too many districts",()=>{
  const x=clone();x.summary="x".repeat(250);assert.throws(()=>validateBlueprint(x),/SUMMARY_TEXT/);
  const y=clone();y.districts[0].name="bad\nname";assert.throws(()=>validateBlueprint(y),/DISTRICT_NAME_TEXT/);
  const z=clone();z.districts=z.districts.slice(0,2);assert.throws(()=>validateBlueprint(z),/DISTRICTS/);
});
test("reject unbounded or malformed simulation plans",()=>{
  for(const val of [-1,101,"8",8.5,true]){
    const x=clone();x.plan.aid_units=val;assert.throws(()=>validateBlueprint(x));
  }
  for(const val of [-.1,1.1,"0.5",true,Infinity]){
    const x=clone();x.plan.diplomacy=val;assert.throws(()=>validateBlueprint(x));
  }
  const x=clone();x.plan.communications_disrupted="false";assert.throws(()=>validateBlueprint(x),/DISRUPTION/);
  const y=clone();y.plan.arbitrary_js="confirm('yes')";assert.throws(()=>validateBlueprint(y),/PLAN_KEYS/);
});
test("preview does not mutate source world and requires approval",()=>{
  const original=JSON.stringify(initialWorld);
  const p=previewExecution(initialWorld,SAMPLE_BLUEPRINT);
  assert.equal(JSON.stringify(initialWorld),original);
  assert.equal(p.after.tick,1);
  assert.equal(p.before.tick,0);
  assert.equal(p.approval_required,true);
  assert.throws(()=>executeApproved(initialWorld,SAMPLE_BLUEPRINT,false),/APPROVAL_REQUIRED/);
  assert.throws(()=>executeApproved(initialWorld,SAMPLE_BLUEPRINT),/APPROVAL_REQUIRED/);
});
test("approved execution produces exactly one synthetic step, never signed evidence",()=>{
  const r=executeApproved(initialWorld,SAMPLE_BLUEPRINT,true);
  assert.equal(r.world.tick,1);
  assert.equal(r.world.supply_units,92);
  assert.equal(r.world.crisis_index,61.85);
  assert.equal(r.world.community_wellbeing_index,37.9);
  assert.equal(r.execution.schema,IRP_EXECUTION_SCHEMA);
  assert.equal(r.execution.evidence_state,"UNSIGNED_BROWSER_EXECUTION");
  assert.equal(r.execution.receipt,null);
  assert.equal(r.execution.anchor,null);
  assert.equal(r.execution.hardware_attestation,false);
  assert.equal(initialWorld.tick,0);
});
test("renderer uses inert DOM creation, not HTML or scripts from blueprint",()=>{
  const source=readFileSync(resolve(here,"..","irp-ui.mjs"),"utf8");
  assert.match(source,/createElementNS/);
  assert.match(source,/textContent/);
  assert.doesNotMatch(source,/innerHTML|eval\s*\(|new Function/);
});
test("site exposes stage, preview, approval and honest synthetic labels",()=>{
  const html=readFileSync(resolve(here,"..","index.html"),"utf8");
  for(const id of ["irp-prompt","irp-generate","irp-sample","irp-import","irp-scene","irp-preview","irp-execute","irp-status"])
    assert.ok(html.includes('id="'+id+'"'),id);
  assert.match(html,/UNSIGNED BROWSER EXECUTION/);
  assert.match(html,/MODEL OUTPUT UNATTESTED/);
});
