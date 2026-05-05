"""
QualiBid — Demo Project Generator
Generates 10 realistic project datasets for demo purposes.
Run: python3 generate_projects.py
"""
import json, random, math
from pathlib import Path

random.seed(42)
OUT = Path("mock_data/projects")
OUT.mkdir(parents=True, exist_ok=True)

# ── Project definitions ──────────────────────────────────────────────────────
PROJECTS = [
    {"id":"p01","name":"Riverside Medical Office Campus","location":"Austin, TX","size_sf":142000,"type":"Medical Office","loc_factor":0.94,"type_mult":1.35,"stories":3,"months":24,"fee":4.5,"contingency":3.0},
    {"id":"p02","name":"One Arts District Tower","location":"Dallas, TX","size_sf":280000,"type":"Mixed-Use High-Rise","loc_factor":0.96,"type_mult":1.20,"stories":22,"months":30,"fee":4.0,"contingency":3.0},
    {"id":"p03","name":"Hillsboro Elementary School","location":"Nashville, TN","size_sf":85000,"type":"K-12 Education","loc_factor":0.88,"type_mult":0.95,"stories":2,"months":18,"fee":5.0,"contingency":3.5},
    {"id":"p04","name":"The Peaks at Stapleton","location":"Denver, CO","size_sf":210000,"type":"Multifamily Residential","loc_factor":0.98,"type_mult":0.88,"stories":6,"months":26,"fee":4.5,"contingency":3.0},
    {"id":"p05","name":"SunCore Data Center","location":"Phoenix, AZ","size_sf":60000,"type":"Mission-Critical / Data Center","loc_factor":0.92,"type_mult":1.85,"stories":2,"months":20,"fee":4.5,"contingency":4.0},
    {"id":"p06","name":"Brickell Restaurant & Retail","location":"Miami, FL","size_sf":22000,"type":"Retail / Restaurant","loc_factor":1.02,"type_mult":0.78,"stories":1,"months":10,"fee":6.0,"contingency":4.0},
    {"id":"p07","name":"Memorial Hospital Patient Tower","location":"Houston, TX","size_sf":350000,"type":"Hospital / Healthcare","loc_factor":0.95,"type_mult":1.85,"stories":8,"months":36,"fee":3.5,"contingency":3.0},
    {"id":"p08","name":"Pacific HQ Campus","location":"Seattle, WA","size_sf":175000,"type":"Corporate Office","loc_factor":1.18,"type_mult":1.15,"stories":5,"months":22,"fee":4.5,"contingency":3.0},
    {"id":"p09","name":"Hartsfield Distribution Hub","location":"Atlanta, GA","size_sf":400000,"type":"Warehouse / Distribution","loc_factor":0.88,"type_mult":0.55,"stories":1,"months":14,"fee":5.0,"contingency":2.5},
    {"id":"p10","name":"Dirksen Federal Courthouse Annex","location":"Chicago, IL","size_sf":120000,"type":"Government / Courthouse","loc_factor":1.15,"type_mult":1.28,"stories":4,"months":28,"fee":4.0,"contingency":3.5},
]

