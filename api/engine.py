import hashlib, json, math

GROUPS = ["columns","x_beams","y_beam","z_axis","x_carriages","y_carriage","z_carriage","x_guides","y_guides","z_guides","x_drives","y_drive","z_drive"]
LABELS = {"columns":"Columns","x_beams":"X beams","y_beam":"Y beam","z_axis":"Z axis","x_carriages":"X carriage plates","y_carriage":"Y carriage plate","z_carriage":"Z carriage plate","x_guides":"X guide system","y_guides":"Y guide system","z_guides":"Z guide system","x_drives":"X drive system","y_drive":"Y drive system","z_drive":"Z drive system"}
KINDS = {**{g:"plate" for g in ["x_carriages","y_carriage","z_carriage"]},**{g:"guide" for g in ["x_guides","y_guides","z_guides"]},**{g:"drive" for g in ["x_drives","y_drive","z_drive"]},**{g:"beam" for g in ["x_beams","y_beam","z_axis"]},"columns":"structure"}
BASE = {"structure":(34,30e6,13000,2900,5500,35),"beam":(42,38e6,15000,3600,6200,47),"plate":(11,70e6,11500,2100,4700,24),"guide":(8,92e6,14500,2600,6500,42),"drive":(13,61e6,5200,2200,4800,68)}
FACTORS = {1:(1,1,1,1,1,1),2:(1.33,1.85,1.55,1.50,1.55,1.38),3:(1.78,3.20,2.45,2.30,2.30,1.98),4:(2.42,5.45,3.75,3.45,3.40,2.92)}

def module(group,size):
    mass,k,force,moment,dynamic,cost=BASE[KINDS[group]]; fm,fk,fc,fd,fl,fco=FACTORS[size]; gf=.9+GROUPS.index(group)*.018
    return {"id":f"{group.upper()}-BG{size}","group":group,"label":LABELS[group],"size":size,"mass_per_m":round(mass*fm*gf,2),"stiffness":round(k*fk*gf),"force_capacity":round(force*fc*gf),"moment_capacity":round(moment*fc*gf),"dynamic_capacity":round(dynamic*fd*gf),"life_rating":round(18000*fl*gf),"section_mm":round(70*(1,.78,1.3,1.65)[size-1]*(1.06 if KINDS[group] in {"beam","structure"} else .72)),"cost":round(cost*fco*gf,1),"compatible_sizes":[s for s in range(1,5) if abs(s-size)<=1]}

CATALOG=[module(g,s) for g in GROUPS for s in range(1,5)]
SCENARIOS=[
 {"id":"fast_handling","name":"Fast Handling","application":"handling","description":"High-throughput handling with no process load.","requirements":{"x_hub":4,"y_hub":2.2,"z_hub":1,"payload":20,"tool_mass":12,"max_speed":2.5,"max_acceleration":6,"force_x":0,"force_y":0,"force_z":0,"max_deflection":.35,"target_life":18000,"tool_offset":.35}},
 {"id":"precision_inspection","name":"Precision Inspection","application":"non_contact","description":"Position-stable non-contact inspection.","requirements":{"x_hub":3.2,"y_hub":1.8,"z_hub":.7,"payload":10,"tool_mass":8,"max_speed":1.2,"max_acceleration":2,"force_x":0,"force_y":0,"force_z":0,"max_deflection":.09,"target_life":24000,"tool_offset":.25}},
 {"id":"force_processing","name":"Force-Controlled Processing","application":"contact","description":"Contact process with a 1,000 N resultant load.","requirements":{"x_hub":4.5,"y_hub":2.5,"z_hub":1.1,"payload":40,"tool_mass":18,"max_speed":.8,"max_acceleration":1.5,"force_x":700,"force_y":300,"force_z":650,"max_deflection":.16,"target_life":30000,"tool_offset":.42}}
]
BOUNDS={"x_hub":(.8,8),"y_hub":(.5,5),"z_hub":(.2,2.5),"payload":(1,250),"tool_mass":(1,120),"max_speed":(.1,5),"max_acceleration":(.1,12),"force_x":(0,5000),"force_y":(0,5000),"force_z":(0,5000),"max_deflection":(.03,2),"target_life":(1000,80000),"tool_offset":(.05,1.2)}

def normalize(raw):
    d=SCENARIOS[0]["requirements"]; out={}
    for k,(lo,hi) in BOUNDS.items():
        try:v=float(raw.get(k,d[k]))
        except (ValueError,TypeError):v=float(d[k])
        out[k]=min(hi,max(lo,v))
    return out

