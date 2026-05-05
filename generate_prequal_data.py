"""QualiBid  - Pre-Qualification PDF Data Generator
Renders RFP + per-contractor SOQ packets and bid tabs for 3 demo projects.
3 contractors per project on a realism gradient (strong / marginal / underqualified)
with bid discrepancies that surface during leveling.

Run:  python generate_prequal_data.py
Output: mock_data/projects/{p01,p05,p09}/RFP.pdf
        mock_data/projects/{p01,p05,p09}/<contractor_slug>/{01..05}_*.pdf
"""
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT


OUT = Path("mock_data/projects")

# ── Trade list (must match app's project trade names exactly) ────────────────
TRADES = [
    ("Demolition & Site Clearing",            "02 40 00"),
    ("Concrete",                              "03 00 00"),
    ("Masonry",                               "04 00 00"),
    ("Structural Steel & Misc Metals",        "05 00 00"),
    ("Roofing, Waterproofing & Insulation",   "07 00 00"),
    ("Doors, Frames, Hardware & Glazing",     "08 00 00"),
    ("Drywall & Framing",                     "09 20 00"),
    ("Flooring",                              "09 60 00"),
    ("Painting & Wall Coverings",             "09 90 00"),
    ("Acoustical Ceilings (ACT)",             "09 51 00"),
    ("Specialties",                           "10 00 00"),
    ("Fire Suppression (Sprinklers)",         "21 00 00"),
    ("Plumbing",                              "22 00 00"),
    ("Mechanical (HVAC)",                     "23 00 00"),
    ("Electrical",                            "26 00 00"),
    ("Communications (Data, AV, Tel)",        "27 00 00"),
    ("Electronic Safety & Security",          "28 00 00"),
    ("Earthwork, Grading & Site Preparation", "31 00 00"),
    ("Site Paving, Curbs & Landscaping",      "32 00 00"),
    ("Site Utilities (Water, Sewer, Storm, Gas)", "33 00 00"),
]


# ── Per-trade weights for splitting direct cost across trades ────────────────
# Approximates the cost share of each trade for typical building types.
TRADE_WEIGHTS = {
    "Medical Office": {
        "Demolition & Site Clearing": 0.018, "Concrete": 0.078, "Masonry": 0.034,
        "Structural Steel & Misc Metals": 0.092, "Roofing, Waterproofing & Insulation": 0.052,
        "Doors, Frames, Hardware & Glazing": 0.066, "Drywall & Framing": 0.054,
        "Flooring": 0.060, "Painting & Wall Coverings": 0.022, "Acoustical Ceilings (ACT)": 0.030,
        "Specialties": 0.018, "Fire Suppression (Sprinklers)": 0.034, "Plumbing": 0.092,
        "Mechanical (HVAC)": 0.122, "Electrical": 0.094,
        "Communications (Data, AV, Tel)": 0.030, "Electronic Safety & Security": 0.022,
        "Earthwork, Grading & Site Preparation": 0.024,
        "Site Paving, Curbs & Landscaping": 0.030, "Site Utilities (Water, Sewer, Storm, Gas)": 0.028,
    },
    "Mission-Critical / Data Center": {
        "Demolition & Site Clearing": 0.012, "Concrete": 0.064, "Masonry": 0.014,
        "Structural Steel & Misc Metals": 0.072, "Roofing, Waterproofing & Insulation": 0.036,
        "Doors, Frames, Hardware & Glazing": 0.022, "Drywall & Framing": 0.026,
        "Flooring": 0.014, "Painting & Wall Coverings": 0.008, "Acoustical Ceilings (ACT)": 0.010,
        "Specialties": 0.010, "Fire Suppression (Sprinklers)": 0.044, "Plumbing": 0.026,
        "Mechanical (HVAC)": 0.224, "Electrical": 0.260,
        "Communications (Data, AV, Tel)": 0.054, "Electronic Safety & Security": 0.040,
        "Earthwork, Grading & Site Preparation": 0.022,
        "Site Paving, Curbs & Landscaping": 0.018, "Site Utilities (Water, Sewer, Storm, Gas)": 0.024,
    },
    "Warehouse / Distribution": {
        "Demolition & Site Clearing": 0.024, "Concrete": 0.190, "Masonry": 0.022,
        "Structural Steel & Misc Metals": 0.180, "Roofing, Waterproofing & Insulation": 0.082,
        "Doors, Frames, Hardware & Glazing": 0.030, "Drywall & Framing": 0.014,
        "Flooring": 0.012, "Painting & Wall Coverings": 0.010, "Acoustical Ceilings (ACT)": 0.006,
        "Specialties": 0.012, "Fire Suppression (Sprinklers)": 0.044, "Plumbing": 0.020,
        "Mechanical (HVAC)": 0.034, "Electrical": 0.060,
        "Communications (Data, AV, Tel)": 0.012, "Electronic Safety & Security": 0.018,
        "Earthwork, Grading & Site Preparation": 0.058,
        "Site Paving, Curbs & Landscaping": 0.118, "Site Utilities (Water, Sewer, Storm, Gas)": 0.054,
    },
}


# ── Project definitions ──────────────────────────────────────────────────────
PROJECTS = [
    {
        "id": "p01",
        "name": "Riverside Medical Office Campus",
        "location": "Austin, TX",
        "size_sf": 142000,
        "type": "Medical Office",
        "stories": 3,
        "direct_cost_target": 8860000,
        "owner": "Riverside Health Partners, LLC",
        "owner_contact": "Dana Whitfield, Director of Capital Projects",
        "owner_phone": "512-555-0140",
        "owner_email": "dwhitfield@riversidehealthpartners.com",
        "architect": "HKS Architects",
        "engineer_struct": "Walter P Moore",
        "engineer_mep": "ccrd",
        "submission_due": "November 14, 2025",
        "bid_due": "December 5, 2025",
        "ntp_target": "February 2026",
        "substantial_completion": "February 2028",
        "delivery_method": "CMAR (this RFP is for the construction package)",
        "scope_summary": (
            "New 3-story Class-A medical office campus on a 9.4-acre infill site adjacent to "
            "Riverside Hospital. Program includes primary care, imaging suite (MRI + CT), "
            "ambulatory surgical clinic with two procedure rooms, retail pharmacy, and a "
            "ground-floor cafe. Cast-in-place concrete frame, brick + metal panel skin, "
            "EPDM roof. Specialty MEP including medical gas, isolation room HVAC zones, "
            "and emergency power for life safety + procedure rooms."
        ),
        "mandatory_quals": [
            "Minimum 5 completed medical office or healthcare construction projects ≥ $7M in the last 7 years",
            "Demonstrated experience with NFPA 99 medical gas systems and certified medical gas installer affiliation",
            "Single-project bonding capacity ≥ $15M; surety with A.M. Best A- or better",
            "EMR ≤ 1.00 averaged across last 3 years; TRIR ≤ 3.0",
            "Active Texas Department of Insurance Contractor Registration",
            "Local field office or established subcontractor base in the Austin metro",
        ],
        "selection_criteria": [
            "Healthcare/MOB project experience and references (30%)",
            "Key personnel qualifications (20%)",
            "Local market presence and subcontractor base (15%)",
            "Safety record and quality program (15%)",
            "Financial capacity and bonding (10%)",
            "Schedule and approach (10%)",
        ],
    },
    {
        "id": "p05",
        "name": "SunCore Data Center",
        "location": "Phoenix, AZ",
        "size_sf": 60000,
        "type": "Mission-Critical / Data Center",
        "stories": 2,
        "direct_cost_target": 5990000,
        "owner": "SunCore Digital Infrastructure, LLC",
        "owner_contact": "Anil Pradhan, VP Critical Construction",
        "owner_phone": "602-555-0271",
        "owner_email": "apradhan@suncoredigital.com",
        "architect": "Corgan",
        "engineer_struct": "Magnusson Klemencic Associates",
        "engineer_mep": "kW Mission Critical Engineering",
        "submission_due": "November 7, 2025",
        "bid_due": "November 28, 2025",
        "ntp_target": "January 2026",
        "substantial_completion": "October 2027",
        "delivery_method": "Lump-sum, design-bid-build",
        "scope_summary": (
            "60,000 SF Tier III certified data center on a fenced 6.2-acre pad, including "
            "30,000 SF white space, 6 MW IT load (Phase 1), N+1 chilled water cooling, "
            "2 (N+1) 2.5 MVA utility services, 4 standby generators (2N at 2.5 MW each), "
            "5 (N+1) 750 kVA UPS modules, hot aisle containment, raised access flooring, "
            "and full project commissioning to Cx Level 5."
        ),
        "mandatory_quals": [
            "Minimum 3 completed Tier II+ data center projects ≥ $25M in the last 5 years",
            "Demonstrated experience with N+1/2N electrical topologies and medium-voltage switchgear installation",
            "Cx Level 5 commissioning oversight on at least 2 mission-critical projects",
            "Single-project bonding capacity ≥ $20M; surety with A.M. Best A- or better",
            "EMR ≤ 0.90 averaged across last 3 years; TRIR ≤ 2.5",
            "Documented data center subcontractor base (UPS, generator, BMS/CMMS, structured cabling)",
        ],
        "selection_criteria": [
            "Tier III data center / mission-critical experience (35%)",
            "MEP self-perform or proven specialty subcontractor base (20%)",
            "Commissioning approach and prior outcomes (15%)",
            "Schedule certainty and on-time completion record (10%)",
            "Safety record (10%)",
            "Financial capacity and bonding (10%)",
        ],
    },
    {
        "id": "p09",
        "name": "Hartsfield Distribution Hub",
        "location": "Atlanta, GA",
        "size_sf": 400000,
        "type": "Warehouse / Distribution",
        "stories": 1,
        "direct_cost_target": 5850000,
        "owner": "Hartsfield Logistics REIT",
        "owner_contact": "Marcus Doyle, Construction Director",
        "owner_phone": "404-555-0162",
        "owner_email": "mdoyle@hartsfieldlogistics.com",
        "architect": "Ware Malcomb",
        "engineer_struct": "Uzun + Case",
        "engineer_mep": "Newcomb & Boyd",
        "submission_due": "November 21, 2025",
        "bid_due": "December 12, 2025",
        "ntp_target": "February 2026",
        "substantial_completion": "March 2027",
        "delivery_method": "Lump-sum, design-bid-build",
        "scope_summary": (
            "400,000 SF concrete tilt-up Class A distribution facility on a 28-acre pad south "
            "of Hartsfield-Jackson, with 60 dock-high loading positions, 4 drive-in doors, "
            "32-foot clear height, 195 trailer storage stalls, 250 auto stalls, ESFR sprinkler "
            "system, 7,500 SF office build-out, and a fully fenced/secured truck court. "
            "EPDM roof, white-box warehouse interior, LED high-bay lighting throughout."
        ),
        "mandatory_quals": [
            "Minimum 4 completed tilt-up warehouse/distribution projects ≥ 250,000 SF in the last 6 years",
            "Self-perform tilt-up panel forming and erection OR qualified tilt subcontractor with comparable experience",
            "Single-project bonding capacity ≥ $15M; surety with A.M. Best A- or better",
            "EMR ≤ 1.00 averaged across last 3 years",
            "Demonstrated experience with ESFR sprinkler systems and high-pile storage AHJ approvals",
            "Project office within 60 miles of the site or willingness to maintain a full-time field office",
        ],
        "selection_criteria": [
            "Tilt-up distribution experience and references (30%)",
            "Schedule approach and on-time completion record (20%)",
            "Self-perform capability for shell trades (15%)",
            "Local market presence and subcontractor base (15%)",
            "Safety record (10%)",
            "Financial capacity and bonding (10%)",
        ],
    },
]