# ── Base trade definitions ($/SF at national average, office baseline) ───────
BASE_TRADES = [
    {"trade":"Demolition & Site Clearing","csi":"02 40 00","low":0.80,"mid":1.20,"high":1.80,"excl_risk":"Hazardous material abatement","type_weights":{"Medical Office":1.1,"Hospital / Healthcare":1.2,"K-12 Education":1.0,"Mixed-Use High-Rise":1.3,"Multifamily Residential":0.9,"Mission-Critical / Data Center":1.0,"Retail / Restaurant":0.8,"Corporate Office":1.0,"Warehouse / Distribution":0.7,"Government / Courthouse":1.1}},
    {"trade":"Concrete","csi":"03 00 00","low":3.00,"mid":3.80,"high":5.00,"excl_risk":"Vapor barrier and underslab insulation","type_weights":{"Medical Office":1.1,"Hospital / Healthcare":1.3,"K-12 Education":1.0,"Mixed-Use High-Rise":1.5,"Multifamily Residential":1.2,"Mission-Critical / Data Center":1.4,"Retail / Restaurant":0.7,"Corporate Office":1.1,"Warehouse / Distribution":0.9,"Government / Courthouse":1.2}},
    {"trade":"Masonry","csi":"04 00 00","low":1.50,"mid":2.10,"high":2.80,"excl_risk":"CMU backup wall","type_weights":{"Medical Office":1.1,"Hospital / Healthcare":1.2,"K-12 Education":1.3,"Mixed-Use High-Rise":0.8,"Multifamily Residential":0.9,"Mission-Critical / Data Center":0.8,"Retail / Restaurant":1.0,"Corporate Office":1.0,"Warehouse / Distribution":0.6,"Government / Courthouse":1.5}},
    {"trade":"Structural Steel & Misc Metals","csi":"05 00 00","low":4.00,"mid":5.20,"high":6.50,"excl_risk":"Miscellaneous metals and embeds","type_weights":{"Medical Office":1.1,"Hospital / Healthcare":1.4,"K-12 Education":1.0,"Mixed-Use High-Rise":1.8,"Multifamily Residential":1.2,"Mission-Critical / Data Center":1.5,"Retail / Restaurant":0.7,"Corporate Office":1.1,"Warehouse / Distribution":1.4,"Government / Courthouse":1.2}},
    {"trade":"Roofing, Waterproofing & Insulation","csi":"07 00 00","low":2.20,"mid":3.00,"high":4.00,"excl_risk":"Below-slab waterproofing","type_weights":{"Medical Office":1.1,"Hospital / Healthcare":1.2,"K-12 Education":1.0,"Mixed-Use High-Rise":0.6,"Multifamily Residential":0.9,"Mission-Critical / Data Center":1.3,"Retail / Restaurant":1.1,"Corporate Office":1.0,"Warehouse / Distribution":1.0,"Government / Courthouse":1.1}},
    {"trade":"Doors, Frames, Hardware & Glazing","csi":"08 00 00","low":2.80,"mid":3.60,"high":4.80,"excl_risk":"Storefront glazing system","type_weights":{"Medical Office":1.1,"Hospital / Healthcare":1.3,"K-12 Education":1.0,"Mixed-Use High-Rise":1.4,"Multifamily Residential":1.0,"Mission-Critical / Data Center":0.9,"Retail / Restaurant":1.5,"Corporate Office":1.2,"Warehouse / Distribution":0.5,"Government / Courthouse":1.4}},
    {"trade":"Drywall & Framing","csi":"09 20 00","low":1.80,"mid":2.40,"high":3.20,"excl_risk":"Shaft wall assemblies","type_weights":{"Medical Office":1.1,"Hospital / Healthcare":1.3,"K-12 Education":1.0,"Mixed-Use High-Rise":1.2,"Multifamily Residential":1.3,"Mission-Critical / Data Center":1.1,"Retail / Restaurant":0.8,"Corporate Office":1.1,"Warehouse / Distribution":0.3,"Government / Courthouse":1.2}},
    {"trade":"Flooring","csi":"09 60 00","low":2.50,"mid":3.20,"high":4.20,"excl_risk":"Specialty sheet vinyl in procedure rooms","type_weights":{"Medical Office":1.2,"Hospital / Healthcare":1.4,"K-12 Education":0.9,"Mixed-Use High-Rise":1.1,"Multifamily Residential":1.2,"Mission-Critical / Data Center":0.8,"Retail / Restaurant":1.3,"Corporate Office":1.2,"Warehouse / Distribution":0.4,"Government / Courthouse":1.3}},
    {"trade":"Painting & Wall Coverings","csi":"09 90 00","low":1.00,"mid":1.40,"high":1.80,"excl_risk":"Exterior painting","type_weights":{"Medical Office":1.1,"Hospital / Healthcare":1.2,"K-12 Education":1.0,"Mixed-Use High-Rise":1.0,"Multifamily Residential":1.0,"Mission-Critical / Data Center":0.8,"Retail / Restaurant":1.0,"Corporate Office":1.1,"Warehouse / Distribution":0.3,"Government / Courthouse":1.2}},
    {"trade":"Acoustical Ceilings (ACT)","csi":"09 51 00","low":1.40,"mid":1.80,"high":2.40,"excl_risk":"Gypsum board soffits and clouds","type_weights":{"Medical Office":1.1,"Hospital / Healthcare":1.2,"K-12 Education":1.0,"Mixed-Use High-Rise":1.1,"Multifamily Residential":0.6,"Mission-Critical / Data Center":1.0,"Retail / Restaurant":0.9,"Corporate Office":1.1,"Warehouse / Distribution":0.2,"Government / Courthouse":1.2}},
    {"trade":"Specialties","csi":"10 00 00","low":0.70,"mid":1.00,"high":1.40,"excl_risk":"ADA signage package","type_weights":{"Medical Office":1.1,"Hospital / Healthcare":1.3,"K-12 Education":1.2,"Mixed-Use High-Rise":1.0,"Multifamily Residential":0.8,"Mission-Critical / Data Center":0.7,"Retail / Restaurant":1.0,"Corporate Office":1.0,"Warehouse / Distribution":0.4,"Government / Courthouse":1.4}},
    {"trade":"Fire Suppression (Sprinklers)","csi":"21 00 00","low":1.80,"mid":2.40,"high":3.00,"excl_risk":"Kitchen hood fire suppression","type_weights":{"Medical Office":1.1,"Hospital / Healthcare":1.3,"K-12 Education":1.1,"Mixed-Use High-Rise":1.2,"Multifamily Residential":1.0,"Mission-Critical / Data Center":1.4,"Retail / Restaurant":1.0,"Corporate Office":1.0,"Warehouse / Distribution":0.8,"Government / Courthouse":1.1}},
    {"trade":"Plumbing","csi":"22 00 00","low":3.80,"mid":4.80,"high":6.00,"excl_risk":"Medical gas outlets and zone valves","type_weights":{"Medical Office":1.3,"Hospital / Healthcare":1.8,"K-12 Education":1.0,"Mixed-Use High-Rise":1.2,"Multifamily Residential":1.4,"Mission-Critical / Data Center":1.1,"Retail / Restaurant":1.5,"Corporate Office":0.9,"Warehouse / Distribution":0.4,"Government / Courthouse":1.0}},
    {"trade":"Mechanical (HVAC)","csi":"23 00 00","low":4.50,"mid":5.80,"high":7.20,"excl_risk":"Medical gas rough-in and kitchen hood exhaust","type_weights":{"Medical Office":1.3,"Hospital / Healthcare":1.8,"K-12 Education":1.1,"Mixed-Use High-Rise":1.2,"Multifamily Residential":0.9,"Mission-Critical / Data Center":2.2,"Retail / Restaurant":1.0,"Corporate Office":1.1,"Warehouse / Distribution":0.4,"Government / Courthouse":1.1}},
    {"trade":"Electrical","csi":"26 00 00","low":3.50,"mid":4.40,"high":5.50,"excl_risk":"Fire alarm system","type_weights":{"Medical Office":1.3,"Hospital / Healthcare":1.8,"K-12 Education":1.1,"Mixed-Use High-Rise":1.3,"Multifamily Residential":1.0,"Mission-Critical / Data Center":2.5,"Retail / Restaurant":1.0,"Corporate Office":1.2,"Warehouse / Distribution":0.6,"Government / Courthouse":1.2}},
    {"trade":"Communications (Data, AV, Tel)","csi":"27 00 00","low":1.20,"mid":1.80,"high":2.40,"excl_risk":"AV rough-in for conference rooms","type_weights":{"Medical Office":1.2,"Hospital / Healthcare":1.4,"K-12 Education":1.3,"Mixed-Use High-Rise":1.1,"Multifamily Residential":0.8,"Mission-Critical / Data Center":2.0,"Retail / Restaurant":0.8,"Corporate Office":1.6,"Warehouse / Distribution":0.5,"Government / Courthouse":1.5}},
    {"trade":"Electronic Safety & Security","csi":"28 00 00","low":1.00,"mid":1.40,"high":1.90,"excl_risk":"Exterior access control and parking","type_weights":{"Medical Office":1.2,"Hospital / Healthcare":1.4,"K-12 Education":1.5,"Mixed-Use High-Rise":1.2,"Multifamily Residential":0.9,"Mission-Critical / Data Center":2.0,"Retail / Restaurant":1.0,"Corporate Office":1.1,"Warehouse / Distribution":0.6,"Government / Courthouse":2.2}},
    {"trade":"Earthwork, Grading & Site Preparation","csi":"31 00 00","low":2.00,"mid":2.80,"high":3.80,"excl_risk":"Rock excavation allowance","type_weights":{"Medical Office":1.1,"Hospital / Healthcare":1.2,"K-12 Education":1.0,"Mixed-Use High-Rise":1.5,"Multifamily Residential":1.0,"Mission-Critical / Data Center":1.3,"Retail / Restaurant":0.8,"Corporate Office":1.0,"Warehouse / Distribution":1.2,"Government / Courthouse":1.1}},
    {"trade":"Site Paving, Curbs & Landscaping","csi":"32 00 00","low":2.80,"mid":3.60,"high":4.80,"excl_risk":"Landscaping and irrigation","type_weights":{"Medical Office":1.1,"Hospital / Healthcare":1.2,"K-12 Education":1.2,"Mixed-Use High-Rise":0.7,"Multifamily Residential":1.0,"Mission-Critical / Data Center":1.0,"Retail / Restaurant":1.2,"Corporate Office":1.1,"Warehouse / Distribution":1.4,"Government / Courthouse":1.2}},
    {"trade":"Site Utilities (Water, Sewer, Storm, Gas)","csi":"33 00 00","low":2.00,"mid":2.80,"high":3.60,"excl_risk":"Underground fire line","type_weights":{"Medical Office":1.1,"Hospital / Healthcare":1.3,"K-12 Education":1.0,"Mixed-Use High-Rise":1.2,"Multifamily Residential":1.1,"Mission-Critical / Data Center":1.3,"Retail / Restaurant":0.9,"Corporate Office":1.0,"Warehouse / Distribution":1.0,"Government / Courthouse":1.0}},
]

