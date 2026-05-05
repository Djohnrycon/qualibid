import copy
import json
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from dotenv import load_dotenv
import anthropic
from ingestor import read_file
from scorer import score_contractor, extract_bid_data, DEFAULT_PREQUAL_CATEGORIES

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

st.set_page_config(page_title="QualiBid", layout="wide", page_icon="🏗️")

@st.cache_data
def load_projects_index():
    with open("mock_data/projects/index.json") as f:
        return json.load(f)

@st.cache_data
def load_project(project_id):
    with open(f"mock_data/projects/{project_id}.json") as f:
        return json.load(f)

# ── New project generator (used by sidebar form) ─────────────────────────────
def generate_new_project(name, location, btype, sf, stories, months, fee=5.0, contingency=3.0):
    import subprocess, sys
    loc_factors = {"Austin, TX":0.94,"Dallas, TX":0.96,"Nashville, TN":0.88,"Denver, CO":0.98,
                   "Phoenix, AZ":0.92,"Miami, FL":1.02,"Houston, TX":0.95,"Seattle, WA":1.18,
                   "Atlanta, GA":0.88,"Chicago, IL":1.15,"New York, NY":1.35,"Los Angeles, CA":1.22,
                   "Other":1.00}
    type_mults = {"Medical Office":1.35,"Hospital / Healthcare":1.85,"K-12 Education":0.95,
                  "Multifamily Residential":0.88,"Mission-Critical / Data Center":1.85,
                  "Retail / Restaurant":0.78,"Corporate Office":1.15,
                  "Warehouse / Distribution":0.90,"Government / Courthouse":1.28,"Mixed-Use High-Rise":1.20}
    lf = loc_factors.get(location, 1.00)
    tm = type_mults.get(btype, 1.00)
    idx_data = load_projects_index()
    new_id = f"p{len(idx_data)+1:02d}"
    proj_def = {"id":new_id,"name":name,"location":location,"size_sf":sf,"type":btype,
                "loc_factor":lf,"type_mult":tm,"stories":stories,"months":months,"fee":fee,"contingency":contingency}
    script = f"""
import json, random, sys
sys.path.insert(0, '.')
from generate_projects import BASE_TRADES, make_trade, make_gc, make_benchmarks
from pathlib import Path
random.seed(None)
proj = {proj_def}
trades_out = [make_trade(td, proj) for td in BASE_TRADES]
out = {{"bids":{{"project":{{"name":proj["name"],"location":proj["location"],"size_sf":proj["size_sf"],"type":proj["type"],"stories":proj["stories"]}},"trades":trades_out}},
        "benchmarks":make_benchmarks(proj),"general_conditions":make_gc(proj)}}
Path("mock_data/projects/{new_id}.json").write_text(json.dumps(out, indent=2))
rec = sum(min((b["post_bid_updates"][-1]["revised_total"] if b["post_bid_updates"] else b["base_bid"]) for b in t["bids"]) for t in trades_out)
idx = json.loads(Path("mock_data/projects/index.json").read_text())
idx.append({{"id":"{new_id}","name":proj["name"],"location":proj["location"],"size_sf":proj["size_sf"],"type":proj["type"],"stories":proj["stories"],"est_direct_cost":rec,"file":"{new_id}.json"}})
Path("mock_data/projects/index.json").write_text(json.dumps(idx, indent=2))
print("OK")
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    return new_id, result.returncode == 0, result.stderr

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("marketing/QauliBid_Logo.png", width=220)
    st.markdown("---")
    st.markdown("### Active Project")
    idx = load_projects_index()
    proj_options = {f"{p['name']} ({p['location']})": p["id"] for p in idx}
    selected_label = st.selectbox("Select Project", list(proj_options.keys()), index=0)
    selected_id = proj_options[selected_label]
    selected_meta = next(p for p in idx if p["id"] == selected_id)
    st.markdown(f"**Type:** {selected_meta['type']}")
    st.markdown(f"**Size:** {selected_meta['size_sf']:,} SF")
    st.markdown(f"**Stories:** {selected_meta['stories']}")
    st.markdown("---")
    with st.expander("➕ Create New Project"):
        with st.form("new_project_form"):
            np_name     = st.text_input("Project Name", placeholder="e.g. Main Street Office Tower")
            np_location = st.selectbox("Location", ["Austin, TX","Dallas, TX","Nashville, TN","Denver, CO",
                                                     "Phoenix, AZ","Miami, FL","Houston, TX","Seattle, WA",
                                                     "Atlanta, GA","Chicago, IL","New York, NY","Los Angeles, CA","Other"])
            np_type     = st.selectbox("Building Type", ["Medical Office","Hospital / Healthcare","K-12 Education",
                                                          "Multifamily Residential","Mission-Critical / Data Center",
                                                          "Retail / Restaurant","Corporate Office",
                                                          "Warehouse / Distribution","Government / Courthouse","Mixed-Use High-Rise"])
            np_sf       = st.number_input("Size (SF)", min_value=5000, max_value=5000000, value=75000, step=5000)
            np_stories  = st.number_input("Stories", min_value=1, max_value=80, value=3)
            np_months   = st.number_input("Duration (months)", min_value=3, max_value=72, value=18)
            if st.form_submit_button("Generate Project", type="primary"):
                with st.spinner("Generating project data..."):
                    new_id, ok, err = generate_new_project(np_name, np_location, np_type, np_sf, np_stories, np_months)
                if ok:
                    load_projects_index.clear()
                    load_project.clear()
                    st.success(f"Project created! Select it above.")
                else:
                    st.error(f"Error: {err[:200]}")
    st.markdown("---")
    st.caption("QualiBid v0.1 · Hackathon Demo")

proj_file = load_project(selected_id)
data        = proj_file["bids"]
bench_data  = proj_file["benchmarks"]
gc_data     = proj_file["general_conditions"]
project     = data["project"]
mock_trades = data["trades"]
benchmarks  = {b["trade"]: b for b in bench_data["benchmarks"]}
SF          = project["size_sf"]

SOURCE_COLORS = {"PDF": "#2563eb", "Excel": "#16a34a", "Email": "#d97706", "Upload": "#7c3aed"}
SOURCE_ICONS  = {"PDF": "📄", "Excel": "📊", "Email": "📧", "Upload": "📤"}

# ── Pre-Qualification helpers ───────────────────────────────────────────────
QUALIFIED_THRESHOLD = 70


def category_signature(categories):
    return hash(tuple((c["name"], c["description"]) for c in categories))


def ingest_one(uploaded_file):
    suffix = Path(uploaded_file.name).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getbuffer())
        tmp_path = tmp.name
    try:
        return read_file(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def combined_text(contractor):
    return "\n\n".join(
        f"=== FILE: {f['name']} ===\n\n{f['text']}"
        for f in contractor.get("files", [])
    )


def guess_contractor_name(text):
    for line in text.split("\n"):
        line = line.strip()
        if line and not line.startswith("==="):
            return line[:80]
    return "Unknown Contractor"


def composite_score(result, categories):
    weights = {c["name"]: c["weight"] for c in categories}
    total_w = sum(weights.values()) or 1.0
    weighted = sum(
        cs["score"] * weights.get(cs["category_name"], 0)
        for cs in result.get("category_scores", [])
    )
    return round(weighted / total_w, 1)


def score_color(score):
    if score >= 85: return "#16a34a"
    if score >= 70: return "#2563eb"
    if score >= 55: return "#d97706"
    return "#dc2626"


def build_rfp_context(project_data, meta, size_sf, extra_text):
    base = (
        f"Project: {project_data['name']}\n"
        f"Location: {project_data['location']}\n"
        f"Project Type: {project_data['type']}\n"
        f"Size: {size_sf:,} SF\n"
        f"Stories: {meta['stories']}"
    )
    if extra_text:
        return f"{base}\n\n# SUPPLEMENTAL SCOPE\n\n{extra_text}"
    return base


def init_prequal_state(project_id):
    """Idempotent. Ensures session_state.prequal[project_id] is initialized."""
    if "prequal" not in st.session_state:
        st.session_state.prequal = {}
    if project_id not in st.session_state.prequal:
        st.session_state.prequal[project_id] = {
            "rfp_extra_text": "",
            "rfp_extra_filename": "",
            "categories": [
                {**c, "weight": round(100 / len(DEFAULT_PREQUAL_CATEGORIES), 1)}
                for c in DEFAULT_PREQUAL_CATEGORIES
            ],
            "contractors": [],
            "cat_hash": None,
        }


def auto_extract_bid_data(contractor, project_trades):
    """Run Claude bid extraction for a contractor's current files. Stores result on the contractor.
    Shows a spinner; warns on failure but does not raise."""
    if not contractor.get("files"):
        contractor["bid_data"] = None
        return
    try:
        with st.spinner(f"Extracting bid data for {contractor.get('name') or 'contractor'}…"):
            contractor["bid_data"] = extract_bid_data(combined_text(contractor), project_trades)
    except Exception as e:
        contractor["bid_data"] = None
        st.warning(f"Bid extraction failed: {e}")


def merge_trades_with_uploads(mock_trades, contractors):
    """Return a copy of mock_trades with extracted bids from uploaded contractors appended."""
    merged = copy.deepcopy(mock_trades)
    trade_idx = {t["trade"]: t for t in merged}

    for c in contractors:
        bid_data = c.get("bid_data")
        if not bid_data:
            continue
        company = bid_data.get("company") or c.get("name") or "Uploaded Bidder"
        for tb in bid_data.get("trades", []):
            target = trade_idx.get(tb.get("trade_name"))
            if not target:
                continue
            target["bids"].append({
                "company": company,
                "contact": bid_data.get("contact") or "—",
                "email": bid_data.get("email") or "—",
                "submitted_date": bid_data.get("submitted_date") or "—",
                "source": bid_data.get("source") or "Upload",
                "base_bid": tb.get("base_bid", 0),
                "exclusions": tb.get("exclusions", []),
                "line_items": tb.get("line_items", []),
                "post_bid_updates": [],
            })

    return merged


def render_prequal_card(rank_label, name, composite, result):
    color = score_color(composite)
    with st.container(border=True):
        h1, h2 = st.columns([3, 1])
        with h1:
            st.markdown(
                f"<div style='color:#666; font-size:11px; font-weight:700; letter-spacing:0.5px;'>{rank_label}</div>"
                f"<div style='font-size:22px; font-weight:700; color:#111;'>{name}</div>",
                unsafe_allow_html=True,
            )
        with h2:
            st.markdown(
                f"<div style='font-size:42px; font-weight:800; color:{color}; "
                f"text-align:right; line-height:1;'>{composite}</div>"
                f"<div style='text-align:right; color:#666; font-size:12px;'>composite</div>",
                unsafe_allow_html=True,
            )

        for cs in result["category_scores"]:
            cat_color = score_color(cs["score"])
            st.markdown(
                f"<div style='margin:8px 0;'>"
                f"<div style='display:flex; justify-content:space-between; margin-bottom:3px;'>"
                f"<span style='font-size:13px; color:#444;'>{cs['category_name']}</span>"
                f"<span style='font-size:13px; font-weight:600; color:{cat_color};'>{cs['score']}/100</span>"
                f"</div>"
                f"<div style='background:#e5e7eb; height:8px; border-radius:4px; overflow:hidden;'>"
                f"<div style='background:{cat_color}; height:100%; width:{cs['score']}%;'></div>"
                f"</div></div>",
                unsafe_allow_html=True,
            )

        st.markdown("**Executive Summary**")
        st.write(result["overall_summary"])

        sc, cn = st.columns(2)
        with sc:
            st.markdown("**Strengths**")
            for s in result["strengths"]:
                st.markdown(f"- {s}")
        with cn:
            st.markdown("**Concerns**")
            for cc in result["concerns"]:
                st.markdown(f"- {cc}")

        with st.expander("📋 Audit trail — evidence per category"):
            for cs in result["category_scores"]:
                st.markdown(f"**{cs['category_name']}** — {cs['score']}/100")
                st.markdown(f"*{cs['reasoning']}*")
                for ev in cs["evidence"]:
                    st.markdown(f"> {ev}")
                st.markdown("")


# ── Initialize prequal state and build merged trades ────────────────────────
# Helpers above must be defined first; merged `trades` is what tabs 1–5 render.
init_prequal_state(selected_id)
trades = merge_trades_with_uploads(
    mock_trades,
    st.session_state.prequal[selected_id]["contractors"],
)


# ── Header ──────────────────────────────────────────────────────────────────
logo_col, title_col = st.columns([1, 5])
with logo_col:
    st.image("marketing/QauliBid_Logo.png", width=140)
with title_col:
    st.markdown("## AI-Powered Bid Leveling & Pre-Construction Intelligence")
    st.caption("Organize · Level · Benchmark · Propose — from first bid to final number")
st.divider()
col1, col2, col3, col4 = st.columns(4)
col1.metric("Project", project["name"])
col2.metric("Location", project["location"])
col3.metric("Size", f"{SF:,} SF")
col4.metric("Type", project["type"])
st.divider()

tab_prequal, tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "✅  Pre-Qualification",
    "📥  Bid Intake",
    "⚖️  Bid Leveling",
    "📊  Cost Benchmarking",
    "🚨  Risk Report",
    "📋  Proposal Summary",
    "📁  Documents & Uploads",
])

# ── Tab 0: Pre-Qualification ─────────────────────────────────────────────────
with tab_prequal:
    st.markdown("## Pre-Qualification")
    st.caption(
        f"Score and qualify bidders for **{project['name']}** before they enter the bid evaluation flow. "
        "Files accumulate per contractor — drop SOQs and financials now, add bid tabs and revisions later."
    )

    if "prequal" not in st.session_state:
        st.session_state.prequal = {}
    if selected_id not in st.session_state.prequal:
        st.session_state.prequal[selected_id] = {
            "rfp_extra_text": "",
            "rfp_extra_filename": "",
            "categories": [
                {**c, "weight": round(100 / len(DEFAULT_PREQUAL_CATEGORIES), 1)}
                for c in DEFAULT_PREQUAL_CATEGORIES
            ],
            "contractors": [],
            "cat_hash": None,
        }
    pq = st.session_state.prequal[selected_id]

    # ---- Project context ----
    with st.container(border=True):
        st.markdown("### Project Context")
        st.caption("Project metadata feeds the scoring. Optionally add a fuller scope document.")
        ctx_l, ctx_r = st.columns([2, 1])
        with ctx_l:
            st.markdown(
                f"**Project:** {project['name']}  \n"
                f"**Location:** {project['location']}  \n"
                f"**Type:** {project['type']}  \n"
                f"**Size:** {SF:,} SF  \n"
                f"**Stories:** {selected_meta['stories']}"
            )
        with ctx_r:
            rfp_file = st.file_uploader(
                "Supplemental scope doc (optional)",
                type=["pdf", "docx", "xlsx"],
                key=f"pq_rfp_{selected_id}",
            )
            if rfp_file and pq.get("rfp_extra_filename") != rfp_file.name:
                with tempfile.NamedTemporaryFile(delete=False, suffix=Path(rfp_file.name).suffix) as tmp:
                    tmp.write(rfp_file.getbuffer())
                    tmp_path = tmp.name
                try:
                    pq["rfp_extra_text"] = read_file(tmp_path)
                    pq["rfp_extra_filename"] = rfp_file.name
                finally:
                    Path(tmp_path).unlink(missing_ok=True)
                st.rerun()
            if pq.get("rfp_extra_filename"):
                st.success(f"Loaded: {pq['rfp_extra_filename']} ({len(pq['rfp_extra_text']):,} chars)")

    # ---- Categories ----
    with st.container(border=True):
        st.markdown("### Pre-Qualification Categories")
        st.caption(
            "Edit names, descriptions, and weights. Composite is normalized — weights don't need to sum to 100. "
            "Changing names or descriptions invalidates prior scores and triggers re-scoring on next run."
        )

        remove_idx = None
        for i, cat in enumerate(pq["categories"]):
            cols = st.columns([3, 5, 3, 1])
            with cols[0]:
                pq["categories"][i]["name"] = st.text_input(
                    "Name", cat["name"],
                    key=f"pq_catname_{selected_id}_{i}", label_visibility="collapsed",
                )
            with cols[1]:
                pq["categories"][i]["description"] = st.text_area(
                    "Description", cat["description"],
                    key=f"pq_catdesc_{selected_id}_{i}",
                    label_visibility="collapsed", height=68,
                )
            with cols[2]:
                pq["categories"][i]["weight"] = st.slider(
                    "Weight", 0, 100, int(cat["weight"]), step=1,
                    key=f"pq_catwt_{selected_id}_{i}", label_visibility="collapsed",
                )
            with cols[3]:
                if st.button("✕", key=f"pq_catdel_{selected_id}_{i}", help="Remove category"):
                    remove_idx = i
        if remove_idx is not None:
            pq["categories"].pop(remove_idx)
            st.rerun()
        if st.button("+ Add Category", key=f"pq_addcat_{selected_id}"):
            pq["categories"].append({
                "name": "New Category",
                "description": "Describe what to evaluate.",
                "weight": 0.0,
            })
            st.rerun()
        total_w = sum(c["weight"] for c in pq["categories"])
        st.caption(f"Total weight: {total_w:.0f}% (composite is normalized)")

    # ---- Contractor submissions (holistic upload) ----
    with st.container(border=True):
        st.markdown("### Contractor Submissions")
        st.caption(
            "Add each bidder. Drop their qualification documents — files accumulate over time. "
            "Add revisions or bid tabs later; the holistic file pile feeds every re-scoring."
        )

        remove_c_idx = None
        for i, c in enumerate(pq["contractors"]):
            label = c.get("name") or "(unnamed)"
            file_count = len(c.get("files", []))
            status = c.get("status", "pending")
            status_tag = {
                "qualified": "✅ Qualified",
                "rejected": "❌ Not Qualified",
                "pending": "⏳ Pending",
            }[status]
            header = f"Contractor {i+1}: {label} · {file_count} file(s) · {status_tag}"

            with st.expander(header, expanded=(file_count == 0)):
                if c.get("files"):
                    st.markdown("**Files in scope**")
                    file_to_remove = None
                    for fi, f in enumerate(c["files"]):
                        fc1, fc2, fc3 = st.columns([6, 3, 1])
                        with fc1:
                            st.markdown(f"- {f['name']}  *({len(f['text']):,} chars)*")
                        with fc2:
                            st.caption(f"added {f['added_at']}")
                        with fc3:
                            if st.button("Remove", key=f"pq_filedel_{selected_id}_{c['id']}_{fi}"):
                                file_to_remove = fi
                    if file_to_remove is not None:
                        c["files"].pop(file_to_remove)
                        auto_extract_bid_data(c, mock_trades)
                        st.rerun()
                else:
                    st.info("No files yet. Drop documents below.")

                counter = c.get("upload_counter", 0)
                upload_key = f"pq_upload_{selected_id}_{c['id']}_{counter}"
                files = st.file_uploader(
                    f"Add files for {label}",
                    type=["pdf", "docx", "xlsx"],
                    accept_multiple_files=True,
                    key=upload_key,
                )
                if files:
                    existing = {f["name"] for f in c["files"]}
                    added = False
                    with st.spinner("Reading files..."):
                        for uf in files:
                            if uf.name in existing:
                                continue
                            text = ingest_one(uf)
                            c["files"].append({
                                "name": uf.name,
                                "text": text,
                                "added_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            })
                            added = True
                    if added:
                        if not c.get("name"):
                            c["name"] = guess_contractor_name(combined_text(c))
                        c["upload_counter"] = counter + 1
                        auto_extract_bid_data(c, mock_trades)
                        st.rerun()

                # ---- Bid flow-through indicator ----
                if c.get("bid_data") and c["bid_data"].get("trades"):
                    summary = " · ".join(
                        f"{tb['trade_name']} (${tb.get('base_bid', 0):,.0f})"
                        for tb in c["bid_data"]["trades"]
                    )
                    st.success(f"📤 Bid data flowing to other tabs — {summary}")
                elif c.get("files"):
                    st.caption(
                        "📤 No priced bid detected in current files. Add a bid document "
                        "to populate the other tabs for this contractor."
                    )
                    if st.button("Re-extract bid data", key=f"pq_reextract_{selected_id}_{c['id']}"):
                        auto_extract_bid_data(c, mock_trades)
                        st.rerun()

                ncol1, ncol2, ncol3 = st.columns([4, 3, 1])
                with ncol1:
                    new_name = st.text_input(
                        "Contractor name",
                        value=c.get("name", ""),
                        key=f"pq_name_{selected_id}_{c['id']}",
                    )
                    c["name"] = new_name
                with ncol2:
                    options = ["pending", "qualified", "rejected"]
                    cur = c.get("status", "pending")
                    new_status = st.selectbox(
                        "Status (manual override)",
                        options,
                        index=options.index(cur),
                        key=f"pq_status_{selected_id}_{c['id']}",
                    )
                    c["status"] = new_status
                with ncol3:
                    st.write("")
                    st.write("")
                    if st.button("Delete", key=f"pq_cdel_{selected_id}_{c['id']}"):
                        remove_c_idx = i
        if remove_c_idx is not None:
            pq["contractors"].pop(remove_c_idx)
            st.rerun()

        if st.button("+ Add Contractor", key=f"pq_addc_{selected_id}"):
            pq["contractors"].append({
                "id": str(uuid.uuid4()),
                "name": "",
                "files": [],
                "result": None,
                "status": "pending",
                "upload_counter": 0,
            })
            st.rerun()

    # ---- Run scoring ----
    with st.container(border=True):
        st.markdown("### Run Pre-Qualification Scoring")
        ready = bool(
            pq["contractors"]
            and all(c.get("files") for c in pq["contractors"])
            and pq["categories"]
        )
        if not ready:
            st.warning("Add at least one contractor with files and one category before scoring.")

        if st.button("▶  Run Pre-Qualification", disabled=not ready, type="primary",
                     use_container_width=True, key=f"pq_run_{selected_id}"):
            cur_sig = category_signature(pq["categories"])
            if cur_sig != pq.get("cat_hash"):
                for c in pq["contractors"]:
                    c["result"] = None
                pq["cat_hash"] = cur_sig

            rfp_text = build_rfp_context(project, selected_meta, SF, pq.get("rfp_extra_text", ""))

            progress = st.progress(0.0)
            status_box = st.empty()
            n = len(pq["contractors"])
            for idx, c in enumerate(pq["contractors"]):
                cid = c.get("name") or f"Contractor {idx+1}"
                if c.get("result"):
                    progress.progress((idx + 1) / n)
                    continue
                status_box.write(f"Scoring **{cid}**…")
                result = score_contractor(rfp_text, combined_text(c), pq["categories"])
                c["result"] = result
                if c.get("status", "pending") == "pending":
                    comp = composite_score(result, pq["categories"])
                    c["status"] = "qualified" if comp >= QUALIFIED_THRESHOLD else "rejected"
                progress.progress((idx + 1) / n)
            status_box.write("Pre-qualification complete.")
            st.rerun()

    # ---- Results ----
    scored = [c for c in pq["contractors"] if c.get("result")]
    if scored:
        st.markdown("---")
        st.markdown("## Results")

        q_count = sum(1 for c in pq["contractors"] if c.get("status") == "qualified")
        r_count = sum(1 for c in pq["contractors"] if c.get("status") == "rejected")
        p_count = sum(1 for c in pq["contractors"] if c.get("status") == "pending")

        st.caption(
            f"Auto-qualification threshold: composite ≥ {QUALIFIED_THRESHOLD}/100. "
            "Override any contractor's status manually above."
        )

        if q_count:
            qualified_names = ", ".join(
                c.get("name") or "(unnamed)"
                for c in pq["contractors"] if c.get("status") == "qualified"
            )
            st.success(
                f"**{q_count} contractor(s) qualified for {project['name']}:** {qualified_names}\n\n"
                f"These bidders carry over to the **Bid Intake**, **Leveling**, **Benchmarking**, "
                f"**Risk Report**, and **Proposal Summary** tabs."
            )
        if r_count:
            st.warning(f"{r_count} contractor(s) marked **Not Qualified** — excluded from bid evaluation.")
        if p_count:
            st.info(f"{p_count} contractor(s) still **Pending** review.")

        rankings = []
        for c in scored:
            comp = composite_score(c["result"], pq["categories"])
            rankings.append((c, comp))
        rankings.sort(key=lambda x: x[1], reverse=True)

        for rank, (c, comp) in enumerate(rankings, 1):
            tag = {
                "qualified": "QUALIFIED",
                "rejected": "NOT QUALIFIED",
                "pending": "PENDING REVIEW",
            }[c.get("status", "pending")]
            render_prequal_card(f"#{rank} — {tag}", c.get("name") or "(unnamed)", comp, c["result"])

# ── Tab 1: Bid Intake ────────────────────────────────────────────────────────
with tab1:
    st.markdown("## Bid Intake Dashboard")
    st.caption("All bids ingested from PDF, Excel, and Email — unified into a single source of truth.")

    for trade in trades:
        st.markdown(f"### {trade['trade']}  `{trade['csi_code']}`")
        cols = st.columns(3)
        for i, bid in enumerate(trade["bids"]):
            has_update = len(bid["post_bid_updates"]) > 0
            current_total = bid["post_bid_updates"][-1]["revised_total"] if has_update else bid["base_bid"]
            delta = bid["post_bid_updates"][-1]["delta"] if has_update else None
            src = bid["source"]

            with cols[i]:
                src_color = {"PDF": "blue", "Excel": "green", "Email": "orange", "Upload": "violet"}.get(src, "gray")
                badge = f":{src_color}[{SOURCE_ICONS.get(src, '📄')} {src}]"
                update_badge = " · 🔄 **Updated**" if has_update else ""
                st.markdown(f"**{bid['company']}**  {badge}{update_badge}")
                st.markdown(f"*{bid['contact']}*  ·  Submitted {bid['submitted_date']}")
                st.metric(
                    label="Current Bid Total",
                    value=f"${current_total:,.0f}",
                    delta=f"+${delta:,.0f} via email" if delta else None,
                    delta_color="inverse"
                )
                with st.expander("📋 Exclusions"):
                    for excl in bid["exclusions"]:
                        st.markdown(f"- ⚠️ {excl}")
                    if not bid["exclusions"]:
                        st.markdown("✅ No exclusions listed")
                if has_update:
                    with st.expander("📬 Post-Bid Update Trail"):
                        for upd in bid["post_bid_updates"]:
                            st.markdown(f"**{upd['date']}** — {upd['from']}")
                            st.markdown(f"**Subject:** {upd['subject']}")
                            st.info(upd["body"])
                            st.success(f"Revised Total: **${upd['revised_total']:,.0f}** (+${upd['delta']:,.0f} for: {upd['scope_added']})")
                with st.expander("📎 Upload Revised Bid or Update"):
                    up_file = st.file_uploader(
                        "Upload revised bid (PDF, Excel, Word, .txt)",
                        type=["pdf","xlsx","xls","docx","txt","eml","msg"],
                        key=f"upload_{trade['csi_code']}_{bid['sub_id']}"
                    )
                    email_body = st.text_area(
                        "Or paste email / note text here:",
                        placeholder="Paste the subcontractor's email or any revision note...",
                        key=f"email_{trade['csi_code']}_{bid['sub_id']}",
                        height=80
                    )
                    if st.button("🔍 Extract Update with AI", key=f"extract_{trade['csi_code']}_{bid['sub_id']}"):
                        content = email_body
                        if up_file and up_file.type == "text/plain":
                            content = up_file.read().decode("utf-8", errors="ignore")
                        elif up_file:
                            content = f"[File uploaded: {up_file.name} — {up_file.size:,} bytes. Extraction pending full parser integration.]"
                        if content.strip():
                            with st.spinner("Extracting revision details..."):
                                extr = client.messages.create(
                                    model="claude-opus-4-7", max_tokens=400,
                                    messages=[{"role":"user","content":f"""A GC received this update from subcontractor {bid['company']} on the {trade['trade']} package for {project['name']}.