# ── Contractor definitions (3 per project, realism gradient) ─────────────────
# Each contractor has a tier: "strong", "marginal", or "underqualified".
# Bid behavior:
#   strong       → 1.04x base, 0 exclusions, all 20 trades
#   marginal     → 0.96x base, 2-3 exclusions, all 20 trades but a few are light
#   underqualified → 0.78x base on trades they bid, skips 4-7 trades, many exclusions

CONTRACTORS = {
    "p01": [
        {
            "tier": "strong",
            "slug": "lone_star_healthcare",
            "name": "Lone Star Healthcare Construction, LLC",
            "founded": 2003,
            "hq": "Austin, TX",
            "branch_offices": "San Antonio, TX",
            "rev_2024": 52, "rev_2023": 48, "rev_2022": 44, "rev_2021": 40, "rev_2020": 36,
            "bonding_single": 80, "bonding_aggregate": 150,
            "surety": "Liberty Mutual Surety (A.M. Best A XV)",
            "employees": 95,
            "primary_market": "Healthcare construction (medical office, ambulatory surgery centers, imaging suites)",
            "secondary_market": "Life sciences fit-out and small acute-care renovations",
            "geographic": "Texas  - primarily Austin, San Antonio, and Houston metros",
            "emr_2024": 0.78, "emr_2023": 0.81, "emr_2022": 0.83,
            "trir_2024": 1.9, "trir_2023": 2.1,
            "osha_recordables_3yr": 5,
            "lost_time_3yr": 1,
            "capabilities": [
                "NFPA 99 medical gas system installation (in-house ASSE 6010 certified medical gas installers)",
                "Healthcare ICRA (Infection Control Risk Assessment) procedures and barrier construction",
                "Imaging suite shielding coordination (lead-lined drywall, RF shielding)",
                "Cast-in-place concrete frame self-perform",
                "Procurement and management of healthcare-specialty subcontractors",
            ],
            "officer_name": "Reagan Castillo",
            "officer_title": "President",
            "officer_email": "rcastillo@lonestarhealthcare.com",
            "officer_phone": "512-555-0218",
            "key_personnel": [
                {
                    "name": "Reagan Castillo",
                    "title": "Principal-in-Charge",
                    "years": 24,
                    "summary": (
                        "24 years healthcare construction. Founded Lone Star Healthcare Construction in 2003. "
                        "Personally directed 14 medical office buildings and 3 ambulatory surgery centers in Texas."
                    ),
                    "credentials": "BS Construction Science, Texas A&M (1999); LEED AP BD+C; OSHA 30",
                    "projects": [
                        "Seton Williamson MOB Phase II  - 110,000 SF, $14.2M, 2023",
                        "Baylor Scott & White Round Rock MOB  - 96,000 SF, $11.8M, 2022",
                        "Methodist Stone Oak ASC  - 38,000 SF, $9.4M, 2024",
                    ],
                },
                {
                    "name": "Maria Delgado",
                    "title": "Project Manager",
                    "years": 14,
                    "summary": (
                        "14 years managing medical office and outpatient surgical projects. "
                        "Led the Seton Williamson MOB Phase II delivery 6 weeks ahead of schedule."
                    ),
                    "credentials": "BS Civil Engineering, UT Austin (2011); PE (Texas); CHC (Certified Healthcare Constructor)",
                    "projects": [
                        "Seton Williamson MOB Phase II (Lead PM)  - $14.2M",
                        "Baylor Round Rock MOB (Lead PM)  - $11.8M",
                        "St. David's North Austin MOB Renovation  - $6.1M",
                    ],
                },
                {
                    "name": "Daniel Rourke",
                    "title": "General Superintendent",
                    "years": 22,
                    "summary": (
                        "22 years field supervision, the last 12 in healthcare. ICRA Class IV experience. "
                        "Has been on the ground for every Lone Star MOB delivery in the last 8 years."
                    ),
                    "credentials": "OSHA 30 (current); ASHE Healthcare Construction Certificate; ICRA-trained",
                    "projects": [
                        "Seton Williamson MOB Phase II  - Gen Sup",
                        "Methodist Stone Oak ASC  - Gen Sup",
                        "Baylor All Saints Imaging Suite  - Gen Sup",
                    ],
                },
                {
                    "name": "Priya Sharma",
                    "title": "QA/QC Manager",
                    "years": 11,
                    "summary": (
                        "11 years quality management on healthcare construction. Manages medical gas verification, "
                        "isolation room pressure commissioning, and TJC/AAAHC pre-survey readiness."
                    ),
                    "credentials": "ASSE 6030 Medical Gas Verifier; CWI; OSHA 30",
                    "projects": [
                        "Seton Williamson MOB Phase II  - QC Manager (zero RFI rework on med-gas)",
                        "Methodist Stone Oak ASC  - QC Manager",
                    ],
                },
            ],
            "past_projects": [
                {"name": "Seton Williamson Medical Office Building Phase II",
                 "scope": "110,000 SF, 4-story MOB with imaging suite + ASC",
                 "value": "$14.2M", "year": "2023", "owner": "Ascension Seton",
                 "outcome": "Delivered 6 weeks ahead of schedule; zero recordables"},
                {"name": "Baylor Scott & White Round Rock MOB",
                 "scope": "96,000 SF, 3-story medical office",
                 "value": "$11.8M", "year": "2022", "owner": "Baylor Scott & White Health",
                 "outcome": "On-time, 0.4% under GMP"},
                {"name": "Methodist Stone Oak Ambulatory Surgery Center",
                 "scope": "38,000 SF ASC with 4 ORs",
                 "value": "$9.4M", "year": "2024", "owner": "Methodist Healthcare",
                 "outcome": "First-pass medical gas verification; AHJ acceptance with no comments"},
                {"name": "St. David's North Austin MOB Renovation",
                 "scope": "Occupied-building MOB renovation, 22,000 SF",
                 "value": "$6.1M", "year": "2023", "owner": "St. David's HealthCare",
                 "outcome": "ICRA Class IV barriers maintained over 11-month phasing"},
                {"name": "Heart Hospital of Austin Cath Lab Expansion",
                 "scope": "Cath lab and CVOR expansion, 18,000 SF",
                 "value": "$8.7M", "year": "2021", "owner": "HCA Healthcare",
                 "outcome": "Delivered through fully active hospital floor"},
                {"name": "Texas Oncology Bee Cave",
                 "scope": "32,000 SF MOB and infusion suite",
                 "value": "$7.9M", "year": "2022", "owner": "Texas Oncology",
                 "outcome": "On-time"},
                {"name": "Austin Regional Clinic Cedar Park MOB",
                 "scope": "44,000 SF MOB",
                 "value": "$8.4M", "year": "2024", "owner": "Austin Regional Clinic",
                 "outcome": "On-time"},
            ],
            "bid_modifier": 1.04,
            "exclusions": [],
            "skip_trades": [],
            "trade_overrides": {},
        },
        {
            "tier": "marginal",
            "slug": "capitol_commercial",
            "name": "Capitol Commercial Builders",
            "founded": 1999,
            "hq": "Austin, TX",
            "branch_offices": "None",
            "rev_2024": 78, "rev_2023": 74, "rev_2022": 70, "rev_2021": 64, "rev_2020": 58,
            "bonding_single": 100, "bonding_aggregate": 175,
            "surety": "Travelers Casualty and Surety Company of America (A.M. Best A++ XV)",
            "employees": 140,
            "primary_market": "Commercial office and corporate interiors",
            "secondary_market": "Retail, K-12 education, occasional medical clinic fit-outs",
            "geographic": "Central Texas (Austin metro and surrounding counties)",
            "emr_2024": 0.92, "emr_2023": 0.94, "emr_2022": 0.96,
            "trir_2024": 2.4, "trir_2023": 2.6,
            "osha_recordables_3yr": 9,
            "lost_time_3yr": 2,
            "capabilities": [
                "Cast-in-place and tilt-up concrete self-perform",
                "Commercial office TI and ground-up shell",
                "Big-box and mid-market retail",
                "Standard MEP coordination via long-term subcontractor relationships",
            ],
            "officer_name": "Jordan Walsh",
            "officer_title": "President",
            "officer_email": "jwalsh@capitolcommercial.com",
            "officer_phone": "512-555-0344",
            "key_personnel": [
                {
                    "name": "Jordan Walsh",
                    "title": "Principal-in-Charge",
                    "years": 28,
                    "summary": (
                        "28 years general contracting, primarily commercial office and retail. "
                        "Has overseen 3 medical clinic fit-outs but no ground-up MOBs."
                    ),
                    "credentials": "BS Construction Mgmt, Texas State; OSHA 30; LEED AP",
                    "projects": [
                        "Domain Northside Office Tower IV  - 220,000 SF, $42M, 2023",
                        "Mueller Town Center Retail  - 86,000 SF, $11M, 2022",
                        "Westlake Surgical Clinic Fit-Out  - 18,000 SF, $3.4M, 2024",
                    ],
                },
                {
                    "name": "Brett McAllister",
                    "title": "Project Manager",
                    "years": 16,
                    "summary": (
                        "16 years construction PM, almost all on Class-A office and retail. "
                        "His most healthcare-adjacent project was an outpatient clinic TI in 2024."
                    ),
                    "credentials": "BBA, UT Austin; CCM; OSHA 30",
                    "projects": [
                        "Domain Northside Office Tower IV (PM)  - $42M",
                        "Westlake Surgical Clinic Fit-Out (PM)  - $3.4M",
                        "Round Rock Premium Outlets Expansion (PM)  - $19M",
                    ],
                },
                {
                    "name": "Carl Reinhart",
                    "title": "General Superintendent",
                    "years": 25,
                    "summary": (
                        "25 years field supervision on Class-A office and retail buildouts. "
                        "Limited healthcare-specific experience; has not run an ICRA-controlled site."
                    ),
                    "credentials": "OSHA 30; First Aid/CPR",
                    "projects": [
                        "Domain Northside Tower IV  - Gen Sup",
                        "Mueller Town Center  - Gen Sup",
                    ],
                },
            ],
            "past_projects": [
                {"name": "Domain Northside Office Tower IV",
                 "scope": "220,000 SF, 8-story Class-A office",
                 "value": "$42M", "year": "2023", "owner": "Endeavor Real Estate",
                 "outcome": "On-time"},
                {"name": "Mueller Town Center Retail",
                 "scope": "86,000 SF mixed-use retail",
                 "value": "$11M", "year": "2022", "owner": "Catellus",
                 "outcome": "On-time"},
                {"name": "Westlake Surgical Clinic Fit-Out",
                 "scope": "18,000 SF outpatient clinic interior fit-out",
                 "value": "$3.4M", "year": "2024", "owner": "Westlake Surgical Group",
                 "outcome": "On-time; first medical-gas project for the company"},
                {"name": "Round Rock Premium Outlets Expansion",
                 "scope": "44,000 SF retail expansion",
                 "value": "$19M", "year": "2021", "owner": "Simon Property Group",
                 "outcome": "On-time"},
                {"name": "Cedar Park Corporate Office II",
                 "scope": "120,000 SF, 4-story office building",
                 "value": "$24M", "year": "2024", "owner": "Lincoln Property Company",
                 "outcome": "Delivered 3 weeks late due to glazing supply issues"},
                {"name": "South Austin Medical Plaza Repositioning",
                 "scope": "Existing-building cosmetic upgrade and small clinic TI",
                 "value": "$2.8M", "year": "2023", "owner": "Hines",
                 "outcome": "On-time"},
            ],
            "bid_modifier": 0.96,
            "exclusions": [
                "Medical gas rough-in and outlets  - to be performed by Owner-furnished, Capitol-installed package",
                "Low-voltage structured cabling  - by Owner's IT integrator",
                "Exterior storefront and curtainwall glazing  - assumed Owner direct purchase",
            ],
            "skip_trades": [],
            "trade_overrides": {
                # Light pricing on specialty MEP  - reflects reliance on a stretched sub
                "Mechanical (HVAC)": 0.84,
                "Plumbing": 0.86,
            },
        },
        {
            "tier": "underqualified",
            "slug": "pedernales_custom",
            "name": "Pedernales Custom Homes & Renovations, Inc.",
            "founded": 2017,
            "hq": "Dripping Springs, TX",
            "branch_offices": "None",
            "rev_2024": 14, "rev_2023": 11, "rev_2022": 9, "rev_2021": 7, "rev_2020": 5,
            "bonding_single": 20, "bonding_aggregate": 30,
            "surety": "Hudson Insurance Group (A.M. Best A- VIII)",
            "employees": 38,
            "primary_market": "Custom single-family residential and high-end residential remodels",
            "secondary_market": "Small commercial fit-outs (under $1.5M)",
            "geographic": "Hill Country and southwest Austin metro",
            "emr_2024": 1.32, "emr_2023": 1.28, "emr_2022": 1.24,
            "trir_2024": 4.0, "trir_2023": 3.8,
            "osha_recordables_3yr": 12,
            "lost_time_3yr": 3,
            "capabilities": [
                "Custom-home framing, finishes, and millwork",
                "Residential foundations and on-site project management",
                "Small commercial tenant improvements",
            ],
            "officer_name": "Wesley Burnham",
            "officer_title": "Owner",
            "officer_email": "wburnham@pedernalescustom.com",
            "officer_phone": "830-555-0177",
            "key_personnel": [
                {
                    "name": "Wesley Burnham",
                    "title": "Owner / Project Executive",
                    "years": 14,
                    "summary": (
                        "14 years residential construction, the last 8 as a custom home builder. "
                        "Has not previously managed a project above $2.5M. No healthcare experience."
                    ),
                    "credentials": "Texas Residential Construction License; OSHA 10",
                    "projects": [
                        "Bee Caves Hillside Custom Home  - $2.4M, 2024",
                        "Lakeway Estate Renovation  - $1.8M, 2023",
                        "Bouldin Creek Bungalow  - $1.1M, 2022",
                    ],
                },
                {
                    "name": "Travis Holden",
                    "title": "Field Superintendent",
                    "years": 9,
                    "summary": (
                        "9 years residential framing and finishes. No commercial healthcare or ICRA experience. "
                        "Has supervised crews of up to 12 on residential sites."
                    ),
                    "credentials": "OSHA 10; First Aid/CPR",
                    "projects": [
                        "Bee Caves Hillside Custom Home  - Sup",
                        "Lakeway Estate Renovation  - Sup",
                    ],
                },
            ],
            "past_projects": [
                {"name": "Bee Caves Hillside Custom Home",
                 "scope": "8,200 SF custom luxury home",
                 "value": "$2.4M", "year": "2024", "owner": "Private",
                 "outcome": "On-time"},
                {"name": "Lakeway Estate Renovation",
                 "scope": "Whole-house remodel + addition, 6,400 SF",
                 "value": "$1.8M", "year": "2023", "owner": "Private",
                 "outcome": "5 months late"},
                {"name": "Bouldin Creek Bungalow",
                 "scope": "New construction, 3,100 SF",
                 "value": "$1.1M", "year": "2022", "owner": "Private",
                 "outcome": "On-time"},
                {"name": "Dripping Springs Boutique Office",
                 "scope": "Small office TI, 4,800 SF",
                 "value": "$0.9M", "year": "2024", "owner": "Hill Country Capital LLC",
                 "outcome": "On-time"},
                {"name": "Westlake Wellness Studio TI",
                 "scope": "Yoga studio interior fit-out, 3,200 SF",
                 "value": "$0.6M", "year": "2023", "owner": "Westlake Wellness LLC",
                 "outcome": "On-time"},
            ],
            "bid_modifier": 0.78,
            "exclusions": [
                "Medical gas system  - NOT IN CONTRACT (no certified installers on staff)",
                "Fire alarm system  - to be performed by Owner direct",
                "Acoustical ceilings  - to be performed by Owner direct",
                "Imaging suite RF / lead shielding  - NOT IN CONTRACT",
                "Emergency power coordination with utility  - by Owner",
                "Commissioning of MEP systems  - NOT IN CONTRACT",
                "Site utility tie-ins beyond 5' from building  - by Owner's civil",
                "Building permit, plan-check, and impact fees  - by Owner",
            ],
            "skip_trades": [
                "Structural Steel & Misc Metals",  # Subbed out, not in our bid
                "Acoustical Ceilings (ACT)",
                "Fire Suppression (Sprinklers)",
                "Communications (Data, AV, Tel)",
                "Electronic Safety & Security",
            ],
            "trade_overrides": {
                "Mechanical (HVAC)": 0.65,
                "Plumbing": 0.70,
                "Electrical": 0.68,
            },
        },
    ],
    "p05": [
        {
            "tier": "strong",
            "slug": "critical_facilities_group",
            "name": "Critical Facilities Group, LLC",
            "founded": 2002,
            "hq": "Dallas, TX",
            "branch_offices": "Phoenix, AZ; Reno, NV; Ashburn, VA; Hillsboro, OR",
            "rev_2024": 410, "rev_2023": 375, "rev_2022": 340, "rev_2021": 295, "rev_2020": 248,
            "bonding_single": 750, "bonding_aggregate": 1500,
            "surety": "Zurich North America (A.M. Best A+ XV)",
            "employees": 620,
            "primary_market": "Hyperscale and enterprise data centers (Tier III/IV)",
            "secondary_market": "Carrier hotels, telecom central offices, and edge facilities",
            "geographic": "Nationwide; Phoenix office staffed by 18 with active Arizona projects",
            "emr_2024": 0.65, "emr_2023": 0.69, "emr_2022": 0.72,
            "trir_2024": 1.4, "trir_2023": 1.6,
            "osha_recordables_3yr": 7,
            "lost_time_3yr": 1,
            "capabilities": [
                "Self-perform medium-voltage switchgear installation up to 35 kV",
                "Self-perform UPS module setting and battery cabinet integration",
                "Cx Level 5 commissioning oversight using owner-engaged CxA",
                "Tier III/IV electrical topology builds (N+1, 2N) with concurrent maintainability",
                "Specialty data center subcontractor base with 12+ year continuous relationships",
            ],
            "officer_name": "Allison Park",
            "officer_title": "Senior Vice President, Western Region",
            "officer_email": "apark@criticalfacilitiesgroup.com",
            "officer_phone": "602-555-0190",
            "key_personnel": [
                {
                    "name": "Allison Park",
                    "title": "Principal-in-Charge",
                    "years": 26,
                    "summary": (
                        "26 years mission-critical construction. Personally oversaw 9 hyperscale data center "
                        "projects in the Western US, including 4 in greater Phoenix."
                    ),
                    "credentials": "BS Electrical Engineering, Stanford (1999); PE (TX, AZ, NV, VA); LEED AP BD+C",
                    "projects": [
                        "Confidential Hyperscale Phoenix DC1  - 220,000 SF, $310M, 2024",
                        "QTS Mesa Phase II  - 90,000 SF, $112M, 2023",
                        "Aligned Phoenix DataPark Build-out  - 60,000 SF, $86M, 2022",
                    ],
                },
                {
                    "name": "Hector Ramirez",
                    "title": "Project Manager",
                    "years": 18,
                    "summary": (
                        "18 years project management exclusively on Tier III/IV data centers. "
                        "Lead PM on 6 completed Phoenix-region data centers totaling $480M."
                    ),
                    "credentials": "BS Construction Mgmt, ASU (2007); PMP; OSHA 30",
                    "projects": [
                        "QTS Mesa Phase II (Lead PM)  - $112M",
                        "Aligned Phoenix DataPark (Lead PM)  - $86M",
                        "Confidential Hyperscale Phoenix DC1 (Assistant PM)  - $310M",
                    ],
                },
                {
                    "name": "Linda Chu",
                    "title": "Commissioning Manager",
                    "years": 15,
                    "summary": (
                        "15 years commissioning oversight on mission-critical projects. ASHRAE/BCxP credentialed; "
                        "has run Cx Level 5 on 11 data centers."
                    ),
                    "credentials": "BCxP (Building Cx Professional); LEED AP O+M",
                    "projects": [
                        "Confidential Hyperscale Phoenix DC1 (Cx Mgr)  - IST and Cx Level 5",
                        "QTS Mesa Phase II (Cx Mgr)",
                    ],
                },
                {
                    "name": "Trevor Yates",
                    "title": "General Superintendent",
                    "years": 24,
                    "summary": (
                        "24 years field supervision on data centers. Managed 2N electrical builds and ran "
                        "180-person crews during peak rough-in phases."
                    ),
                    "credentials": "OSHA 30; CESCO; First Aid/CPR/AED Instructor",
                    "projects": [
                        "QTS Mesa Phase II  - Gen Sup",
                        "Aligned Phoenix DataPark  - Gen Sup",
                    ],
                },
            ],
            "past_projects": [
                {"name": "Confidential Hyperscale Phoenix DC1",
                 "scope": "220,000 SF, 80 MW Tier III hyperscale (NDA owner)",
                 "value": "$310M", "year": "2024", "owner": "Confidential (Fortune 50)",
                 "outcome": "Delivered 4 weeks ahead of CD; passed Cx Level 5 first attempt"},
                {"name": "QTS Mesa Phase II",
                 "scope": "90,000 SF, 24 MW Tier III expansion",
                 "value": "$112M", "year": "2023", "owner": "QTS Realty Trust",
                 "outcome": "On-time; zero recordables across 215,000 field hours"},
                {"name": "Aligned Phoenix DataPark Build-out",
                 "scope": "60,000 SF, 18 MW Tier III",
                 "value": "$86M", "year": "2022", "owner": "Aligned Data Centers",
                 "outcome": "On-time; selected by Aligned for repeat work in 2025"},
                {"name": "CyrusOne Chandler Phase III",
                 "scope": "75,000 SF, 22 MW Tier III",
                 "value": "$94M", "year": "2021", "owner": "CyrusOne",
                 "outcome": "On-time"},
                {"name": "Confidential Hyperscale Reno NV1",
                 "scope": "180,000 SF, 64 MW Tier III hyperscale",
                 "value": "$240M", "year": "2023", "owner": "Confidential",
                 "outcome": "On-time"},
            ],
            "bid_modifier": 1.04,
            "exclusions": [],
            "skip_trades": [],
            "trade_overrides": {},
        },
        {
            "tier": "marginal",
            "slug": "sonoran_industrial",
            "name": "Sonoran Industrial Constructors",
            "founded": 2008,
            "hq": "Phoenix, AZ",
            "branch_offices": "Tucson, AZ",
            "rev_2024": 128, "rev_2023": 115, "rev_2022": 102, "rev_2021": 88, "rev_2020": 74,
            "bonding_single": 200, "bonding_aggregate": 350,
            "surety": "Liberty Mutual Surety (A.M. Best A XV)",
            "employees": 175,
            "primary_market": "Semiconductor fab support and process manufacturing facilities",
            "secondary_market": "Distribution / cold storage; small data centers (sub-10 MW edge)",
            "geographic": "Arizona, southern Nevada, southern California",
            "emr_2024": 0.85, "emr_2023": 0.88, "emr_2022": 0.91,
            "trir_2024": 2.3, "trir_2023": 2.5,
            "osha_recordables_3yr": 11,
            "lost_time_3yr": 2,
            "capabilities": [
                "Heavy industrial process MEP coordination",
                "Cleanroom-adjacent civil and shell construction",
                "Standard medium-voltage gear installation up to 15 kV",
                "Small-scale data hall fit-outs (edge / colo style)",
            ],
            "officer_name": "Frank Estrella",
            "officer_title": "President",
            "officer_email": "festrella@sonoranindustrial.com",
            "officer_phone": "602-555-0298",
            "key_personnel": [
                {
                    "name": "Frank Estrella",
                    "title": "Principal-in-Charge",
                    "years": 30,
                    "summary": (
                        "30 years industrial construction. Led 2 small data center projects (3 MW and 5 MW) "
                        "in addition to a heavy semiconductor and manufacturing portfolio."
                    ),
                    "credentials": "BS Civil Engineering, ASU; PE (Arizona); OSHA 30",
                    "projects": [
                        "TSMC Phoenix Fab Support Building 4  - 180,000 SF, $94M, 2023",
                        "Edge Connect Glendale (5 MW edge DC)  - 18,000 SF, $24M, 2023",
                        "Stryker Tempe Manufacturing Expansion  - $42M, 2022",
                    ],
                },
                {
                    "name": "Naveen Kapoor",
                    "title": "Project Manager",
                    "years": 12,
                    "summary": (
                        "12 years construction PM. Lead PM on Sonoran's largest data center to date "
                        "(5 MW edge facility); learning curve to Tier III topology."
                    ),
                    "credentials": "BS Construction Mgmt, ASU; OSHA 30",
                    "projects": [
                        "Edge Connect Glendale  - Lead PM",
                        "TSMC Fab Support Building 4  - Assistant PM",
                    ],
                },
                {
                    "name": "Cody Whitman",
                    "title": "General Superintendent",
                    "years": 19,
                    "summary": (
                        "19 years industrial field supervision. Has not previously run a 2N electrical build "
                        "or full Cx Level 5 IST sequence."
                    ),
                    "credentials": "OSHA 30; First Aid/CPR",
                    "projects": [
                        "TSMC Phoenix Fab Support Building 4  - Gen Sup",
                        "Edge Connect Glendale  - Gen Sup",
                    ],
                },
            ],
            "past_projects": [
                {"name": "TSMC Phoenix Fab Support Building 4",
                 "scope": "180,000 SF process support building, MEP-intensive",
                 "value": "$94M", "year": "2023", "owner": "Taiwan Semiconductor Mfg Co",
                 "outcome": "On-time"},
                {"name": "Edge Connect Glendale",
                 "scope": "18,000 SF edge data center, 5 MW",
                 "value": "$24M", "year": "2023", "owner": "Edge Connect",
                 "outcome": "On-time; first Tier III build for the company"},
                {"name": "Cox Communications Mesa Co-Lo",
                 "scope": "12,000 SF colo expansion, 3 MW",
                 "value": "$14M", "year": "2021", "owner": "Cox",
                 "outcome": "On-time"},
                {"name": "Stryker Tempe Manufacturing Expansion",
                 "scope": "ISO 8 cleanroom shell expansion",
                 "value": "$42M", "year": "2022", "owner": "Stryker",
                 "outcome": "On-time"},
                {"name": "Lucid Motors Casa Grande Civil Phase",
                 "scope": "Civil work and utility tie-ins for EV plant expansion",
                 "value": "$28M", "year": "2024", "owner": "Lucid Motors",
                 "outcome": "On-time"},
            ],
            "bid_modifier": 0.95,
            "exclusions": [
                "Cx Level 5 commissioning oversight  - assumed performed by Owner-engaged CxA",
                "Medium-voltage switchgear above 15 kV  - by Owner direct purchase",
                "UPS battery cabinet integration  - by UPS manufacturer's field service",
                "BMS / DCIM software configuration  - by Owner's IT integrator",
            ],
            "skip_trades": [],
            "trade_overrides": {
                "Mechanical (HVAC)": 0.88,  # Light pricing on redundant cooling
                "Electrical": 0.86,  # Light pricing on 2N gear
            },
        },
        {
            "tier": "underqualified",
            "slug": "desert_office_builders",
            "name": "Desert Office Builders, Inc.",
            "founded": 2017,
            "hq": "Phoenix, AZ",
            "branch_offices": "None",
            "rev_2024": 34, "rev_2023": 30, "rev_2022": 26, "rev_2021": 22, "rev_2020": 18,
            "bonding_single": 50, "bonding_aggregate": 75,
            "surety": "Old Republic Surety (A.M. Best A+ X)",
            "employees": 62,
            "primary_market": "Class-A corporate office (ground-up and major TI)",
            "secondary_market": "Lifestyle retail centers",
            "geographic": "Maricopa County, AZ",
            "emr_2024": 1.18, "emr_2023": 1.22, "emr_2022": 1.20,
            "trir_2024": 3.6, "trir_2023": 3.8,
            "osha_recordables_3yr": 13,
            "lost_time_3yr": 2,
            "capabilities": [
                "Tilt-up and steel-frame Class-A office shell",
                "Office tenant improvement",
                "Lifestyle retail and small mixed-use",
            ],
            "officer_name": "Mitchell Brand",
            "officer_title": "President",
            "officer_email": "mbrand@desertofficebuilders.com",
            "officer_phone": "602-555-0411",
            "key_personnel": [
                {
                    "name": "Mitchell Brand",
                    "title": "Owner / Project Executive",
                    "years": 18,
                    "summary": (
                        "18 years GC management. Previously COO at a regional office GC; founded Desert Office "
                        "Builders in 2017. No mission-critical or data center experience."
                    ),
                    "credentials": "BBA, Arizona; OSHA 30",
                    "projects": [
                        "Camelback Corporate Center IV  - 110,000 SF Class-A office, $26M, 2023",
                        "Scottsdale Lifestyle Center Phase II  - $14M, 2022",
                        "Tempe Marketplace Office Pad  - $9M, 2024",
                    ],
                },
                {
                    "name": "Allison Burke",
                    "title": "Project Manager",
                    "years": 8,
                    "summary": (
                        "8 years construction PM on Class-A office and retail. No data center, "
                        "no commissioning, no medium-voltage experience."
                    ),
                    "credentials": "BS Construction Mgmt, NAU; OSHA 30",
                    "projects": [
                        "Camelback Corporate Center IV  - PM",
                        "Tempe Marketplace Office Pad  - PM",
                    ],
                },
            ],
            "past_projects": [
                {"name": "Camelback Corporate Center IV",
                 "scope": "110,000 SF Class-A office building",
                 "value": "$26M", "year": "2023", "owner": "Ryan Companies",
                 "outcome": "On-time"},
                {"name": "Scottsdale Lifestyle Center Phase II",
                 "scope": "Retail expansion, 64,000 SF",
                 "value": "$14M", "year": "2022", "owner": "Macerich",
                 "outcome": "On-time"},
                {"name": "Tempe Marketplace Office Pad",
                 "scope": "44,000 SF, 2-story office shell",
                 "value": "$9M", "year": "2024", "owner": "Vestar",
                 "outcome": "On-time"},
                {"name": "Mesa Corporate Plaza I",
                 "scope": "70,000 SF office shell",
                 "value": "$15M", "year": "2021", "owner": "Lincoln Property",
                 "outcome": "5 weeks late"},
                {"name": "Chandler Office Park Spec Building 7",
                 "scope": "55,000 SF office shell",
                 "value": "$11M", "year": "2024", "owner": "Wentworth Property",
                 "outcome": "On-time"},
            ],
            "bid_modifier": 0.78,
            "exclusions": [
                "UPS systems and DC battery plant  - NOT IN CONTRACT (no qualified subs on staff)",
                "Standby diesel generators  - by Owner direct purchase",
                "Medium-voltage switchgear  - by Owner direct purchase",
                "Redundant N+1 chilled water cooling  - by Owner direct purchase",
                "Cx Level 5 commissioning  - NOT IN CONTRACT",
                "Hot aisle containment systems  - by Owner direct",
                "Raised access flooring  - by Owner direct",
                "BMS / DCIM  - NOT IN CONTRACT",
                "Fiber backbone rough-in  - by Owner direct",
                "Security access control beyond standard card reader  - NOT IN CONTRACT",
            ],
            "skip_trades": [
                "Communications (Data, AV, Tel)",
                "Electronic Safety & Security",
            ],
            "trade_overrides": {
                "Mechanical (HVAC)": 0.45,  # massive miss on redundant cooling
                "Electrical": 0.52,  # massive miss on 2N gear, UPS, gens
                "Fire Suppression (Sprinklers)": 0.70,
            },
        },
    ],
    "p09": [
        {
            "tier": "strong",
            "slug": "peachtree_industrial",
            "name": "Peachtree Industrial Constructors",
            "founded": 1992,
            "hq": "Atlanta, GA",
            "branch_offices": "Charlotte, NC; Jacksonville, FL",
            "rev_2024": 295, "rev_2023": 268, "rev_2022": 244, "rev_2021": 218, "rev_2020": 188,
            "bonding_single": 500, "bonding_aggregate": 1000,
            "surety": "Travelers Casualty and Surety Company of America (A.M. Best A++ XV)",
            "employees": 410,
            "primary_market": "Concrete tilt-up distribution and logistics facilities",
            "secondary_market": "Light industrial / manufacturing; cold storage",
            "geographic": "Southeast (GA, NC, SC, FL, AL, TN)",
            "emr_2024": 0.72, "emr_2023": 0.75, "emr_2022": 0.79,
            "trir_2024": 1.9, "trir_2023": 2.1,
            "osha_recordables_3yr": 8,
            "lost_time_3yr": 2,
            "capabilities": [
                "Self-perform tilt-up panel forming, casting, and erection",
                "Self-perform concrete slab-on-grade up to 1.0M SF",
                "ESFR sprinkler subcontractor base with high-pile storage AHJ history",
                "Speed-to-market scheduling  - Atlanta-region 400k SF deliveries in 11-14 months",
                "Long-term subcontractor relationships across the Southeast",
            ],
            "officer_name": "Ben Holcomb",
            "officer_title": "President",
            "officer_email": "bholcomb@peachtreeindustrial.com",
            "officer_phone": "404-555-0277",
            "key_personnel": [
                {
                    "name": "Ben Holcomb",
                    "title": "Principal-in-Charge",
                    "years": 32,
                    "summary": (
                        "32 years industrial construction. Personally directed 22 distribution centers across "
                        "the Southeast in the last 12 years, including 8 above 500,000 SF."
                    ),
                    "credentials": "BS Building Construction, Georgia Tech (1993); OSHA 30; LEED AP",
                    "projects": [
                        "Hartsfield Logistics South Pad  - 580,000 SF, $58M, 2024",
                        "Amazon ATL3 Build-out  - 720,000 SF, $74M, 2023",
                        "Walmart Greenwood SC DC  - 1,100,000 SF, $112M, 2022",
                    ],
                },
                {
                    "name": "Sandra Reeves",
                    "title": "Project Manager",
                    "years": 17,
                    "summary": (
                        "17 years PM on tilt-up distribution. Lead PM on 5 of Peachtree's last 7 hyperscale "
                        "warehouses; consistently delivers ≤ 13 months from NTP."
                    ),
                    "credentials": "BS Civil Engineering, Auburn (2008); PE (GA, NC); OSHA 30",
                    "projects": [
                        "Hartsfield Logistics South Pad  - Lead PM",
                        "Amazon ATL3 Build-out  - Lead PM",
                        "Walmart Greenwood SC DC  - Lead PM",
                    ],
                },
                {
                    "name": "Tom Brady",
                    "title": "Tilt-up Superintendent",
                    "years": 26,
                    "summary": (
                        "26 years tilt-up panel construction. Has erected over 4,200 panels in his career. "
                        "Self-perform crew leader."
                    ),
                    "credentials": "OSHA 30; ACI Concrete Field Testing; First Aid/CPR",
                    "projects": [
                        "Hartsfield Logistics South Pad  - Tilt-up Sup",
                        "Walmart Greenwood SC DC  - Tilt-up Sup",
                    ],
                },
                {
                    "name": "Rita Esparza",
                    "title": "Safety Manager",
                    "years": 14,
                    "summary": (
                        "14 years construction safety. Authored Peachtree's tilt-up panel rigging plan template "
                        "in current use across all active jobs."
                    ),
                    "credentials": "CSP; OSHA 500; First Aid/CPR Instructor",
                    "projects": [
                        "Hartsfield Logistics South Pad  - Safety Mgr",
                        "Amazon ATL3 Build-out  - Safety Mgr",
                    ],
                },
            ],
            "past_projects": [
                {"name": "Hartsfield Logistics South Pad",
                 "scope": "580,000 SF tilt-up distribution, 72 dock doors",
                 "value": "$58M", "year": "2024", "owner": "Hartsfield Logistics REIT",
                 "outcome": "Delivered 5 weeks ahead of schedule; zero recordables in 142,000 hours"},
                {"name": "Amazon ATL3 Build-out",
                 "scope": "720,000 SF distribution / fulfillment center",
                 "value": "$74M", "year": "2023", "owner": "Amazon",
                 "outcome": "On-time; selected for follow-on project ATL5 in 2025"},
                {"name": "Walmart Greenwood SC DC",
                 "scope": "1,100,000 SF perishables distribution center",
                 "value": "$112M", "year": "2022", "owner": "Walmart",
                 "outcome": "On-time"},
                {"name": "Target Northeast Atlanta Sortation",
                 "scope": "420,000 SF tilt-up sortation center",
                 "value": "$44M", "year": "2024", "owner": "Target",
                 "outcome": "On-time"},
                {"name": "FedEx Ground Charlotte Hub",
                 "scope": "650,000 SF cross-dock",
                 "value": "$66M", "year": "2021", "owner": "FedEx Ground",
                 "outcome": "On-time"},
                {"name": "Home Depot Locust Grove DC",
                 "scope": "880,000 SF distribution center",
                 "value": "$92M", "year": "2023", "owner": "The Home Depot",
                 "outcome": "On-time"},
            ],
            "bid_modifier": 1.04,
            "exclusions": [],
            "skip_trades": [],
            "trade_overrides": {},
        },
        {
            "tier": "marginal",
            "slug": "southern_commercial",
            "name": "Southern Commercial Builders",
            "founded": 2007,
            "hq": "Marietta, GA",
            "branch_offices": "None",
            "rev_2024": 92, "rev_2023": 85, "rev_2022": 78, "rev_2021": 70, "rev_2020": 62,
            "bonding_single": 150, "bonding_aggregate": 250,
            "surety": "Liberty Mutual Surety (A.M. Best A XV)",
            "employees": 130,
            "primary_market": "Mid-market retail and lifestyle centers",
            "secondary_market": "Light industrial and warehouse (under 250,000 SF)",
            "geographic": "Georgia and Alabama",
            "emr_2024": 0.88, "emr_2023": 0.91, "emr_2022": 0.94,
            "trir_2024": 2.4, "trir_2023": 2.6,
            "osha_recordables_3yr": 9,
            "lost_time_3yr": 2,
            "capabilities": [
                "Self-perform concrete slab-on-grade",
                "Tilt-up coordination via long-term tilt subcontractor (not self-performed)",
                "Standard MEP coordination",
                "Mid-market retail / lifestyle center delivery",
            ],
            "officer_name": "Garrett Holloway",
            "officer_title": "President",
            "officer_email": "gholloway@southerncommercial.com",
            "officer_phone": "770-555-0184",
            "key_personnel": [
                {
                    "name": "Garrett Holloway",
                    "title": "Principal-in-Charge",
                    "years": 24,
                    "summary": (
                        "24 years construction. Strong track record on retail and small warehouse projects. "
                        "Largest distribution project completed: 215,000 SF in 2023."
                    ),
                    "credentials": "BS Building Science, Auburn; OSHA 30",
                    "projects": [
                        "Kennesaw Marketplace Phase III  - $28M, 2023",
                        "ALDI Distribution Loganville  - 215,000 SF, $26M, 2023",
                        "Acworth Logistics Building 1  - 180,000 SF, $19M, 2024",
                    ],
                },
                {
                    "name": "Rachel Owens",
                    "title": "Project Manager",
                    "years": 11,
                    "summary": (
                        "11 years construction PM. Most warehouse experience is sub-200,000 SF; "
                        "no prior 400,000 SF delivery."
                    ),
                    "credentials": "BS Construction Mgmt, Auburn; OSHA 30",
                    "projects": [
                        "ALDI Distribution Loganville  - PM",
                        "Acworth Logistics Building 1  - PM",
                    ],
                },
                {
                    "name": "Doug Patterson",
                    "title": "General Superintendent",
                    "years": 22,
                    "summary": (
                        "22 years field supervision. Strong on retail; tilt-up coordination via "
                        "subcontracted specialty erector."
                    ),
                    "credentials": "OSHA 30; First Aid/CPR",
                    "projects": [
                        "ALDI Distribution Loganville  - Gen Sup",
                        "Kennesaw Marketplace Phase III  - Gen Sup",
                    ],
                },
            ],
            "past_projects": [
                {"name": "ALDI Distribution Loganville",
                 "scope": "215,000 SF tilt-up distribution",
                 "value": "$26M", "year": "2023", "owner": "ALDI",
                 "outcome": "On-time"},
                {"name": "Acworth Logistics Building 1",
                 "scope": "180,000 SF tilt-up",
                 "value": "$19M", "year": "2024", "owner": "Stonemont Financial",
                 "outcome": "On-time"},
                {"name": "Kennesaw Marketplace Phase III",
                 "scope": "Lifestyle center expansion, 86,000 SF",
                 "value": "$28M", "year": "2023", "owner": "RPAI",
                 "outcome": "On-time"},
                {"name": "Cumming Town Center",
                 "scope": "Retail anchored center, 124,000 SF",
                 "value": "$22M", "year": "2022", "owner": "Cousins Properties",
                 "outcome": "On-time"},
                {"name": "Buford Industrial Building 4",
                 "scope": "150,000 SF speculative warehouse",
                 "value": "$15M", "year": "2024", "owner": "EastGroup Properties",
                 "outcome": "On-time"},
            ],
            "bid_modifier": 0.96,
            "exclusions": [
                "Dock equipment (levelers, seals, bumpers, restraints)  - by Owner direct purchase",
                "Parking lot striping and signage  - by Owner direct",
                "ESFR adjustments for cold-storage zones  - assumed not required per current drawings",
            ],
            "skip_trades": [],
            "trade_overrides": {
                "Concrete": 0.92,  # Tilt-up via sub, slightly stretched pricing
            },
        },
        {
            "tier": "underqualified",
            "slug": "buckhead_ti",
            "name": "Buckhead Tenant Improvement Co.",
            "founded": 2019,
            "hq": "Atlanta, GA",
            "branch_offices": "None",
            "rev_2024": 22, "rev_2023": 18, "rev_2022": 14, "rev_2021": 10, "rev_2020": 6,
            "bonding_single": 30, "bonding_aggregate": 45,
            "surety": "Hudson Insurance Group (A.M. Best A- VIII)",
            "employees": 48,
            "primary_market": "Office tenant improvements and small retail fit-outs",
            "secondary_market": "Restaurant TIs",
            "geographic": "Atlanta metro only",
            "emr_2024": 1.15, "emr_2023": 1.18, "emr_2022": 1.10,
            "trir_2024": 3.2, "trir_2023": 3.5,
            "osha_recordables_3yr": 10,
            "lost_time_3yr": 3,
            "capabilities": [
                "Office tenant improvement (drywall, ceilings, flooring, finishes)",
                "Small restaurant TI",
                "Small retail TI",
            ],
            "officer_name": "Cameron Brooks",
            "officer_title": "Owner / Managing Partner",
            "officer_email": "cbrooks@buckheadti.com",
            "officer_phone": "404-555-0367",
            "key_personnel": [
                {
                    "name": "Cameron Brooks",
                    "title": "Owner / Project Executive",
                    "years": 12,
                    "summary": (
                        "12 years construction; founded the company in 2019. Career has been entirely tenant "
                        "improvements; no ground-up shell or warehouse experience."
                    ),
                    "credentials": "BS Business, Georgia State; OSHA 30",
                    "projects": [
                        "Truist Plaza 14th Floor TI  - $1.4M, 2024",
                        "Phipps Plaza Apple Store TI  - $0.9M, 2023",
                        "BoA Tower 22nd Floor TI  - $1.6M, 2024",
                    ],
                },
                {
                    "name": "Jenna Rios",
                    "title": "Field Superintendent",
                    "years": 9,
                    "summary": (
                        "9 years TI superintendent experience. No experience with tilt-up panel erection, "
                        "site civil, or large-format warehouse work."
                    ),
                    "credentials": "OSHA 30; First Aid/CPR",
                    "projects": [
                        "Truist Plaza 14th Floor TI  - Sup",
                        "BoA Tower 22nd Floor TI  - Sup",
                    ],
                },
            ],
            "past_projects": [
                {"name": "Truist Plaza 14th Floor TI",
                 "scope": "22,000 SF Class-A office TI",
                 "value": "$1.4M", "year": "2024", "owner": "Cousins Properties",
                 "outcome": "On-time"},
                {"name": "BoA Tower 22nd Floor TI",
                 "scope": "26,000 SF executive office TI",
                 "value": "$1.6M", "year": "2024", "owner": "Bank of America",
                 "outcome": "On-time"},
                {"name": "Phipps Plaza Apple Store TI",
                 "scope": "Retail interior fit-out, 8,500 SF",
                 "value": "$0.9M", "year": "2023", "owner": "Simon Property Group",
                 "outcome": "On-time"},
                {"name": "Lenox Mall Shake Shack TI",
                 "scope": "Restaurant TI, 4,200 SF",
                 "value": "$0.6M", "year": "2023", "owner": "Shake Shack",
                 "outcome": "On-time"},
            ],
            "bid_modifier": 0.74,
            "exclusions": [
                "Concrete tilt-up panel forming, casting, and erection  - NOT IN CONTRACT (no tilt experience)",
                "Structural steel and roof joist erection  - NOT IN CONTRACT",
                "EPDM roofing system  - by Owner direct",
                "Site work, earthwork, paving, and utilities  - by Owner direct civil package",
                "ESFR sprinkler system  - NOT IN CONTRACT (assumed by sprinkler subcontractor under separate contract)",
                "Dock doors, dock levelers, dock equipment  - by Owner direct",
                "Building permit and impact fees  - by Owner",
                "Commissioning and testing  - NOT IN CONTRACT",
            ],
            "skip_trades": [
                "Demolition & Site Clearing",
                "Structural Steel & Misc Metals",
                "Earthwork, Grading & Site Preparation",
                "Site Paving, Curbs & Landscaping",
                "Site Utilities (Water, Sewer, Storm, Gas)",
                "Roofing, Waterproofing & Insulation",
                "Masonry",
            ],
            "trade_overrides": {
                "Concrete": 0.40,  # Only interior slab; no tilt panels
                "Fire Suppression (Sprinklers)": 0.55,
            },
        },
    ],
}