def compatibility(s):
    pairs=[("x_beams","x_guides"),("y_beam","y_guides"),("z_axis","z_guides"),("x_guides","x_carriages"),("y_guides","y_carriage"),("z_guides","z_carriage"),("x_drives","x_beams"),("y_drive","y_beam"),("z_drive","z_axis")]
    issues=[f"{LABELS[a]} BG{s[a]} is not compatible with {LABELS[b]} BG{s[b]}." for a,b in pairs if abs(s[a]-s[b])>1]
    return not issues,issues

def calculate(requirements,sizes=None):
    r=normalize(requirements); s={g:max(1,min(4,int((sizes or {}).get(g,2)))) for g in GROUPS}; mods={g:module(g,s[g]) for g in GROUPS}
    length={g:{"columns":1.15+r["z_hub"],"x_beams":r["x_hub"]+.7,"y_beam":r["y_hub"]+.6,"z_axis":r["z_hub"]+.35,"x_guides":r["x_hub"]+.45,"y_guides":r["y_hub"]+.35,"z_guides":r["z_hub"]+.2}.get(g,.38) for g in GROUPS}
    qty={g:(4 if g=="columns" else 2 if g in {"x_beams","x_carriages","x_guides","x_drives"} else 1) for g in GROUPS}
    masses={g:mods[g]["mass_per_m"]*length[g]*qty[g] for g in GROUPS}
    zm=r["payload"]+r["tool_mass"]+sum(masses[g] for g in ["z_axis","z_carriage","z_guides","z_drive"]); ym=zm+sum(masses[g] for g in ["y_beam","y_carriage","y_guides","y_drive"]); xm=ym+sum(masses[g] for g in ["x_carriages","x_drives"])
    grav=9.81; proc=math.sqrt(r["force_x"]**2+r["force_y"]**2+r["force_z"]**2); sf=1.25
    forces={"x":sf*(xm*r["max_acceleration"]+r["force_x"]+.035*xm*grav),"y":sf*(ym*r["max_acceleration"]+r["force_y"]+.035*ym*grav),"z":sf*(zm*(grav+r["max_acceleration"])+r["force_z"])}
    load=max(max(forces.values()),sf*(zm*grav+proc)); moment=load*(r["tool_offset"]+.25*r["z_hub"])
    cases={"static":zm*grav*sf,"dynamic":max(forces.values()),"process":proc*sf}; critical=max(cases,key=cases.get); cload=max(cases.values())
    weights={"columns":.75,"x_beams":1.16,"y_beam":1.32,"z_axis":1.12,"x_carriages":.48,"y_carriage":.54,"z_carriage":.5,"x_guides":.72,"y_guides":.78,"z_guides":.66,"x_drives":.3,"y_drive":.34,"z_drive":.27}
    defl={}
    for group in GROUPS:
        span=length[group] if KINDS[group] in {"beam","structure"} else 1.44
        sfactor=(span/2)**3 if KINDS[group] in {"beam","structure"} else 1
        local=cload*weights[group]+moment*(85 if KINDS[group] in {"guide","plate"} else 35)
        # Calibrated compliance surrogate: keeps output in a plausible POC millimetre range.
        defl[group]=max(.00005,8*local*sfactor/mods[group]["stiffness"])
    total=sum(defl.values()); comps=[]; maxu=0
    axes={"x_beams":"x","x_guides":"x","x_drives":"x","y_beam":"y","y_guides":"y","y_drive":"y","z_axis":"z","z_guides":"z","z_drive":"z"}
    for group in GROUPS:
        m=mods[group]; rel=forces.get(axes.get(group),load*weights[group]); ratios={"load":rel/m["force_capacity"],"moment":moment*weights[group]/m["moment_capacity"],"dynamic":rel*(1+.16*r["max_speed"])/m["dynamic_capacity"],"life":(r["target_life"]/m["life_rating"])*max(.25,rel/m["force_capacity"])**2.4,"stiffness_budget":defl[group]/max(r["max_deflection"]*.60,.001)}
        key=max(ratios,key=ratios.get); util=max(ratios.values())*100; maxu=max(maxu,util); cost=m["cost"]*qty[group]*(length[group] if KINDS[group] in {"beam","structure","guide"} else 1)
        comps.append({"id":group,"module_id":m["id"],"label":LABELS[group],"size":s[group],"mass":round(masses[group],2),"cost":round(cost,1),"utilization":round(util,1),"critical_criterion":key,"criteria":{k:round(v*100,1) for k,v in ratios.items()},"reserve":round(100-util,1),"deflection":round(defl[group],5),"section_mm":m["section_mm"]})
    ok,cissues=compatibility(s); issues=list(cissues); minsize=1+int(r["x_hub"]>4.2)+int(r["x_hub"]>6.2)
    if s["x_beams"]<minsize:issues.append(f"X beam BG{s['x_beams']} does not support the {r['x_hub']:.1f} m span envelope.")
    if maxu>100:issues.append(f"Peak component utilization is {maxu:.1f}%.")
    if total>r["max_deflection"]:issues.append(f"TCP deflection {total:.3f} mm exceeds {r['max_deflection']:.3f} mm.")
    valid=ok and s["x_beams"]>=minsize and maxu<=100 and total<=r["max_deflection"]
    eff=1/sum(1/mods[g]["stiffness"] for g in GROUPS); freq=(1/(2*math.pi))*math.sqrt(eff/max(xm,1)); canonical=json.dumps({"r":r,"s":s},sort_keys=True)
    return {"configuration_id":"CFG-"+hashlib.sha1(canonical.encode()).hexdigest()[:8].upper(),"requirements":r,"sizes":s,"modules":comps,"metrics":{"total_cost":round(sum(c["cost"] for c in comps),1),"total_mass":round(sum(masses.values())+r["payload"]+r["tool_mass"],1),"moving_masses":{"x":round(xm,1),"y":round(ym,1),"z":round(zm,1)},"axis_forces":{k:round(v,1) for k,v in forces.items()},"tcp_deflection":round(total,5),"allowed_deflection":r["max_deflection"],"max_utilization":round(maxu,1),"natural_frequency":round(freq,1),"critical_load_case":critical,"status":"valid" if valid else "invalid"},"deflection_breakdown":{k:round(v,5) for k,v in defl.items()},"load_cases":{k:round(v,1) for k,v in cases.items()},"violations":issues,"warnings":["Synthetic module data — demonstration only."],"valid":valid}

