from __future__ import annotations

import platform
import subprocess
from pathlib import Path

from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pymodbus.client import ModbusTcpClient

from meter_ui.database import init_db, SessionLocal
from meter_ui.models import Meter

app = FastAPI(title="VuWatt Meter Management UI")

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

init_db()


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    db = SessionLocal()
    meters = db.query(Meter).order_by(Meter.id).all()
    return templates.TemplateResponse("meters.html", {"request": request, "meters": meters})


@app.get("/meter/new", response_class=HTMLResponse)
def meter_new(request: Request):
    return templates.TemplateResponse("meter_edit.html", {"request": request, "meter": None})


@app.post("/meter/save")
def meter_save(
    request: Request,
    serial_number: str = Form(...),
    ip_address: str = Form(...),
    unit_id: int = Form(1),
    baud_rate: int = Form(9600),
    model: str = Form("Acuvim-L"),
    site_name: str = Form(""),
):
    db = SessionLocal()
    new_meter = Meter(
        serial_number=serial_number,
        ip_address=ip_address,
        unit_id=unit_id,
        baud_rate=baud_rate,
        model=model,
        site_name=site_name,
    )
    db.add(new_meter)
    db.commit()

    return RedirectResponse(url="/", status_code=302)


@app.get("/meter/{meter_id}/edit", response_class=HTMLResponse)
def meter_edit(request: Request, meter_id: int):
    db = SessionLocal()
    meter = db.query(Meter).filter(Meter.id == meter_id).first()
    return templates.TemplateResponse("meter_edit.html", {"request": request, "meter": meter})


@app.post("/meter/{meter_id}/update")
def meter_update(
    request: Request,
    meter_id: int,
    serial_number: str = Form(...),
    ip_address: str = Form(...),
    unit_id: int = Form(1),
    baud_rate: int = Form(9600),
    model: str = Form("Acuvim-L"),
    site_name: str = Form(""),
):
    db = SessionLocal()
    meter = db.query(Meter).filter(Meter.id == meter_id).first()
    meter.serial_number = serial_number
    meter.ip_address = ip_address
    meter.unit_id = unit_id
    meter.baud_rate = baud_rate
    meter.model = model
    meter.site_name = site_name
    db.commit()

    return RedirectResponse(url="/", status_code=302)


@app.get("/meter/{meter_id}/delete")
def meter_delete(meter_id: int):
    db = SessionLocal()
    meter = db.query(Meter).filter(Meter.id == meter_id).first()
    if meter:
        db.delete(meter)
        db.commit()
    return RedirectResponse(url="/", status_code=302)


@app.get("/api/ping")
def api_ping(ip: str = Query(...)):
    """Ping a device and return whether it's reachable."""
    params = "-n" if platform.system().lower() == "windows" else "-c"
    command = ["ping", params, "1", ip]

    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        reachable = result.returncode == 0
        return JSONResponse({"reachable": reachable})
    except Exception:
        return JSONResponse({"reachable": False})


@app.get("/api/test_device")
def test_device(ip: str = Query(...), unit: int = Query(1)):
    """
    Attempts to read Acuvim date/time registers (0x1040–0x1045).
    If successful → device is reachable & alive.

    Returns a reason string on failure so the UI can show something more
    useful than a generic "No Modbus response" message.
    """

    client = ModbusTcpClient(ip, port=502, timeout=3)

    # Make sure pymodbus uses the requested unit/device id on TCP
    client.unit_id = unit
    if hasattr(client, "device_id"):
        client.device_id = unit

    try:
        if not client.connect():
            return {"reachable": False, "reason": "TCP connect failed"}

        result = client.read_holding_registers(0x1040, 6, slave=unit)

        if result.isError():
            return {"reachable": False, "reason": str(result)}

        year, month, day, hour, minute, second = result.registers
        device_time = f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"

        return {"reachable": True, "device_time": device_time}

    except Exception as exc:  # pragma: no cover - network errors
        return {"reachable": False, "reason": str(exc)}

    finally:
        client.close()
