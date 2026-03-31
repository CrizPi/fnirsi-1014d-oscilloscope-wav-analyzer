import atexit
import os
import tempfile
import uuid
from threading import Lock

import numpy as np
from flask import session


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_NAME = "FNIRSI 1014D Analyzer"
DEFAULT_APP_DATA_ROOT = os.getenv("LOCALAPPDATA") or tempfile.gettempdir()
APP_DATA_DIR = os.getenv("FNIRSI_APP_DATA_DIR", os.path.join(DEFAULT_APP_DATA_ROOT, "FNIRSI1014DAnalyzer"))
UPLOAD_FOLDER = os.path.join(APP_DATA_DIR, "uploads")
SECRET_KEY_PATH = os.path.join(APP_DATA_DIR, "flask_secret.key")
os.makedirs(APP_DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DEFAULT_CONFIG = {
    "volts_div": [0, 0],
    "volt_units": ["V", "V"],
    "volt_multiplier": [1, 1],
    "probe": [1, 1],
    "coupling": ["DC", "DC"],
    "time_div": 0,
    "time_units": "S",
    "time_multiplier": 1,
    "trigger_type": "auto",
    "trigger_edge": "rising",
    "trigger_channel": "CH1",
    "trigger_50": "Off",
}
DEFAULT_MEASURES = {
    "Vmax": [0, 0],
    "Vmin": [0, 0],
    "Vavg": [0, 0],
    "Vrms": [0, 0],
    "Vpp": [0, 0],
    "Vp": [0, 0],
    "Freq": [0, 0],
    "Cycle": [0, 0],
    "Time+": [0, 0],
    "Time-": [0, 0],
    "Duty+": [0, 0],
    "Duty-": [0, 0],
    "freq_units": ["Hz", "Hz"],
    "freq_multiplier": [1, 1],
    "cycle_units": ["S", "S"],
    "cycle_multiplier": [1, 1],
    "time_plus_units": ["S", "S"],
    "time_minus_units": ["S", "S"],
    "time_plus_multiplier": [1, 1],
    "time_minus_multiplier": [1, 1],
}
DEFAULT_MATH_MEASURES = {
    "Vmax": 0,
    "Vmin": 0,
    "Vavg": 0,
    "Vrms": 0,
    "Vpp": 0,
    "Vp": 0,
    "Freq": 0,
    "freq_unit": "Hz",
    "Cycle": 0,
    "cycle_unit": "s",
    "Time+": 0,
    "time_plus_unit": "s",
    "Time-": 0,
    "time_minus_unit": "s",
    "Duty+": 0,
    "Duty-": 0,
}
DEFAULT_FFT_SETTINGS = {
    "channel": "X",
    "scale": "linear",
    "max_frequency": "",
    "window_type": "hann",
}
DEFAULT_CALCULUS_SETTINGS = {"channel": "X"}
DEFAULT_CURRENT_SETTINGS = {
    "channel": "X",
    "method": "resistor",
    "component_value": "1",
    "inductor_initial_mode": "zero",
    "inductor_initial_value": "0",
}
DEFAULT_TOTAL_CURRENT_SETTINGS = {
    "voltage_channel": "X",
    "combination_mode": "parallel",
    "frequency_tolerance_percent": "5",
}
DEFAULT_TRANSFER_SETTINGS = {
    "input_channel": "X",
    "output_channel": "Y",
}
DEFAULT_XY_SETTINGS = {
    "x_channel": "X",
    "y_channel": "Y",
}
DEFAULT_CALIBRATION_SETTINGS = {
    "x_gain": 1.0,
    "y_gain": 1.0,
    "x_offset": 0.0,
    "y_offset": 0.0,
    "invert_x": False,
    "invert_y": False,
    "normalize": False,
}
DEFAULT_CURSOR_SETTINGS = {"channel": "X", "t1": "", "t2": ""}
DEFAULT_CYCLE_SETTINGS = {"channel": "X"}
T_CLEAR = np.arange(-375, 376)
CH_CLEAR = np.zeros(751)
ALLOWED_EXTENSIONS = {".wav"}
ANALYSIS_CACHE = {}
GRAPH_CACHE = {}
CURRENT_WAVEFORM_STORE = {}
CACHE_LOCK = Lock()
STATE_LOCK = Lock()
APP_STATE_STORE = {}
MAX_CACHE_ITEMS = 32
AJAX_MODULE_ACTIONS = {
    "math",
    "fft",
    "statistics",
    "advanced",
    "calculus",
    "current",
    "transfer",
    "xy",
    "correlation",
    "calibration",
    "cursor",
    "cycle",
    "snapshot",
    "comparison",
}


def load_or_create_secret_key():
    if os.path.exists(SECRET_KEY_PATH):
        try:
            with open(SECRET_KEY_PATH, "r", encoding="utf-8") as secret_file:
                secret_key = secret_file.read().strip()
            if secret_key:
                return secret_key
        except OSError:
            pass

    secret_key = os.getenv("FLASK_SECRET_KEY", uuid.uuid4().hex)
    try:
        with open(SECRET_KEY_PATH, "w", encoding="utf-8") as secret_file:
            secret_file.write(secret_key)
    except OSError:
        pass
    return secret_key


def get_client_id():
    client_id = session.get("client_id")
    if not client_id:
        client_id = uuid.uuid4().hex
        session["client_id"] = client_id
    return client_id


def _ensure_state_bucket():
    client_id = get_client_id()
    with STATE_LOCK:
        return APP_STATE_STORE.setdefault(client_id, {})


def state_get(key, default=None):
    client_id = get_client_id()
    with STATE_LOCK:
        bucket = APP_STATE_STORE.setdefault(client_id, {})
        return bucket.get(key, default)


def state_set(key, value):
    bucket = _ensure_state_bucket()
    with STATE_LOCK:
        bucket[key] = value
    return value


def state_pop(key, default=None):
    bucket = _ensure_state_bucket()
    with STATE_LOCK:
        return bucket.pop(key, default)


def state_update(values):
    bucket = _ensure_state_bucket()
    with STATE_LOCK:
        bucket.update(values)


def clear_client_state():
    client_id = get_client_id()
    with STATE_LOCK:
        APP_STATE_STORE.pop(client_id, None)


def freeze_value(value):
    if isinstance(value, dict):
        return tuple(sorted((key, freeze_value(inner)) for key, inner in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(freeze_value(item) for item in value)
    if isinstance(value, np.ndarray):
        return ("ndarray", tuple(value.tolist()))
    return value


def cache_get(cache, key):
    with CACHE_LOCK:
        return cache.get(key)


def cache_set(cache, key, value):
    with CACHE_LOCK:
        cache[key] = value
        while len(cache) > MAX_CACHE_ITEMS:
            oldest_key = next(iter(cache))
            cache.pop(oldest_key, None)
    return value


def invalidate_file_cache(file_path):
    if not file_path:
        return
    with CACHE_LOCK:
        analysis_keys = [key for key in ANALYSIS_CACHE if file_path in key]
        for key in analysis_keys:
            ANALYSIS_CACHE.pop(key, None)
        graph_keys = [key for key in GRAPH_CACHE if file_path in key]
        for key in graph_keys:
            GRAPH_CACHE.pop(key, None)


def cleanup_file():
    file_path = state_get("file_wav")
    invalidate_file_cache(file_path)
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass


def cleanup_upload_folder():
    if not os.path.isdir(UPLOAD_FOLDER):
        return

    for entry in os.scandir(UPLOAD_FOLDER):
        if not entry.is_file():
            continue
        invalidate_file_cache(entry.path)
        try:
            os.remove(entry.path)
        except OSError:
            pass


atexit.register(cleanup_upload_folder)


def clear_current_waveforms():
    client_prefix = f"{get_client_id()}:"
    with CACHE_LOCK:
        stale_ids = [key for key in CURRENT_WAVEFORM_STORE if str(key).startswith(client_prefix)]
        for key in stale_ids:
            CURRENT_WAVEFORM_STORE.pop(key, None)


def clear_loaded_state():
    cleanup_file()
    clear_current_waveforms()
    keys = (
        "file_wav",
        "original_name",
        "config",
        "measures",
        "math_operation",
        "math_measures",
        "fft_settings",
        "fft_enabled",
        "statistics_enabled",
        "statistics_data",
        "advanced_enabled",
        "advanced_data",
        "calculus_enabled",
        "calculus_settings",
        "calculus_data",
        "current_enabled",
        "current_settings",
        "current_data",
        "transfer_enabled",
        "transfer_settings",
        "transfer_data",
        "correlation_enabled",
        "correlation_data",
        "calibration_settings",
        "calibration_enabled",
        "cursor_settings",
        "cursor_enabled",
        "cursor_data",
        "cycle_settings",
        "cycle_enabled",
        "cycle_data",
        "comparison_enabled",
        "comparison_snapshot_id",
        "comparison_data",
        "fft_data",
    )
    for key in keys:
        state_pop(key, None)
    for key in ("current_snapshots", "total_current_enabled", "total_current_settings", "total_current_data"):
        state_pop(key, None)


def get_unique_filename():
    return f"{uuid.uuid4().hex}.wav"


def is_allowed_file(filename):
    _, extension = os.path.splitext(filename or "")
    return extension.lower() in ALLOWED_EXTENSIONS
