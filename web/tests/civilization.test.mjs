import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {fileURLToPath} from "node:url";
import {resolve,dirname} from "node:path";
import {advance,bound,initialWorld,snapshot,summarizeJournalText,MAX_JOURNAL_BYTES,ORIGIN} from "../civilization.mjs";

const here=dirname(fileURLToPath(import.meta.url));
const root=resolve(here,"..");

test("initial world state agrees with CODED core/simulation.py",()=>{
  assert.deepEqual(initialWorld,{
    tick:0,fictional_region:"OMEGA_SANDBOX",crisis_index:65,
    community_wellbeing_index:35,supply_units:100,communications_online:true
  });
  assert.equal(ORIGIN,"SYNTHETIC_SIMULATION");
});

test("default advance mirrors Python formulas",()=>{
  assert.deepEqual(advance(initialWorld),{
    tick:1,fictional_region:"OMEGA_SANDBOX",crisis_index:62.9,
    community_wellbeing_index:36.8,supply_units:96,communications_online:true
  });
});

test("disruption affects indexes without operational side effect",()=>{
  const r=advance(initialWorld,{aid_units:4,diplomacy:.5,communications_disrupted:true});
  assert.equal(r.crisis_index,65.9);
  assert.equal(r.community_wellbeing_index,33.8);
  assert.equal(r.communications_online,false);
});

test("aid allocation is bounded by synthetic inventory",()=>{
  const r=advance({...initialWorld,supply_units:2},{aid_units:90,diplomacy:0});
  assert.equal(r.supply_units,0);
  assert.equal(r.crisis_index,64.7);
  assert.equal(r.community_wellbeing_index,35.4);
});

test("bound clamps values to 0..100",()=>{
  assert.equal(bound(999),100);
  assert.equal(bound(-30),0);
  assert.throws(()=>bound(Infinity),TypeError);
});

test("invalid aid units and diplomacy fail closed",()=>{
  for(const bad of [NaN,Infinity,-1,101,2.5,true,"4"]) {
    assert.throws(()=>advance(initialWorld,{aid_units:bad}),{name:"RangeError"});
  }
  for(const bad of [NaN,Infinity,-.01,1.01,"0.5",true]) {
    assert.throws(()=>advance(initialWorld,{diplomacy:bad}),{name:"RangeError"});
  }
  assert.throws(()=>advance(initialWorld,{communications_disrupted:"false"}),TypeError);
});

test("world state is not mutated by a tick",()=>{
  const before=JSON.stringify(initialWorld);
  const next=advance(initialWorld);
  assert.equal(JSON.stringify(initialWorld),before);
  assert.notEqual(next,initialWorld);
});

test("snapshot labels synthetic origin and deterministic scope",()=>{
  const r=snapshot(initialWorld);
  assert.equal(r.origin,"SYNTHETIC_SIMULATION");
  assert.equal(r.verification_scope,"DETERMINISTIC_SOFTWARE_STATE_ONLY");
  assert.equal(r.schema,"innovulis.coded.world-state.v1");
  assert.equal(r.world.tick,0);
});

const fakeEntry=(n)=>JSON.stringify({
  sequence:n,
  receipt:{body:{id:"RCP-12345678-1234-1234-1234-"+String(n).padStart(12,"0"),identity:"SECRET_TEST_ID"}},
  chain_sha256:"not-checked"
});

test("viewer returns only safe receipt metadata and explicitly unverified status",()=>{
  const r=summarizeJournalText(fakeEntry(1)+"\n"+fakeEntry(2)+"\n");
  assert.equal(r.count,2);
  assert.equal(r.verified,false);
  assert.match(r.verification_scope,/NOT_CRYPTOGRAPHICALLY_VERIFIED/);
  assert.deepEqual(r.latest.map(x=>x.sequence),[2,1]);
  assert.equal(JSON.stringify(r).includes("SECRET_TEST_ID"),false);
});

test("viewer rejects malformed and oversize journal",()=>{
  assert.throws(()=>summarizeJournalText("not-json"),SyntaxError);
  assert.throws(()=>summarizeJournalText("{}"),/not a recognized/);
  assert.throws(()=>summarizeJournalText("X".repeat(MAX_JOURNAL_BYTES+1)),RangeError);
});

test("viewer allows empty local ledger but does not claim verification",()=>{
  const r=summarizeJournalText("");
  assert.equal(r.count,0);
  assert.equal(r.verified,false);
});

test("static document has simulation and trust-boundary disclosures",()=>{
  const html=readFileSync(resolve(root,"index.html"),"utf8");
  for(const id of ["console","run-step","reset","journal-file","crisis","wellbeing","supply","communications","history-chart"])
    assert.match(html,new RegExp('id="'+id+'"'));
  assert.match(html,/NO LIVE OPERATIONS/);
  assert.match(html,/does not verify signatures/);
  assert.doesNotMatch(html,/Verified 100%|globally deployed|4,268,320|92\.4%/i);
});

test("all app assets are local relative paths; no trackers or remote scripts",()=>{
  const html=readFileSync(resolve(root,"index.html"),"utf8");
  assert.doesNotMatch(html,/<script[^>]+src="https?:\/\//);
  assert.doesNotMatch(html,/<link[^>]+href="https?:\/\//);
  assert.doesNotMatch(html,/gtag|analytics|pixel\.js/i);
  for(const path of ["styles.css","app.js","civilization.mjs","assets/mark.svg","assets/civilization.svg"])
    assert.ok(readFileSync(resolve(root,path)).length>40,path);
});