Their original bid: ${bid['base_bid']:,.0f}
Exclusions on file: {', '.join(bid['exclusions']) or 'None'}

Update content:
{content}

Extract: (1) revised dollar amount if stated, (2) scope added or removed, (3) any new exclusions or clarifications. Be concise."""}]
                                )
                                st.success("Extracted Update:")
                                st.markdown(extr.content[0].text)
                        else:
                            st.warning("Please upload a file or paste text to extract.")
        st.markdown("---")
        with st.expander(f"➕ Add New Bid — {trade['trade']}"):
            st.caption("Upload a bid from a subcontractor not yet in the system for this trade package.")
            new_sub_name = st.text_input("Subcontractor Name", key=f"newsub_name_{trade['csi_code']}")
            new_sub_contact = st.text_input("Contact Name", key=f"newsub_contact_{trade['csi_code']}")
            new_bid_src = st.selectbox("Bid Source", ["PDF","Excel","Email","Phone/Verbal"], key=f"newsub_src_{trade['csi_code']}")
            new_bid_file = st.file_uploader("Upload Bid Document", type=["pdf","xlsx","docx","txt"], key=f"newsub_file_{trade['csi_code']}")
            new_bid_text = st.text_area("Or paste bid content / email body:", key=f"newsub_text_{trade['csi_code']}", height=80, placeholder="Paste the full bid email or any relevant text...")
            if st.button("📥 Ingest & Extract Bid", type="primary", key=f"newsub_btn_{trade['csi_code']}"):
                content = new_bid_text
                if new_bid_file and new_bid_file.type == "text/plain":
                    content = new_bid_file.read().decode("utf-8", errors="ignore")
                elif new_bid_file:
                    content = f"[File: {new_bid_file.name}]"
                if content.strip() or new_sub_name:
                    with st.spinner("Extracting bid data..."):
                        extr = client.messages.create(
                            model="claude-opus-4-7", max_tokens=600,
                            messages=[{"role":"user","content":f"""Extract a structured bid summary from this content for the {trade['trade']} package on {project['name']} ({project['location']}, {SF:,} SF).