def optimize(requirements,strategy="minimum_cost"):
    # Deterministic coordinate search followed by a cheapest-valid downsizing pass.
    sizes={g:1 for g in GROUPS}; evaluated=0
    def penalty(result):
        m=result["metrics"]
        return max(1,m["max_utilization"]/100)+max(1,m["tcp_deflection"]/m["allowed_deflection"])+len([v for v in result["violations"] if "compatible" in v])*.25
    chosen=calculate(requirements,sizes); evaluated+=1
    while not chosen["valid"] and any(v<4 for v in sizes.values()) and evaluated<180:
        options=[]
        for group in GROUPS:
            if sizes[group]<4:
                trial=sizes.copy();trial[group]+=1; result=calculate(requirements,trial);evaluated+=1
                options.append((penalty(result)+result["metrics"]["total_cost"]*.000002,result))
        chosen=min(options,key=lambda x:x[0])[1];sizes=chosen["sizes"].copy()
    if not chosen["valid"]:
        sizes={g:4 for g in GROUPS};chosen=calculate(requirements,sizes);evaluated+=1
    # Remove unnecessary cost where constraints remain satisfied.
    changed=True
    while changed:
        changed=False
        for group in sorted(GROUPS,key=lambda g:next(c["cost"] for c in chosen["modules"] if c["id"]==g),reverse=True):
            if sizes[group]>1:
                trial=sizes.copy();trial[group]-=1;result=calculate(requirements,trial);evaluated+=1
                if result["valid"] and result["metrics"]["total_cost"]<chosen["metrics"]["total_cost"]:
                    chosen=result;sizes=trial;changed=True
    # Reserve-oriented strategies spend more on dominant contributors.
    upgrades=3 if strategy=="balanced" else 7 if strategy=="high_performance" else 0
    for _ in range(upgrades):
        options=[]
        for group in GROUPS:
            if chosen["sizes"][group]<4:
                trial=chosen["sizes"].copy();trial[group]+=1;candidate=calculate(requirements,trial);evaluated+=1
                if candidate["valid"]:
                    metric=candidate["metrics"]["tcp_deflection"]/candidate["metrics"]["allowed_deflection"]+candidate["metrics"]["max_utilization"]/100
                    options.append((metric,candidate))
        if not options:break
        chosen=min(options,key=lambda item:item[0])[1]
    chosen["optimization"]={"strategy":strategy,"evaluated":evaluated,"feasible_found":1 if chosen["valid"] else 0,"heuristic":True};return chosen

def compare(requirements):return [optimize(requirements,s) for s in ["minimum_cost","balanced","high_performance"]]
