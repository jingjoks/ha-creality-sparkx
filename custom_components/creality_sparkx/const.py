"""Constants for the Creality SPARKX integration."""

DOMAIN = "creality_sparkx"

CONF_HOST = "host"

DEFAULT_PORT = 80
WS_PATH = "/ws"
INFO_PATH = "/info"

# Reconnect / keepalive tuning
RECONNECT_DELAY_SECONDS = 5
PING_INTERVAL_SECONDS = 20

# ---------------------------------------------------------------------------
# Printer "state" field is a small integer. Mapping observed on SPARKX i7 /
# F022 firmware 1.1.5.8. Some values are inferred from Creality K-series
# community integrations (fields match: nozzleTemp, bedTemp0, printProgress,
# cfsConnect, etc.) — please open an issue if your firmware reports
# differently so this table can be corrected.
# ---------------------------------------------------------------------------
PRINTER_STATE_MAP = {
    0: "idle",
    1: "printing",
    2: "paused",
    3: "completed",
    4: "error",
    5: "self_test",
    6: "leveling",
    7: "heating",
}

DEVICE_MANUFACTURER = "Creality"

# ---------------------------------------------------------------------------
# Official SPARKX error codes, from https://wiki.creality.com/en/sparkx/error-code
# Key = the alphanumeric code the printer reports in err.value (e.g. "CZ2768").
# ---------------------------------------------------------------------------
ERROR_CODE_MAP = {
    "CZ2768": "Z-axis homing issue, may have an external disturbance",
    "FB2944": "Feeding abnormal — filament odometer normal but the filament sensor in the extrusion assembly has not been triggered for an extended period; the PTFE tube may be disconnected",
    "FR2939": "Filament depleted in slot, please insert filament promptly",
    "FO2971": "Pre-loading filament abnormal, timeout when feeding filament to the designated position. Please resolve the issue and tap \"Retry\"",
    "FR2949": "Filament unloading abnormal, filament cannot retract to the toolhead manifold. Please resolve the issue and tap \"Retry\"",
    "FO2970": "Filament unloading abnormal, feeding motor stalled, filament cannot exit the extruder",
    "FB2964": "Feeding abnormal, buffer not reaching full limit, filament may be ground",
    "FB2947": "Buffer stuck at empty limit, filament may be tangled",
    "FR0122": "External spool filament detected during use",
    "FO0528": "Possible under-extrusion detected",
    "FO2936": "Feeding abnormal: filament sensor in the extrusion assembly not triggered, filament not fed into the extrusion assembly",
    "FO2945": "Possible extruder clog detected — please resolve the issue and click \"Retry\"",
    "TR2963": "Unloading abnormal — extruder filament detection triggered, filament may be broken inside the extruder",
    "TE2564": "Nozzle not heating as expected",
}