Sub: {new_sub_name or 'Unknown'} · Source: {new_bid_src}
Content:
{content or '[No content provided — summarize what data would be needed]'}
Return: total bid amount, list of line items with amounts, exclusions, inclusions, and any notes. Format clearly."""}]
                        )
                    st.success(f"Bid from {new_sub_name or 'New Sub'} extracted:")
                    st.markdown(extr.content[0].text)
                    st.info("To permanently add this bid, save the extracted data and refresh the project. Full write-back coming in next release.")
                else:
                    st.warning("Please provide a subcontractor name and bid content.")
        st.divider()

# ── Tab 2: Bid Leveling ──────────────────────────────────────────────────────
with tab2:
    st.markdown("## Bid Leveling")
    st.caption("Normalized side-by-side comparison. 🟡 = excluded by this sub. 🔴 = missing from bid entirely.")

    trade_names = [t["trade"] for t in trades]
    selected_trade = st.selectbox("Select Trade Package", trade_names)
    trade = next(t for t in trades if t["trade"] == selected_trade)
    bids = trade["bids"]

    all_items = []
    for bid in bids:
        for item in bid["line_items"]:
            if item["description"] not in all_items:
                all_items.append(item["description"])

    rows = []
    for item in all_items:
        row = {"Line Item": item}
        for bid in bids:
            match = next((li for li in bid["line_items"] if li["description"] == item), None)
            excl_keywords = item.lower()
            is_excluded = any(
                excl_keywords in e.lower() or any(word in e.lower() for word in excl_keywords.split()[:3])
                for e in bid["exclusions"]
            )
            if match and match["amount"] > 0:
                current = bid["post_bid_updates"][-1]["revised_total"] if bid["post_bid_updates"] and item == all_items[0] else match["amount"]
                row[bid["company"]] = f"${match['amount']:,.0f}"
            elif is_excluded:
                row[bid["company"]] = "⚠️ EXCLUDED"
            else:
                row[bid["company"]] = "—"
        rows.append(row)

    totals_row = {"Line Item": "**TOTAL BID**"}
    for bid in bids:
        has_update = len(bid["post_bid_updates"]) > 0
        total = bid["post_bid_updates"][-1]["revised_total"] if has_update else bid["base_bid"]
        label = f"**${total:,.0f}**" + (" 🔄" if has_update else "")
        totals_row[bid["company"]] = label
    rows.append(totals_row)

    df = pd.DataFrame(rows)

    def highlight_gaps(val):
        if "EXCLUDED" in str(val):
            return "background-color: #fef3c7; color: #92400e; font-weight: bold"
        if val == "—":
            return "background-color: #fee2e2; color: #991b1b"
        if "TOTAL" in str(val) or "$" in str(val) and "**" in str(val):
            return "background-color: #d1fae5; font-weight: bold"
        return ""

    st.dataframe(df.style.map(highlight_gaps, subset=df.columns[1:]), use_container_width=True, height=420)

    st.markdown("### 📬 Request Clarification from Sub")
    st.caption("Select an excluded item and generate a professional follow-up email instantly.")
    excluded_items = [r["Line Item"] for r in rows if any("EXCLUDED" in str(r.get(b["company"], "")) for b in bids)]
    if excluded_items:
        col_a, col_b = st.columns(2)
        with col_a:
            selected_item = st.selectbox("Excluded line item", excluded_items)
        with col_b:
            target_sub = st.selectbox("Sub to contact", [b["company"] for b in bids])
        target_bid = next(b for b in bids if b["company"] == target_sub)
        if st.button("✉️ Draft Clarification Email", type="primary"):
            with st.spinner("Drafting email with AI..."):
                prompt = f"""You are a General Contractor's estimator. Draft a short, professional email to a subcontractor requesting they price an excluded scope item.

