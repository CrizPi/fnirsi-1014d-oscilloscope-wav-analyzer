import atexit
import os
import re
import socket
import sys
import time
import uuid
from datetime import datetime
from threading import Lock, Thread

import numpy as np
from flask import Flask, Response, after_this_request, jsonify, render_template, request, send_file, session
from werkzeug.utils import secure_filename
import webview

from file_analizer import ScopeFileError, get_scope_config, get_scope_measures, get_scope_raw_data_display
from plot_maker import (
    generate_correlation_grafic,
    generate_cursor_grafic_file,
    generate_fft_grafic,
    generate_grafic,
    generate_signal_analysis_grafic,
    generate_voltage_current_grafic,
)
from report import (
    generate_advanced_measures_latex,
    generate_calibration_latex,
    generate_comparison_latex,
    generate_correlation_grafic_download,
    generate_correlation_latex,
    generate_current_grafic_download,
    generate_current_latex,
    generate_total_current_latex,
    generate_cursor_latex,
    generate_cycle_latex,
    generate_fft_grafic_download,
    generate_fft_latex,
    generate_grafic_download,
    generate_grafic_download_math,
    generate_math_measures_latex,
    generate_measures_latex,
    generate_signal_analysis_download,
    generate_statistics_latex,
)
from signal_analyzer import (
    adaptive_scope_filter,
    apply_math_operation,
    apply_signal_calibration,
    build_cycle_template,
    calculate_advanced_measures,
    calculate_correlation_analysis,
    calculate_current_analysis,
    calculate_cycle_analysis,
    calculate_derivative_integral,
    calculate_manual_measurement,
    calculate_math_measures,
    calculate_signal_statistics,
    calculate_voltage_current_phase_angle,
    convert_scope_data,
    crop_scope_window,
    estimate_frequency_hz,
    estimate_template_phase_shift,
    get_fft_spectrum,
    get_scope_fs_and_time,
    project_cycle_template,
    shift_cycle_template,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_NAME = "FNIRSI 1014D Analyzer"
APP_DATA_DIR = os.path.join(os.getenv("LOCALAPPDATA", BASE_DIR), "FNIRSI1014DAnalyzer")
UPLOAD_FOLDER = os.path.join(APP_DATA_DIR, "uploads")
os.makedirs(APP_DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)
app.secret_key = os.getenv("FLASK_SECRET_KEY", uuid.uuid4().hex)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

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
MAX_CACHE_ITEMS = 32
MAIN_WINDOW = None
AJAX_MODULE_ACTIONS = {
    "math",
    "fft",
    "statistics",
    "advanced",
    "calculus",
    "current",
    "correlation",
    "calibration",
    "cursor",
    "cycle",
    "snapshot",
    "comparison",
}


class DesktopApi:
    def save_download(self, filename, content_base64):
        if MAIN_WINDOW is None:
            return {"ok": False, "message": "Desktop window is not available."}

        try:
            save_dialog = getattr(getattr(webview, "FileDialog", None), "SAVE", None)
            if save_dialog is None:
                save_dialog = webview.SAVE_DIALOG
            file_path = MAIN_WINDOW.create_file_dialog(
                save_dialog,
                save_filename=filename or "download.bin",
            )
            if not file_path:
                return {"ok": False, "message": "Download canceled."}

            selected_path = file_path[0] if isinstance(file_path, (list, tuple)) else file_path
            import base64
            data = base64.b64decode(content_base64.encode("utf-8"))
            with open(selected_path, "wb") as output_file:
                output_file.write(data)
            return {"ok": True, "message": f"Saved to {selected_path}"}
        except Exception as exc:
            return {"ok": False, "message": f"Download failed: {exc}"}


def _freeze_value(value):
    if isinstance(value, dict):
        return tuple(sorted((key, _freeze_value(inner)) for key, inner in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, np.ndarray):
        return ("ndarray", tuple(value.tolist()))
    return value


def _cache_get(cache, key):
    with CACHE_LOCK:
        return cache.get(key)


def _cache_set(cache, key, value):
    with CACHE_LOCK:
        cache[key] = value
        while len(cache) > MAX_CACHE_ITEMS:
            oldest_key = next(iter(cache))
            cache.pop(oldest_key, None)
    return value


def _invalidate_file_cache(file_path):
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
    file_path = session.get("file_wav")
    _invalidate_file_cache(file_path)
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
        _invalidate_file_cache(entry.path)
        try:
            os.remove(entry.path)
        except OSError:
            pass


atexit.register(cleanup_upload_folder)


def clear_current_waveforms():
    with CACHE_LOCK:
        CURRENT_WAVEFORM_STORE.clear()


def clear_loaded_state(preserve_current_library=False):
    cleanup_file()
    if not preserve_current_library:
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
        session.pop(key, None)
    if not preserve_current_library:
        for key in ("current_snapshots", "total_current_enabled", "total_current_settings", "total_current_data"):
            session.pop(key, None)


def get_unique_filename():
    return f"{uuid.uuid4().hex}.wav"


def is_allowed_file(filename):
    _, extension = os.path.splitext(filename or "")
    return extension.lower() in ALLOWED_EXTENSIONS


def parse_uploaded_scope_file(file_path):
    return get_scope_config(file_path), get_scope_measures(file_path)


def load_signal_data(file_path, config, measures):
    cache_key = ("signal_data", file_path, _freeze_value(config), _freeze_value(measures))
    cached = _cache_get(ANALYSIS_CACHE, cache_key)
    if cached is not None:
        return cached

    ch1, ch2 = get_scope_raw_data_display(file_path, measures)
    ch1_v, ch2_v = convert_scope_data(ch1, ch2, config, measures)
    ch1_v, ch2_v, trigger_index = crop_scope_window(ch1_v, ch2_v, config)
    fs, time_axis = get_scope_fs_and_time(ch1_v, config, ch2_v, trigger_index=trigger_index)
    return _cache_set(ANALYSIS_CACHE, cache_key, (ch1_v, ch2_v, fs, time_axis))


def apply_visual_filter(ch1, ch2, fs, math_result=None):
    filtered_x = adaptive_scope_filter(ch1, fs)
    filtered_y = adaptive_scope_filter(ch2, fs)
    filtered_math = adaptive_scope_filter(math_result, fs) if math_result is not None else None
    return filtered_x, filtered_y, filtered_math


def get_processed_signals(file_path, config, measures):
    calibration_settings = get_calibration_settings()
    math_operation = session.get("math_operation")
    cache_key = (
        "processed_signals",
        file_path,
        _freeze_value(config),
        _freeze_value(measures),
        _freeze_value(calibration_settings),
        math_operation,
    )
    cached = _cache_get(ANALYSIS_CACHE, cache_key)
    if cached is not None:
        return cached

    ch1, ch2, fs, time_axis = load_signal_data(file_path, config, measures)
    ch1, ch2 = apply_signal_calibration(ch1, ch2, calibration_settings)
    math_result, math_measures = process_math(ch1, ch2, fs)
    ch1, ch2, math_result = apply_visual_filter(ch1, ch2, fs, math_result)

    result = {
        "ch1": ch1,
        "ch2": ch2,
        "fs": fs,
        "time_axis": time_axis,
        "math_result": math_result,
        "math_measures": math_measures,
    }
    return _cache_set(ANALYSIS_CACHE, cache_key, result)


def get_main_graph(time_axis, ch1, ch2, file_name, measures, file_path):
    cache_key = ("main_graph", file_path, _freeze_value(measures), _freeze_value(get_calibration_settings()))
    cached = _cache_get(GRAPH_CACHE, cache_key)
    if cached is not None:
        return cached
    graph = generate_grafic(time_axis, ch1, ch2, "Oscilloscope Signals", measures, scope_config=session.get("config", DEFAULT_CONFIG))
    return _cache_set(GRAPH_CACHE, cache_key, graph)


def get_math_graph(time_axis, math_result, file_path, math_operation):
    cache_key = ("math_graph", file_path, math_operation, _freeze_value(get_calibration_settings()))
    cached = _cache_get(GRAPH_CACHE, cache_key)
    if cached is not None:
        return cached
    graph = generate_grafic(time_axis, [], [], "MATH", math_result=math_result, show_empty=True)
    return _cache_set(GRAPH_CACHE, cache_key, graph)


def get_fft_graph_key(raw_max_frequency):
    settings = get_fft_settings()
    return (
        "fft_graph",
        session.get("file_wav"),
        settings["channel"],
        settings["scale"],
        raw_max_frequency,
        settings["window_type"],
        _freeze_value(get_calibration_settings()),
        session.get("math_operation"),
    )


def get_derivative_graph_key(selected_channel):
    return (
        "derivative_graph",
        session.get("file_wav"),
        selected_channel,
        _freeze_value(get_calibration_settings()),
        session.get("math_operation"),
    )


def get_integral_graph_key(selected_channel):
    return (
        "integral_graph",
        session.get("file_wav"),
        selected_channel,
        _freeze_value(get_calibration_settings()),
        session.get("math_operation"),
    )


def get_correlation_graph_key():
    return ("correlation_graph", session.get("file_wav"), _freeze_value(get_calibration_settings()))


def get_current_graph_key(selected_channel, method, component_value):
    current_settings = get_current_settings()
    return (
        "current_graph",
        session.get("file_wav"),
        selected_channel,
        method,
        component_value,
        current_settings.get("inductor_initial_mode", "zero"),
        current_settings.get("inductor_initial_value", "0"),
        _freeze_value(get_calibration_settings()),
        session.get("math_operation"),
    )


def process_math(ch1, ch2, fs):
    math_operation = session.get("math_operation")
    if not math_operation:
        return None, DEFAULT_MATH_MEASURES.copy()

    math_result = apply_math_operation(ch1, ch2, math_operation)
    math_measures = calculate_math_measures(math_result, fs)
    session["math_measures"] = math_measures
    return math_result, math_measures


def get_fft_settings():
    settings = session.get("fft_settings", DEFAULT_FFT_SETTINGS.copy())
    return {
        "channel": settings.get("channel", "X"),
        "scale": settings.get("scale", "linear"),
        "max_frequency": settings.get("max_frequency", ""),
        "window_type": settings.get("window_type", "hann"),
    }


def get_calculus_settings():
    settings = session.get("calculus_settings", DEFAULT_CALCULUS_SETTINGS.copy())
    return {"channel": settings.get("channel", "X")}


def get_current_settings():
    settings = session.get("current_settings", DEFAULT_CURRENT_SETTINGS.copy())
    return {
        "channel": settings.get("channel", "X"),
        "method": settings.get("method", "resistor"),
        "component_value": str(settings.get("component_value", "1")),
        "inductor_initial_mode": settings.get("inductor_initial_mode", "zero"),
        "inductor_initial_value": str(settings.get("inductor_initial_value", "0")),
    }


def get_total_current_settings():
    settings = session.get("total_current_settings", DEFAULT_TOTAL_CURRENT_SETTINGS.copy())
    return {
        "voltage_channel": settings.get("voltage_channel", "X"),
        "combination_mode": settings.get("combination_mode", "parallel"),
        "frequency_tolerance_percent": str(settings.get("frequency_tolerance_percent", "5")),
    }


def get_calibration_settings():
    settings = session.get("calibration_settings", DEFAULT_CALIBRATION_SETTINGS.copy())
    return {
        "x_gain": float(settings.get("x_gain", 1.0)),
        "y_gain": float(settings.get("y_gain", 1.0)),
        "x_offset": float(settings.get("x_offset", 0.0)),
        "y_offset": float(settings.get("y_offset", 0.0)),
        "invert_x": bool(settings.get("invert_x", False)),
        "invert_y": bool(settings.get("invert_y", False)),
        "normalize": bool(settings.get("normalize", False)),
    }


def get_cursor_settings():
    settings = session.get("cursor_settings", DEFAULT_CURSOR_SETTINGS.copy())
    return {
        "channel": settings.get("channel", "X"),
        "t1": settings.get("t1", ""),
        "t2": settings.get("t2", ""),
    }


def get_cycle_settings():
    settings = session.get("cycle_settings", DEFAULT_CYCLE_SETTINGS.copy())
    return {"channel": settings.get("channel", "X")}


def parse_float_field(raw_value, field_name, default=None):
    raw_value = str(raw_value or "").strip()
    if raw_value == "":
        if default is None:
            raise ValueError(f"El campo {field_name} es obligatorio.")
        return default, ""
    try:
        return float(raw_value), raw_value
    except ValueError as exc:
        raise ValueError(f"El campo {field_name} debe ser numerico.") from exc


def parse_fft_max_frequency(raw_value):
    raw_value = (raw_value or "").strip()
    if not raw_value:
        return None, ""
    value, normalized = parse_float_field(raw_value, "frecuencia maxima de FFT")
    if value <= 0:
        raise ValueError("La frecuencia maxima de FFT debe ser mayor que cero.")
    return value, normalized


def parse_positive_component_value(raw_value, field_name):
    value, normalized = parse_float_field(raw_value, field_name)
    if value <= 0:
        raise ValueError(f"El campo {field_name} debe ser mayor que cero.")
    return value, normalized


def parse_nonnegative_float_field(raw_value, field_name, default=0.0):
    value, normalized = parse_float_field(raw_value, field_name, default=default)
    if value < 0:
        raise ValueError(f"El campo {field_name} no puede ser negativo.")
    return value, normalized


def measure_freq_to_hz(value, unit):
    unit = (unit or "Hz").lower()
    multiplier = {"hz": 1, "khz": 1e3, "mhz": 1e6}.get(unit, 1)
    return float(value) * multiplier


def build_statistics_view(ch1, ch2, math_result):
    empty_stats = calculate_signal_statistics(np.array([]))
    if not session.get("statistics_enabled"):
        return {"X": empty_stats, "Y": empty_stats, "MATH": empty_stats, "math_enabled": False, "enabled": False}
    cache_key = (
        "statistics",
        session.get("file_wav"),
        _freeze_value(get_calibration_settings()),
        session.get("math_operation"),
    )
    cached = _cache_get(ANALYSIS_CACHE, cache_key)
    if cached is not None:
        return cached
    data = {
        "X": calculate_signal_statistics(ch1),
        "Y": calculate_signal_statistics(ch2),
        "MATH": calculate_signal_statistics(math_result if math_result is not None else np.array([])),
        "math_enabled": math_result is not None and np.asarray(math_result).size > 0,
        "enabled": True,
    }
    return _cache_set(ANALYSIS_CACHE, cache_key, data)


def build_advanced_view(ch1, ch2, math_result, fs):
    zero = calculate_advanced_measures(np.array([]), 0)
    if not session.get("advanced_enabled"):
        return {"X": zero, "Y": zero, "MATH": zero, "math_enabled": False, "enabled": False}
    cache_key = (
        "advanced",
        session.get("file_wav"),
        _freeze_value(get_calibration_settings()),
        session.get("math_operation"),
    )
    cached = _cache_get(ANALYSIS_CACHE, cache_key)
    if cached is not None:
        return cached
    data = {
        "X": calculate_advanced_measures(ch1, fs),
        "Y": calculate_advanced_measures(ch2, fs),
        "MATH": calculate_advanced_measures(math_result if math_result is not None else np.array([]), fs),
        "math_enabled": math_result is not None and np.asarray(math_result).size > 0,
        "enabled": True,
    }
    return _cache_set(ANALYSIS_CACHE, cache_key, data)


def build_fft_view(ch1, ch2, math_result, fs, file_name):
    settings = get_fft_settings()
    if not session.get("fft_enabled"):
        return generate_fft_grafic([], [], "", settings["channel"]), {
            "channel": settings["channel"],
            "scale": settings["scale"],
            "max_frequency": settings["max_frequency"],
            "window_type": settings["window_type"],
            "dominant_frequency": 0,
            "dominant_frequency_unit": "Hz",
            "dominant_magnitude": 0,
            "top_peaks": [],
            "harmonics": [],
            "thd_percent": 0,
            "enabled": False,
        }

    max_frequency_hz, raw_max_frequency = parse_fft_max_frequency(settings["max_frequency"])
    signals = {"X": ch1, "Y": ch2, "MATH": math_result if math_result is not None else np.array([])}
    selected_signal = signals.get(settings["channel"], ch1)
    cache_key = (
        "fft",
        session.get("file_wav"),
        settings["channel"],
        settings["scale"],
        raw_max_frequency,
        settings["window_type"],
        _freeze_value(get_calibration_settings()),
        session.get("math_operation"),
    )
    cached = _cache_get(ANALYSIS_CACHE, cache_key)
    if cached is not None:
        return cached

    fft_data = get_fft_spectrum(selected_signal, fs, max_frequency=max_frequency_hz, window_type=settings["window_type"])
    graph_key = get_fft_graph_key(raw_max_frequency)
    fft_graph = _cache_get(GRAPH_CACHE, graph_key)
    if fft_graph is None:
        fft_graph = generate_fft_grafic(
            fft_data["frequencies_hz"],
            fft_data["magnitudes"],
            file_name,
            settings["channel"],
            scale_mode=settings["scale"],
            dominant_frequency_hz=fft_data["dominant_frequency_hz"],
        )
        _cache_set(GRAPH_CACHE, graph_key, fft_graph)
    fft_data.update(
        {
            "channel": settings["channel"],
            "scale": settings["scale"],
            "max_frequency": raw_max_frequency,
            "window_type": settings["window_type"],
            "enabled": True,
        }
    )
    result = (fft_graph, fft_data)
    return _cache_set(ANALYSIS_CACHE, cache_key, result)


def build_calculus_view(ch1, ch2, math_result, fs, time_axis, file_name):
    settings = get_calculus_settings()
    selected_channel = settings["channel"]
    signals = {"X": ch1, "Y": ch2, "MATH": math_result if math_result is not None else np.array([])}
    selected_signal = signals.get(selected_channel, ch1)

    if not session.get("calculus_enabled"):
        return {
            "channel": selected_channel,
            "enabled": False,
            "derivative_peak": 0.0,
            "integral_final": 0.0,
            "derivative": np.array([]),
            "integral": np.array([]),
            "derivative_graph": generate_signal_analysis_grafic([], [], f"Derivative {selected_channel}", "dV/dt (V/s)"),
            "integral_graph": generate_signal_analysis_grafic([], [], f"Integral {selected_channel}", "Integral (V*s)"),
        }

    cache_key = (
        "calculus",
        session.get("file_wav"),
        selected_channel,
        _freeze_value(get_calibration_settings()),
        session.get("math_operation"),
    )
    cached = _cache_get(ANALYSIS_CACHE, cache_key)
    if cached is not None:
        return cached

    calculus_data = calculate_derivative_integral(selected_signal, fs)
    calculus_data["channel"] = selected_channel
    calculus_data["enabled"] = True
    derivative_graph_key = get_derivative_graph_key(selected_channel)
    integral_graph_key = get_integral_graph_key(selected_channel)
    calculus_data["derivative_graph"] = _cache_get(GRAPH_CACHE, derivative_graph_key)
    if calculus_data["derivative_graph"] is None:
        calculus_data["derivative_graph"] = generate_signal_analysis_grafic(
            time_axis,
            calculus_data["derivative"],
            f"Derivative {selected_channel}",
            "dV/dt (V/s)",
        )
        _cache_set(GRAPH_CACHE, derivative_graph_key, calculus_data["derivative_graph"])
    calculus_data["integral_graph"] = _cache_get(GRAPH_CACHE, integral_graph_key)
    if calculus_data["integral_graph"] is None:
        calculus_data["integral_graph"] = generate_signal_analysis_grafic(
            time_axis,
            calculus_data["integral"],
            f"Integral {selected_channel}",
            "Integral (V*s)",
        )
        _cache_set(GRAPH_CACHE, integral_graph_key, calculus_data["integral_graph"])
    return _cache_set(ANALYSIS_CACHE, cache_key, calculus_data)


def build_current_view(ch1, ch2, math_result, fs, time_axis, file_name):
    settings = get_current_settings()
    empty = {
        "channel": settings["channel"],
        "method": settings["method"],
        "component_value_input": settings["component_value"],
        "component_value": 0.0,
        "current_mean": 0.0,
        "current_rms": 0.0,
        "current_max": 0.0,
        "current_min": 0.0,
        "current_peak_to_peak": 0.0,
        "phase_angle_deg": 0.0,
        "detected_frequency_hz": 0.0,
        "inductor_initial_mode": settings["inductor_initial_mode"],
        "inductor_initial_value": 0.0,
        "inductor_initial_value_input": settings["inductor_initial_value"],
        "warnings": [],
        "current": np.array([]),
        "graph": generate_voltage_current_grafic([], [], [], "Current Analysis"),
        "enabled": False,
    }
    if not session.get("current_enabled"):
        return empty

    try:
        component_value = float(settings["component_value"])
    except (TypeError, ValueError):
        return empty

    signals = {
        "X": ch1,
        "Y": ch2,
        "MATH": math_result if math_result is not None else np.array([]),
    }
    selected_signal = signals.get(settings["channel"], ch1)

    cache_key = (
        "current",
        session.get("file_wav"),
        settings["channel"],
        settings["method"],
        component_value,
        settings.get("inductor_initial_mode", "zero"),
        settings.get("inductor_initial_value", "0"),
        _freeze_value(get_calibration_settings()),
        session.get("math_operation"),
    )
    cached = _cache_get(ANALYSIS_CACHE, cache_key)
    if cached is not None:
        return cached

    try:
        initial_current_value, _ = parse_float_field(
            settings.get("inductor_initial_value", "0"),
            "condicion inicial del inductor",
            default=0.0,
        )
    except ValueError:
        initial_current_value = 0.0
    current_data = calculate_current_analysis(
        selected_signal,
        fs,
        settings["method"],
        component_value,
        initial_condition_mode=settings.get("inductor_initial_mode", "zero"),
        initial_current_value=initial_current_value,
    )
    current_data["channel"] = settings["channel"]
    current_data["component_value_input"] = settings["component_value"]
    current_data["inductor_initial_mode"] = settings.get("inductor_initial_mode", "zero")
    current_data["inductor_initial_value_input"] = settings.get("inductor_initial_value", "0")
    current_data["source_frequency_hz"] = round(float(estimate_frequency_hz(selected_signal, fs)), 6) if fs > 0 else 0.0
    current_data["source_voltage"] = np.asarray(selected_signal, dtype=float)
    current_data["source_time_axis"] = np.asarray(time_axis, dtype=float)
    phase_data = calculate_voltage_current_phase_angle(selected_signal, current_data.get("current", []), fs)
    current_data["phase_angle_deg"] = phase_data.get("phase_angle_deg", 0.0)
    if not phase_data.get("enabled"):
        warnings = list(current_data.get("warnings", []))
        warning_message = "No se pudo estimar el desfase entre voltaje y corriente con suficiente confianza."
        if warning_message not in warnings:
            warnings.append(warning_message)
        current_data["warnings"] = warnings
    graph_key = get_current_graph_key(settings["channel"], settings["method"], component_value)
    current_data["graph"] = _cache_get(GRAPH_CACHE, graph_key)
    if current_data["graph"] is None:
        current_data["graph"] = generate_voltage_current_grafic(
            time_axis,
            selected_signal,
            current_data["current"],
            f"Current Analysis {settings['channel']}",
        )
        _cache_set(GRAPH_CACHE, graph_key, current_data["graph"])
    return _cache_set(ANALYSIS_CACHE, cache_key, current_data)


def save_current_snapshot(snapshot_name, current_data, time_axis, file_name):
    if not current_data.get("enabled"):
        return False

    waveform_id = uuid.uuid4().hex
    source_voltage = np.asarray(current_data.get("source_voltage", []), dtype=float)
    source_time_axis = np.asarray(current_data.get("source_time_axis", time_axis), dtype=float)
    source_fs = 1.0 / np.mean(np.diff(source_time_axis)) if source_time_axis.size > 1 else 0.0
    template, frequency_hz = build_cycle_template(
        np.asarray(current_data.get("current", []), dtype=float),
        np.asarray(time_axis, dtype=float),
        1.0 / np.mean(np.diff(time_axis)) if np.asarray(time_axis).size > 1 else 0.0,
    )
    voltage_template, voltage_frequency_hz = build_cycle_template(
        source_voltage,
        source_time_axis,
        source_fs,
    )
    relative_phase_shift_cycles = (
        estimate_template_phase_shift(voltage_template, template) if voltage_template.size > 0 and template.size > 0 else 0.0
    )
    with CACHE_LOCK:
        CURRENT_WAVEFORM_STORE[waveform_id] = {
            "time_axis": np.asarray(time_axis, dtype=float),
            "current": np.asarray(current_data.get("current", []), dtype=float),
            "template": template,
            "frequency_hz": frequency_hz,
            "voltage_template": voltage_template,
            "voltage_frequency_hz": voltage_frequency_hz,
            "relative_phase_shift_cycles": relative_phase_shift_cycles,
            "phase_angle_deg": float(current_data.get("phase_angle_deg", 0.0)),
        }

    snapshots = session.get("current_snapshots", [])
    snapshots.append(
        {
            "id": waveform_id,
            "name": snapshot_name,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "file_name": file_name,
            "channel": current_data.get("channel", "X"),
            "method": current_data.get("method", "resistor"),
            "component_value": current_data.get("component_value", 0.0),
            "current_rms": current_data.get("current_rms", 0.0),
            "current_peak_to_peak": current_data.get("current_peak_to_peak", 0.0),
            "frequency_hz": round(float(frequency_hz), 6),
            "phase_angle_deg": round(float(current_data.get("phase_angle_deg", 0.0)), 4),
        }
    )
    trimmed = snapshots[-20:]
    session["current_snapshots"] = trimmed
    valid_ids = {item["id"] for item in trimmed}
    with CACHE_LOCK:
        stale_ids = [key for key in CURRENT_WAVEFORM_STORE if key not in valid_ids]
        for key in stale_ids:
            CURRENT_WAVEFORM_STORE.pop(key, None)
    return True


def _resample_current_to_reference(reference_time_axis, reference_frequency_hz, reference_voltage_template, sample):
    reference_time_axis = np.asarray(reference_time_axis, dtype=float)
    template = np.asarray(sample.get("template", []), dtype=float)
    if reference_time_axis.size == 0:
        return np.zeros_like(reference_time_axis)
    if template.size > 0 and reference_frequency_hz > 0:
        aligned_template = template
        sample_voltage_template = np.asarray(sample.get("voltage_template", []), dtype=float)
        if reference_voltage_template.size > 0 and sample_voltage_template.size > 0:
            shift_fraction = estimate_template_phase_shift(reference_voltage_template, sample_voltage_template)
            aligned_template = shift_cycle_template(aligned_template, shift_fraction)
        return project_cycle_template(aligned_template, reference_time_axis, reference_frequency_hz)

    sample_time = np.asarray(sample.get("time_axis", []), dtype=float)
    sample_current = np.asarray(sample.get("current", []), dtype=float)
    if sample_time.size == 0 or sample_current.size == 0:
        return np.zeros_like(reference_time_axis)
    length = min(sample_time.size, sample_current.size)
    sample_time = sample_time[:length]
    sample_current = sample_current[:length]
    reference_relative = reference_time_axis - float(reference_time_axis[0])
    sample_relative = sample_time - float(sample_time[0])
    return np.interp(reference_relative, sample_relative, sample_current, left=0.0, right=0.0)


def build_total_current_view(ch1, ch2, math_result, fs, time_axis, file_name):
    settings = get_total_current_settings()
    empty = {
        "enabled": False,
        "voltage_channel": settings["voltage_channel"],
        "combination_mode": settings["combination_mode"],
        "frequency_tolerance_percent": settings["frequency_tolerance_percent"],
        "saved_count": len(session.get("current_snapshots", [])),
        "compatible_count": 0,
        "incompatible_count": 0,
        "total_current_mean": 0.0,
        "total_current_rms": 0.0,
        "total_current_max": 0.0,
        "total_current_min": 0.0,
        "total_current_peak_to_peak": 0.0,
        "phase_angle_deg": 0.0,
        "series_mismatch_rms": 0.0,
        "warnings": [],
        "graph": generate_voltage_current_grafic([], [], [], "Total Current Analysis"),
    }
    if not session.get("total_current_enabled"):
        return empty

    saved_metadata = session.get("current_snapshots", [])
    if not saved_metadata:
        return empty

    signals = {
        "X": ch1,
        "Y": ch2,
        "MATH": math_result if math_result is not None else np.array([]),
    }
    voltage = np.asarray(signals.get(settings["voltage_channel"], ch1), dtype=float)
    reference_time_axis = np.asarray(time_axis, dtype=float)
    if voltage.size == 0 or reference_time_axis.size == 0:
        return empty
    reference_frequency_hz = estimate_frequency_hz(voltage, fs)
    reference_voltage_template, _ = build_cycle_template(voltage, reference_time_axis, fs)
    try:
        tolerance_percent, _ = parse_nonnegative_float_field(
            settings.get("frequency_tolerance_percent", "5"),
            "tolerancia de frecuencia",
            default=5.0,
        )
    except ValueError:
        tolerance_percent = 5.0

    warnings = []
    aligned_currents = []
    incompatible_count = 0
    for item in saved_metadata:
        sample = _cache_get(CURRENT_WAVEFORM_STORE, item["id"])
        if sample is None:
            continue
        sample_frequency_hz = float(sample.get("frequency_hz", 0.0) or 0.0)
        if reference_frequency_hz > 0 and sample_frequency_hz > 0:
            frequency_error_percent = abs(sample_frequency_hz - reference_frequency_hz) / reference_frequency_hz * 100.0
            if frequency_error_percent > tolerance_percent:
                incompatible_count += 1
                warnings.append(
                    f"Se omitio '{item.get('name', 'snapshot')}' por incompatibilidad de frecuencia ({sample_frequency_hz:.4f} Hz vs {reference_frequency_hz:.4f} Hz)."
                )
                continue
        aligned_currents.append(
            _resample_current_to_reference(reference_time_axis, reference_frequency_hz, reference_voltage_template, sample)
        )

    used_count = len(aligned_currents)

    if used_count == 0:
        empty["incompatible_count"] = incompatible_count
        empty["warnings"] = warnings or ["No hay corrientes compatibles para combinar con la referencia actual."]
        return empty

    stacked_currents = np.vstack(aligned_currents)
    combination_mode = settings.get("combination_mode", "parallel")
    if combination_mode == "series":
        total_current = np.mean(stacked_currents, axis=0)
        mismatch = np.sqrt(np.mean((stacked_currents - total_current) ** 2, axis=1))
        series_mismatch_rms = round(float(np.max(mismatch)), 6) if mismatch.size else 0.0
        if series_mismatch_rms > max(float(np.sqrt(np.mean(total_current ** 2))) * 0.1, 1e-9):
            warnings.append("Las corrientes en modo serie no coinciden bien entre si; revise polaridad, fase y compatibilidad fisica.")
    else:
        total_current = np.sum(stacked_currents, axis=0)
        series_mismatch_rms = 0.0

    finite_current = total_current[np.isfinite(total_current)]
    if finite_current.size == 0:
        return empty

    phase_data = calculate_voltage_current_phase_angle(voltage, total_current, fs)
    graph_key = (
        "total_current_graph",
        session.get("file_wav"),
        settings["voltage_channel"],
        settings["combination_mode"],
        settings["frequency_tolerance_percent"],
        tuple(item["id"] for item in saved_metadata),
        _freeze_value(get_calibration_settings()),
        session.get("math_operation"),
    )
    graph = _cache_get(GRAPH_CACHE, graph_key)
    if graph is None:
        graph = generate_voltage_current_grafic(
            reference_time_axis,
            voltage,
            total_current,
            f"Total Current Analysis {settings['voltage_channel']}",
        )
        _cache_set(GRAPH_CACHE, graph_key, graph)

    return {
        "enabled": True,
        "voltage_channel": settings["voltage_channel"],
        "combination_mode": combination_mode,
        "frequency_tolerance_percent": settings["frequency_tolerance_percent"],
        "saved_count": used_count,
        "compatible_count": used_count,
        "incompatible_count": incompatible_count,
        "total_current_mean": round(float(np.mean(finite_current)), 6),
        "total_current_rms": round(float(np.sqrt(np.mean(finite_current ** 2))), 6),
        "total_current_max": round(float(np.max(finite_current)), 6),
        "total_current_min": round(float(np.min(finite_current)), 6),
        "total_current_peak_to_peak": round(float(np.ptp(finite_current)), 6),
        "phase_angle_deg": phase_data.get("phase_angle_deg", 0.0),
        "series_mismatch_rms": series_mismatch_rms,
        "warnings": warnings,
        "graph": graph,
        "current": total_current,
    }


def build_correlation_view(ch1, ch2, fs, file_name):
    if not session.get("correlation_enabled"):
        return {
            "lags_seconds": np.array([]),
            "correlation": np.array([]),
            "max_correlation": 0.0,
            "delay_seconds": 0.0,
            "delay_value": 0.0,
            "delay_unit": "s",
            "enabled": False,
            "graph": generate_correlation_grafic([], [], "Correlation"),
        }

    cache_key = ("correlation", session.get("file_wav"), _freeze_value(get_calibration_settings()))
    cached = _cache_get(ANALYSIS_CACHE, cache_key)
    if cached is not None:
        return cached

    correlation_data = calculate_correlation_analysis(ch1, ch2, fs)
    correlation_data["enabled"] = True
    graph_key = get_correlation_graph_key()
    correlation_data["graph"] = _cache_get(GRAPH_CACHE, graph_key)
    if correlation_data["graph"] is None:
        correlation_data["graph"] = generate_correlation_grafic(
            correlation_data["lags_seconds"],
            correlation_data["correlation"],
            "Correlation",
            marker_x=correlation_data["delay_seconds"],
            marker_y=correlation_data["max_correlation"],
        )
        _cache_set(GRAPH_CACHE, graph_key, correlation_data["graph"])
    return _cache_set(ANALYSIS_CACHE, cache_key, correlation_data)


def build_cursor_view(ch1, ch2, math_result, time_axis):
    settings = get_cursor_settings()
    empty = {
        "channel": settings["channel"],
        "t1": 0.0,
        "t2": 0.0,
        "t1_input": settings["t1"],
        "t2_input": settings["t2"],
        "v1": 0.0,
        "v2": 0.0,
        "delta_t": 0.0,
        "delta_t_unit": "s",
        "delta_v": 0.0,
        "estimated_frequency": 0.0,
        "estimated_frequency_unit": "Hz",
        "graph": None,
        "time_min": 0.0,
        "time_max": 1.0,
        "voltage_min": -1.0,
        "voltage_max": 1.0,
        "plot_points": [],
        "enabled": False,
    }
    if not session.get("cursor_enabled"):
        return empty

    cache_key = (
        "cursor",
        session.get("file_wav"),
        settings["channel"],
        settings["t1"],
        settings["t2"],
        _freeze_value(get_calibration_settings()),
        session.get("math_operation"),
    )
    cached = _cache_get(ANALYSIS_CACHE, cache_key)
    if cached is not None:
        return cached

    signals = {"X": ch1, "Y": ch2, "MATH": math_result if math_result is not None else np.array([])}
    selected_signal = signals.get(settings["channel"], ch1)
    if len(time_axis):
        start_time = float(time_axis[0])
        end_time = float(time_axis[-1])
        if settings["t1"] == "" or settings["t2"] == "":
            span = end_time - start_time
            default_t1 = start_time + span * 0.33
            default_t2 = start_time + span * 0.66
            settings["t1"] = f"{default_t1:.9f}"
            settings["t2"] = f"{default_t2:.9f}"

    measurement = calculate_manual_measurement(
        selected_signal,
        time_axis,
        float(settings["t1"]),
        float(settings["t2"]),
    )
    measurement["channel"] = settings["channel"]
    measurement["t1_input"] = settings["t1"]
    measurement["t2_input"] = settings["t2"]
    measurement["time_min"] = float(time_axis[0]) if len(time_axis) else 0.0
    measurement["time_max"] = float(time_axis[-1]) if len(time_axis) else 1.0
    if len(selected_signal):
        measurement["voltage_min"] = float(np.min(selected_signal))
        measurement["voltage_max"] = float(np.max(selected_signal))
        if measurement["voltage_min"] == measurement["voltage_max"]:
            measurement["voltage_min"] -= 1.0
            measurement["voltage_max"] += 1.0
        point_count = min(1200, len(selected_signal))
        sample_indices = np.unique(np.linspace(0, len(selected_signal) - 1, num=point_count, dtype=int))
        measurement["plot_points"] = [
            {
                "t": round(float(time_axis[index]), 9),
                "v": round(float(selected_signal[index]), 6),
            }
            for index in sample_indices
        ]
    else:
        measurement["voltage_min"] = -1.0
        measurement["voltage_max"] = 1.0
        measurement["plot_points"] = []
    return _cache_set(ANALYSIS_CACHE, cache_key, measurement)


def build_cycle_view(ch1, ch2, math_result, fs):
    settings = get_cycle_settings()
    empty = {
        "channel": settings["channel"],
        "cycle_count": 0,
        "avg_frequency": 0.0,
        "avg_frequency_unit": "Hz",
        "avg_period": 0.0,
        "avg_period_unit": "s",
        "avg_vpp": 0.0,
        "avg_rms": 0.0,
        "enabled": False,
    }
    if not session.get("cycle_enabled"):
        return empty

    signals = {"X": ch1, "Y": ch2, "MATH": math_result if math_result is not None else np.array([])}
    cache_key = (
        "cycle",
        session.get("file_wav"),
        settings["channel"],
        _freeze_value(get_calibration_settings()),
        session.get("math_operation"),
    )
    cached = _cache_get(ANALYSIS_CACHE, cache_key)
    if cached is not None:
        return cached

    cycle_data = calculate_cycle_analysis(signals.get(settings["channel"], ch1), fs)
    cycle_data["channel"] = settings["channel"]
    return _cache_set(ANALYSIS_CACHE, cache_key, cycle_data)


def build_calibration_view():
    settings = get_calibration_settings()
    settings["enabled"] = bool(session.get("calibration_enabled"))
    return settings


def summarize_current_analysis(file_name, measures, fft_data):
    return {
        "file_name": file_name,
        "vpp_x": float(measures["Vpp"][0]),
        "vpp_y": float(measures["Vpp"][1]),
        "freq_x_hz": measure_freq_to_hz(measures["Freq"][0], measures["freq_units"][0]),
        "freq_y_hz": measure_freq_to_hz(measures["Freq"][1], measures["freq_units"][1]),
        "fft_dominant_hz": float(fft_data.get("dominant_frequency_hz", 0)),
    }


def save_snapshot(snapshot_name, file_name, measures, fft_data):
    snapshots = session.get("snapshots", [])
    snapshots.append(
        {
            "id": uuid.uuid4().hex,
            "name": snapshot_name,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            **summarize_current_analysis(file_name, measures, fft_data),
        }
    )
    session["snapshots"] = snapshots[-10:]


def build_comparison_view(file_name, measures):
    empty = {
        "enabled": False,
        "snapshot_name": "",
        "current_file": file_name,
        "saved_file": "",
        "delta_vpp_x": 0.0,
        "delta_vpp_y": 0.0,
        "delta_freq_x": 0.0,
        "delta_freq_y": 0.0,
        "delta_freq_x_unit": "Hz",
        "delta_freq_y_unit": "Hz",
    }
    if not session.get("comparison_enabled"):
        return empty

    snapshot_id = session.get("comparison_snapshot_id")
    snapshot = next((item for item in session.get("snapshots", []) if item["id"] == snapshot_id), None)
    if not snapshot:
        return empty

    return {
        "enabled": True,
        "snapshot_name": snapshot["name"],
        "current_file": file_name,
        "saved_file": snapshot["file_name"],
        "delta_vpp_x": round(float(measures["Vpp"][0]) - snapshot["vpp_x"], 6),
        "delta_vpp_y": round(float(measures["Vpp"][1]) - snapshot["vpp_y"], 6),
        "delta_freq_x": round(measure_freq_to_hz(measures["Freq"][0], measures["freq_units"][0]) - snapshot["freq_x_hz"], 6),
        "delta_freq_y": round(measure_freq_to_hz(measures["Freq"][1], measures["freq_units"][1]) - snapshot["freq_y_hz"], 6),
        "delta_freq_x_unit": "Hz",
        "delta_freq_y_unit": "Hz",
    }


def get_fft_download_data(ch1, ch2, math_result, fs):
    settings = get_fft_settings()
    max_frequency_hz, raw_max_frequency = parse_fft_max_frequency(settings["max_frequency"])
    signals = {"X": ch1, "Y": ch2, "MATH": math_result if math_result is not None else np.array([])}
    fft_data = get_fft_spectrum(
        signals.get(settings["channel"], ch1),
        fs,
        max_frequency=max_frequency_hz,
        window_type=settings["window_type"],
    )
    fft_data["channel"] = settings["channel"]
    fft_data["scale"] = settings["scale"]
    fft_data["max_frequency"] = raw_max_frequency
    fft_data["window_type"] = settings["window_type"]
    return fft_data


def build_empty_view(error_message=None, toast_message=None, toast_variant="success"):
    empty_stats = calculate_signal_statistics(np.array([]))
    empty_advanced = calculate_advanced_measures(np.array([]), 0)
    return {
        "file": None,
        "file_name": "No File",
        "config": DEFAULT_CONFIG,
        "measures": DEFAULT_MEASURES,
        "grafica": generate_grafic(T_CLEAR, CH_CLEAR, CH_CLEAR, "No File", DEFAULT_MEASURES),
        "grafica_math": generate_grafic(T_CLEAR, [], [], "MATH", math_result=None, show_empty=True),
        "math_operation": None,
        "math_measures": DEFAULT_MATH_MEASURES.copy(),
        "fft_graph": generate_fft_grafic([], [], "", "X"),
        "fft_data": {
            "channel": "X",
            "scale": "linear",
            "max_frequency": "",
            "window_type": "hann",
            "dominant_frequency": 0,
            "dominant_frequency_unit": "Hz",
            "dominant_magnitude": 0,
            "top_peaks": [],
            "harmonics": [],
            "thd_percent": 0,
            "enabled": False,
        },
        "statistics_data": {"X": empty_stats, "Y": empty_stats, "MATH": empty_stats, "math_enabled": False, "enabled": False},
        "advanced_data": {"X": empty_advanced, "Y": empty_advanced, "MATH": empty_advanced, "math_enabled": False, "enabled": False},
        "calculus_data": {
            "channel": "X",
            "enabled": False,
            "derivative_peak": 0.0,
            "integral_final": 0.0,
            "derivative_graph": generate_signal_analysis_grafic([], [], "Derivative X", "dV/dt (V/s)"),
            "integral_graph": generate_signal_analysis_grafic([], [], "Integral X", "Integral (V*s)"),
        },
        "current_data": {
            "channel": "X",
            "method": "resistor",
            "component_value_input": "1",
            "component_value": 0.0,
            "current_mean": 0.0,
            "current_rms": 0.0,
            "current_max": 0.0,
            "current_min": 0.0,
            "current_peak_to_peak": 0.0,
            "phase_angle_deg": 0.0,
            "detected_frequency_hz": 0.0,
            "inductor_initial_mode": "zero",
            "inductor_initial_value_input": "0",
            "warnings": [],
            "current": np.array([]),
            "graph": generate_voltage_current_grafic([], [], [], "Current Analysis"),
            "enabled": False,
        },
        "total_current_data": {
            "enabled": False,
            "voltage_channel": "X",
            "combination_mode": "parallel",
            "frequency_tolerance_percent": "5",
            "saved_count": 0,
            "compatible_count": 0,
            "incompatible_count": 0,
            "total_current_mean": 0.0,
            "total_current_rms": 0.0,
            "total_current_max": 0.0,
            "total_current_min": 0.0,
            "total_current_peak_to_peak": 0.0,
            "phase_angle_deg": 0.0,
            "series_mismatch_rms": 0.0,
            "warnings": [],
            "graph": generate_voltage_current_grafic([], [], [], "Total Current Analysis"),
        },
        "correlation_data": {
            "enabled": False,
            "max_correlation": 0.0,
            "delay_value": 0.0,
            "delay_unit": "s",
            "graph": generate_correlation_grafic([], [], "Correlation"),
        },
        "calibration_data": build_calibration_view(),
        "cursor_data": {
            "channel": "X",
            "t1": 0,
            "t2": 0,
            "t1_input": "",
            "t2_input": "",
            "v1": 0,
            "v2": 0,
            "delta_t": 0,
            "delta_t_unit": "s",
            "delta_v": 0,
            "estimated_frequency": 0,
            "estimated_frequency_unit": "Hz",
            "graph": None,
            "time_min": 0.0,
            "time_max": 1.0,
            "voltage_min": -1.0,
            "voltage_max": 1.0,
            "plot_points": [],
            "enabled": False,
        },
        "cycle_data": {
            "channel": "X",
            "cycle_count": 0,
            "avg_frequency": 0,
            "avg_frequency_unit": "Hz",
            "avg_period": 0,
            "avg_period_unit": "s",
            "avg_vpp": 0,
            "avg_rms": 0,
            "enabled": False,
        },
        "comparison_data": {
            "enabled": False,
            "snapshot_name": "",
            "current_file": "No File",
            "saved_file": "",
            "delta_vpp_x": 0,
            "delta_vpp_y": 0,
            "delta_freq_x": 0,
            "delta_freq_y": 0,
            "delta_freq_x_unit": "Hz",
            "delta_freq_y_unit": "Hz",
        },
        "snapshots": session.get("snapshots", []),
        "current_snapshots": session.get("current_snapshots", []),
        "error_message": error_message,
        "toast_message": toast_message,
        "toast_variant": toast_variant,
    }


def cleanup_temp_download(file_path):
    @after_this_request
    def remove_file(response):
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
        return response


def is_ajax_request():
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def extract_template_fragment(rendered_html, fragment_name):
    pattern = re.compile(
        rf"<!-- FRAGMENT:{re.escape(fragment_name)}:start -->(.*?)<!-- FRAGMENT:{re.escape(fragment_name)}:end -->",
        re.DOTALL,
    )
    match = pattern.search(rendered_html)
    return match.group(1).strip() if match else ""


def build_ajax_fragment_response(rendered_html, action_name, error_message=None):
    section_map = {
        "math": "module-math",
        "fft": "module-fft",
        "statistics": "module-stat",
        "advanced": "module-advanced",
        "calculus": "module-calculus",
        "current": "module-current",
        "correlation": "module-correlation",
        "calibration": "module-calibration",
        "cursor": "module-cursor",
        "cycle": "module-cycle",
        "snapshot": "module-snapshots",
        "comparison": "module-snapshots",
    }

    fragments = {
        "alertHost": extract_template_fragment(rendered_html, "alert-host"),
        "pageState": extract_template_fragment(rendered_html, "page-state"),
    }

    section_fragment = section_map.get(action_name)
    if section_fragment:
        fragments["moduleSection"] = extract_template_fragment(rendered_html, section_fragment)
        fragments["moduleSectionId"] = section_fragment

    if action_name == "calibration":
        fragments["measuresPanel"] = extract_template_fragment(rendered_html, "measures-panel")

    if error_message:
        fragments["error"] = error_message

    return jsonify(fragments)


def should_refresh_all(action_name):
    return action_name in {"upload", "math", "calibration"}


def prepare_analysis_context(action_name=None):
    file_path = session.get("file_wav")
    if not file_path or not os.path.exists(file_path):
        return None

    config = session.get("config", DEFAULT_CONFIG)
    measures = session.get("measures", DEFAULT_MEASURES)
    file_name = session.get("original_name", "No File")

    processed = get_processed_signals(file_path, config, measures)
    ch1 = processed["ch1"]
    ch2 = processed["ch2"]
    fs = processed["fs"]
    time_axis = processed["time_axis"]
    math_result = processed["math_result"]
    math_measures = processed["math_measures"]

    full_refresh = should_refresh_all(action_name)

    if full_refresh or action_name == "fft" or "fft_data" not in session:
        fft_graph, fft_data = build_fft_view(ch1, ch2, math_result, fs, file_name)
    else:
        fft_data = session.get("fft_data", {})
        raw_max_frequency = fft_data.get("max_frequency", "")
        fft_graph = _cache_get(GRAPH_CACHE, get_fft_graph_key(raw_max_frequency))
        if fft_graph is None:
            fft_graph, fft_data = build_fft_view(ch1, ch2, math_result, fs, file_name)

    if full_refresh or action_name == "statistics" or "statistics_data" not in session:
        statistics_data = build_statistics_view(ch1, ch2, math_result)
    else:
        statistics_data = session.get("statistics_data")

    if full_refresh or action_name == "advanced" or "advanced_data" not in session:
        advanced_data = build_advanced_view(ch1, ch2, math_result, fs)
    else:
        advanced_data = session.get("advanced_data")

    if full_refresh or action_name == "calculus" or "calculus_data" not in session:
        calculus_data = build_calculus_view(ch1, ch2, math_result, fs, time_axis, file_name)
    else:
        calculus_data = session.get("calculus_data", {})
        selected_channel = calculus_data.get("channel", get_calculus_settings()["channel"])
        derivative_graph = _cache_get(GRAPH_CACHE, get_derivative_graph_key(selected_channel))
        integral_graph = _cache_get(GRAPH_CACHE, get_integral_graph_key(selected_channel))
        if derivative_graph is None or integral_graph is None:
            calculus_data = build_calculus_view(ch1, ch2, math_result, fs, time_axis, file_name)
        else:
            calculus_data = {
                "channel": selected_channel,
                "enabled": bool(session.get("calculus_enabled")),
                "derivative_peak": calculus_data.get("derivative_peak", 0.0),
                "integral_final": calculus_data.get("integral_final", 0.0),
                "derivative_graph": derivative_graph,
                "integral_graph": integral_graph,
            }

    if full_refresh or action_name == "current" or "current_data" not in session:
        current_data = build_current_view(ch1, ch2, math_result, fs, time_axis, file_name)
    else:
        current_data = session.get("current_data", {})
        selected_channel = current_data.get("channel", get_current_settings()["channel"])
        method = current_data.get("method", get_current_settings()["method"])
        component_value = current_data.get("component_value", 0.0)
        current_graph = _cache_get(GRAPH_CACHE, get_current_graph_key(selected_channel, method, component_value))
        if current_graph is None:
            current_data = build_current_view(ch1, ch2, math_result, fs, time_axis, file_name)
        else:
            current_data = {
                "channel": selected_channel,
                "method": method,
                "component_value_input": current_data.get("component_value_input", get_current_settings()["component_value"]),
                "component_value": component_value,
                "current_mean": current_data.get("current_mean", 0.0),
                "current_rms": current_data.get("current_rms", 0.0),
                "current_max": current_data.get("current_max", 0.0),
                "current_min": current_data.get("current_min", 0.0),
                "current_peak_to_peak": current_data.get("current_peak_to_peak", 0.0),
                "phase_angle_deg": current_data.get("phase_angle_deg", 0.0),
                "detected_frequency_hz": current_data.get("detected_frequency_hz", 0.0),
                "inductor_initial_mode": current_data.get("inductor_initial_mode", get_current_settings()["inductor_initial_mode"]),
                "inductor_initial_value_input": current_data.get("inductor_initial_value_input", get_current_settings()["inductor_initial_value"]),
                "warnings": current_data.get("warnings", []),
                "graph": current_graph,
                "enabled": bool(session.get("current_enabled")),
            }

    total_current_data = build_total_current_view(ch1, ch2, math_result, fs, time_axis, file_name)

    if full_refresh or action_name == "correlation" or "correlation_data" not in session:
        correlation_data = build_correlation_view(ch1, ch2, fs, file_name)
    else:
        correlation_data = session.get("correlation_data", {})
        correlation_graph = _cache_get(GRAPH_CACHE, get_correlation_graph_key())
        if correlation_graph is None:
            correlation_data = build_correlation_view(ch1, ch2, fs, file_name)
        else:
            correlation_data = {
                "enabled": bool(session.get("correlation_enabled")),
                "max_correlation": correlation_data.get("max_correlation", 0.0),
                "delay_value": correlation_data.get("delay_value", 0.0),
                "delay_unit": correlation_data.get("delay_unit", "s"),
                "graph": correlation_graph,
                "delay_seconds": correlation_data.get("delay_seconds", 0.0),
            }

    if full_refresh or action_name == "cursor":
        cursor_data = build_cursor_view(ch1, ch2, math_result, time_axis)
    else:
        cursor_data = build_cursor_view(ch1, ch2, math_result, time_axis)

    if full_refresh or action_name == "cycle" or "cycle_data" not in session:
        cycle_data = build_cycle_view(ch1, ch2, math_result, fs)
    else:
        cycle_data = session.get("cycle_data")

    if full_refresh or action_name == "comparison" or action_name == "snapshot" or "comparison_data" not in session:
        comparison_data = build_comparison_view(file_name, measures)
    else:
        comparison_data = session.get("comparison_data")

    return {
        "file_path": file_path,
        "file_name": file_name,
        "config": config,
        "measures": measures,
        "ch1": ch1,
        "ch2": ch2,
        "fs": fs,
        "time_axis": time_axis,
        "math_result": math_result,
        "math_measures": math_measures,
        "fft_graph": fft_graph,
        "fft_data": fft_data,
        "statistics_data": statistics_data,
        "advanced_data": advanced_data,
        "calculus_data": calculus_data,
        "current_data": current_data,
        "total_current_data": total_current_data,
        "correlation_data": correlation_data,
        "cursor_data": cursor_data,
        "cycle_data": cycle_data,
        "comparison_data": comparison_data,
        "calibration_data": build_calibration_view(),
        "main_graph": get_main_graph(time_axis, ch1, ch2, file_name, measures, file_path),
        "math_graph": get_math_graph(time_axis, math_result, file_path, session.get("math_operation")),
    }


def store_enabled_views(context):
    if context["statistics_data"]["enabled"]:
        session["statistics_data"] = context["statistics_data"]
    if context["advanced_data"]["enabled"]:
        session["advanced_data"] = context["advanced_data"]
    if context["fft_data"]["enabled"]:
        session["fft_data"] = {k: v for k, v in context["fft_data"].items() if k not in {"frequencies_hz", "magnitudes"}}
    if context["calculus_data"]["enabled"]:
        session["calculus_data"] = {
            "channel": context["calculus_data"]["channel"],
            "derivative_peak": context["calculus_data"]["derivative_peak"],
            "integral_final": context["calculus_data"]["integral_final"],
        }
    if context["current_data"]["enabled"]:
        session["current_data"] = {
            "channel": context["current_data"]["channel"],
            "method": context["current_data"]["method"],
            "component_value_input": context["current_data"]["component_value_input"],
            "component_value": context["current_data"]["component_value"],
            "current_mean": context["current_data"]["current_mean"],
            "current_rms": context["current_data"]["current_rms"],
            "current_max": context["current_data"]["current_max"],
            "current_min": context["current_data"]["current_min"],
            "current_peak_to_peak": context["current_data"]["current_peak_to_peak"],
            "phase_angle_deg": context["current_data"].get("phase_angle_deg", 0.0),
            "detected_frequency_hz": context["current_data"].get("detected_frequency_hz", 0.0),
            "inductor_initial_mode": context["current_data"].get("inductor_initial_mode", "zero"),
            "inductor_initial_value": context["current_data"].get("initial_current_value", 0.0),
            "inductor_initial_value_input": context["current_data"].get("inductor_initial_value_input", "0"),
            "warnings": context["current_data"].get("warnings", []),
        }
    if context["total_current_data"]["enabled"]:
        session["total_current_data"] = {
            "voltage_channel": context["total_current_data"]["voltage_channel"],
            "combination_mode": context["total_current_data"].get("combination_mode", "parallel"),
            "frequency_tolerance_percent": context["total_current_data"].get("frequency_tolerance_percent", "5"),
            "saved_count": context["total_current_data"]["saved_count"],
            "compatible_count": context["total_current_data"].get("compatible_count", 0),
            "incompatible_count": context["total_current_data"].get("incompatible_count", 0),
            "total_current_mean": context["total_current_data"]["total_current_mean"],
            "total_current_rms": context["total_current_data"]["total_current_rms"],
            "total_current_max": context["total_current_data"]["total_current_max"],
            "total_current_min": context["total_current_data"]["total_current_min"],
            "total_current_peak_to_peak": context["total_current_data"]["total_current_peak_to_peak"],
            "phase_angle_deg": context["total_current_data"]["phase_angle_deg"],
            "series_mismatch_rms": context["total_current_data"].get("series_mismatch_rms", 0.0),
            "warnings": context["total_current_data"].get("warnings", []),
        }
    if context["correlation_data"]["enabled"]:
        session["correlation_data"] = {
            "max_correlation": context["correlation_data"]["max_correlation"],
            "delay_value": context["correlation_data"]["delay_value"],
            "delay_unit": context["correlation_data"]["delay_unit"],
        }
    if context["cursor_data"]["enabled"]:
        session["cursor_data"] = {
            "channel": context["cursor_data"]["channel"],
            "t1": context["cursor_data"]["t1"],
            "t2": context["cursor_data"]["t2"],
            "t1_input": context["cursor_data"]["t1_input"],
            "t2_input": context["cursor_data"]["t2_input"],
            "v1": context["cursor_data"]["v1"],
            "v2": context["cursor_data"]["v2"],
            "delta_t": context["cursor_data"]["delta_t"],
            "delta_t_unit": context["cursor_data"]["delta_t_unit"],
            "delta_v": context["cursor_data"]["delta_v"],
            "estimated_frequency": context["cursor_data"]["estimated_frequency"],
            "estimated_frequency_unit": context["cursor_data"]["estimated_frequency_unit"],
        }
    if context["cycle_data"]["enabled"]:
        session["cycle_data"] = context["cycle_data"]
    if context["comparison_data"]["enabled"]:
        session["comparison_data"] = context["comparison_data"]


@app.route("/", methods=["GET", "POST"])
def main():
    error_message = None
    toast_message = session.pop("toast_message", None)
    toast_variant = session.pop("toast_variant", "success")
    pending_snapshot_name = None
    pending_current_snapshot_name = None
    action_name = None

    if request.method == "POST" and "upload-file" in request.form:
        action_name = "upload"
        cleanup_file()
        uploaded_file = request.files.get("file")
        if uploaded_file and uploaded_file.filename:
            if not is_allowed_file(uploaded_file.filename):
                return render_template("main.html", **build_empty_view("Solo se permiten archivos .wav."))

            clear_loaded_state(preserve_current_library=True)
            file_path = os.path.join(UPLOAD_FOLDER, get_unique_filename())
            uploaded_file.save(file_path)

            try:
                config, measures = parse_uploaded_scope_file(file_path)
            except (OSError, ScopeFileError, IndexError, ValueError) as exc:
                if os.path.exists(file_path):
                    os.remove(file_path)
                return render_template("main.html", **build_empty_view(f"Archivo no valido: {exc}"))

            session.update(
                {
                    "file_wav": file_path,
                    "original_name": secure_filename(uploaded_file.filename) or "scope_capture.wav",
                    "config": config,
                    "measures": measures,
                    "fft_settings": DEFAULT_FFT_SETTINGS.copy(),
                    "fft_enabled": False,
                    "statistics_enabled": False,
                    "advanced_enabled": False,
                    "calculus_enabled": False,
                    "calculus_settings": DEFAULT_CALCULUS_SETTINGS.copy(),
                    "current_enabled": False,
                    "current_settings": DEFAULT_CURRENT_SETTINGS.copy(),
                    "total_current_enabled": bool(session.get("current_snapshots")),
                    "total_current_settings": session.get("total_current_settings", DEFAULT_TOTAL_CURRENT_SETTINGS.copy()),
                    "correlation_enabled": False,
                    "calibration_enabled": False,
                    "calibration_settings": DEFAULT_CALIBRATION_SETTINGS.copy(),
                    "cursor_enabled": True,
                    "cursor_settings": DEFAULT_CURSOR_SETTINGS.copy(),
                    "cycle_enabled": False,
                    "cycle_settings": DEFAULT_CYCLE_SETTINGS.copy(),
                    "comparison_enabled": False,
                    "comparison_snapshot_id": "",
                }
            )
            toast_message = f"File loaded: {secure_filename(uploaded_file.filename) or 'scope_capture.wav'}"
            toast_variant = "success"

    if request.method == "POST" and "math_op" in request.form:
        action_name = "math"
        session["math_operation"] = request.form.get("math_op")
        if session["math_operation"]:
            toast_message = f"Math applied: {session['math_operation'].upper()}"
            toast_variant = "success"

    if request.method == "POST" and "fft_apply" in request.form:
        action_name = "fft"
        try:
            _, raw_max_frequency = parse_fft_max_frequency(request.form.get("fft_max_frequency"))
        except ValueError as exc:
            error_message = str(exc)
        else:
            session["fft_settings"] = {
                "channel": request.form.get("fft_channel", "X"),
                "scale": request.form.get("fft_scale", "linear"),
                "max_frequency": raw_max_frequency,
                "window_type": request.form.get("fft_window_type", "hann"),
            }
            session["fft_enabled"] = True
            toast_message = f"FFT applied on channel {session['fft_settings']['channel']}"
            toast_variant = "success"

    if request.method == "POST" and "statistics_apply" in request.form:
        action_name = "statistics"
        session["statistics_enabled"] = True
        toast_message = "Statistics applied."
        toast_variant = "success"

    if request.method == "POST" and "advanced_apply" in request.form:
        action_name = "advanced"
        session["advanced_enabled"] = True
        toast_message = "Advanced measures applied."
        toast_variant = "success"

    if request.method == "POST" and "calculus_apply" in request.form:
        action_name = "calculus"
        session["calculus_enabled"] = True
        session["calculus_settings"] = {"channel": request.form.get("calculus_channel", "X")}
        toast_message = f"Derivative and integral applied on channel {session['calculus_settings']['channel']}"
        toast_variant = "success"

    if request.method == "POST" and "current_apply" in request.form:
        action_name = "current"
        try:
            component_value, normalized = parse_positive_component_value(
                request.form.get("current_component_value"),
                "valor del componente",
            )
            initial_current_value, normalized_initial_current = parse_float_field(
                request.form.get("current_inductor_initial_value"),
                "corriente inicial del inductor",
                default=0.0,
            )
        except ValueError as exc:
            error_message = str(exc)
        else:
            session["current_enabled"] = True
            session["current_settings"] = {
                "channel": request.form.get("current_channel", "X"),
                "method": request.form.get("current_method", "resistor"),
                "component_value": normalized,
                "inductor_initial_mode": request.form.get("current_inductor_initial_mode", "zero"),
                "inductor_initial_value": normalized_initial_current or "0",
            }
            method_label = {
                "resistor": "resistor",
                "capacitor": "capacitor",
                "inductor": "inductor",
            }.get(request.form.get("current_method", "resistor"), "component")
            toast_message = f"Current analysis applied on channel {session['current_settings']['channel']} using {method_label} mode."
            toast_variant = "success"

    if request.method == "POST" and "current_save" in request.form:
        action_name = "current"
        session["current_enabled"] = True
        pending_current_snapshot_name = (request.form.get("current_snapshot_name") or "").strip() or "Current snapshot"
        toast_variant = "success"

    if request.method == "POST" and "total_current_apply" in request.form:
        action_name = "current"
        try:
            _, tolerance_normalized = parse_nonnegative_float_field(
                request.form.get("total_current_frequency_tolerance"),
                "tolerancia de frecuencia",
                default=5.0,
            )
        except ValueError as exc:
            error_message = str(exc)
        else:
            session["total_current_settings"] = {
                "voltage_channel": request.form.get("total_current_voltage_channel", "X"),
                "combination_mode": request.form.get("total_current_combination_mode", "parallel"),
                "frequency_tolerance_percent": tolerance_normalized or "5",
            }
            session["total_current_enabled"] = True
            toast_message = f"Total current analysis applied using voltage channel {session['total_current_settings']['voltage_channel']}."
            toast_variant = "success"

    if request.method == "POST" and "correlation_apply" in request.form:
        action_name = "correlation"
        session["correlation_enabled"] = True
        toast_message = "Correlation applied."
        toast_variant = "success"

    if request.method == "POST" and "calibration_apply" in request.form:
        action_name = "calibration"
        try:
            x_gain, _ = parse_float_field(request.form.get("x_gain"), "ganancia X", 1.0)
            y_gain, _ = parse_float_field(request.form.get("y_gain"), "ganancia Y", 1.0)
            x_offset, _ = parse_float_field(request.form.get("x_offset"), "offset X", 0.0)
            y_offset, _ = parse_float_field(request.form.get("y_offset"), "offset Y", 0.0)
        except ValueError as exc:
            error_message = str(exc)
        else:
            session["calibration_settings"] = {
                "x_gain": x_gain,
                "y_gain": y_gain,
                "x_offset": x_offset,
                "y_offset": y_offset,
                "invert_x": request.form.get("invert_x") == "on",
                "invert_y": request.form.get("invert_y") == "on",
                "normalize": request.form.get("normalize") == "on",
            }
            session["calibration_enabled"] = True
            toast_message = "Calibration applied."
            toast_variant = "success"

    if request.method == "POST" and "cursor_apply" in request.form:
        action_name = "cursor"
        raw_t1 = str(request.form.get("cursor_t1") or "").strip()
        raw_t2 = str(request.form.get("cursor_t2") or "").strip()
        if raw_t1:
            try:
                float(raw_t1)
            except ValueError:
                error_message = "The t1 cursor value is invalid."
        if raw_t2 and not error_message:
            try:
                float(raw_t2)
            except ValueError:
                error_message = "The t2 cursor value is invalid."
        if not error_message:
            session["cursor_settings"] = {
                "channel": request.form.get("cursor_channel", "X"),
                "t1": raw_t1,
                "t2": raw_t2,
            }
            session["cursor_enabled"] = True
            toast_message = f"Cursors applied on channel {session['cursor_settings']['channel']}"
            toast_variant = "success"

    if request.method == "POST" and "cycle_apply" in request.form:
        action_name = "cycle"
        session["cycle_settings"] = {"channel": request.form.get("cycle_channel", "X")}
        session["cycle_enabled"] = True
        toast_message = f"Cycle analysis applied on channel {session['cycle_settings']['channel']}"
        toast_variant = "success"

    if request.method == "POST" and "save_snapshot" in request.form:
        action_name = "snapshot"
        pending_snapshot_name = (request.form.get("snapshot_name") or "").strip() or "Snapshot"

    if request.method == "POST" and "compare_apply" in request.form:
        action_name = "comparison"
        session["comparison_snapshot_id"] = request.form.get("snapshot_id", "")
        session["comparison_enabled"] = bool(session["comparison_snapshot_id"])
        if session["comparison_enabled"]:
            toast_message = "Snapshot comparison applied."
            toast_variant = "success"

    if request.method == "POST" and "reset" in request.form:
        clear_loaded_state()
        cleanup_upload_folder()
        session.clear()
        return render_template("main.html", **build_empty_view(toast_message="Workspace reset and uploads cleaned.", toast_variant="success"))

    file_path = session.get("file_wav")
    if not file_path or not os.path.exists(file_path):
        rendered_html = render_template("main.html", **build_empty_view(error_message=error_message, toast_message=toast_message, toast_variant=toast_variant))
        if is_ajax_request() and action_name in AJAX_MODULE_ACTIONS:
            return build_ajax_fragment_response(rendered_html, action_name, error_message=error_message), 400
        return rendered_html

    try:
        context = prepare_analysis_context(action_name)
        if pending_snapshot_name:
            save_snapshot(pending_snapshot_name, context["file_name"], context["measures"], context["fft_data"])
            context["comparison_data"] = build_comparison_view(context["file_name"], context["measures"])
            toast_message = f"Snapshot saved: {pending_snapshot_name}"
            toast_variant = "success"
        if pending_current_snapshot_name:
            if save_current_snapshot(pending_current_snapshot_name, context["current_data"], context["time_axis"], context["file_name"]):
                context["total_current_data"] = build_total_current_view(
                    context["ch1"],
                    context["ch2"],
                    context["math_result"],
                    context["fs"],
                    context["time_axis"],
                    context["file_name"],
                )
                toast_message = f"Current snapshot saved: {pending_current_snapshot_name}"
                toast_variant = "success"
        store_enabled_views(context)
    except (OSError, ScopeFileError, ValueError, ZeroDivisionError) as exc:
        clear_loaded_state()
        rendered_html = render_template("main.html", **build_empty_view(f"No se pudo procesar el archivo: {exc}"))
        if is_ajax_request() and action_name in AJAX_MODULE_ACTIONS:
            return build_ajax_fragment_response(rendered_html, action_name, error_message=f"No se pudo procesar el archivo: {exc}"), 400
        return rendered_html

    template_context = dict(
        file=context["file_path"],
        file_name=context["file_name"],
        config=context["config"],
        measures=context["measures"],
        grafica=context["main_graph"],
        grafica_math=context["math_graph"],
        math_operation=session.get("math_operation"),
        math_measures=context["math_measures"],
        fft_graph=context["fft_graph"],
        fft_data=context["fft_data"],
        statistics_data=context["statistics_data"],
        advanced_data=context["advanced_data"],
        calculus_data=context["calculus_data"],
        current_data=context["current_data"],
        total_current_data=context["total_current_data"],
        correlation_data=context["correlation_data"],
        calibration_data=context["calibration_data"],
        cursor_data=context["cursor_data"],
        cycle_data=context["cycle_data"],
        comparison_data=context["comparison_data"],
        snapshots=session.get("snapshots", []),
        current_snapshots=session.get("current_snapshots", []),
        error_message=error_message,
        toast_message=toast_message,
        toast_variant=toast_variant,
    )

    rendered_html = render_template("main.html", **template_context)
    if is_ajax_request() and action_name in AJAX_MODULE_ACTIONS:
        return build_ajax_fragment_response(rendered_html, action_name)

    return rendered_html


@app.route("/download_latex")
def download_latex():
    measures = session.get("measures")
    if not measures:
        return "No hay datos de medidas", 400
    return Response(generate_measures_latex(measures), mimetype="text/plain")


@app.route("/download_math_latex")
def download_math_latex():
    math_measures = session.get("math_measures")
    operation = session.get("math_operation")
    if not math_measures:
        return "No hay datos de medidas MATH", 400
    return Response(generate_math_measures_latex(math_measures, operation), mimetype="text/plain")


@app.route("/download_statistics_latex")
def download_statistics_latex():
    statistics_data = session.get("statistics_data")
    if not statistics_data:
        return "No hay datos estadisticos", 400
    return Response(generate_statistics_latex(statistics_data), mimetype="text/plain")


@app.route("/download_advanced_latex")
def download_advanced_latex():
    advanced_data = session.get("advanced_data")
    if not advanced_data:
        return "No hay datos de medidas avanzadas", 400
    return Response(generate_advanced_measures_latex(advanced_data), mimetype="text/plain")


@app.route("/download_correlation_latex")
def download_correlation_latex():
    correlation_data = session.get("correlation_data")
    if not correlation_data:
        return "No hay datos de correlacion", 400
    return Response(generate_correlation_latex(correlation_data), mimetype="text/plain")


@app.route("/download_fft_latex")
def download_fft_latex():
    fft_data = session.get("fft_data")
    if not fft_data:
        return "No hay datos FFT", 400
    return Response(generate_fft_latex(fft_data), mimetype="text/plain")


@app.route("/download_calibration_latex")
def download_calibration_latex():
    return Response(generate_calibration_latex(get_calibration_settings()), mimetype="text/plain")


@app.route("/download_current_latex")
def download_current_latex():
    current_data = session.get("current_data")
    if not current_data:
        return "No hay analisis de corriente", 400
    return Response(generate_current_latex(current_data), mimetype="text/plain")


@app.route("/download_total_current_latex")
def download_total_current_latex():
    total_current_data = session.get("total_current_data")
    if not total_current_data:
        return "No hay analisis de corriente total", 400
    return Response(generate_total_current_latex(total_current_data), mimetype="text/plain")


@app.route("/download_cursor_latex")
def download_cursor_latex():
    cursor_data = session.get("cursor_data")
    if not cursor_data:
        return "No hay medicion manual", 400
    return Response(generate_cursor_latex(cursor_data), mimetype="text/plain")


@app.route("/download_cursor_graph")
def download_cursor_graph():
    if not session.get("cursor_enabled"):
        return "Primero debes aplicar Cursors", 400
    context = prepare_download_data()
    if not context:
        return "No hay archivo cargado o el archivo es invalido", 400

    cursor_data = context["cursor_data"]
    signals = {
        "X": context["ch1"],
        "Y": context["ch2"],
        "MATH": context["math_result"] if context["math_result"] is not None else np.array([]),
    }
    selected_signal = signals.get(cursor_data["channel"], context["ch1"])
    png_path = generate_cursor_grafic_file(
        context["time_axis"],
        selected_signal,
        f"Cursor measurement {cursor_data['channel']}",
        marker_points=[(cursor_data["t1"], cursor_data["v1"]), (cursor_data["t2"], cursor_data["v2"])],
    )
    cleanup_temp_download(png_path)
    return send_file(
        png_path,
        mimetype="image/png",
        as_attachment=True,
        download_name=f"{context['file_name']}_cursors_{cursor_data['channel']}.png",
    )


@app.route("/download_cycle_latex")
def download_cycle_latex():
    cycle_data = session.get("cycle_data")
    if not cycle_data:
        return "No hay analisis por ciclo", 400
    return Response(generate_cycle_latex(cycle_data), mimetype="text/plain")


@app.route("/download_comparison_latex")
def download_comparison_latex():
    comparison_data = session.get("comparison_data")
    if not comparison_data:
        return "No hay comparacion", 400
    return Response(generate_comparison_latex(comparison_data), mimetype="text/plain")


def prepare_download_data(action_name=None):
    try:
        return prepare_analysis_context(action_name)
    except (OSError, ScopeFileError, ValueError, ZeroDivisionError):
        return None


@app.route("/download_graph")
def download_graph():
    context = prepare_download_data()
    if not context:
        return "No hay archivo cargado o el archivo es invalido", 400
    png_path = generate_grafic_download(
        context["time_axis"],
        context["ch1"],
        context["ch2"],
        context["file_name"],
        context["measures"],
        scope_config=context["config"],
    )
    cleanup_temp_download(png_path)
    return send_file(png_path, mimetype="image/png", as_attachment=True, download_name=f"{context['file_name']}_graph.png")


@app.route("/download_math_graph")
def download_math_graph():
    context = prepare_download_data()
    if not context:
        return "No hay archivo cargado o el archivo es invalido", 400
    if session.get("math_operation") is None:
        return "No hay operacion matematica activa", 400
    png_path = generate_grafic_download_math(context["time_axis"], [], [], f"MATH_{session.get('math_operation')}", math_result=context["math_result"])
    cleanup_temp_download(png_path)
    return send_file(
        png_path,
        mimetype="image/png",
        as_attachment=True,
        download_name=f"{context['file_name']}_math_{session.get('math_operation')}.png",
    )


@app.route("/download_fft_graph")
def download_fft_graph():
    if not session.get("fft_enabled"):
        return "Primero debes aplicar la FFT", 400
    context = prepare_download_data()
    if not context:
        return "No hay archivo cargado o el archivo es invalido", 400
    fft_data = get_fft_download_data(context["ch1"], context["ch2"], context["math_result"], context["fs"])
    png_path = generate_fft_grafic_download(
        fft_data["frequencies_hz"],
        fft_data["magnitudes"],
        context["file_name"],
        fft_data["channel"],
        scale_mode=fft_data["scale"],
        dominant_frequency_hz=fft_data["dominant_frequency_hz"],
    )
    cleanup_temp_download(png_path)
    return send_file(png_path, mimetype="image/png", as_attachment=True, download_name=f"{context['file_name']}_fft_{fft_data['channel']}.png")


@app.route("/download_derivative_graph")
def download_derivative_graph():
    if not session.get("calculus_enabled"):
        return "Primero debes aplicar Derivative & Integral", 400
    context = prepare_download_data("calculus")
    if not context:
        return "No hay archivo cargado o el archivo es invalido", 400
    png_path = generate_signal_analysis_download(
        context["time_axis"],
        context["calculus_data"]["derivative"],
        f"Derivative {context['calculus_data']['channel']}",
        "dV/dt (V/s)",
    )
    cleanup_temp_download(png_path)
    return send_file(png_path, mimetype="image/png", as_attachment=True, download_name=f"{context['file_name']}_derivative_{context['calculus_data']['channel']}.png")


@app.route("/download_integral_graph")
def download_integral_graph():
    if not session.get("calculus_enabled"):
        return "Primero debes aplicar Derivative & Integral", 400
    context = prepare_download_data("calculus")
    if not context:
        return "No hay archivo cargado o el archivo es invalido", 400
    png_path = generate_signal_analysis_download(
        context["time_axis"],
        context["calculus_data"]["integral"],
        f"Integral {context['calculus_data']['channel']}",
        "Integral (V*s)",
    )
    cleanup_temp_download(png_path)
    return send_file(png_path, mimetype="image/png", as_attachment=True, download_name=f"{context['file_name']}_integral_{context['calculus_data']['channel']}.png")


@app.route("/download_current_graph")
def download_current_graph():
    if not session.get("current_enabled"):
        return "Primero debes aplicar Current", 400
    context = prepare_download_data("current")
    if not context:
        return "No hay archivo cargado o el archivo es invalido", 400

    current_data = context["current_data"]
    signals = {
        "X": context["ch1"],
        "Y": context["ch2"],
        "MATH": context["math_result"] if context["math_result"] is not None else np.array([]),
    }
    selected_signal = signals.get(current_data["channel"], context["ch1"])
    png_path = generate_current_grafic_download(
        context["time_axis"],
        selected_signal,
        current_data["current"],
        f"Current Analysis {current_data['channel']}",
    )
    cleanup_temp_download(png_path)
    return send_file(
        png_path,
        mimetype="image/png",
        as_attachment=True,
        download_name=f"{context['file_name']}_current_{current_data['channel']}.png",
    )


@app.route("/download_total_current_graph")
def download_total_current_graph():
    if not session.get("total_current_enabled"):
        return "No hay analisis de corriente total", 400

    context = prepare_download_data("current")
    total_current_data = context["total_current_data"]
    if not total_current_data.get("enabled"):
        return "No hay analisis de corriente total", 400

    signals = {
        "X": context["ch1"],
        "Y": context["ch2"],
        "MATH": context["math_result"] if context["math_result"] is not None else np.array([]),
    }
    voltage = signals.get(total_current_data["voltage_channel"], context["ch1"])
    png_path = generate_current_grafic_download(
        context["time_axis"],
        voltage,
        total_current_data["current"],
        f"Total Current Analysis {total_current_data['voltage_channel']}",
    )
    cleanup_temp_download(png_path)
    return send_file(
        png_path,
        mimetype="image/png",
        as_attachment=True,
        download_name=f"{context['file_name']}_total_current_{total_current_data['voltage_channel']}.png",
    )


@app.route("/download_correlation_graph")
def download_correlation_graph():
    if not session.get("correlation_enabled"):
        return "Primero debes aplicar Correlation", 400
    context = prepare_download_data("correlation")
    if not context:
        return "No hay archivo cargado o el archivo es invalido", 400
    png_path = generate_correlation_grafic_download(
        context["correlation_data"]["lags_seconds"],
        context["correlation_data"]["correlation"],
        "Correlation",
        marker_x=context["correlation_data"]["delay_seconds"],
        marker_y=context["correlation_data"]["max_correlation"],
    )
    cleanup_temp_download(png_path)
    return send_file(png_path, mimetype="image/png", as_attachment=True, download_name=f"{context['file_name']}_correlation.png")


def run_flask_server(host="127.0.0.1", port=5000):
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)


def wait_for_server(host="127.0.0.1", port=5000, timeout_seconds=10):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def launch_desktop(host="127.0.0.1", port=5000, width=1200, height=800):
    global MAIN_WINDOW
    desktop_api = DesktopApi()

    flask_thread = Thread(target=run_flask_server, kwargs={"host": host, "port": port}, daemon=True)
    flask_thread.start()

    if not wait_for_server(host=host, port=port):
        raise RuntimeError(f"Flask server did not start on http://{host}:{port}")

    window = webview.create_window(
        APP_NAME,
        f"http://{host}:{port}",
        width=width,
        height=height,
        js_api=desktop_api,
    )
    MAIN_WINDOW = window

    def on_window_closed():
        cleanup_upload_folder()

    window.events.closed += on_window_closed
    webview.start()


if __name__ == "__main__":
    mode = os.getenv("FNIRSI_APP_MODE", "desktop").lower()
    if mode == "server":
        run_flask_server()
    else:
        launch_desktop()