# ── Fixed contractor roster ──────────────────────────────────────────────────
# Three contractors bid every trade on every project. Tiers drive bid behavior:
#   strong         → premium pricing, zero exclusions, no post-bid revisions
#   marginal       → mid-market pricing, 1-2 exclusions, occasional post-bid update
#   underqualified → low pricing on paper, several exclusions that mask true cost
CONTRACTORS = [
    {
        "slug": "lone_star_healthcare",
        "name": "Lone Star Healthcare Construction, LLC",
        "contact": "Reagan Castillo",
        "email": "rcastillo@lonestarhealthcare.com",
        "tier": "strong",
        "bid_modifier": 1.04,
        "excl_count": 0,
        "source": "PDF",
        "submitted_date": "2024-04-18",
    },
    {
        "slug": "capitol_commercial",
        "name": "Capitol Commercial Builders",
        "contact": "Jordan Walsh",
        "email": "jwalsh@capitolcommercial.com",
        "tier": "marginal",
        "bid_modifier": 0.96,
        "excl_count": 2,
        "source": "Excel",
        "submitted_date": "2024-04-19",
    },
    {
        "slug": "pedernales_custom",
        "name": "Pedernales Custom Homes & Renovations, Inc.",
        "contact": "Wyatt Burnham",
        "email": "wburnham@pedernalescustom.com",
        "tier": "underqualified",
        "bid_modifier": 0.78,
        "excl_count": 3,
        "source": "Email",
        "submitted_date": "2024-04-20",
    },
]

