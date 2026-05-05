import json
import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from dotenv import load_dotenv
import anthropic

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
    st.caption("QualiBid v0.1 · Hackathon Demo")

proj_file = load_project(selected_id)
data       = proj_file["bids"]
bench_data = proj_file["benchmarks"]
gc_data    = proj_file["general_conditions"]
project    = data["project"]
trades     = data["trades"]
benchmarks = {b["trade"]: b for b in bench_data["benchmarks"]}
SF         = project["size_sf"]

SOURCE_COLORS = {"PDF": "#2563eb", "Excel": "#16a34a", "Email": "#d97706"}
SOURCE_ICONS  = {"PDF": "📄", "Excel": "📊", "Email": "📧"}

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

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📥  Bid Intake",
    "⚖️  Bid Leveling",
    "📊  Cost Benchmarking",
    "🚨  Risk Report",
    "📋  Proposal Summary"
])

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
                badge = f":{('blue' if src=='PDF' else 'green' if src=='Excel' else 'orange')}[{SOURCE_ICONS[src]} {src}]"
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

    st.dataframe(df.style.applymap(highlight_gaps, subset=df.columns[1:]), use_container_width=True, height=420)

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
    st.dataframe(display_df.style.applymap(color_status, subset=["Status"]), use_container_width=True, hide_index=True, height=680)

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