# ── PDF rendering ────────────────────────────────────────────────────────────
def get_styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("CompanyTitle", parent=s["Heading1"], fontSize=20, spaceAfter=2, textColor=colors.HexColor("#111111")))
    s.add(ParagraphStyle("DocSubtitle", parent=s["Italic"], fontSize=12, textColor=colors.HexColor("#555555"), spaceAfter=14))
    s.add(ParagraphStyle("SectionH", parent=s["Heading2"], fontSize=13, spaceBefore=12, spaceAfter=6, textColor=colors.HexColor("#111111")))
    s.add(ParagraphStyle("Body10", parent=s["Normal"], fontSize=10, leading=14))
    s.add(ParagraphStyle("BodySmall", parent=s["Normal"], fontSize=9, leading=12))
    return s


def fmt_money(n):
    return f"${n:,.0f}"


def header(story, styles, company, subtitle):
    story.append(Paragraph(company, styles["CompanyTitle"]))
    story.append(Paragraph(subtitle, styles["DocSubtitle"]))


def kv_block(story, styles, kvs):
    for k, v in kvs:
        story.append(Paragraph(f"<b>{k}:</b> {v}", styles["Body10"]))


def bullets(story, styles, items):
    for it in items:
        story.append(Paragraph(f"- {it}", styles["Body10"]))