POST_BID_TEMPLATES = [
    ("We can include {scope} for an additional ${delta:,}. Revised total would be ${revised:,}.","RE: {proj} - {scope} Add"),
    ("Following up on our call — we can pick up {scope} for ${delta:,} additional. Revised total ${revised:,}.","RE: {proj} - {scope} Clarification"),
    ("Per our conversation this morning: {scope} can be added for ${delta:,}. New total is ${revised:,}.","RE: {proj} - {scope} Scope Add"),
]

def round_k(val, k=5000):
    return round(val / k) * k

def make_bid(trade_def, proj, contractor, base_total, has_update=False):
    excl_risk = trade_def["excl_risk"]
    excl_count = contractor["excl_count"]
    total = max(round_k(base_total * contractor["bid_modifier"] * random.uniform(0.97, 1.04)), 0)
    update_delta = round_k(total * 0.07)

    exclusions = []
    if excl_count >= 1:
        exclusions.append(f"{excl_risk} - NOT IN CONTRACT")
    if excl_count >= 2:
        exclusions.append("Extended warranty (by owner)")
    if excl_count >= 3:
        exclusions.append("Specialty subcontractors and engineered systems (separate quote)")

    post_bid_updates = []
    if has_update and excl_count >= 1:
        revised = total + update_delta
        tmpl = random.choice(POST_BID_TEMPLATES)
        post_bid_updates.append({
            "update_id": f"{trade_def['csi'][:2]}-{contractor['slug'][:3].upper()}-U1",
            "date": "2024-04-28",
            "from": f"{contractor['contact']} <{contractor['email']}>",
            "subject": tmpl[1].format(proj=proj["name"], scope=excl_risk),
            "body": tmpl[0].format(scope=excl_risk, delta=update_delta, revised=revised),
            "revised_total": revised,
            "delta": update_delta,
            "scope_added": excl_risk
        })

    num_items = random.randint(3, 6)
    amounts = [round_k(total / num_items * (0.8 + random.random() * 0.4)) for _ in range(num_items - 1)]
    amounts.append(max(round_k(total - sum(amounts)), 0))
    items = [{"description": f"{trade_def['trade']} - component {i+1}", "amount": a} for i, a in enumerate(amounts) if a > 0]
    if not items:
        items = [{"description": f"Complete {trade_def['trade']} scope", "amount": total}]

    return {
        "sub_id": f"{trade_def['csi'][:2]}-{contractor['slug']}",
        "company": contractor["name"],
        "contact": contractor["contact"],
        "email": contractor["email"],
        "source": contractor["source"],
        "submitted_date": contractor["submitted_date"],
        "base_bid": total,
        "line_items": items,
        "exclusions": exclusions,
        "inclusions": ["All labor, material, and permits per contract documents"],
        "notes": f"Bid per {proj['name']} drawings issued 03/15/2024.",
        "post_bid_updates": post_bid_updates
    }

