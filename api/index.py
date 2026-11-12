import json, os, re, urllib.request
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

try: from .engine import CATALOG, GROUPS, SCENARIOS, calculate, compare, optimize
except ImportError: from engine import CATALOG, GROUPS, SCENARIOS, calculate, compare, optimize

app=FastAPI(title="GantryLab API",version="0.1")
ROOT=Path(__file__).resolve().parents[1]

class ConfigRequest(BaseModel):
    requirements:dict
    sizes:dict[str,int]=Field(default_factory=dict)
class OptimizeRequest(BaseModel):
    requirements:dict
    strategy:str="minimum_cost"
class ChatRequest(BaseModel):
    message:str=Field(min_length=1,max_length=1600)
    requirements:dict
    sizes:dict[str,int]=Field(default_factory=dict)
    result:dict|None=None
    history:list[dict]=Field(default_factory=list)

@app.get("/api/health")
def health():return {"ok":True,"engine":"deterministic-v0.1","llm":bool(os.getenv("OPENAI_API_KEY"))}
@app.get("/api/modules")
def modules():return {"synthetic":True,"groups":GROUPS,"modules":CATALOG}
@app.get("/api/scenarios")
def scenarios():return SCENARIOS
@app.post("/api/calculate")
def calc(body:ConfigRequest):return calculate(body.requirements,body.sizes)
@app.post("/api/optimize")
def opt(body:OptimizeRequest):
    if body.strategy not in {"minimum_cost","balanced","high_performance"}:raise HTTPException(400,"Unknown strategy")
    return optimize(body.requirements,body.strategy)
@app.post("/api/compare")
def comparison(body:ConfigRequest):return {"alternatives":compare(body.requirements)}

def local_assistant(body):
    msg=body.message.lower(); changes={}; current=calculate(body.requirements,body.sizes)
    patterns={"payload":r"(?:payload|load)[^\d]{0,12}(\d+(?:\.\d+)?)\s*kg","x_hub":r"(?:x[ -]?(?:hub|stroke|travel))[^\d]{0,8}(\d+(?:\.\d+)?)\s*m","y_hub":r"(?:y[ -]?(?:hub|stroke|travel))[^\d]{0,8}(\d+(?:\.\d+)?)\s*m","z_hub":r"(?:z[ -]?(?:hub|stroke|travel))[^\d]{0,8}(\d+(?:\.\d+)?)\s*m"}
    for k,p in patterns.items():
        hit=re.search(p,msg)
        if hit:changes[k]=float(hit.group(1))
    if "double" in msg and "payload" in msg:changes["payload"]=body.requirements.get("payload",20)*2
    if changes:
        projected=calculate({**body.requirements,**changes},body.sizes); d=projected["metrics"]
        named=", ".join(f"{k.replace('_',' ')} = {v:g}" for k,v in changes.items())
        return {"message":f"I found {named}. Applying these values gives {d['tcp_deflection']:.3f} mm TCP deflection and {d['max_utilization']:.0f}% peak utilization. Review and confirm the proposed changes.","proposed_changes":changes,"requires_confirmation":True,"result":projected}
    if "why" in msg:
        worst=max(current["modules"],key=lambda c:c["deflection"])
        explanation=f"{worst['label']} is the largest TCP compliance contributor at {worst['deflection']:.3f} mm. Its BG{worst['size']} selection balances the {worst['utilization']:.0f}% governing {worst['critical_criterion'].replace('_',' ')} utilization against cost and added moving mass."
    elif "cost" in msg:
        alt=optimize(body.requirements,"minimum_cost"); saving=current["metrics"]["total_cost"]-alt["metrics"]["total_cost"]
        explanation=f"The minimum-cost feasible configuration is {max(0,saving):.0f} cost units cheaper. It reaches {alt['metrics']['max_utilization']:.0f}% peak utilization and {alt['metrics']['tcp_deflection']:.3f} mm deflection; load that strategy to inspect the trade-off."
    elif "deflection" in msg or "stiff" in msg:
        top=sorted(current["modules"],key=lambda c:c["deflection"],reverse=True)[:3]
        explanation="The leading TCP deflection contributors are "+", ".join(f"{c['label']} ({c['deflection']:.3f} mm)" for c in top)+f". Total deflection is {current['metrics']['tcp_deflection']:.3f} mm against {current['metrics']['allowed_deflection']:.3f} mm allowed."
    else:
        explanation=f"This configuration is {current['metrics']['status']} at {current['metrics']['max_utilization']:.0f}% peak utilization and {current['metrics']['tcp_deflection']:.3f} mm TCP deflection. Ask about cost, deflection, a component choice, or describe requirement changes with units."
    return {"message":explanation,"proposed_changes":{},"requires_confirmation":False,"result":current}

@app.post("/api/chat")
def chat(body:ChatRequest):
    fallback=local_assistant(body); key=os.getenv("OPENAI_API_KEY")
    if not key:return {**fallback,"mode":"deterministic"}
    engine=body.result or calculate(body.requirements,body.sizes)
    prompt={"current_requirements":body.requirements,"current_sizes":body.sizes,"authoritative_engine_result":engine,"recent_history":body.history[-6:],"user_message":body.message,"local_interpretation":fallback}
    schema={"type":"object","properties":{"message":{"type":"string"}},"required":["message"],"additionalProperties":False}
    payload={"model":os.getenv("OPENAI_MODEL","gpt-5-mini"),"instructions":"You are an engineering configuration adviser. Use only supplied authoritative engine values. Never invent calculations. Be concise. Proposed changes require confirmation. Return JSON.","input":json.dumps(prompt),"text":{"format":{"type":"json_schema","name":"gantry_advice","strict":True,"schema":schema}}}
    req=urllib.request.Request("https://api.openai.com/v1/responses",data=json.dumps(payload).encode(),headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=35) as res: raw=json.loads(res.read())
        text=raw.get("output_text") or next((c.get("text") for i in raw.get("output",[]) for c in i.get("content",[]) if c.get("type")=="output_text"),None)
        return {**fallback,"message":json.loads(text or "{}").get("message",fallback["message"]),"mode":"openai"}
    except Exception:return {**fallback,"mode":"deterministic","warning":"LLM unavailable; deterministic assistant used."}

@app.get("/")
def index():return FileResponse(ROOT/"index.html")
