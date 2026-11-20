/** iRp™ v1: bounded, inert blueprint compiler for CODED fictional civilizations.
 * Data only; model output is never interpreted as HTML, JS, code, paths or network instructions.
 */
import {advance} from "./civilization.mjs";

export const IRP_SCHEMA="innovulis.irp.blueprint.v1";
export const IRP_EXECUTION_SCHEMA="innovulis.irp.execution.v1";
export const IRP_MAX_BYTES=16384;
export const SECTORS=Object.freeze(["habitat","energy","health","agriculture","transport","civic"]);
export const THEMES=Object.freeze(["ocean","forest","desert","night"]);
const TEXT=/^[^\u0000-\u001f\u007f]*$/u;
const ID=/^[a-z][a-z0-9-]{0,23}$/;

function insist(ok,reason) {if(!ok)throw new Error("IRP_BLUEPRINT_INVALID:"+reason)}
function exactKeys(obj,keys,where) {
  insist(obj!==null&&typeof obj==="object"&&!Array.isArray(obj),where+"_OBJECT_REQUIRED");
  insist(Object.keys(obj).length===keys.length&&Object.keys(obj).every(k=>keys.includes(k)),where+"_KEYS");
}
function label(value,min,max,where) {
  insist(typeof value==="string"&&value.length>=min&&value.length<=max&&TEXT.test(value)&&
    value.trim()===value,where+"_TEXT");
  return value;
}
function numeric(value,min,max,where) {
  insist(typeof value==="number"&&Number.isFinite(value)&&value>=min&&value<=max,where+"_RANGE");
  return value;
}
function asciiId(value) {insist(typeof value==="string"&&ID.test(value),"DISTRICT_ID");return value;}
export function validateBlueprint(value) {
  insist(value!==null&&typeof value==="object"&&!Array.isArray(value),"OBJECT");
  // Explicit schema disallows extra instructions, scripts, URLs and executable actions.
  exactKeys(value,["schema","title","summary","theme","districts","plan"],"ROOT");
  insist(value.schema===IRP_SCHEMA,"SCHEMA");
  label(value.title,3,80,"TITLE");label(value.summary,3,240,"SUMMARY");
  insist(THEMES.includes(value.theme),"THEME");
  insist(Array.isArray(value.districts)&&value.districts.length>=3&&value.districts.length<=12,"DISTRICTS");
  const ids=new Set();
  const districts=value.districts.map((d,i)=>{
    exactKeys(d,["id","name","sector","x","y","height"],"DISTRICT");
    const id=asciiId(d.id);
    insist(!ids.has(id),"DISTRICT_DUPLICATE");ids.add(id);
    label(d.name,2,48,"DISTRICT_NAME");
    insist(SECTORS.includes(d.sector),"SECTOR");
    numeric(d.x,8,92,"X");numeric(d.y,8,92,"Y");
    insist(Number.isInteger(d.height)&&d.height>=1&&d.height<=5,"HEIGHT");
    return {id,name:d.name,sector:d.sector,x:d.x,y:d.y,height:d.height};
  });
  exactKeys(value.plan,["aid_units","diplomacy","communications_disrupted"],"PLAN");
  insist(Number.isSafeInteger(value.plan.aid_units)&&value.plan.aid_units>=0&&
    value.plan.aid_units<=100,"AID");
  numeric(value.plan.diplomacy,0,1,"DIPLOMACY");
  insist(typeof value.plan.communications_disrupted==="boolean","DISRUPTION");
  // Safely clone only the allowed keys to strip prototypes/getters from imported data.
  const approved={
    schema:IRP_SCHEMA,title:value.title,summary:value.summary,theme:value.theme,
    districts,plan:{
      aid_units:value.plan.aid_units,
      diplomacy:value.plan.diplomacy,
      communications_disrupted:value.plan.communications_disrupted
    }
  };
  insist(new TextEncoder().encode(JSON.stringify(approved)).length<=IRP_MAX_BYTES,"SIZE");
  return approved;
}

export const SAMPLE_BLUEPRINT=Object.freeze({
  schema:IRP_SCHEMA,
  title:"Aurelia · The Ocean Citadel",
  summary:"A fictional island civilization with shared gardens, transit rings and modular coastal districts.",
  theme:"ocean",
  districts:[
    {id:"central-spire",name:"Civic Nexus",sector:"civic",x:51,y:25,height:5},
    {id:"arc-harbor",name:"Arc Harbor",sector:"transport",x:23,y:73,height:3},
    {id:"helios-grid",name:"Helios Grid",sector:"energy",x:80,y:61,height:4},
    {id:"medica",name:"Medica",sector:"health",x:72,y:31,height:3},
    {id:"garden-dome",name:"Garden Dome",sector:"agriculture",x:33,y:47,height:2},
    {id:"sky-habitat",name:"Sky Habitat",sector:"habitat",x:56,y:76,height:4}
  ],
  plan:{aid_units:8,diplomacy:0.65,communications_disrupted:false}
});

export function sceneFromBlueprint(untrusted) {
  const b=validateBlueprint(untrusted);
  const buildings=b.districts.map(d=>{
    // Deterministic 2D geometry compiled from bounded numeric inputs.
    const px=75+d.x*7.5;
    const py=102+d.y*3.2;
    const width=14+d.height*3;
    const rise=18+d.height*17;
    return {...d,px:+px.toFixed(2),py:+py.toFixed(2),width,rise};
  }).sort((a,b)=>a.py-b.py||a.id.localeCompare(b.id));
  return {schema:"innovulis.irp.scene.v1",title:b.title,theme:b.theme,buildings,
    render_scope:"DETERMINISTIC_2D_VECTOR_SYNTHETIC_ONLY"};
}

export function previewExecution(world,untrusted) {
  const b=validateBlueprint(untrusted);
  const projected=advance(world,b.plan);
  return {
    schema:"innovulis.irp.preview.v1",
    before:{...world},after:projected,plan:{...b.plan},
    approval_required:true,
    scope:"SIMULATION_ONLY_NO_REAL_WORLD_EFFECT"
  };
}

export function executeApproved(world,untrusted,approval) {
  const b=validateBlueprint(untrusted);
  insist(approval===true,"APPROVAL_REQUIRED");
  const next=advance(world,b.plan);
  return {
    world:next,
    execution:{
      schema:IRP_EXECUTION_SCHEMA,
      blueprint_title:b.title,
      applied_plan:{...b.plan},
      tick_before:world.tick,tick_after:next.tick,
      evidence_state:"UNSIGNED_BROWSER_EXECUTION",
      receipt:null,anchor:null,hardware_attestation:false,
      execution_scope:"LOCAL_SYNTHETIC_STATE_ONLY"
    }
  };
}