def make_trade(trade_def, proj):
    tw = trade_def["type_weights"].get(proj["type"], 1.0)
    mid_psf = trade_def["mid"] * tw * proj["loc_factor"] * proj["type_mult"]
    sf = proj["size_sf"]
    base_total = round_k(mid_psf * sf)

    # Only the marginal contractor (Capitol Commercial) gets occasional post-bid revisions.
    has_update = random.random() < 0.35
    bids = []
    for contractor in CONTRACTORS:
        send_update = has_update and contractor["tier"] == "marginal"
        bids.append(make_bid(trade_def, proj, contractor, base_total, has_update=send_update))
    return {
        "trade": trade_def["trade"],
        "csi_code": trade_def["csi"],
        "bids": bids
    }

def make_gc(proj):
    sf = proj["size_sf"]
    m  = proj["months"]
    lf = proj["loc_factor"]
    pm_rate   = round(13000 * lf)
    super_rate = round(10500 * lf)
    total = round((pm_rate + super_rate) * m + sf * 8 * lf)
    items = [
        {"category":"Project Management","items":[
            {"description":f"Project Manager ({m} months)","unit":"LS","monthly_rate":pm_rate,"months":m,"total":pm_rate*m},
            {"description":f"Project Engineer ({m} months)","unit":"LS","monthly_rate":round(7500*lf),"months":m,"total":round(7500*lf)*m},
        ]},
        {"category":"Field Supervision","items":[
            {"description":f"General Superintendent ({m} months)","unit":"LS","monthly_rate":super_rate,"months":m,"total":super_rate*m},
            {"description":f"Assistant Superintendent ({m-4} months)","unit":"LS","monthly_rate":round(8000*lf),"months":m-4,"total":round(8000*lf)*(m-4)},
        ]},
        {"category":"Temporary Facilities","items":[
            {"description":"Field office, toilets, fencing, temp power","unit":"LS","monthly_rate":round(4000*lf),"months":m,"total":round(4000*lf)*m},
        ]},
        {"category":"Site Operations","items":[
            {"description":"Cleanup, dumpsters, safety, vehicles","unit":"LS","monthly_rate":round(5500*lf),"months":m,"total":round(5500*lf)*m},
        ]},
        {"category":"Insurance & Bonding","items":[
            {"description":"Builder's Risk, GL, Payment & Performance Bond","unit":"LS","monthly_rate":None,"months":None,"total":round(sf*5*lf)},
        ]},
        {"category":"Permits & Fees","items":[
            {"description":"Building permit, special inspections, surveying","unit":"LS","monthly_rate":None,"months":None,"total":round(sf*1.8*lf)},
        ]},
        {"category":"Technology","items":[
            {"description":"BIM, Procore, closeout documentation","unit":"LS","monthly_rate":round(1800*lf),"months":m,"total":round(1800*lf)*m},
        ]},
    ]
    subtotal = sum(
        (i["total"] for cat in items for i in cat["items"])
    )
    return {
        "section":"General Conditions & General Requirements",
        "csi_code":"01 00 00",
        "description":f"GC overhead for {proj['name']}",
        "duration_months":m,
        "line_items":items,
        "subtotal_gc":subtotal,
        "gc_fee_percent":proj["fee"],
        "contingency_percent":proj["contingency"]
    }

