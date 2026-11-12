"""
Financial reports from Tally: Trial Balance, Profit & Loss.
Routes via WebSocket tunnel (production) or direct HTTP (dev).
Falls back to demo data when Tally is unreachable.
"""
import xml.etree.ElementTree as ET
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.tally_routing import route_tally_xml
from app.models.client import Client

router = APIRouter()


# ── Demo data (your existing data kept intact) ────────────────────────────────

DEMO_TRIAL_BALANCE = {
    "report_type": "trial_balance",
    "period": "Apr 2024 – Mar 2025",
    "generated_at": "2025-01-11",
    "source": "demo",
    "groups": [
        {
            "name": "Capital Account",
            "entries": [
                {"ledger": "Capital Account", "opening_dr": 0, "opening_cr": 500000, "transactions_dr": 0, "transactions_cr": 0, "closing_dr": 0, "closing_cr": 500000},
            ]
        },
        {
            "name": "Sundry Creditors",
            "entries": [
                {"ledger": "ABC Suppliers",   "opening_dr": 0, "opening_cr": 25000, "transactions_dr": 10000, "transactions_cr": 35000, "closing_dr": 0, "closing_cr": 50000},
                {"ledger": "XYZ Trading LLC", "opening_dr": 0, "opening_cr": 18000, "transactions_dr": 5000,  "transactions_cr": 20000, "closing_dr": 0, "closing_cr": 33000},
            ]
        },
        {
            "name": "Current Assets",
            "entries": [
                {"ledger": "Cash",                       "opening_dr": 15000,  "opening_cr": 0, "transactions_dr": 85000,  "transactions_cr": 72000,  "closing_dr": 28000,  "closing_cr": 0},
                {"ledger": "Bank Account - Emirates NBD","opening_dr": 120000, "opening_cr": 0, "transactions_dr": 320000, "transactions_cr": 290000, "closing_dr": 150000, "closing_cr": 0},
                {"ledger": "Accounts Receivable",        "opening_dr": 45000,  "opening_cr": 0, "transactions_dr": 180000, "transactions_cr": 165000, "closing_dr": 60000,  "closing_cr": 0},
            ]
        },
        {
            "name": "Sales Accounts",
            "entries": [
                {"ledger": "Sales – Services", "opening_dr": 0, "opening_cr": 0, "transactions_dr": 0, "transactions_cr": 450000, "closing_dr": 0, "closing_cr": 450000},
                {"ledger": "Sales – Products", "opening_dr": 0, "opening_cr": 0, "transactions_dr": 0, "transactions_cr": 85000,  "closing_dr": 0, "closing_cr": 85000},
            ]
        },
        {
            "name": "Expenses",
            "entries": [
                {"ledger": "Salaries Payable", "opening_dr": 0, "opening_cr": 0, "transactions_dr": 180000, "transactions_cr": 0, "closing_dr": 180000, "closing_cr": 0},
                {"ledger": "Rent Expense",     "opening_dr": 0, "opening_cr": 0, "transactions_dr": 60000,  "transactions_cr": 0, "closing_dr": 60000,  "closing_cr": 0},
                {"ledger": "Utilities",        "opening_dr": 0, "opening_cr": 0, "transactions_dr": 12000,  "transactions_cr": 0, "closing_dr": 12000,  "closing_cr": 0},
                {"ledger": "Office Expenses",  "opening_dr": 0, "opening_cr": 0, "transactions_dr": 8500,   "transactions_cr": 0, "closing_dr": 8500,   "closing_cr": 0},
            ]
        },
    ],
    "totals": {"debit": 1066500, "credit": 1066500},
}

DEMO_PL = {
    "report_type": "profit_loss",
    "period": "Apr 2024 – Mar 2025",
    "generated_at": "2025-01-11",
    "source": "demo",
    "income": [
        {"name": "Sales – Services", "amount": 450000},
        {"name": "Sales – Products", "amount": 85000},
        {"name": "Other Income",     "amount": 12500},
    ],
    "expenses": [
        {"name": "Salaries & Wages",        "amount": 180000},
        {"name": "Rent Expense",            "amount": 60000},
        {"name": "Cost of Goods Sold",      "amount": 42000},
        {"name": "Utilities",               "amount": 12000},
        {"name": "Office Expenses",         "amount": 8500},
        {"name": "Marketing & Advertising", "amount": 15000},
        {"name": "Depreciation",            "amount": 9000},
    ],
    "gross_profit": 450500,
    "net_profit": 221000,
    "total_income": 547500,
    "total_expenses": 326500,
}


# ── Tally XML builders ────────────────────────────────────────────────────────

def _trial_balance_xml(company: str, from_date: str, to_date: str) -> str:
    return f"""<ENVELOPE>
  <HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
  <BODY><EXPORTDATA>
    <REQUESTDESC>
      <REPORTNAME>Trial Balance</REPORTNAME>
      <STATICVARIABLES>
        <SVFROMDATE>{from_date}</SVFROMDATE>
        <SVTODATE>{to_date}</SVTODATE>
        <SVCOMPANYNAME>{company}</SVCOMPANYNAME>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
      </STATICVARIABLES>
    </REQUESTDESC>
  </EXPORTDATA></BODY>
</ENVELOPE>"""


