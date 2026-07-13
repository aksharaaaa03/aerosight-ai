from fastapi import APIRouter, Query
from app.pipelines.operations_dashboard import (
    get_fleet_overview,
    build_active_alerts,
    get_recent_events,
    get_sensor_trends,
    get_prediction_summary,
)


router = APIRouter(prefix="/operations", tags=["Operations Dashboard"])


@router.get("/fleet-overview")
def fleet_overview():
    return get_fleet_overview()


@router.get("/active-alerts")
def active_alerts():
    return {"alerts": build_active_alerts()}


@router.get("/recent-events")
def recent_events(
    turbine_id: str = Query(None),
    start_date: str = Query(None),
    end_date: str = Query(None),
    limit: int = Query(20),
):
    return {"events": get_recent_events(turbine_id, start_date, end_date, limit)}


@router.get("/sensor-trends/{turbine_id}")
def sensor_trends(
    turbine_id: str,
    sensors: str = Query(None, description="Comma-separated sensor names"),
    start_date: str = Query(None),
    end_date: str = Query(None),
    resample: str = Query("h"),
):
    sensor_list = sensors.split(",") if sensors else None
    return get_sensor_trends(turbine_id, sensor_list, start_date, end_date, resample)

@router.get("/prediction-summary")
def prediction_summary():
    return {"predictions": get_prediction_summary()}