from api.engine import GROUPS, SCENARIOS, calculate, compatibility, optimize
from api.index import ChatRequest, local_assistant

BASE=SCENARIOS[0]["requirements"]
SIZES={g:3 for g in GROUPS}

def test_payload_increases_static_loading():
    low=calculate({**BASE,"payload":10},SIZES)
    high=calculate({**BASE,"payload":80},SIZES)
    assert high["load_cases"]["static"] >= low["load_cases"]["static"]

def test_span_increases_beam_deflection():
    short=calculate({**BASE,"x_hub":2,"support_pairs":2},SIZES)
    long=calculate({**BASE,"x_hub":6,"support_pairs":2},SIZES)
    assert long["deflection_breakdown"]["x_beams"] > short["deflection_breakdown"]["x_beams"]

def test_additional_supports_reduce_x_deflection_but_cost_more():
    sparse=calculate({**BASE,"x_hub":15,"support_pairs":2},SIZES)
    supported=calculate({**BASE,"x_hub":15,"support_pairs":4},SIZES)
    assert supported["deflection_breakdown"]["x_beams"] < sparse["deflection_breakdown"]["x_beams"]
    assert supported["metrics"]["total_cost"] > sparse["metrics"]["total_cost"]
    assert supported["metrics"]["layout_flexibility"] < sparse["metrics"]["layout_flexibility"]

def test_fifteen_metre_bridge_and_support_metrics():
    result=calculate({**BASE,"x_hub":15,"support_pairs":4},SIZES)
    assert result["requirements"]["x_hub"] == 15
    assert result["metrics"]["support_pairs"] == 4
    assert result["metrics"]["support_spacing"] <= 6

def test_new_travel_payload_ranges_and_chf_price():
    result=calculate({**BASE,"x_hub":30,"y_hub":15,"z_hub":4,"payload":3000,"support_pairs":6},{g:4 for g in GROUPS})
    assert result["requirements"] | {"x_hub":30,"y_hub":15,"z_hub":4,"payload":3000} == result["requirements"]
    assert 15000 <= result["metrics"]["total_cost"] <= 400000

def test_strokes_round_and_out_of_range_values_report_adjustment():
    result=calculate({**BASE,"x_hub":35.4,"y_hub":7.6,"z_hub":0.2,"payload":5000},SIZES)
    assert result["requirements"]["x_hub"] == 30
    assert result["requirements"]["y_hub"] == 8
    assert result["requirements"]["z_hub"] == 1
    assert result["requirements"]["payload"] == 3000
    assert {a["field"] for a in result["adjustments"]} >= {"x_hub","y_hub","z_hub","payload"}

def test_stiffer_size_reduces_own_contribution():
    small=calculate(BASE,{**SIZES,"y_beam":2})
    large=calculate(BASE,{**SIZES,"y_beam":4})
    assert large["deflection_breakdown"]["y_beam"] < small["deflection_breakdown"]["y_beam"]

def test_acceleration_increases_force():
    low=calculate({**BASE,"max_acceleration":1},SIZES)
    high=calculate({**BASE,"max_acceleration":8},SIZES)
    assert high["metrics"]["axis_forces"]["x"] > low["metrics"]["axis_forces"]["x"]

def test_process_force_increases_load():
    low=calculate({**BASE,"force_x":0},SIZES)
    high=calculate({**BASE,"force_x":1500},SIZES)
    assert high["load_cases"]["process"] > low["load_cases"]["process"]

def test_compatibility_is_enforced():
    ok,_=compatibility(SIZES)
    bad,issues=compatibility({**SIZES,"x_beams":1,"x_guides":4})
    assert ok and not bad and issues

def test_invalid_combination_marked():
    result=calculate({**BASE,"payload":250,"max_acceleration":12,"max_deflection":.03},{g:1 for g in GROUPS})
    assert not result["valid"] and result["violations"]

def test_manual_size_changes_metrics():
    a=calculate(BASE,SIZES)
    b=calculate(BASE,{**SIZES,"z_axis":4})
    assert a["metrics"] != b["metrics"]

def test_breakdown_sums_to_total():
    result=calculate(BASE,SIZES)
    assert abs(sum(result["deflection_breakdown"].values())-result["metrics"]["tcp_deflection"]) < .0001

def test_scenarios_and_determinism():
    assert len(SCENARIOS)==3
    for scenario in SCENARIOS:
        a=calculate(scenario["requirements"],SIZES)
        b=calculate(scenario["requirements"],SIZES)
        assert a==b

def test_optimizer_returns_compatible_configuration():
    for scenario in SCENARIOS:
        result=optimize(scenario["requirements"],"minimum_cost")
        ok,_=compatibility(result["sizes"])
        assert ok

def test_chat_module_change_is_proposed_not_applied():
    body=ChatRequest(message="Change the Y beam to BG4",requirements=BASE,sizes=SIZES)
    reply=local_assistant(body)
    assert reply["requires_confirmation"]
    assert reply["proposed_size_changes"] == {"y_beam":4}
    assert body.sizes["y_beam"] == 3
    assert reply["result"]["sizes"]["y_beam"] == 4

def test_chat_cost_reduction_returns_confirmable_configuration():
    body=ChatRequest(message="Can we reduce cost?",requirements=BASE,sizes={g:4 for g in GROUPS})
    reply=local_assistant(body)
    assert reply["requires_confirmation"]
    assert reply["proposed_size_changes"]
    assert set(reply["proposed_size_changes"]).issubset(GROUPS)