def make_benchmarks(proj):
    benches = []
    for td in BASE_TRADES:
        tw = td["type_weights"].get(proj["type"], 1.0)
        lf = proj["loc_factor"] * proj["type_mult"]
        unit = "$/stop" if td["trade"] == "Elevator" else "$/SF"
        benches.append({
            "trade": td["trade"],
            "csi_code": td["csi"],
            "unit": unit,
            "low":  round(td["low"]  * tw * lf, 2),
            "mid":  round(td["mid"]  * tw * lf, 2),
            "high": round(td["high"] * tw * lf, 2),
            "notes": f"{proj['type']} benchmark — {proj['location']}"
        })
    return {"source":"RSMeans 2024 (Simulated)","location":proj["location"],"location_factor":proj["loc_factor"],"project_type":proj["type"],"benchmarks":benches}

# ── Generate all projects ────────────────────────────────────────────────────
index = []
for proj in PROJECTS:
    print(f"Generating {proj['id']}: {proj['name']} ({proj['size_sf']:,} SF) ...")
    trades_data = [make_trade(td, proj) for td in BASE_TRADES]
    project_json = {
        "bids": {
            "project": {
                "name": proj["name"],
                "location": proj["location"],
                "size_sf": proj["size_sf"],
                "type": proj["type"],
                "stories": proj["stories"]
            },
            "trades": trades_data
        },
        "benchmarks": make_benchmarks(proj),
        "general_conditions": make_gc(proj)
    }
    out_path = OUT / f"{proj['id']}.json"
    with open(out_path, "w") as f:
        json.dump(project_json, f, indent=2)

    # Compute totals for index
    direct = sum(
        (b["post_bid_updates"][-1]["revised_total"] if b["post_bid_updates"] else b["base_bid"])
        for t in trades_data
        for b in [sorted(t["bids"], key=lambda x: (x["post_bid_updates"][-1]["revised_total"] if x["post_bid_updates"] else x["base_bid"]))[0]]
    )
    index.append({
        "id": proj["id"],
        "name": proj["name"],
        "location": proj["location"],
        "size_sf": proj["size_sf"],
        "type": proj["type"],
        "stories": proj["stories"],
        "est_direct_cost": direct,
        "file": f"{proj['id']}.json"
    })

# Write index + also copy p01 as default bids.json for backward compat
with open(OUT / "index.json", "w") as f:
    json.dump(index, f, indent=2)

print(f"\nDone. {len(PROJECTS)} projects written to {OUT}/")
for item in index:
    print(f"  {item['id']} | {item['name']:45s} | {item['size_sf']:>7,} SF | est ${item['est_direct_cost']:>12,.0f}")