def section(story, styles, title):
    story.append(Paragraph(title, styles["SectionH"]))


def build_doc(out_path, story):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(out_path), pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
    )
    doc.build(story)


# ── Renderers ────────────────────────────────────────────────────────────────
def render_rfp(project, out_path):
    s = get_styles()
    story = []
    story.append(Paragraph(project["owner"], s["CompanyTitle"]))
    story.append(Paragraph("Request for Proposal  - Construction Services", s["DocSubtitle"]))

    section(story, s, "Project")
    kv_block(story, s, [
        ("Project", project["name"]),
        ("Location", project["location"]),
        ("Type", project["type"]),
        ("Size", f"{project['size_sf']:,} SF, {project['stories']} {'story' if project['stories']==1 else 'stories'}"),
        ("Delivery Method", project["delivery_method"]),
    ])

    section(story, s, "Owner Contact")
    kv_block(story, s, [
        ("Owner", project["owner"]),
        ("Project Lead", project["owner_contact"]),
        ("Phone", project["owner_phone"]),
        ("Email", project["owner_email"]),
    ])

    section(story, s, "Design Team")
    kv_block(story, s, [
        ("Architect", project["architect"]),
        ("Structural Engineer", project["engineer_struct"]),
        ("MEP Engineer", project["engineer_mep"]),
    ])

    section(story, s, "Schedule")
    kv_block(story, s, [
        ("SOQ / Pre-Qualification Submission Due", project["submission_due"]),
        ("Bid Due", project["bid_due"]),
        ("Notice to Proceed Target", project["ntp_target"]),
        ("Substantial Completion Target", project["substantial_completion"]),
    ])

    section(story, s, "Project Scope Summary")
    story.append(Paragraph(project["scope_summary"], s["Body10"]))

    section(story, s, "Mandatory Qualifications")
    bullets(story, s, project["mandatory_quals"])

    section(story, s, "Selection Criteria")
    bullets(story, s, project["selection_criteria"])

    section(story, s, "Submission Requirements")
    bullets(story, s, [
        "Cover letter signed by an officer with binding authority",
        "Company profile (history, markets, capabilities, geographic presence)",
        "Financial summary including current bonding capacity letter from surety",
        "5-year safety record (EMR, TRIR, OSHA recordables)",
        "Organizational chart for proposed project team with allocation %",
        "Resumes for principal-in-charge, project manager, superintendent, QC manager, safety manager",
        "Past project profiles  - minimum 5 relevant projects with owner references",
        "Lump-sum bid tab broken out by trade package (CSI division)",
    ])

    section(story, s, "Trade Packages to be Priced")
    rows = [["CSI Code", "Trade Package"]]
    for name, code in TRADES:
        rows.append([code, name])
    t = Table(rows, colWidths=[1.0 * inch, 4.7 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#9CA3AF")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D1D5DB")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    build_doc(out_path, story)


def render_cover_letter(contractor, project, out_path):
    s = get_styles()
    story = []
    header(story, s, contractor["name"], "Cover Letter")

    section(story, s, "Submitted To")
    kv_block(story, s, [
        ("Project", project["name"]),
        ("Owner", project["owner"]),
        ("Date", "October 2025"),
        ("Submitted by", f"{contractor['officer_name']}, {contractor['officer_title']}"),
        ("Contact", f"{contractor['officer_email']} / {contractor['officer_phone']}"),
    ])

    section(story, s, "Letter")
    if contractor["tier"] == "strong":
        body = (
            f"Dear Selection Committee,<br/><br/>"
            f"{contractor['name']} is pleased to submit our qualifications for the "
            f"{project['name']} in {project['location']}. Our firm has built our reputation on "
            f"{contractor['primary_market'].lower()}, and we are uniquely positioned for this work given "
            f"our track record of relevant projects, deep specialty subcontractor base, and a project team "
            f"that has personally delivered comparable scope multiple times.<br/><br/>"
            f"We have reviewed the RFP requirements and confirm that we meet every mandatory qualification, "
            f"including bonding, safety performance, and demonstrated experience. We look forward to the "
            f"opportunity to interview with the selection committee.<br/><br/>"
            f"Sincerely,<br/>{contractor['officer_name']}, {contractor['officer_title']}"
        )
    elif contractor["tier"] == "marginal":
        body = (
            f"Dear Selection Committee,<br/><br/>"
            f"{contractor['name']} is pleased to submit our qualifications for the "
            f"{project['name']}. While our primary specialty is "
            f"{contractor['primary_market'].lower()}, we have meaningful experience adjacent to this scope "
            f"and have invested in growing our capabilities in this market.<br/><br/>"
            f"Our team brings strong local knowledge, an established subcontractor base in "
            f"{project['location'].split(',')[0]}, and a competitive bid backed by long-standing trade "
            f"relationships. We respectfully ask the committee to consider our proposal alongside the "
            f"specialty firms competing for this work.<br/><br/>"
            f"Sincerely,<br/>{contractor['officer_name']}, {contractor['officer_title']}"
        )
    else:
        body = (
            f"Dear Selection Committee,<br/><br/>"
            f"{contractor['name']} is excited to submit our company for consideration on the "
            f"{project['name']} project. While our background is in "
            f"{contractor['primary_market'].lower()}, we are a hungry, hands-on team that is eager to "
            f"expand into larger-scale commercial work. Our pricing is highly competitive and our "
            f"local presence is unmatched.<br/><br/>"
            f"We are confident that our energy and competitive bid will allow us to bring this project "
            f"in for less than the larger firms competing.<br/><br/>"
            f"Sincerely,<br/>{contractor['officer_name']}, {contractor['officer_title']}"
        )
    story.append(Paragraph(body, s["Body10"]))

    build_doc(out_path, story)


def render_company_profile(contractor, out_path):
    s = get_styles()
    story = []
    header(story, s, contractor["name"], "Company Profile")

    section(story, s, "Overview")
    kv_block(story, s, [
        ("Founded", str(contractor["founded"])),
        ("Headquarters", contractor["hq"]),
        ("Branch Offices", contractor["branch_offices"]),
        ("Annual Revenue (2024)", f"${contractor['rev_2024']}M"),
        ("Annual Revenue (2023)", f"${contractor['rev_2023']}M"),
        ("Bonding Capacity", f"${contractor['bonding_single']}M single project / ${contractor['bonding_aggregate']}M aggregate"),
        ("Surety", contractor["surety"]),
        ("Employees", str(contractor["employees"])),
    ])

    section(story, s, "Markets")
    kv_block(story, s, [
        ("Primary", contractor["primary_market"]),
        ("Secondary", contractor["secondary_market"]),
        ("Geographic Focus", contractor["geographic"]),
    ])

    section(story, s, "Capabilities")
    bullets(story, s, contractor["capabilities"])

    section(story, s, "Safety Performance (5-Year)")
    kv_block(story, s, [
        ("EMR (2024)", f"{contractor['emr_2024']}"),
        ("EMR (2023)", f"{contractor['emr_2023']}"),
        ("EMR (2022)", f"{contractor['emr_2022']}"),
        ("TRIR (2024)", f"{contractor['trir_2024']}"),
        ("TRIR (2023)", f"{contractor['trir_2023']}"),
        ("OSHA Recordables (last 3 years)", str(contractor["osha_recordables_3yr"])),
        ("Lost-Time Incidents (last 3 years)", str(contractor["lost_time_3yr"])),
    ])

    section(story, s, "Financial Summary")
    rev_rows = [["Year", "Revenue (US$M)"]]
    for y in (2024, 2023, 2022, 2021, 2020):
        rev_rows.append([str(y), f"${contractor[f'rev_{y}']}M"])
    t = Table(rev_rows, colWidths=[1.5 * inch, 1.8 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#9CA3AF")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D1D5DB")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    build_doc(out_path, story)


def render_past_projects(contractor, out_path):
    s = get_styles()
    story = []
    header(story, s, contractor["name"], "Past Projects List")

    section(story, s, "Selected Recent Projects")
    rows = [["Project", "Scope", "Value", "Year", "Owner", "Outcome"]]
    for p in contractor["past_projects"]:
        rows.append([p["name"], p["scope"], p["value"], p["year"], p["owner"], p["outcome"]])
    t = Table(rows, colWidths=[1.4*inch, 1.7*inch, 0.7*inch, 0.5*inch, 1.2*inch, 1.5*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#9CA3AF")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D1D5DB")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)

    if contractor["tier"] == "underqualified":
        section(story, s, "Notes")
        story.append(Paragraph(
            "Our project values to date have generally fallen below the size of the current opportunity. "
            "We are excited to use this project to expand our portfolio and credentials.",
            s["Body10"]))

    build_doc(out_path, story)


def render_key_personnel(contractor, out_path):
    s = get_styles()
    story = []
    header(story, s, contractor["name"], "Key Personnel  - Resumes")

    for i, kp in enumerate(contractor["key_personnel"]):
        if i > 0:
            story.append(Spacer(1, 0.15 * inch))
        story.append(Paragraph(f"{kp['name']}, {kp['title']}", s["SectionH"]))
        kv_block(story, s, [("Years of Experience", str(kp["years"]))])
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"<b>Summary</b>", s["Body10"]))
        story.append(Paragraph(kp["summary"], s["Body10"]))
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"<b>Credentials</b>", s["Body10"]))
        story.append(Paragraph(kp["credentials"], s["Body10"]))
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"<b>Selected Project Experience</b>", s["Body10"]))
        for proj in kp["projects"]:
            story.append(Paragraph(f"• {proj}", s["Body10"]))

    build_doc(out_path, story)