def _pl_xml(company: str, from_date: str, to_date: str) -> str:
    return f"""<ENVELOPE>
  <HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
  <BODY><EXPORTDATA>
    <REQUESTDESC>
      <REPORTNAME>Profit and Loss</REPORTNAME>
      <STATICVARIABLES>
        <SVFROMDATE>{from_date}</SVFROMDATE>
        <SVTODATE>{to_date}</SVTODATE>
        <SVCOMPANYNAME>{company}</SVCOMPANYNAME>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
      </STATICVARIABLES>
    </REQUESTDESC>
  </EXPORTDATA></BODY>
</ENVELOPE>"""


# ── Tally XML parsers ─────────────────────────────────────────────────────────

def _parse_trial_balance(xml_text: str, period: str) -> dict:
    """Parse Tally Trial Balance XML into structured groups."""
    try:
        root = ET.fromstring(xml_text)
        groups: dict = {}

        for ledger in root.iter("LEDGER"):
            name = ledger.findtext("NAME") or ledger.get("NAME", "Unknown")
            parent = ledger.findtext("PARENT") or "Uncategorised"
            closing_dr = float(ledger.findtext("CLOSINGBALANCE") or 0)
            closing_cr = 0.0
            if closing_dr < 0:
                closing_cr = abs(closing_dr)
                closing_dr = 0.0

            if parent not in groups:
                groups[parent] = []
            groups[parent].append({
                "ledger": name,
                "opening_dr": 0, "opening_cr": 0,
                "transactions_dr": 0, "transactions_cr": 0,
                "closing_dr": closing_dr,
                "closing_cr": closing_cr,
            })

        total_dr = sum(e["closing_dr"] for g in groups.values() for e in g)
        total_cr = sum(e["closing_cr"] for g in groups.values() for e in g)

        return {
            "report_type": "trial_balance",
            "period": period,
            "source": "tally",
            "groups": [{"name": k, "entries": v} for k, v in groups.items()],
            "totals": {"debit": round(total_dr, 2), "credit": round(total_cr, 2)},
        }
    except Exception:
        return None


def _parse_pl(xml_text: str, period: str) -> dict:
    """Parse Tally P&L XML into income/expense structure."""
    INCOME_GROUPS = {"Sales Accounts", "Direct Income", "Indirect Income", "Other Income"}
    EXPENSE_GROUPS = {"Direct Expenses", "Indirect Expenses", "Purchase Accounts"}

    try:
        root = ET.fromstring(xml_text)
        income, expenses = [], []

        for ledger in root.iter("LEDGER"):
            name = ledger.findtext("NAME") or ledger.get("NAME", "Unknown")
            parent = ledger.findtext("PARENT") or ""
            amount = abs(float(ledger.findtext("CLOSINGBALANCE") or 0))
            if amount == 0:
                continue

            if any(g in parent for g in INCOME_GROUPS):
                income.append({"name": name, "amount": round(amount, 2)})
            elif any(g in parent for g in EXPENSE_GROUPS):
                expenses.append({"name": name, "amount": round(amount, 2)})

        total_income = sum(i["amount"] for i in income)
        total_expenses = sum(e["amount"] for e in expenses)

        return {
            "report_type": "profit_loss",
            "period": period,
            "source": "tally",
            "income": income,
            "expenses": expenses,
            "total_income": round(total_income, 2),
            "total_expenses": round(total_expenses, 2),
            "net_profit": round(total_income - total_expenses, 2),
            "gross_profit": round(total_income - total_expenses, 2),
        }
    except Exception:
        return None


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get("/tally")
async def get_tally_report(
    client_id: str = Query(...),
    report_type: str = Query("trial_balance"),  # trial_balance | profit_loss
    from_date: str = Query(None),
    to_date: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(404, "Client not found")

    today = date.today()
    _from = from_date or f"{today.year}-04-01"
    _to = to_date or today.isoformat()
    period_label = f"{_from} – {_to}"

    # Fallback to demo if Tally not configured
    if not client.tally_company or not client.tally_host:
        demo = DEMO_PL if report_type == "profit_loss" else DEMO_TRIAL_BALANCE
        return {**demo, "client_id": client_id, "client_name": client.name}

    # Build XML for the requested report
    if report_type == "profit_loss":
        xml = _pl_xml(client.tally_company, _from, _to)
    else:
        xml = _trial_balance_xml(client.tally_company, _from, _to)

    try:
        raw_xml = await route_tally_xml(client, xml)

        # Parse real Tally response
        if report_type == "profit_loss":
            parsed = _parse_pl(raw_xml, period_label)
        else:
            parsed = _parse_trial_balance(raw_xml, period_label)

        if parsed:
            return {**parsed, "client_id": client_id, "client_name": client.name}

        # Parse failed — return demo with warning
        demo = DEMO_PL if report_type == "profit_loss" else DEMO_TRIAL_BALANCE
        return {**demo, "client_id": client_id, "client_name": client.name,
                "source": "demo", "warning": "Could not parse Tally response"}

    except Exception as e:
        # Connector offline or Tally error — graceful demo fallback
        demo = DEMO_PL if report_type == "profit_loss" else DEMO_TRIAL_BALANCE
        return {**demo, "client_id": client_id, "client_name": client.name,
                "source": "demo", "tally_error": str(e)}