Project: {project['name']}, {project['location']}
Trade: {trade['trade']}
Subcontractor: {target_sub} (contact: {target_bid['contact']}, email: {target_bid['email']})
Excluded item: {selected_item}
Their current bid total: ${target_bid['base_bid']:,.0f}
Their listed exclusions: {', '.join(target_bid['exclusions'])}

Write a 3-4 sentence email. Be direct and professional. Ask for a revised number including this scope. Sign off as Kevin (GC Estimator)."""
                msg = client.messages.create(
                    model="claude-opus-4-7",
                    max_tokens=400,
                    messages=[{"role": "user", "content": prompt}]
                )
                st.markdown("**Generated Email:**")
                st.text_area("Review and copy before sending:", msg.content[0].text, height=200)

# ── Tab 3: Cost Benchmarking ─────────────────────────────────────────────────
with tab3:
    st.markdown("## Cost Benchmarking")
    st.caption(f"Bid $/SF vs. regional benchmarks for {project['location']} · {project['type']} · Source: RSMeans 2024 (Simulated)")

    for trade in trades:
        bench = benchmarks.get(trade["trade"])
        if not bench:
            continue
        st.markdown(f"### {trade['trade']}")
        sub_names, sub_psf, bar_colors, deltas = [], [], [], []
        for bid in trade["bids"]:
            has_update = len(bid["post_bid_updates"]) > 0
            total = bid["post_bid_updates"][-1]["revised_total"] if has_update else bid["base_bid"]
            psf = round(total / SF, 2)
            in_range = bench["low"] <= psf <= bench["high"]
            sub_names.append(bid["company"] + (" 🔄" if has_update else ""))
            sub_psf.append(psf)
            bar_colors.append("#16a34a" if in_range else "#dc2626")
            deltas.append(psf - bench["mid"])

        fig = go.Figure()
        fig.add_trace(go.Bar(x=sub_names, y=sub_psf, marker_color=bar_colors,
                             name="Bid $/SF", text=[f"${v:.2f}" for v in sub_psf], textposition="outside"))
        fig.add_hrect(y0=bench["low"], y1=bench["high"], fillcolor="rgba(34,197,94,0.15)",
                      line_width=0, annotation_text=f"Benchmark range ${bench['low']}–${bench['high']}/SF",
                      annotation_position="top left")
        fig.add_hline(y=bench["mid"], line_dash="dash", line_color="#16a34a",
                      annotation_text=f"Midpoint ${bench['mid']}/SF")
        fig.update_layout(height=320, margin=dict(t=40, b=20), yaxis_title="$/SF",
                          showlegend=False, plot_bgcolor="#f9fafb")
        st.plotly_chart(fig, use_container_width=True)

        summary_rows = []
        for bid, psf, delta in zip(trade["bids"], sub_psf, deltas):
            has_update = len(bid["post_bid_updates"]) > 0
            total = bid["post_bid_updates"][-1]["revised_total"] if has_update else bid["base_bid"]
            in_range = bench["low"] <= psf <= bench["high"]
            status = "✅ In Range" if in_range else ("🔴 Above Range" if psf > bench["high"] else "🟡 Below Range")
            summary_rows.append({
                "Sub": bid["company"],
                "Source": bid["source"],
                "Total Bid": f"${total:,.0f}",
                "$/SF": f"${psf:.2f}",
                "vs. Midpoint": f"{'↑' if delta > 0 else '↓'} ${abs(delta):.2f}/SF",
                "Status": status
            })
        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
        st.markdown("---")

# ── Tab 4: Risk Report ───────────────────────────────────────────────────────
with tab4:
    st.markdown("## AI Risk Report")
    st.caption("Claude analyzes all bids, exclusions, post-bid updates, and benchmarks — then surfaces every dollar at risk.")

    if st.button("🚨 Generate Risk Report", type="primary", use_container_width=True):
        with st.spinner("Analyzing all bids, exclusions, and post-bid updates..."):
            summary_for_ai = []
            for trade in trades:
                bench = benchmarks.get(trade["trade"], {})
                for bid in trade["bids"]:
                    has_update = len(bid["post_bid_updates"]) > 0
                    total = bid["post_bid_updates"][-1]["revised_total"] if has_update else bid["base_bid"]
                    psf = round(total / SF, 2)
                    summary_for_ai.append({
                        "trade": trade["trade"],
                        "sub": bid["company"],
                        "base_bid": bid["base_bid"],
                        "current_total": total,
                        "psf": psf,
                        "benchmark_low": bench.get("low"), "benchmark_high": bench.get("high"),
                        "exclusions": bid["exclusions"],
                        "post_bid_updates": [u["scope_added"] + f" (+${u['delta']:,})" for u in bid["post_bid_updates"]],
                        "source": bid["source"]
                    })

            prompt = f"""You are a senior construction estimator reviewing bids for a GC on the {project['name']} project in {project['location']} ({SF:,} SF, {project['type']}).

