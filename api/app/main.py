from fastapi import FastAPI

from app.routers.access import router as access_router
from app.routers.attendance import router as attendance_router
from app.routers.payroll import router as payroll_router

app = FastAPI(title="EIGSI Attendance API", version="0.1.0")
app.include_router(access_router)
app.include_router(attendance_router)
app.include_router(payroll_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
