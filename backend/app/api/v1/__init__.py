from fastapi import APIRouter
from app.api.v1.clients import router as clients_router
from app.api.v1.documents import router as documents_router
from app.api.v1.vouchers import router as vouchers_router
from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.tally import router as tally_router
from app.api.v1.tally_ws import router as tally_ws_router          # NEW
from app.api.v1.connector_key import router as connector_key_router  # NEW
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.reports import router as reports_router
from app.api.v1.bank_reconciliation import router as bank_rec_router
from app.api.v1.checklist import router as checklist_router
from app.api.v1.tenants import router as tenants_router
from app.api.v1.ledgers import router as ledgers_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(clients_router)
api_router.include_router(documents_router,     prefix="/documents",           tags=["documents"])
api_router.include_router(vouchers_router,      prefix="/vouchers",            tags=["vouchers"])
api_router.include_router(chat_router,          prefix="/chat",                tags=["chat"])
api_router.include_router(tally_router,         prefix="/tally",               tags=["tally"])
api_router.include_router(tally_ws_router,      prefix="/tally",               tags=["tally-ws"])   # NEW
api_router.include_router(connector_key_router, prefix="/connector",           tags=["connector"])  # NEW
api_router.include_router(dashboard_router,     prefix="/dashboard",           tags=["dashboard"])
api_router.include_router(reports_router,       prefix="/reports",             tags=["reports"])
api_router.include_router(bank_rec_router,      prefix="/bank-reconciliation", tags=["bank-reconciliation"])
api_router.include_router(checklist_router,     prefix="/checklist",           tags=["checklists"])
api_router.include_router(tenants_router,       prefix="/tenants",             tags=["tenants"])
api_router.include_router(ledgers_router,       prefix="/ledgers",             tags=["ledgers"])