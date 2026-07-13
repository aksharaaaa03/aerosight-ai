from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import data_management
from app.api import health_monitoring
from app.api import power_performance
from app.api import fault_analysis
from app.api import predictive_maintenance
from app.api import operations_dashboard
from app.api import business_impact

app = FastAPI(title="SCADA Sentinel")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(data_management.router)
app.include_router(health_monitoring.router)
app.include_router(power_performance.router)
app.include_router(fault_analysis.router)
app.include_router(predictive_maintenance.router)
app.include_router(operations_dashboard.router)
app.include_router(business_impact.router)

@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "SCADA Sentinel backend is running"}