Here is the full bid data:
{json.dumps(summary_for_ai, indent=2)}

Write a structured risk report with these sections:
1. **Executive Summary** (2-3 sentences, total scope and risk exposure)
2. **Scope Gaps** (items excluded by the low bidder in each trade — these create change order risk)
3. **Post-Bid Updates Captured** (list each email update that changed a number — these would have been missed without QualiBid)
4. **Benchmark Outliers** (flag any bid more than 15% above or below the benchmark midpoint)
5. **Recommended Leveling Actions** (specific steps before finalizing the proposal)
6. **Estimated Risk Exposure** (dollar range of unresolved scope gaps)

Be specific with company names and dollar amounts. This is a real pre-construction decision."""

            msg = client.messages.create(
                model="claude-opus-4-7",
                max_tokens=1200,
                messages=[{"role": "user", "content": prompt}]
            )
            st.markdown(msg.content[0].text)

            total_bids = sum(
                (b["post_bid_updates"][-1]["revised_total"] if b["post_bid_updates"] else b["base_bid"])
                for t in trades for b in t["bids"]
            )
            m1, m2, m3 = st.columns(3)
            leveled_direct = sum(
                min((b["post_bid_updates"][-1]["revised_total"] if b["post_bid_updates"] else b["base_bid"]) for b in t["bids"])
                for t in trades
            )
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Bids Analyzed", f"{sum(len(t['bids']) for t in trades)}", help="Number of individual sub bids received across all trade packages.")
            m2.metric("Post-Bid Updates Captured", f"{sum(len(b['post_bid_updates']) for t in trades for b in t['bids'])}", help="Email updates that revised a bid after initial submission — each one would have been easy to miss without QualiBid.")
            m3.metric("Leveled Direct Cost", f"${leveled_direct:,.0f}", help="Sum of the lowest complete bid per trade. This is the recommended direct construction cost going into the proposal.")
            m4.metric("Total Submitted Bid Volume", f"${total_bids:,.0f}", help="Sum of all bids received from all subcontractors across all trades. This is larger than the project cost because multiple subs competed on each trade.")

# ── Tab 5: Proposal Summary ──────────────────────────────────────────────────
with tab5:
    st.markdown("## Consolidated Bid Proposal")
    st.caption(f"GC Proposal for {project['name']} · {project['location']} · {SF:,} SF · {project['type']}")

    proposal_rows = []
    direct_cost_total = 0

    for trade in trades:
        bids = trade["bids"]
        # Select recommended bid: lowest COMPLETE bid (has fewest exclusions, use current total)
        scored = []
        for bid in bids:
            total = bid["post_bid_updates"][-1]["revised_total"] if bid["post_bid_updates"] else bid["base_bid"]
            excl_count = len(bid["exclusions"])
            scored.append((total + excl_count * 5000, bid, total))
        scored.sort(key=lambda x: x[0])
        rec_bid = scored[0][1]
        rec_total = scored[0][2]
        has_update = len(rec_bid["post_bid_updates"]) > 0

        gap_flags = [e for e in rec_bid["exclusions"] if not any(
            skip in e.lower() for skip in ["utility furnished", "structural steel", "by ec", "by gc", "by others", "by plumbing", "by mech", "ofe", "owner"]
        )]
        status = "⚠️ Gaps" if gap_flags else ("🔄 Updated" if has_update else "✅ Clean")
        notes = f"Gaps: {'; '.join(gap_flags[:2])}" if gap_flags else ("Via post-bid email" if has_update else "Complete bid")

        proposal_rows.append({
            "CSI": trade["csi_code"],
            "Trade": trade["trade"],
            "Recommended Sub": rec_bid["company"],
            "Source": rec_bid["source"],
            "Bid Total": rec_total,
            "Status": status,
            "Notes": notes
        })
        direct_cost_total += rec_total

    df_proposal = pd.DataFrame(proposal_rows)

    def color_status(val):
        if "Gaps" in str(val):   return "background-color:#fef3c7;color:#92400e;font-weight:bold"
        if "Updated" in str(val): return "background-color:#dbeafe;color:#1e40af;font-weight:bold"
        if "Clean" in str(val):  return "background-color:#d1fae5;color:#065f46;font-weight:bold"
        return ""

    display_df = df_proposal.copy()
    display_df["Bid Total"] = display_df["Bid Total"].apply(lambda x: f"${x:,.0f}")
    st.dataframe(display_df.style.map(color_status, subset=["Status"]), use_container_width=True, hide_index=True, height=680)

    st.markdown("---")
    st.markdown("### General Conditions & Requirements `01 00 00`")
    gc_rows = []
    for cat in gc_data["line_items"]:
        for item in cat["items"]:
            gc_rows.append({"Category": cat["category"], "Description": item["description"], "Amount": f"${item['total']:,.0f}"})
    st.dataframe(pd.DataFrame(gc_rows), use_container_width=True, hide_index=True, height=320)

    st.markdown("---")
    gc_total = gc_data["subtotal_gc"]
    subtotal = direct_cost_total + gc_total
    fee_pct = gc_data["gc_fee_percent"] / 100
    contingency_pct = gc_data["contingency_percent"] / 100
    gc_fee = subtotal * fee_pct
    contingency = subtotal * contingency_pct
    grand_total = subtotal + gc_fee + contingency
    psf_total = grand_total / SF

    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("### Proposal Roll-Up")
        roll_data = [
            {"Line": "Direct Construction (All Trades)", "Amount": f"${direct_cost_total:,.0f}", "$/SF": f"${direct_cost_total/SF:.2f}"},
            {"Line": "General Conditions & Requirements", "Amount": f"${gc_total:,.0f}", "$/SF": f"${gc_total/SF:.2f}"},
            {"Line": "**SUBTOTAL (Hard Cost)**", "Amount": f"**${subtotal:,.0f}**", "$/SF": f"**${subtotal/SF:.2f}**"},
            {"Line": f"GC Fee ({gc_data['gc_fee_percent']}%)", "Amount": f"${gc_fee:,.0f}", "$/SF": f"${gc_fee/SF:.2f}"},
            {"Line": f"Design/Pricing Contingency ({gc_data['contingency_percent']}%)", "Amount": f"${contingency:,.0f}", "$/SF": f"${contingency/SF:.2f}"},
            {"Line": "**TOTAL GC PROPOSAL**", "Amount": f"**${grand_total:,.0f}**", "$/SF": f"**${psf_total:.2f}**"},
        ]
        st.dataframe(pd.DataFrame(roll_data), use_container_width=True, hide_index=True)
    with col2:
        st.metric("Total GC Proposal", f"${grand_total:,.0f}")
        st.metric("Cost per SF", f"${psf_total:.2f}/SF")
        st.metric("Trades Covered", f"{len(trades)} CSI Divisions")
        st.metric("Open Scope Gaps", f"{sum(1 for r in proposal_rows if 'Gaps' in r['Status'])}")

# ── Tab 6: Documents & Uploads ───────────────────────────────────────────────
with tab6:
    st.markdown("## Documents & Uploads")
    st.caption("Central document hub for this project. Upload any bid, specification, drawing, addendum, or correspondence and QualiBid will extract and organize the relevant data.")

    st.markdown("### Upload a New Document")
    doc_cols = st.columns([2, 1, 1])
    with doc_cols[0]:
        doc_file = st.file_uploader(
            "Upload document (PDF, Excel, Word, email, or plain text)",
            type=["pdf","xlsx","xls","docx","doc","txt","eml","msg","csv"],
            key="central_doc_upload"
        )
    with doc_cols[1]:
        doc_type = st.selectbox("Document Type", [
            "Subcontractor Bid", "Revised Bid", "Post-Bid Email / Clarification",
            "Addendum / Bulletin", "Specification Section", "Drawing / Plan Sheet",
            "Owner Correspondence", "Contract Document", "RFI Response", "Other"
        ])
        doc_trade = st.selectbox("Related Trade (if applicable)", ["— General / Project-Wide —"] + [t["trade"] for t in trades])
    with doc_cols[1]:
        doc_sub = st.text_input("Subcontractor / Sender Name", placeholder="Optional")
    with doc_cols[2]:
        st.markdown("&nbsp;")
        process_btn = st.button("⚙️ Process & Extract", type="primary", use_container_width=True, key="central_process")
        st.markdown("&nbsp;")
        st.caption("AI will extract key data, flag scope changes, and identify anything that could affect the bid or proposal.")

    if process_btn:
        content = ""
        fname = ""
        if doc_file:
            fname = doc_file.name
            if doc_file.type == "text/plain" or fname.endswith((".txt",".eml",".csv")):
                content = doc_file.read().decode("utf-8", errors="ignore")
            else:
                content = f"[Binary file uploaded: {fname} ({doc_file.size:,} bytes). Full parser for {fname.split('.')[-1].upper()} files integrates with production deployment.]"
        if content or fname:
            with st.spinner(f"Processing {fname or 'document'}..."):
                trade_ctx = doc_trade if doc_trade != "— General / Project-Wide —" else "general project scope"
                prompt = f"""You are a senior construction estimator reviewing a document uploaded to QualiBid for project: {project['name']} ({project['location']}, {SF:,} SF {project['type']}).

