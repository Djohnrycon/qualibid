"""Contractor scorer for QualiBid. Sends contractor docs + project context to Claude
and gets back a structured pre-qualification evaluation via tool use."""
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()
client = Anthropic()

MODEL = "claude-sonnet-4-6"

EVAL_TOOL = {
    "name": "submit_evaluation",
    "description": "Submit a structured evaluation of a contractor against the project's requirements.",
    "input_schema": {
        "type": "object",
        "properties": {
            "category_scores": {
                "type": "array",
                "description": "One entry per scoring category provided in the prompt.",
                "items": {
                    "type": "object",
                    "properties": {
                        "category_name": {
                            "type": "string",
                            "description": "Must match one of the provided category names exactly."
                        },
                        "score": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 100,
                            "description": "Integer 0-100. 0 means total mismatch, 100 means ideal fit."
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "2-3 sentence explanation grounding the score in the contractor's documents."
                        },
                        "evidence": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "At least 2 specific facts or quotes from the contractor's documents that justify the score."
                        }
                    },
                    "required": ["category_name", "score", "reasoning", "evidence"]
                }
            },
            "overall_summary": {
                "type": "string",
                "description": "3-4 sentence executive summary of the contractor's fit for this project."
            },
            "strengths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Top 3-5 strengths for this project."
            },
            "concerns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Top 3-5 concerns or gaps for this project."
            }
        },
        "required": ["category_scores", "overall_summary", "strengths", "concerns"]
    }
}

SYSTEM_PROMPT = (
    "You are a senior pre-construction evaluator working for a construction owner. "
    "Your job is to assess a bidding contractor's qualification package against a "
    "specific project's requirements. You score 0-100 on each provided category and "
    "back every score with specific evidence quoted or paraphrased from the contractor's "
    "documents. You are rigorous and fair. You never invent facts not present in the "
    "source documents. If a contractor's documents do not address a stated requirement, "
    "that absence is itself meaningful evidence and should lower the score for the "
    "affected category. Always submit your evaluation using the submit_evaluation tool."
)


def score_contractor(rfp_text, contractor_text, categories):
    """Score a contractor against project context using the provided categories.

    Args:
        rfp_text: full text of the project RFP / requirements / context
        contractor_text: full text of the contractor's documents
        categories: list of {"name": str, "description": str, ...} dicts

    Returns:
        dict with keys: category_scores, overall_summary, strengths, concerns
    """
    cat_block = "\n".join(
        f"- {c['name']}: {c['description']}" for c in categories
    )

    cached_block = (
        "# PROJECT CONTEXT\n\n"
        f"{rfp_text}\n\n"
        "# SCORING CATEGORIES\n\n"
        f"{cat_block}\n\n"
        "You will score a contractor against the project context and categories above. "
        "The contractor's documents follow in the next text block."
    )

    contractor_block = (
        "# CONTRACTOR DOCUMENTS\n\n"
        f"{contractor_text}\n\n"
        "Submit your evaluation using the submit_evaluation tool. "
        "For each category, give a 0-100 score, 2-3 sentences of reasoning, "
        "and at least 2 specific pieces of evidence drawn from the contractor's documents."
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=[EVAL_TOOL],
        tool_choice={"type": "tool", "name": "submit_evaluation"},
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": cached_block,
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": contractor_block,
                    },
                ],
            }
        ],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_evaluation":
            return block.input

    raise RuntimeError("Claude did not return a submit_evaluation tool call.")


BID_EXTRACT_TOOL = {
    "name": "submit_bid_data",
    "description": "Extract structured bid data from a contractor's documents.",
    "input_schema": {
        "type": "object",
        "properties": {
            "company": {
                "type": "string",
                "description": "Bidding company's full name."
            },
            "contact": {
                "type": "string",
                "description": "Primary contact name (empty string if unknown)."
            },
            "email": {
                "type": "string",
                "description": "Contact email (empty string if unknown)."
            },
            "submitted_date": {
                "type": "string",
                "description": "Date the bid was submitted in YYYY-MM-DD format. Use '—' if unknown."
            },
            "source": {
                "type": "string",
                "enum": ["PDF", "Excel", "Email", "Upload"],
                "description": "Original document format. Use 'Upload' if mixed or unknown."
            },
            "trades": {
                "type": "array",
                "description": (
                    "One entry per trade package this contractor bid on. Use exact trade names "
                    "from the project trade list. Empty array if the documents are qualification-only "
                    "with no priced bid."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "trade_name": {
                            "type": "string",
                            "description": "Must match one of the available trade package names exactly."
                        },
                        "csi_code": {"type": "string"},
                        "base_bid": {
                            "type": "number",
                            "description": "Total base bid in dollars for this trade."
                        },
                        "exclusions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Items the contractor explicitly excluded from their scope."
                        },
                        "line_items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "description": {"type": "string"},
                                    "amount": {"type": "number"}
                                },
                                "required": ["description", "amount"]
                            },
                            "description": "Detailed line items if the bid breaks them out. Empty if not provided."
                        }
                    },
                    "required": ["trade_name", "csi_code", "base_bid", "exclusions", "line_items"]
                }
            }
        },
        "required": ["company", "trades"]
    }
}


def extract_bid_data(contractor_text, project_trades):
    """Extract structured bid data from contractor docs against the project's trade packages.

    Args:
        contractor_text: full text of the contractor's documents
        project_trades: list of {"trade": str, "csi_code": str, ...} from the project

    Returns:
        dict with keys: company, contact, email, submitted_date, source, trades.
        The 'trades' list may be empty if the documents are qualification-only.
    """
    trades_block = "\n".join(
        f"- {t['trade']} (CSI {t['csi_code']})" for t in project_trades
    )

    prompt = (
        "# AVAILABLE TRADE PACKAGES FOR THIS PROJECT\n\n"
        f"{trades_block}\n\n"
        "# CONTRACTOR DOCUMENTS\n\n"
        f"{contractor_text}\n\n"
        "Extract structured bid data from these contractor documents. For each trade package "
        "the contractor bid on, use exact trade names from the list above and report the "
        "company info, base bid amount, exclusions, and line items if available. "
        "If the documents are qualification-only (no priced bid), return an empty trades list. "
        "Submit using the submit_bid_data tool."
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        tools=[BID_EXTRACT_TOOL],
        tool_choice={"type": "tool", "name": "submit_bid_data"},
        messages=[{"role": "user", "content": prompt}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_bid_data":
            return block.input

    raise RuntimeError("Claude did not return a submit_bid_data tool call.")


DEFAULT_PREQUAL_CATEGORIES = [
    {
        "name": "Experience",
        "description": (
            "Has this contractor done this type of work before? Look for relevant "
            "past projects matching the scope (size, building type, construction "
            "methods, certifications). Weight self-performed work over subcontracted, "
            "recent over old, similar-sized over much smaller."
        ),
    },
    {
        "name": "Experience in Market",
        "description": (
            "Has this contractor worked in the project's geography? Look for prior "
            "projects in the same state or region, established relationships with the "
            "owner agency, familiarity with regional regulators, and access to a "
            "qualified local labor force."
        ),
    },
    {
        "name": "Marketplace Posture",
        "description": (
            "Is this contractor a credible business at the right scale for this "
            "project? Consider bonding capacity vs. project value, financial health "
            "(revenue trend, working capital), safety record (EMR, TRIR, OSHA "
            "recordables), and right-sizing (not too small to deliver, not so "
            "overcommitted that they can't take on more)."
        ),
    },
]
