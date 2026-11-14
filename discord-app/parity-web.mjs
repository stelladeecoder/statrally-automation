const byId=id=>document.getElementById(id);
const el=(tag,value,cls)=>{const node=document.createElement(tag);if(value!==undefined)node.textContent=value;if(cls)node.className=cls;return node;};
const pct=p=>typeof p==="number"&&Number.isFinite(p)?(p*100).toFixed(1)+"%":"—";
const kickoff=s=>new Intl.DateTimeFormat("en-US",{timeZone:"America/Chicago",month:"short",day:"numeric",hour:"numeric",minute:"2-digit",timeZoneName:"short"}).format(new Date(s));
let source=null;
function render(){
 const sports=byId("sport").value,league=byId("league").value,state=byId("state").value;
 const rows=source.records.filter(x=>(!sports||x.sport===sports)&&(!league||x.league===league)&&(!state||x.grade_status===state));
 const summary=byId("summary");summary.replaceChildren();
 const graded=rows.filter(x=>x.prediction_status==="research_prediction"&&x.grade_status==="graded");
 const correct=graded.filter(x=>(x.p_even>=.5)===(x.actual==="EVEN")).length;
 for(const [name,val] of [["Recorded",rows.length],["Graded",graded.length],["Pending",rows.filter(x=>x.grade_status!=="graded").length],["Accuracy",graded.length?pct(correct/graded.length):"Not established"]]){
   const metric=el("div",undefined,"metric");metric.append(el("span",name),el("strong",String(val)));summary.append(metric);
 }
 const main=byId("content");main.replaceChildren();
 if(!rows.length){main.append(el("p","No forward-recorded forecasts match these filters. Historical backtests are not being substituted.","muted"));return;}
 for(const record of rows.slice(0,300)){
   const card=el("article",undefined,"card");
   const heading=el("h3",record.away+" @ "+record.home);
   const meta=el("p",record.competition+" · "+(record.category==="women"?"Women's competition":"")+" · "+kickoff(record.kickoff_utc),"muted");
   const detail=el("div",undefined,"detail");
   if(record.prediction_status==="research_prediction"){
     detail.append(el("span","EVEN "+pct(record.p_even)),el("span","ODD "+pct(record.p_odd)));
   }else{
     detail.append(el("span","Insufficient verified history; no probability issued"));
   }
   const outcome=record.grade_status==="graded"?
     "Verified "+record.actual+" · Final combined total "+record.total:
     "Outcome pending, not counted as a loss";
   const issued=el("small","Recorded "+new Date(record.issued_at).toLocaleString()+" · "+record.settlement_basis.replaceAll("_"," "));
   card.append(heading,meta,detail,el("p",outcome),issued);
   main.append(card);
 }
 if(rows.length>300)main.append(el("p","Showing first 300 of "+rows.length+" records. More remain in the verified snapshot.","muted"));
}
function options(){
 const select=byId("league");
 const selected=select.value;
 select.replaceChildren(el("option","All competitions"));
 select.firstChild.value="";
 const sport=byId("sport").value;
 for(const item of source.performance_by_league.filter(x=>!sport||x.league.startsWith("soccer")&&sport==="soccer"||x.league==="nhl"&&sport==="hockey")){
   const option=el("option",item.competition+(item.category==="women"?" (Women)":""));
   option.value=item.league;select.append(option);
 }
 select.value=[...select.options].some(x=>x.value===selected)?selected:"";
}
for(const name of ["sport","league","state"])byId(name).addEventListener("change",()=>{
 if(name==="sport")options();
 if(source)render();
});
try{
 const response=await fetch("./parity.json",{cache:"no-store"});
 if(!response.ok)throw Error("unavailable");
 const json=await response.json();
 if(json.schema_version!==1||json.market!=="TOTAL_SCORE_PARITY"||json.qualified_bets!==0||json.trades_placed!==0||json.markets_verified!==false||json.models_calibrated!==false||!Array.isArray(json.records)||!Array.isArray(json.performance_by_league))throw Error("untrusted snapshot");
 source=json;
 const age=Date.now()-Date.parse(source.generated_at);
 const stale=!Number.isFinite(age)||age>48*60*60*1000;
 byId("source").textContent="Recorded research snapshot: "+new Date(source.generated_at).toLocaleString()+(stale?" · STALE, current games are not guaranteed":"");
 byId("source").className=stale?"error":"muted";
 options();render();
}catch{
 byId("source").textContent="Verified parity records are unavailable; no scores or predictions will be invented.";
 byId("source").className="error";
}
