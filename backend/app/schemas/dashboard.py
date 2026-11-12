from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class DashboardStats(BaseModel):
    activeClients: int
    documents: int
    vouchers: int
    complianceAlerts: int


class ActivityItem(BaseModel):
    client: str
    action: str
    time: str
    status: str


class DashboardOut(BaseModel):
    stats: DashboardStats
    recentActivity: List[ActivityItem]
    extraStats: Optional[Dict[str, Any]] = None