def compute_trade_prices(project, contractor):
    """Return list of {trade, csi, amount, included} per project trade for this contractor."""
    weights = TRADE_WEIGHTS[project["type"]]
    base_total = project["direct_cost_target"]
    mod = contractor["bid_modifier"]
    skip = set(contractor.get("skip_trades", []))
    overrides = contractor.get("trade_overrides", {})

    rows = []
    for trade, csi in TRADES:
        weight = weights.get(trade, 0.04)
        base_amt = base_total * weight
        if trade in skip:
            rows.append({"trade": trade, "csi": csi, "amount": 0, "included": False})
            continue
        ovr = overrides.get(trade, 1.0)
        amt = round(base_amt * mod * ovr / 1000) * 1000
        rows.append({"trade": trade, "csi": csi, "amount": amt, "included": True})
    return rows


def render_bid_tab(contractor, project, out_path):
    s = get_styles()
    story = []
    header(story, s, contractor["name"], "Bid Tab  - Lump-Sum Proposal")

    section(story, s, "Project")
    kv_block(story, s, [
        ("Project", project["name"]),
        ("Location", project["location"]),
        ("Owner", project["owner"]),
        ("Submitted by", f"{contractor['officer_name']}, {contractor['officer_title']}"),
        ("Contact", f"{contractor['officer_email']} / {contractor['officer_phone']}"),
        ("Bid Date", "December 2025"),
    ])

    section(story, s, "Lump-Sum Bid by CSI Trade Package")
    rows = [["CSI Code", "Trade Package", "Base Bid"]]
    trade_rows = compute_trade_prices(project, contractor)
    total = 0
    for r in trade_rows:
        if r["included"]:
            rows.append([r["csi"], r["trade"], fmt_money(r["amount"])])
            total += r["amount"]
        else:
            rows.append([r["csi"], r["trade"], "NO BID  - see exclusions"])
    rows.append(["", "TOTAL BASE BID", fmt_money(total)])

    t = Table(rows, colWidths=[0.9 * inch, 4.0 * inch, 1.6 * inch])
    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#9CA3AF")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D1D5DB")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#F9FAFB")]),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#D1FAE5")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ])
    t.setStyle(style)
    story.append(t)

    section(story, s, "Exclusions")
    if contractor["exclusions"]:
        bullets(story, s, contractor["exclusions"])
    else:
        story.append(Paragraph("No exclusions. Bid is for the full scope as described in the contract documents.", s["Body10"]))

    section(story, s, "Inclusions")
    bullets(story, s, [
        "All labor, material, equipment, taxes, and supervision required to deliver the scope priced above",
        "All permits and inspection fees customarily provided by the contractor",
        "Standard manufacturer warranties; one-year general workmanship warranty",
    ])

    section(story, s, "Bid Notes")
    story.append(Paragraph(
        f"Bid based on contract documents issued by {project['architect']} dated October 2025. "
        f"Pricing held firm for 60 days from bid date. Schedule assumes Notice to Proceed by "
        f"{project['ntp_target']} and substantial completion by {project['substantial_completion']}.",
        s["Body10"]
    ))

    build_doc(out_path, story)


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    total_pdfs = 0
    for project in PROJECTS:
        proj_dir = OUT / project["id"]
        proj_dir.mkdir(parents=True, exist_ok=True)
        rfp_path = proj_dir / "RFP.pdf"
        print(f"Generating {project['id']}: {project['name']}")
        render_rfp(project, rfp_path)
        total_pdfs += 1

        for c in CONTRACTORS[project["id"]]:
            c_dir = proj_dir / c["slug"]
            c_dir.mkdir(parents=True, exist_ok=True)
            print(f"  - {c['slug']} ({c['tier']})")
            render_cover_letter(c, project, c_dir / "01_cover_letter.pdf")
            render_company_profile(c, c_dir / "02_company_profile.pdf")
            render_past_projects(c, c_dir / "03_past_projects.pdf")
            render_key_personnel(c, c_dir / "04_key_personnel.pdf")
            render_bid_tab(c, project, c_dir / "05_bid_tab.pdf")
            total_pdfs += 5

    print(f"\nDone. {total_pdfs} PDFs written under {OUT}/")


if __name__ == "__main__":
    main()