Document type: {doc_type}
Related trade: {trade_ctx}
Sender / Sub: {doc_sub or 'Not specified'}
File: {fname}

Content:
{content}

Provide a structured extraction with these sections:
1. **Document Summary** — what this document is and who sent it
2. **Key Numbers** — any dollar amounts, quantities, or dates
3. **Scope Changes** — anything added, removed, or clarified vs. the base bid
4. **Exclusions or Conditions** — any new exclusions, clarifications, or qualifications
5. **Action Required** — what the GC estimator should do next
6. **Risk Flag** — any items that could affect the proposal number (flag as 🔴 High / 🟡 Medium / 🟢 Low)"""
                result = client.messages.create(
                    model="claude-opus-4-7", max_tokens=800,
                    messages=[{"role":"user","content":prompt}]
                )
            st.success("Extraction complete.")
            st.markdown(result.content[0].text)
            st.divider()
        else:
            st.warning("Please upload a file to process.")

    st.markdown("---")
    st.markdown("### Project Document Log")
    st.caption("All documents uploaded to this project this session.")
    if "doc_log" not in st.session_state:
        st.session_state.doc_log = [
            {"Date":"2024-04-22","Document":"Electrical Bid — Lone Star Electric.pdf","Type":"Subcontractor Bid","Trade":"Electrical","Uploaded By":"Kevin (GC Estimator)","Status":"✅ Extracted"},
            {"Date":"2024-04-23","Document":"HVAC Bid — AirRight Mechanical.xlsx","Type":"Subcontractor Bid","Trade":"Mechanical (HVAC)","Uploaded By":"Kevin (GC Estimator)","Status":"✅ Extracted"},
            {"Date":"2024-04-28","Document":"RE_ Fire Alarm Clarification.eml","Type":"Post-Bid Email / Clarification","Trade":"Electrical","Uploaded By":"Kevin (GC Estimator)","Status":"✅ Extracted"},
            {"Date":"2024-04-29","Document":"Addendum No. 2 — Revised Mechanical Spec.pdf","Type":"Addendum / Bulletin","Trade":"Mechanical (HVAC)","Uploaded By":"Kevin (GC Estimator)","Status":"⚠️ Review Needed"},
            {"Date":"2024-04-30","Document":"Medical Gas Clarification Email.eml","Type":"Post-Bid Email / Clarification","Trade":"Plumbing","Uploaded By":"Kevin (GC Estimator)","Status":"✅ Extracted"},
        ]
    if doc_file and process_btn:
        st.session_state.doc_log.insert(0,{
            "Date":"Today","Document":doc_file.name,"Type":doc_type,
            "Trade":doc_trade,"Uploaded By":"Kevin (GC Estimator)","Status":"✅ Extracted"
        })
    st.dataframe(pd.DataFrame(st.session_state.doc_log), use_container_width=True, hide_index=True)
