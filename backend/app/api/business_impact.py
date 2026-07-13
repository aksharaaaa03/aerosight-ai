from fastapi import APIRouter
from app.pipelines.business_impact import (
    get_energy_loss_cost,
    get_fault_repair_cost,
    get_asset_risk_ranking,
    get_fleet_performance_summary,
)

router = APIRouter(prefix="/business-impact", tags=["Business Impact Dashboard"])


@router.get("/energy-loss-cost")
def energy_loss_cost():
    return get_energy_loss_cost()


@router.get("/fault-repair-cost")
def fault_repair_cost():
    return get_fault_repair_cost()


@router.get("/asset-risk-ranking")
def asset_risk_ranking():
    return {"ranking": get_asset_risk_ranking()}


@router.get("/fleet-performance-summary")
def fleet_performance_summary():
    return get_fleet_performance_summary()