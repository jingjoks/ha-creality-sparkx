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
