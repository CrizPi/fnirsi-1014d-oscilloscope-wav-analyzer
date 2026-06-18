import os
import uuid
from datetime import datetime

import numpy as np

from file_analizer import get_scope_config, get_scope_measures, get_scope_raw_data_display
from plot_maker import (
    _compute_vdiv_from_data,
    _fmt_vdiv,
    generate_correlation_grafic,
    generate_fft_grafic,
    generate_grafic,
    generate_signal_analysis_grafic,
    generate_voltage_current_grafic,
    generate_xy_mode_grafic,
)
from signal_analyzer import (
    adaptive_scope_filter,
    apply_math_operation,
    build_cycle_template,
    calculate_advanced_measures,
    calculate_correlation_analysis,
    calculate_current_analysis,
    calculate_cycle_analysis,
    calculate_derivative_integral,
    calculate_manual_measurement,
    calculate_math_measures,
    calculate_power_analysis,
    calculate_signal_statistics,
    calculate_transfer_analysis,
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
from state_store import (
    ANALYSIS_CACHE,
    CACHE_LOCK,
    CH_CLEAR,
    CURRENT_WAVEFORM_STORE,
    DEFAULT_CALCULUS_SETTINGS,
    DEFAULT_CALIBRATION_SETTINGS,
    DEFAULT_CONFIG,
    DEFAULT_CURSOR_SETTINGS,
    DEFAULT_CURRENT_SETTINGS,
    DEFAULT_CYCLE_SETTINGS,
    DEFAULT_FFT_SETTINGS,
    DEFAULT_MATH_MEASURES,
    DEFAULT_MEASURES,
    DEFAULT_TOTAL_CURRENT_SETTINGS,
    DEFAULT_TRANSFER_SETTINGS,
    DEFAULT_XY_SETTINGS,
    GRAPH_CACHE,
    T_CLEAR,
    cache_get,
    cache_set,
    freeze_value,
    get_client_id,
    state_get,
    state_set,
)

def _has_math_result(math_result):
    return math_result is not None and np.asarray(math_result).size > 0


def parse_uploaded_scope_file(file_path):
    return get_scope_config(file_path), get_scope_measures(file_path)


def load_signal_data(file_path, config, measures):
    cache_key = ("signal_data", file_path, freeze_value(config), freeze_value(measures))
    cached = cache_get(ANALYSIS_CACHE, cache_key)
    if cached is not None:
        return cached

    ch1, ch2 = get_scope_raw_data_display(file_path, measures)
    ch1_v, ch2_v = convert_scope_data(ch1, ch2, config, measures)
    ch1_v, ch2_v, trigger_index = crop_scope_window(ch1_v, ch2_v, config)
    fs, time_axis = get_scope_fs_and_time(ch1_v, config, ch2_v, trigger_index=trigger_index)
    return cache_set(ANALYSIS_CACHE, cache_key, (ch1_v, ch2_v, fs, time_axis))


def apply_visual_filter(ch1, ch2, fs, math_result=None):
    # CH1 y CH2 ya fueron suavizados en convert_scope_data (sobre datos RAW),
    # por lo que no se aplica suavizado adicional aqui.
    # Solo se suaviza el resultado MATH si existe.
    filtered_math = adaptive_scope_filter(math_result, fs) if math_result is not None else None
    return ch1, ch2, filtered_math


def process_math(ch1, ch2, fs):
    math_operation = state_get("math_operation")
    if not math_operation:
        return None, DEFAULT_MATH_MEASURES.copy()

    math_result = apply_math_operation(ch1, ch2, math_operation)
    math_measures = calculate_math_measures(math_result, fs)
    state_set("math_measures", math_measures)
    return math_result, math_measures


def get_processed_signals(file_path, config, measures):
    math_operation = state_get("math_operation")
    cal_settings = get_calibration_settings()
    invert_x = bool(cal_settings.get("invert_x", False))
    invert_y = bool(cal_settings.get("invert_y", False))
    cache_key = (
        "processed_signals",
        file_path,
        freeze_value(config),
        freeze_value(measures),
        math_operation,
        invert_x,
        invert_y,
    )
    cached = cache_get(ANALYSIS_CACHE, cache_key)
    if cached is not None:
        return cached

    ch1, ch2, fs, time_axis = load_signal_data(file_path, config, measures)

    # Apply inversion using the existing calibration logic (gain/offset kept at
    # defaults; only the invert flags set from the load-file dialog are used).
    if invert_x or invert_y:
        from signal_analyzer import apply_signal_calibration
        invert_settings = {
            "x_gain": 1.0, "y_gain": 1.0,
            "x_offset": 0.0, "y_offset": 0.0,
            "invert_x": invert_x,
            "invert_y": invert_y,
            "normalize": False,
        }
        ch1, ch2 = apply_signal_calibration(ch1, ch2, invert_settings)

    ch1_analysis, ch2_analysis = ch1, ch2
    math_result_analysis, math_measures = process_math(ch1_analysis, ch2_analysis, fs)
    ch1_visual, ch2_visual, math_result_visual = apply_visual_filter(
        ch1_analysis,
        ch2_analysis,
        fs,
        math_result_analysis,
    )

    result = {
        "ch1": ch1,
        "ch2": ch2,
        "ch1_analysis": ch1_analysis,
        "ch2_analysis": ch2_analysis,
        "math_result_analysis": math_result_analysis,
        "ch1_visual": ch1_visual,
        "ch2_visual": ch2_visual,
        "math_result_visual": math_result_visual,
        "fs": fs,
        "time_axis": time_axis,
        "math_measures": math_measures,
    }
    return cache_set(ANALYSIS_CACHE, cache_key, result)


def get_main_graph(time_axis, ch1, ch2, file_name, measures, file_path, ch1_name="CH1", ch2_name="CH2"):
    scope_config = state_get("config", DEFAULT_CONFIG)
    cache_key = ("main_graph", file_path, freeze_value(measures), freeze_value(scope_config), ch1_name, ch2_name)
    cached = cache_get(GRAPH_CACHE, cache_key)
    if cached is not None:
        return cached
    graph = generate_grafic(time_axis, ch1, ch2, "Oscilloscope Signals", measures, scope_config=scope_config, ch1_name=ch1_name, ch2_name=ch2_name)
    return cache_set(GRAPH_CACHE, cache_key, graph)


def get_math_graph(time_axis, math_result, file_path, math_operation):
    cache_key = ("math_graph", file_path, math_operation)
    cached = cache_get(GRAPH_CACHE, cache_key)
    if cached is not None:
        return cached
    graph = generate_grafic(time_axis, [], [], "MATH", math_result=math_result, show_empty=True)
    return cache_set(GRAPH_CACHE, cache_key, graph)


def get_fft_graph_key(raw_max_frequency):
    settings = get_fft_settings()
    return (
        "fft_graph",
        state_get("file_wav"),
        settings["channel"],
        settings["scale"],
        raw_max_frequency,
        settings["window_type"],
        state_get("math_operation"),
    )


def get_derivative_graph_key(selected_channel):
    return (
        "derivative_graph",
        state_get("file_wav"),
        selected_channel,
        state_get("math_operation"),
    )


def get_integral_graph_key(selected_channel):
    return (
        "integral_graph",
        state_get("file_wav"),
        selected_channel,
        state_get("math_operation"),
    )


def get_correlation_graph_key():
    return ("correlation_graph", state_get("file_wav"))


def get_xy_graph_key(x_channel, y_channel):
    return (
        "xy_graph",
        state_get("file_wav"),
        x_channel,
        y_channel,
        state_get("math_operation"),
    )


def get_current_graph_key(selected_channel, method, component_value):
    current_settings = get_current_settings()
    return (
        "current_graph",
        state_get("file_wav"),
        selected_channel,
        method,
        component_value,
        current_settings.get("inductor_initial_mode", "zero"),
        current_settings.get("inductor_initial_value", "0"),
        state_get("math_operation"),
    )


def _get_settings(key, default_dict):
    return dict(state_get(key, default_dict.copy()))


def get_fft_settings():
    return _get_settings("fft_settings", DEFAULT_FFT_SETTINGS)


def get_calculus_settings():
    return _get_settings("calculus_settings", DEFAULT_CALCULUS_SETTINGS)


def get_current_settings():
    settings = state_get("current_settings", DEFAULT_CURRENT_SETTINGS.copy())
    return {
        "channel": settings.get("channel", "X"),
        "method": settings.get("method", "resistor"),
        "component_value": str(settings.get("component_value", "1")),
        "inductor_initial_mode": settings.get("inductor_initial_mode", "zero"),
        "inductor_initial_value": str(settings.get("inductor_initial_value", "0")),
    }


def get_total_current_settings():
    settings = state_get("total_current_settings", DEFAULT_TOTAL_CURRENT_SETTINGS.copy())
    return {
        "voltage_channel": settings.get("voltage_channel", "X"),
        "combination_mode": settings.get("combination_mode", "parallel"),
        "frequency_tolerance_percent": str(settings.get("frequency_tolerance_percent", "5")),
    }


def get_transfer_settings():
    return _get_settings("transfer_settings", DEFAULT_TRANSFER_SETTINGS)


def get_xy_settings():
    return _get_settings("xy_settings", DEFAULT_XY_SETTINGS)


def get_calibration_settings():
    settings = state_get("calibration_settings", DEFAULT_CALIBRATION_SETTINGS.copy())
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
    return _get_settings("cursor_settings", DEFAULT_CURSOR_SETTINGS)


def get_cycle_settings():
    return _get_settings("cycle_settings", DEFAULT_CYCLE_SETTINGS)


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
    if not state_get("statistics_enabled"):
        return {"X": empty_stats, "Y": empty_stats, "MATH": empty_stats, "math_enabled": False, "enabled": False}
    cache_key = (
        "statistics",
        state_get("file_wav"),
        state_get("math_operation"),
    )
    cached = cache_get(ANALYSIS_CACHE, cache_key)
    if cached is not None:
        return cached
    data = {
        "X": calculate_signal_statistics(ch1),
        "Y": calculate_signal_statistics(ch2),
        "MATH": calculate_signal_statistics(math_result if math_result is not None else np.array([])),
        "math_enabled": _has_math_result(math_result),
        "enabled": True,
    }
    return cache_set(ANALYSIS_CACHE, cache_key, data)


def build_advanced_view(ch1, ch2, math_result, fs):
    zero = calculate_advanced_measures(np.array([]), 0)
    if not state_get("advanced_enabled"):
        return {"X": zero, "Y": zero, "MATH": zero, "math_enabled": False, "enabled": False}
    cache_key = (
        "advanced",
        state_get("file_wav"),
        state_get("math_operation"),
    )
    cached = cache_get(ANALYSIS_CACHE, cache_key)
    if cached is not None:
        return cached
    data = {
        "X": calculate_advanced_measures(ch1, fs),
        "Y": calculate_advanced_measures(ch2, fs),
        "MATH": calculate_advanced_measures(math_result if _has_math_result(math_result) else np.array([]), fs),
        "math_enabled": _has_math_result(math_result),
        "enabled": True,
    }
    return cache_set(ANALYSIS_CACHE, cache_key, data)


def build_fft_view(ch1, ch2, math_result, fs, file_name):
    settings = get_fft_settings()
    if not state_get("fft_enabled"):
        _graph, _vdiv, _tdiv = generate_fft_grafic([], [], "", settings["channel"])
        return _graph, {
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
            "hz_div_str": _vdiv,
            "mag_div_str": _tdiv,
        }

    max_frequency_hz, raw_max_frequency = parse_fft_max_frequency(settings["max_frequency"])
    signals = {"X": ch1, "Y": ch2, "MATH": math_result if math_result is not None else np.array([])}
    selected_signal = signals.get(settings["channel"], ch1)
    cache_key = (
        "fft",
        state_get("file_wav"),
        settings["channel"],
        settings["scale"],
        raw_max_frequency,
        settings["window_type"],
        state_get("math_operation"),
    )
    cached = cache_get(ANALYSIS_CACHE, cache_key)
    if cached is not None:
        return cached

    fft_data = get_fft_spectrum(selected_signal, fs, max_frequency=max_frequency_hz, window_type=settings["window_type"])
    graph_key = get_fft_graph_key(raw_max_frequency)
    fft_graph_cached = cache_get(GRAPH_CACHE, graph_key)
    if fft_graph_cached is None:
        fft_graph, fft_vdiv_str, fft_tdiv_str = generate_fft_grafic(
            fft_data["frequencies_hz"],
            fft_data["magnitudes"],
            file_name,
            settings["channel"],
            scale_mode=settings["scale"],
            dominant_frequency_hz=fft_data["dominant_frequency_hz"],
            max_frequency_hz=max_frequency_hz,
        )
        cache_set(GRAPH_CACHE, graph_key, (fft_graph, fft_vdiv_str, fft_tdiv_str))
    else:
        fft_graph, fft_vdiv_str, fft_tdiv_str = fft_graph_cached
    fft_data.update(
        {
            "channel": settings["channel"],
            "scale": settings["scale"],
            "max_frequency": raw_max_frequency,
            "window_type": settings["window_type"],
            "enabled": True,
            "hz_div_str": fft_vdiv_str,
            "mag_div_str": fft_tdiv_str,
        }
    )
    result = (fft_graph, fft_data)
    return cache_set(ANALYSIS_CACHE, cache_key, result)


def build_calculus_view(ch1, ch2, math_result, fs, time_axis, file_name):
    settings = get_calculus_settings()
    selected_channel = settings["channel"]
    signals = {"X": ch1, "Y": ch2, "MATH": math_result if math_result is not None else np.array([])}
    selected_signal = signals.get(selected_channel, ch1)

    if not state_get("calculus_enabled"):
        _dg, _dv, _dt = generate_signal_analysis_grafic([], [], f"Derivative {selected_channel}", "dV/dt (V/s)", channel=selected_channel)
        _ig, _iv, _it = generate_signal_analysis_grafic([], [], f"Integral {selected_channel}", "Integral (V*s)", channel=selected_channel)
        return {
            "channel": selected_channel,
            "enabled": False,
            "derivative_peak": 0.0,
            "integral_final": 0.0,
            "derivative": np.array([]),
            "integral": np.array([]),
            "derivative_graph": _dg,
            "derivative_vdiv_str": _dv,
            "derivative_tdiv_str": _dt,
            "integral_graph": _ig,
            "integral_vdiv_str": _iv,
            "integral_tdiv_str": _it,
        }

    cache_key = (
        "calculus",
        state_get("file_wav"),
        selected_channel,
        state_get("math_operation"),
    )
    cached = cache_get(ANALYSIS_CACHE, cache_key)
    if cached is not None:
        return cached

    calculus_data = calculate_derivative_integral(selected_signal, fs)
    calculus_data["channel"] = selected_channel
    calculus_data["enabled"] = True
    derivative_graph_key = get_derivative_graph_key(selected_channel)
    integral_graph_key = get_integral_graph_key(selected_channel)
    _cached_dg = cache_get(GRAPH_CACHE, derivative_graph_key)
    if _cached_dg is None:
        _dg, _dv, _dt = generate_signal_analysis_grafic(
            time_axis,
            calculus_data["derivative"],
            f"Derivative {selected_channel}",
            "dV/dt (V/s)",
            channel=selected_channel,
        )
        cache_set(GRAPH_CACHE, derivative_graph_key, (_dg, _dv, _dt))
    else:
        _dg, _dv, _dt = _cached_dg
    calculus_data["derivative_graph"] = _dg
    calculus_data["derivative_vdiv_str"] = _dv
    calculus_data["derivative_tdiv_str"] = _dt
    _cached_ig = cache_get(GRAPH_CACHE, integral_graph_key)
    if _cached_ig is None:
        _ig, _iv, _it = generate_signal_analysis_grafic(
            time_axis,
            calculus_data["integral"],
            f"Integral {selected_channel}",
            "Integral (V*s)",
            channel=selected_channel,
        )
        cache_set(GRAPH_CACHE, integral_graph_key, (_ig, _iv, _it))
    else:
        _ig, _iv, _it = _cached_ig
    calculus_data["integral_graph"] = _ig
    calculus_data["integral_vdiv_str"] = _iv
    calculus_data["integral_tdiv_str"] = _it
    return cache_set(ANALYSIS_CACHE, cache_key, calculus_data)


def build_current_view(ch1, ch2, math_result, ch1_visual, ch2_visual, math_result_visual, fs, time_axis, file_name):
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
        "voltage_rms": 0.0,
        "apparent_power_va": 0.0,
        "active_power_w": 0.0,
        "reactive_power_var": 0.0,
        "power_factor": 0.0,
        "complex_power_real_w": 0.0,
        "complex_power_imag_var": 0.0,
        "detected_frequency_hz": 0.0,
        "inductor_initial_mode": settings["inductor_initial_mode"],
        "inductor_initial_value": 0.0,
        "inductor_initial_value_input": settings["inductor_initial_value"],
        "warnings": [],
        "current": np.array([]),
        "graph": generate_voltage_current_grafic([], [], [], "Current Analysis")[0],
        "vdiv_str": "",
        "vdiv2_str": "",
        "tdiv_str": "",
        "enabled": False,
    }
    if not state_get("current_enabled"):
        return empty

    try:
        component_value = float(settings["component_value"])
    except (TypeError, ValueError):
        return empty

    analysis_signals = {
        "X": ch1,
        "Y": ch2,
        "MATH": math_result if math_result is not None else np.array([]),
    }
    visual_signals = {
        "X": ch1_visual,
        "Y": ch2_visual,
        "MATH": math_result_visual if math_result_visual is not None else np.array([]),
    }
    selected_signal = analysis_signals.get(settings["channel"], ch1)
    selected_signal_visual = visual_signals.get(settings["channel"], ch1_visual)

    cache_key = (
        "current",
        state_get("file_wav"),
        settings["channel"],
        settings["method"],
        component_value,
        settings.get("inductor_initial_mode", "zero"),
        settings.get("inductor_initial_value", "0"),
        state_get("math_operation"),
    )
    cached = cache_get(ANALYSIS_CACHE, cache_key)
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
    current_data.update(calculate_power_analysis(selected_signal, current_data.get("current", []), fs))
    if not phase_data.get("enabled"):
        warnings = list(current_data.get("warnings", []))
        warning_message = "No se pudo estimar el desfase entre voltaje y corriente con suficiente confianza."
        if warning_message not in warnings:
            warnings.append(warning_message)
        current_data["warnings"] = warnings
    graph_key = get_current_graph_key(settings["channel"], settings["method"], component_value)
    _cached_cg = cache_get(GRAPH_CACHE, graph_key)
    if _cached_cg is None:
        _cg, _cv, _cv2, _ct = generate_voltage_current_grafic(
            time_axis,
            selected_signal_visual,
            current_data["current"],
            f"Current Analysis {settings['channel']}",
            voltage_channel=settings["channel"],
        )
        cache_set(GRAPH_CACHE, graph_key, (_cg, _cv, _cv2, _ct))
    else:
        _cg, _cv, _cv2, _ct = _cached_cg
    current_data["graph"] = _cg
    current_data["vdiv_str"] = _cv
    current_data["vdiv2_str"] = _cv2
    current_data["tdiv_str"] = _ct
    return cache_set(ANALYSIS_CACHE, cache_key, current_data)


def save_current_snapshot(snapshot_name, current_data, time_axis, file_name):
    if not current_data.get("enabled"):
        return False

    waveform_id = f"{get_client_id()}:{uuid.uuid4().hex}"
    source_voltage = np.asarray(current_data.get("source_voltage", []), dtype=float)
    source_time_axis = np.asarray(current_data.get("source_time_axis", time_axis), dtype=float)
    source_fs = 1.0 / np.mean(np.diff(source_time_axis)) if source_time_axis.size > 1 else 0.0
    template, frequency_hz = build_cycle_template(
        np.asarray(current_data.get("current", []), dtype=float),
        np.asarray(time_axis, dtype=float),
        1.0 / np.mean(np.diff(time_axis)) if np.asarray(time_axis).size > 1 else 0.0,
    )
    voltage_template, voltage_frequency_hz = build_cycle_template(source_voltage, source_time_axis, source_fs)
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

    snapshots = state_get("current_snapshots", [])
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
    state_set("current_snapshots", trimmed)
    valid_ids = {item["id"] for item in trimmed}
    client_prefix = f"{get_client_id()}:"
    with CACHE_LOCK:
        stale_ids = [key for key in CURRENT_WAVEFORM_STORE if key.startswith(client_prefix) and key not in valid_ids]
        for key in stale_ids:
            CURRENT_WAVEFORM_STORE.pop(key, None)
    return True


def _resample_current_to_reference(reference_time_axis, reference_frequency_hz, reference_voltage_template, sample):
    reference_time_axis = np.asarray(reference_time_axis, dtype=float)
    if reference_time_axis.size == 0:
        return np.zeros_like(reference_time_axis)

    sample_time = np.asarray(sample.get("time_axis", []), dtype=float)
    sample_current = np.asarray(sample.get("current", []), dtype=float)
    if sample_time.size > 0 and sample_current.size > 0:
        length = min(sample_time.size, sample_current.size)
        sample_time = sample_time[:length]
        sample_current = sample_current[:length]
        return np.interp(reference_time_axis, sample_time, sample_current, left=0.0, right=0.0)

    template = np.asarray(sample.get("template", []), dtype=float)
    if template.size > 0 and reference_frequency_hz > 0:
        aligned_template = template
        sample_voltage_template = np.asarray(sample.get("voltage_template", []), dtype=float)
        if reference_voltage_template.size > 0 and sample_voltage_template.size > 0:
            shift_fraction = _estimate_template_shift_fraction(reference_voltage_template, sample_voltage_template)
            aligned_template = shift_cycle_template(aligned_template, shift_fraction)
        return project_cycle_template(aligned_template, reference_time_axis, reference_frequency_hz)

    return np.zeros_like(reference_time_axis)


def _estimate_template_shift_fraction(reference_template, sample_template):
    reference_template = np.asarray(reference_template if reference_template is not None else [], dtype=float)
    sample_template = np.asarray(sample_template if sample_template is not None else [], dtype=float)
    length = min(reference_template.size, sample_template.size)
    if length < 8:
        return 0.0

    reference_template = reference_template[:length]
    sample_template = sample_template[:length]
    phase_data = calculate_voltage_current_phase_angle(reference_template, sample_template, float(length))
    if phase_data.get("enabled"):
        phase_shift_deg = float(phase_data.get("phase_angle_deg", 0.0))
        return float(((-phase_shift_deg) / 360.0) % 1.0)
    return estimate_template_phase_shift(reference_template, sample_template)


def build_total_current_view(ch1, ch2, math_result, ch1_visual, ch2_visual, math_result_visual, fs, time_axis, file_name):
    settings = get_total_current_settings()
    current_file_snapshots = [item for item in state_get("current_snapshots", []) if item.get("file_name") == file_name]
    empty = {
        "enabled": False,
        "voltage_channel": settings["voltage_channel"],
        "combination_mode": "parallel",
        "frequency_tolerance_percent": settings["frequency_tolerance_percent"],
        "saved_count": len(current_file_snapshots),
        "compatible_count": 0,
        "incompatible_count": 0,
        "total_current_mean": 0.0,
        "total_current_rms": 0.0,
        "total_current_max": 0.0,
        "total_current_min": 0.0,
        "total_current_peak_to_peak": 0.0,
        "phase_angle_deg": 0.0,
        "voltage_rms": 0.0,
        "apparent_power_va": 0.0,
        "active_power_w": 0.0,
        "reactive_power_var": 0.0,
        "power_factor": 0.0,
        "complex_power_real_w": 0.0,
        "complex_power_imag_var": 0.0,
        "series_mismatch_rms": 0.0,
        "warnings": [],
        "graph": generate_voltage_current_grafic([], [], [], "Total Current Analysis")[0],
        "vdiv_str": "",
        "vdiv2_str": "",
        "tdiv_str": "",
    }
    if not state_get("total_current_enabled"):
        return empty

    saved_metadata = current_file_snapshots
    if not saved_metadata:
        return empty

    analysis_signals = {
        "X": ch1,
        "Y": ch2,
        "MATH": math_result if math_result is not None else np.array([]),
    }
    visual_signals = {
        "X": ch1_visual,
        "Y": ch2_visual,
        "MATH": math_result_visual if math_result_visual is not None else np.array([]),
    }
    voltage = np.asarray(analysis_signals.get(settings["voltage_channel"], ch1), dtype=float)
    voltage_visual = np.asarray(visual_signals.get(settings["voltage_channel"], ch1_visual), dtype=float)
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
    compatible_samples = []
    incompatible_count = 0
    for item in saved_metadata:
        sample = cache_get(CURRENT_WAVEFORM_STORE, item["id"])
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
        compatible_samples.append(sample)

    used_count = len(compatible_samples)
    if used_count == 0:
        empty["incompatible_count"] = incompatible_count
        empty["warnings"] = warnings or ["No hay corrientes compatibles para combinar con la referencia actual."]
        return empty

    aligned_currents = []
    combination_mode = "parallel"
    for sample in compatible_samples:
        aligned_currents.append(
            _resample_current_to_reference(reference_time_axis, reference_frequency_hz, reference_voltage_template, sample)
        )
    stacked_currents = np.vstack(aligned_currents)
    total_current = np.sum(stacked_currents, axis=0)
    series_mismatch_rms = 0.0

    finite_current = total_current[np.isfinite(total_current)]
    if finite_current.size == 0:
        return empty

    phase_data = calculate_voltage_current_phase_angle(voltage, total_current, fs)
    power_data = calculate_power_analysis(voltage, total_current, fs)
    graph_key = (
        "total_current_graph",
        state_get("file_wav"),
        settings["voltage_channel"],
        settings["combination_mode"],
        settings["frequency_tolerance_percent"],
        tuple(item["id"] for item in saved_metadata),
        state_get("math_operation"),
    )
    _cached_tcg = cache_get(GRAPH_CACHE, graph_key)
    if _cached_tcg is None:
        _tcg, _tcv, _tcv2, _tct = generate_voltage_current_grafic(
            reference_time_axis,
            voltage_visual,
            total_current,
            f"Total Current Analysis {settings['voltage_channel']}",
            voltage_channel=settings["voltage_channel"],
        )
        cache_set(GRAPH_CACHE, graph_key, (_tcg, _tcv, _tcv2, _tct))
    else:
        _tcg, _tcv, _tcv2, _tct = _cached_tcg

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
        "voltage_rms": power_data.get("voltage_rms", 0.0),
        "apparent_power_va": power_data.get("apparent_power_va", 0.0),
        "active_power_w": power_data.get("active_power_w", 0.0),
        "reactive_power_var": power_data.get("reactive_power_var", 0.0),
        "power_factor": power_data.get("power_factor", 0.0),
        "complex_power_real_w": power_data.get("complex_power_real_w", 0.0),
        "complex_power_imag_var": power_data.get("complex_power_imag_var", 0.0),
        "series_mismatch_rms": series_mismatch_rms,
        "warnings": warnings,
        "graph": _tcg,
        "vdiv_str": _tcv,
        "vdiv2_str": _tcv2,
        "tdiv_str": _tct,
        "current": total_current,
    }


def build_correlation_view(ch1, ch2, fs, file_name):
    if not state_get("correlation_enabled"):
        _cg, _cv, _ct = generate_correlation_grafic([], [], "Correlation")
        return {
            "lags_seconds": np.array([]),
            "correlation": np.array([]),
            "max_correlation": 0.0,
            "delay_seconds": 0.0,
            "delay_value": 0.0,
            "delay_unit": "s",
            "enabled": False,
            "graph": _cg,
            "vdiv_str": _cv,
            "tdiv_str": _ct,
        }

    cache_key = ("correlation", state_get("file_wav"))
    cached = cache_get(ANALYSIS_CACHE, cache_key)
    if cached is not None:
        return cached

    correlation_data = calculate_correlation_analysis(ch1, ch2, fs)
    correlation_data["enabled"] = True
    graph_key = get_correlation_graph_key()
    _cached_corrg = cache_get(GRAPH_CACHE, graph_key)
    if _cached_corrg is None:
        _cg, _cv, _ct = generate_correlation_grafic(
            correlation_data["lags_seconds"],
            correlation_data["correlation"],
            "Correlation",
            marker_x=correlation_data["delay_seconds"],
            marker_y=correlation_data["max_correlation"],
        )
        cache_set(GRAPH_CACHE, graph_key, (_cg, _cv, _ct))
    else:
        _cg, _cv, _ct = _cached_corrg
    correlation_data["graph"] = _cg
    correlation_data["vdiv_str"] = _cv
    correlation_data["tdiv_str"] = _ct
    return cache_set(ANALYSIS_CACHE, cache_key, correlation_data)


def build_transfer_view(ch1, ch2, math_result, ch1_visual, ch2_visual, math_result_visual, fs, time_axis, file_name):
    settings = get_transfer_settings()
    empty = {
        "input_channel": settings["input_channel"],
        "output_channel": settings["output_channel"],
        "vin_rms": 0.0,
        "vout_rms": 0.0,
        "vin_vpp": 0.0,
        "vout_vpp": 0.0,
        "gain_rms": 0.0,
        "gain_vpp": 0.0,
        "gain_db": 0.0,
        "phase_angle_deg": 0.0,
        "frequency_hz": 0.0,
        "delay_value": 0.0,
        "delay_unit": "s",
        "delay_seconds": 0.0,
        "correlation_peak": 0.0,
        "graph": generate_grafic([], [], [], "Transfer Analysis", show_empty=True),
        "enabled": False,
    }
    if not state_get("transfer_enabled"):
        return empty

    analysis_signals = {
        "X": ch1,
        "Y": ch2,
        "MATH": math_result if math_result is not None else np.array([]),
    }
    visual_signals = {
        "X": ch1_visual,
        "Y": ch2_visual,
        "MATH": math_result_visual if math_result_visual is not None else np.array([]),
    }
    vin = np.asarray(analysis_signals.get(settings["input_channel"], ch1), dtype=float)
    vout = np.asarray(analysis_signals.get(settings["output_channel"], ch2), dtype=float)
    vin_visual = np.asarray(visual_signals.get(settings["input_channel"], ch1_visual), dtype=float)
    vout_visual = np.asarray(visual_signals.get(settings["output_channel"], ch2_visual), dtype=float)
    cache_key = (
        "transfer",
        state_get("file_wav"),
        settings["input_channel"],
        settings["output_channel"],
        state_get("math_operation"),
    )
    cached = cache_get(ANALYSIS_CACHE, cache_key)
    if cached is not None:
        return cached

    transfer_data = calculate_transfer_analysis(vin, vout, fs)
    transfer_data["input_channel"] = settings["input_channel"]
    transfer_data["output_channel"] = settings["output_channel"]
    transfer_data["graph"] = generate_grafic(
        time_axis,
        vin_visual,
        vout_visual,
        f"Transfer Analysis {settings['input_channel']} vs {settings['output_channel']}",
        show_empty=True,
    )
    return cache_set(ANALYSIS_CACHE, cache_key, transfer_data)


def build_xy_view(ch1, ch2, math_result, ch1_visual, ch2_visual, math_result_visual):
    settings = get_xy_settings()
    _xyg, _xyv, _xyt = generate_xy_mode_grafic([], [], "X-Y Mode", f"{settings['x_channel']} (V)", f"{settings['y_channel']} (V)")
    empty = {
        "x_channel": settings["x_channel"],
        "y_channel": settings["y_channel"],
        "sample_count": 0,
        "x_min": 0.0,
        "x_max": 0.0,
        "y_min": 0.0,
        "y_max": 0.0,
        "x_rms": 0.0,
        "y_rms": 0.0,
        "correlation_coefficient": 0.0,
        "graph": _xyg,
        "vdiv_str": _xyv,
        "tdiv_str": _xyt,
        "enabled": False,
    }
    if not state_get("xy_enabled"):
        return empty

    analysis_signals = {
        "X": np.asarray(ch1, dtype=float),
        "Y": np.asarray(ch2, dtype=float),
        "MATH": np.asarray(math_result if math_result is not None else np.array([]), dtype=float),
    }
    visual_signals = {
        "X": np.asarray(ch1_visual, dtype=float),
        "Y": np.asarray(ch2_visual, dtype=float),
        "MATH": np.asarray(math_result_visual if math_result_visual is not None else np.array([]), dtype=float),
    }
    x_signal = analysis_signals.get(settings["x_channel"], analysis_signals["X"])
    y_signal = analysis_signals.get(settings["y_channel"], analysis_signals["Y"])
    x_signal_visual = visual_signals.get(settings["x_channel"], visual_signals["X"])
    y_signal_visual = visual_signals.get(settings["y_channel"], visual_signals["Y"])
    length = min(x_signal.size, y_signal.size)
    if length == 0:
        return empty

    cache_key = (
        "xy",
        state_get("file_wav"),
        settings["x_channel"],
        settings["y_channel"],
        state_get("math_operation"),
    )
    cached = cache_get(ANALYSIS_CACHE, cache_key)
    if cached is not None:
        return cached

    x_signal = x_signal[:length]
    y_signal = y_signal[:length]
    x_signal_visual = x_signal_visual[:length]
    y_signal_visual = y_signal_visual[:length]
    finite_mask = np.isfinite(x_signal) & np.isfinite(y_signal)
    x_finite = x_signal[finite_mask]
    y_finite = y_signal[finite_mask]
    x_finite_visual = x_signal_visual[finite_mask]
    y_finite_visual = y_signal_visual[finite_mask]
    if x_finite.size == 0 or y_finite.size == 0:
        return empty

    graph_key = get_xy_graph_key(settings["x_channel"], settings["y_channel"])
    _cached_xyg = cache_get(GRAPH_CACHE, graph_key)
    x_label = f"{settings['x_channel']} (V)"
    y_label = f"{settings['y_channel']} (V)"
    if _cached_xyg is None:
        _xyg, _xyv, _xyt = generate_xy_mode_grafic(
            x_finite_visual,
            y_finite_visual,
            f"X-Y Mode {settings['x_channel']} vs {settings['y_channel']}",
            x_label,
            y_label,
        )
        cache_set(GRAPH_CACHE, graph_key, (_xyg, _xyv, _xyt))
    else:
        _xyg, _xyv, _xyt = _cached_xyg

    correlation_coefficient = 0.0
    if x_finite.size > 1 and y_finite.size > 1:
        x_std = float(np.std(x_finite))
        y_std = float(np.std(y_finite))
        if x_std > 0 and y_std > 0:
            correlation_coefficient = round(float(np.corrcoef(x_finite, y_finite)[0, 1]), 6)

    xy_data = {
        "x_channel": settings["x_channel"],
        "y_channel": settings["y_channel"],
        "sample_count": int(x_finite.size),
        "x_min": round(float(np.min(x_finite)), 6),
        "x_max": round(float(np.max(x_finite)), 6),
        "y_min": round(float(np.min(y_finite)), 6),
        "y_max": round(float(np.max(y_finite)), 6),
        "x_rms": round(float(np.sqrt(np.mean(x_finite ** 2))), 6),
        "y_rms": round(float(np.sqrt(np.mean(y_finite ** 2))), 6),
        "correlation_coefficient": correlation_coefficient,
        "graph": _xyg,
        "vdiv_str": _xyv,
        "tdiv_str": _xyt,
        "enabled": True,
    }
    return cache_set(ANALYSIS_CACHE, cache_key, xy_data)


def _scale_time_value(time_seconds):
    if time_seconds >= 1:
        return round(time_seconds, 6), "s"
    if time_seconds >= 1e-3:
        return round(time_seconds * 1e3, 3), "ms"
    if time_seconds >= 1e-6:
        return round(time_seconds * 1e6, 3), "us"
    return round(time_seconds * 1e9, 3), "ns"


def build_cursor_view(ch1, ch2, math_result, ch1_visual, ch2_visual, math_result_visual, time_axis, fs=None):
    settings = get_cursor_settings()
    mode = settings.get("mode", "single")
    empty = {
        "mode": mode,
        "channel": settings["channel"],
        "signal_a": settings.get("signal_a", "X"),
        "signal_b": settings.get("signal_b", "Y"),
        "t1": 0.0,
        "t2": 0.0,
        "t1_input": settings["t1"],
        "t2_input": settings["t2"],
        "v1": 0.0,
        "v2": 0.0,
        "delta_t": 0.0,
        "delta_t_unit": "s",
        "delta_v": 0.0,
        "delta_phi": 0.0,
        "period": 0.0,
        "period_unit": "s",
        "estimated_frequency": 0.0,
        "estimated_frequency_unit": "Hz",
        "graph": None,
        "time_min": 0.0,
        "time_max": 1.0,
        "voltage_min": -1.0,
        "voltage_max": 1.0,
        "voltage_min_a": -1.0,
        "voltage_max_a": 1.0,
        "voltage_min_b": -1.0,
        "voltage_max_b": 1.0,
        "plot_points": [],
        "plot_points_b": [],
        "enabled": False,
    }
    if not state_get("cursor_enabled"):
        return empty

    if mode == "dual":
        return _build_dual_cursor_view(
            ch1, ch2, math_result,
            ch1_visual, ch2_visual, math_result_visual,
            time_axis, fs, settings,
        )

    cache_key = (
        "cursor",
        state_get("file_wav"),
        settings["channel"],
        settings["t1"],
        settings["t2"],
        state_get("math_operation"),
    )
    cached = cache_get(ANALYSIS_CACHE, cache_key)
    if cached is not None:
        return cached

    analysis_signals = {"X": ch1, "Y": ch2, "MATH": math_result if math_result is not None else np.array([])}
    visual_signals = {"X": ch1_visual, "Y": ch2_visual, "MATH": math_result_visual if math_result_visual is not None else np.array([])}
    selected_signal = analysis_signals.get(settings["channel"], ch1)
    selected_signal_visual = visual_signals.get(settings["channel"], ch1_visual)
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
        selected_signal_visual,
        time_axis,
        float(settings["t1"]),
        float(settings["t2"]),
    )
    measurement["mode"] = "single"
    measurement["signal_a"] = settings["channel"]
    measurement["signal_b"] = "Y"
    measurement["channel"] = settings["channel"]
    measurement["t1_input"] = settings["t1"]
    measurement["t2_input"] = settings["t2"]
    measurement["time_min"] = float(time_axis[0]) if len(time_axis) else 0.0
    measurement["time_max"] = float(time_axis[-1]) if len(time_axis) else 1.0
    if len(selected_signal_visual):
        vmin = float(np.min(selected_signal_visual))
        vmax = float(np.max(selected_signal_visual))
        max_abs = max(abs(vmin), abs(vmax), 1e-9)
        measurement["voltage_min"] = -max_abs
        measurement["voltage_max"] = max_abs
        point_count = min(1200, len(selected_signal_visual))
        sample_indices = np.unique(np.linspace(0, len(selected_signal_visual) - 1, num=point_count, dtype=int))
        measurement["plot_points"] = [
            {
                "t": round(float(time_axis[index]), 9),
                "v": round(float(selected_signal_visual[index]), 6),
            }
            for index in sample_indices
        ]
    else:
        measurement["voltage_min"] = -1.0
        measurement["voltage_max"] = 1.0
        measurement["plot_points"] = []
    measurement["plot_points_b"] = []
    measurement["delta_phi"] = 0.0
    measurement["period"] = 0.0
    measurement["period_unit"] = "s"
    return cache_set(ANALYSIS_CACHE, cache_key, measurement)


def _get_signal_by_channel(ch1, ch2, math_result, channel):
    signals = {"X": ch1, "Y": ch2, "MATH": math_result if math_result is not None else np.array([])}
    return signals.get(channel, ch1)


def _get_visual_signal_by_channel(ch1_visual, ch2_visual, math_result_visual, channel):
    signals = {"X": ch1_visual, "Y": ch2_visual, "MATH": math_result_visual if math_result_visual is not None else np.array([])}
    return signals.get(channel, ch1_visual)


def _build_dual_cursor_view(ch1, ch2, math_result, ch1_visual, ch2_visual, math_result_visual, time_axis, fs, settings):
    signal_a_ch = settings.get("signal_a", "X")
    signal_b_ch = settings.get("signal_b", "Y")
    signal_a_visual = _get_visual_signal_by_channel(ch1_visual, ch2_visual, math_result_visual, signal_a_ch)
    signal_b_visual = _get_visual_signal_by_channel(ch1_visual, ch2_visual, math_result_visual, signal_b_ch)
    signal_a_analysis = _get_signal_by_channel(ch1, ch2, math_result, signal_a_ch)

    if len(time_axis):
        start_time = float(time_axis[0])
        end_time = float(time_axis[-1])
        if settings["t1"] == "" or settings["t2"] == "":
            span = end_time - start_time
            default_t1 = start_time + span * 0.33
            default_t2 = start_time + span * 0.66
            settings["t1"] = f"{default_t1:.9f}"
            settings["t2"] = f"{default_t2:.9f}"

    t1 = float(settings["t1"])
    t2 = float(settings["t2"])

    start = min(t1, t2)
    end = max(t1, t2)
    start = max(start, float(time_axis[0])) if len(time_axis) else start
    end = min(end, float(time_axis[-1])) if len(time_axis) else end
    delta_t_seconds = end - start if end > start else 0.0
    delta_t_value, delta_t_unit = _scale_time_value(delta_t_seconds)

    period = 0.0
    freq_hz = 0.0
    if fs and fs > 0 and signal_a_analysis.size >= 4:
        freq_hz = estimate_frequency_hz(signal_a_analysis, fs)
    if freq_hz > 0:
        period = 1.0 / freq_hz
    elif delta_t_seconds > 0:
        period = delta_t_seconds

    delta_phi_deg = ((delta_t_seconds / period) * 360.0) % 360.0 if period > 0 else 0.0

    from signal_analyzer import scale_frequency_value
    freq_val, freq_unit, _ = scale_frequency_value(freq_hz) if freq_hz > 0 else (0.0, "Hz", 1)
    period_val, period_unit = _scale_time_value(period)

    v1 = 0.0
    if len(time_axis) and len(signal_a_visual) == len(time_axis):
        t1_clamped = max(time_axis[0], min(t1, time_axis[-1]))
        v1 = float(np.interp(t1_clamped, time_axis, signal_a_visual))
    v2 = 0.0
    if len(time_axis) and len(signal_b_visual) == len(time_axis):
        t2_clamped = max(time_axis[0], min(t2, time_axis[-1]))
        v2 = float(np.interp(t2_clamped, time_axis, signal_b_visual))

    base = {
        "mode": "dual",
        "signal_a": signal_a_ch,
        "signal_b": signal_b_ch,
        "channel": "X",
        "t1": round(t1, 9),
        "t2": round(t2, 9),
        "t1_input": settings["t1"],
        "t2_input": settings["t2"],
        "v1": round(v1, 6),
        "v2": round(v2, 6),
        "delta_t": delta_t_value,
        "delta_t_unit": delta_t_unit,
        "delta_v": 0.0,
        "delta_phi": round(delta_phi_deg, 2),
        "estimated_frequency": freq_val,
        "estimated_frequency_unit": freq_unit,
        "period": period_val,
        "period_unit": period_unit,
        "graph": None,
        "time_min": float(time_axis[0]) if len(time_axis) else 0.0,
        "time_max": float(time_axis[-1]) if len(time_axis) else 1.0,
        "plot_points": [],
        "enabled": True,
    }

    all_voltages = []
    line_points_a = []
    line_points_b = []
    point_count = min(1200, len(time_axis))
    sample_indices = np.unique(np.linspace(0, len(time_axis) - 1, num=point_count, dtype=int)) if len(time_axis) else []

    if len(signal_a_visual) and len(time_axis):
        vmin_a = float(np.min(signal_a_visual))
        vmax_a = float(np.max(signal_a_visual))
        all_voltages.extend([vmin_a, vmax_a])
        line_points_a = [
            {
                "t": round(float(time_axis[index]), 9),
                "v": round(float(signal_a_visual[index]), 6),
            }
            for index in sample_indices if index < len(signal_a_visual)
        ]

    if len(signal_b_visual) and len(time_axis):
        vmin_b = float(np.min(signal_b_visual))
        vmax_b = float(np.max(signal_b_visual))
        all_voltages.extend([vmin_b, vmax_b])
        line_points_b = [
            {
                "t": round(float(time_axis[index]), 9),
                "v": round(float(signal_b_visual[index]), 6),
            }
            for index in sample_indices if index < len(signal_b_visual)
        ]

    if len(signal_a_visual):
        max_abs_a = max(abs(vmin_a), abs(vmax_a), 1e-9)
        base["voltage_min_a"] = -max_abs_a
        base["voltage_max_a"] = max_abs_a
    else:
        base["voltage_min_a"] = -1.0
        base["voltage_max_a"] = 1.0

    if len(signal_b_visual):
        max_abs_b = max(abs(vmin_b), abs(vmax_b), 1e-9)
        base["voltage_min_b"] = -max_abs_b
        base["voltage_max_b"] = max_abs_b
    else:
        base["voltage_min_b"] = -1.0
        base["voltage_max_b"] = 1.0

    if all_voltages:
        overall_min = min(all_voltages)
        overall_max = max(all_voltages)
        max_abs = max(abs(overall_min), abs(overall_max), 1e-9)
        base["voltage_min"] = -max_abs
        base["voltage_max"] = max_abs
    else:
        base["voltage_min"] = -1.0
        base["voltage_max"] = 1.0

    base["plot_points"] = line_points_a
    base["plot_points_b"] = line_points_b

    return base


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
    if not state_get("cycle_enabled"):
        return empty

    signals = {"X": ch1, "Y": ch2, "MATH": math_result if math_result is not None else np.array([])}
    cache_key = (
        "cycle",
        state_get("file_wav"),
        settings["channel"],
        state_get("math_operation"),
    )
    cached = cache_get(ANALYSIS_CACHE, cache_key)
    if cached is not None:
        return cached

    cycle_data = calculate_cycle_analysis(signals.get(settings["channel"], ch1), fs)
    cycle_data["channel"] = settings["channel"]
    return cache_set(ANALYSIS_CACHE, cache_key, cycle_data)


def build_calibration_view(raw_ch1=None, raw_ch2=None, time_axis=None):
    settings = get_calibration_settings()
    settings["enabled"] = bool(state_get("calibration_enabled"))
    if raw_ch1 is not None and raw_ch2 is not None and time_axis is not None:
        try:
            from signal_analyzer import apply_signal_calibration
            cal_ch1, cal_ch2 = apply_signal_calibration(raw_ch1, raw_ch2, settings)
            raw_plot = generate_grafic(time_axis, raw_ch1, raw_ch2, "Original (preview)", {},
                                       show_empty=True)
            cal_plot = generate_grafic(time_axis, cal_ch1, cal_ch2, "Calibrated (preview)", {},
                                       show_empty=True)
            settings["preview_original"] = raw_plot
            settings["preview_calibrated"] = cal_plot
            # V/div derived from the actual calibrated signal amplitude (same
            # formula used by OscilloscopePlotter when no scope_config is given)
            import numpy as np
            cal_ch1_arr = np.asarray(cal_ch1) if cal_ch1 is not None else np.array([])
            cal_ch2_arr = np.asarray(cal_ch2) if cal_ch2 is not None else np.array([])
            settings["cal_ch1_vdiv_str"] = _fmt_vdiv(_compute_vdiv_from_data(cal_ch1_arr)) if cal_ch1_arr.size > 0 else ""
            settings["cal_ch2_vdiv_str"] = _fmt_vdiv(_compute_vdiv_from_data(cal_ch2_arr)) if cal_ch2_arr.size > 0 else ""
        except Exception:
            settings["preview_original"] = None
            settings["preview_calibrated"] = None
            settings["cal_ch1_vdiv_str"] = ""
            settings["cal_ch2_vdiv_str"] = ""
    else:
        settings["preview_original"] = None
        settings["preview_calibrated"] = None
        settings["cal_ch1_vdiv_str"] = ""
        settings["cal_ch2_vdiv_str"] = ""
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
    snapshots = state_get("snapshots", [])
    snapshots.append(
        {
            "id": uuid.uuid4().hex,
            "name": snapshot_name,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            **summarize_current_analysis(file_name, measures, fft_data),
        }
    )
    state_set("snapshots", snapshots[-10:])


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
    if not state_get("comparison_enabled"):
        return empty

    snapshot_id = state_get("comparison_snapshot_id")
    snapshot = next((item for item in state_get("snapshots", []) if item["id"] == snapshot_id), None)
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


_EMPTY_GRAPH_CACHE = {}

def _cached_empty_graph(key, generator):
    if key not in _EMPTY_GRAPH_CACHE:
        _EMPTY_GRAPH_CACHE[key] = generator()
    return _EMPTY_GRAPH_CACHE[key]

def build_empty_view(error_message=None, toast_message=None, toast_variant="success"):
    empty_stats = calculate_signal_statistics(np.array([]))
    empty_advanced = calculate_advanced_measures(np.array([]), 0)
    return {
        "file": None,
        "file_name": "No File",
        "config": DEFAULT_CONFIG,
        "measures": DEFAULT_MEASURES,
        "grafica": _cached_empty_graph("main", lambda: generate_grafic(T_CLEAR, CH_CLEAR, CH_CLEAR, "No File", DEFAULT_MEASURES)),
        "grafica_math": _cached_empty_graph("math", lambda: generate_grafic(T_CLEAR, [], [], "MATH", math_result=None, show_empty=True)),
        "math_operation": None,
        "math_measures": DEFAULT_MATH_MEASURES.copy(),
        "fft_graph": _cached_empty_graph("fft", lambda: generate_fft_grafic([], [], "", "X")[0]),
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
            "hz_div_str": "",
            "mag_div_str": "",
        },
        "statistics_data": {"X": empty_stats, "Y": empty_stats, "MATH": empty_stats, "math_enabled": False, "enabled": False},
        "advanced_data": {"X": empty_advanced, "Y": empty_advanced, "MATH": empty_advanced, "math_enabled": False, "enabled": False},
        "calculus_data": {
            "channel": "X",
            "enabled": False,
            "derivative_peak": 0.0,
            "integral_final": 0.0,
            "derivative_graph": _cached_empty_graph("derivative", lambda: generate_signal_analysis_grafic([], [], "Derivative X", "dV/dt (V/s)", channel="X")[0]),
            "derivative_vdiv_str": "",
            "derivative_tdiv_str": "",
            "integral_graph": _cached_empty_graph("integral", lambda: generate_signal_analysis_grafic([], [], "Integral X", "Integral (V*s)", channel="X")[0]),
            "integral_vdiv_str": "",
            "integral_tdiv_str": "",
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
            "voltage_rms": 0.0,
            "apparent_power_va": 0.0,
            "active_power_w": 0.0,
            "reactive_power_var": 0.0,
            "power_factor": 0.0,
            "complex_power_real_w": 0.0,
            "complex_power_imag_var": 0.0,
            "detected_frequency_hz": 0.0,
            "inductor_initial_mode": "zero",
            "inductor_initial_value_input": "0",
            "warnings": [],
            "current": np.array([]),
            "graph": _cached_empty_graph("current", lambda: generate_voltage_current_grafic([], [], [], "Current Analysis")[0]),
            "vdiv_str": "",
            "vdiv2_str": "",
            "tdiv_str": "",
            "enabled": False,
        },
        "transfer_data": {
            "input_channel": "X",
            "output_channel": "Y",
            "vin_rms": 0.0,
            "vout_rms": 0.0,
            "vin_vpp": 0.0,
            "vout_vpp": 0.0,
            "gain_rms": 0.0,
            "gain_vpp": 0.0,
            "gain_db": 0.0,
            "phase_angle_deg": 0.0,
            "frequency_hz": 0.0,
            "delay_value": 0.0,
            "delay_unit": "s",
            "delay_seconds": 0.0,
            "correlation_peak": 0.0,
            "graph": _cached_empty_graph("transfer", lambda: generate_grafic([], [], [], "Transfer Analysis", show_empty=True)),
            "enabled": False,
        },
        "xy_data": {
            "x_channel": "X",
            "y_channel": "Y",
            "sample_count": 0,
            "x_min": 0.0,
            "x_max": 0.0,
            "y_min": 0.0,
            "y_max": 0.0,
            "x_rms": 0.0,
            "y_rms": 0.0,
            "correlation_coefficient": 0.0,
            "graph": _cached_empty_graph("xy", lambda: generate_xy_mode_grafic([], [], "X-Y Mode", "X (V)", "Y (V)")[0]),
            "vdiv_str": "",
            "tdiv_str": "",
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
            "voltage_rms": 0.0,
            "apparent_power_va": 0.0,
            "active_power_w": 0.0,
            "reactive_power_var": 0.0,
            "power_factor": 0.0,
            "complex_power_real_w": 0.0,
            "complex_power_imag_var": 0.0,
            "series_mismatch_rms": 0.0,
            "warnings": [],
            "graph": _cached_empty_graph("total_current", lambda: generate_voltage_current_grafic([], [], [], "Total Current Analysis")[0]),
            "vdiv_str": "",
            "vdiv2_str": "",
            "tdiv_str": "",
        },
        "correlation_data": {
            "enabled": False,
            "max_correlation": 0.0,
            "delay_value": 0.0,
            "delay_unit": "s",
            "graph": _cached_empty_graph("correlation", lambda: generate_correlation_grafic([], [], "Correlation")[0]),
            "vdiv_str": "",
            "tdiv_str": "",
        },
        "calibration_data": build_calibration_view(),
        "cursor_data": {
            "mode": "single",
            "channel": "X",
            "signal_a": "X",
            "signal_b": "Y",
            "t1": 0,
            "t2": 0,
            "t1_input": "",
            "t2_input": "",
            "v1": 0,
            "v2": 0,
            "delta_t": 0,
            "delta_t_unit": "s",
            "delta_v": 0,
            "delta_phi": 0.0,
            "period": 0.0,
            "period_unit": "s",
            "estimated_frequency": 0,
            "estimated_frequency_unit": "Hz",
            "graph": None,
            "time_min": 0.0,
            "time_max": 1.0,
            "voltage_min": -1.0,
            "voltage_max": 1.0,
            "plot_points": [],
            "plot_points_b": [],
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
        "snapshots": state_get("snapshots", []),
        "current_snapshots": state_get("current_snapshots", []),
        "digital_data": state_get("digital_data", {}),
        "ch1_name": "CH1",
        "ch2_name": "CH2",
        "error_message": error_message,
        "toast_message": toast_message,
        "toast_variant": toast_variant,
    }


def should_refresh_all(action_name):
    return action_name in {"upload", "math"}


def prepare_analysis_context(action_name=None):
    file_path = state_get("file_wav")
    if not file_path or not os.path.exists(file_path):
        return None

    config = state_get("config", DEFAULT_CONFIG)
    measures = state_get("measures", DEFAULT_MEASURES)
    file_name = state_get("original_name", "No File")

    processed = get_processed_signals(file_path, config, measures)
    raw_ch1 = processed.get("ch1")
    raw_ch2 = processed.get("ch2")
    ch1_analysis = processed["ch1_analysis"]
    ch2_analysis = processed["ch2_analysis"]
    math_result_analysis = processed["math_result_analysis"]
    ch1_visual = processed["ch1_visual"]
    ch2_visual = processed["ch2_visual"]
    math_result_visual = processed["math_result_visual"]
    fs = processed["fs"]
    time_axis = processed["time_axis"]
    math_measures = processed["math_measures"]

    full_refresh = should_refresh_all(action_name)

    if full_refresh or action_name == "fft" or state_get("fft_data") is None:
        fft_graph, fft_data = build_fft_view(ch1_analysis, ch2_analysis, math_result_analysis, fs, file_name)
    else:
        fft_data = state_get("fft_data", {})
        raw_max_frequency = fft_data.get("max_frequency", "")
        _fft_cached = cache_get(GRAPH_CACHE, get_fft_graph_key(raw_max_frequency))
        if _fft_cached is None:
            fft_graph, fft_data = build_fft_view(ch1_analysis, ch2_analysis, math_result_analysis, fs, file_name)
        else:
            fft_graph = _fft_cached[0] if isinstance(_fft_cached, tuple) else _fft_cached

    if full_refresh or action_name == "statistics" or state_get("statistics_data") is None:
        # Usar ch1_visual/ch2_visual (señal suavizada y convertida a voltaje real)
        # para que los valores Min/Max de la tabla Measurements coincidan con la gráfica principal.
        statistics_data = build_statistics_view(ch1_visual, ch2_visual, math_result_analysis)
    else:
        statistics_data = state_get("statistics_data")

    if full_refresh or action_name == "advanced" or state_get("advanced_data") is None:
        advanced_data = build_advanced_view(ch1_analysis, ch2_analysis, math_result_analysis, fs)
    else:
        advanced_data = state_get("advanced_data")

    if full_refresh or action_name == "calculus" or state_get("calculus_data") is None:
        calculus_data = build_calculus_view(ch1_analysis, ch2_analysis, math_result_analysis, fs, time_axis, file_name)
    else:
        calculus_data = state_get("calculus_data", {})
        selected_channel = calculus_data.get("channel", get_calculus_settings()["channel"])
        derivative_graph = cache_get(GRAPH_CACHE, get_derivative_graph_key(selected_channel))
        integral_graph = cache_get(GRAPH_CACHE, get_integral_graph_key(selected_channel))
        if derivative_graph is None or integral_graph is None:
            calculus_data = build_calculus_view(ch1_analysis, ch2_analysis, math_result_analysis, fs, time_axis, file_name)
        else:
            calculus_data = {
                "channel": selected_channel,
                "enabled": bool(state_get("calculus_enabled")),
                "derivative_peak": calculus_data.get("derivative_peak", 0.0),
                "integral_final": calculus_data.get("integral_final", 0.0),
                "derivative_graph": derivative_graph,
                "integral_graph": integral_graph,
            }

    if full_refresh or action_name == "current" or state_get("current_data") is None:
        current_data = build_current_view(
            ch1_analysis,
            ch2_analysis,
            math_result_analysis,
            ch1_visual,
            ch2_visual,
            math_result_visual,
            fs,
            time_axis,
            file_name,
        )
    else:
        current_data = state_get("current_data", {})
        selected_channel = current_data.get("channel", get_current_settings()["channel"])
        method = current_data.get("method", get_current_settings()["method"])
        component_value = current_data.get("component_value", 0.0)
        current_graph = cache_get(GRAPH_CACHE, get_current_graph_key(selected_channel, method, component_value))
        if current_graph is None:
            current_data = build_current_view(
                ch1_analysis,
                ch2_analysis,
                math_result_analysis,
                ch1_visual,
                ch2_visual,
                math_result_visual,
                fs,
                time_axis,
                file_name,
            )
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
                "voltage_rms": current_data.get("voltage_rms", 0.0),
                "apparent_power_va": current_data.get("apparent_power_va", 0.0),
                "active_power_w": current_data.get("active_power_w", 0.0),
                "reactive_power_var": current_data.get("reactive_power_var", 0.0),
                "power_factor": current_data.get("power_factor", 0.0),
                "complex_power_real_w": current_data.get("complex_power_real_w", 0.0),
                "complex_power_imag_var": current_data.get("complex_power_imag_var", 0.0),
                "detected_frequency_hz": current_data.get("detected_frequency_hz", 0.0),
                "inductor_initial_mode": current_data.get("inductor_initial_mode", get_current_settings()["inductor_initial_mode"]),
                "inductor_initial_value_input": current_data.get("inductor_initial_value_input", get_current_settings()["inductor_initial_value"]),
                "warnings": current_data.get("warnings", []),
                "graph": current_graph,
                "enabled": bool(state_get("current_enabled")),
            }

    transfer_data = build_transfer_view(
        ch1_analysis,
        ch2_analysis,
        math_result_analysis,
        ch1_visual,
        ch2_visual,
        math_result_visual,
        fs,
        time_axis,
        file_name,
    )

    if full_refresh or action_name == "xy" or state_get("xy_data") is None:
        xy_data = build_xy_view(
            ch1_analysis,
            ch2_analysis,
            math_result_analysis,
            ch1_visual,
            ch2_visual,
            math_result_visual,
        )
    else:
        xy_data = state_get("xy_data", {})
        settings = get_xy_settings()
        xy_graph = cache_get(GRAPH_CACHE, get_xy_graph_key(settings["x_channel"], settings["y_channel"]))
        if xy_graph is None:
            xy_data = build_xy_view(
                ch1_analysis,
                ch2_analysis,
                math_result_analysis,
                ch1_visual,
                ch2_visual,
                math_result_visual,
            )
        else:
            xy_data = {
                "x_channel": settings["x_channel"],
                "y_channel": settings["y_channel"],
                "sample_count": xy_data.get("sample_count", 0),
                "x_min": xy_data.get("x_min", 0.0),
                "x_max": xy_data.get("x_max", 0.0),
                "y_min": xy_data.get("y_min", 0.0),
                "y_max": xy_data.get("y_max", 0.0),
                "x_rms": xy_data.get("x_rms", 0.0),
                "y_rms": xy_data.get("y_rms", 0.0),
                "correlation_coefficient": xy_data.get("correlation_coefficient", 0.0),
                "graph": xy_graph,
                "enabled": bool(state_get("xy_enabled")),
            }

    total_current_data = build_total_current_view(
        ch1_analysis,
        ch2_analysis,
        math_result_analysis,
        ch1_visual,
        ch2_visual,
        math_result_visual,
        fs,
        time_axis,
        file_name,
    )

    if full_refresh or action_name == "correlation" or state_get("correlation_data") is None:
        correlation_data = build_correlation_view(ch1_analysis, ch2_analysis, fs, file_name)
    else:
        correlation_data = state_get("correlation_data", {})
        correlation_graph = cache_get(GRAPH_CACHE, get_correlation_graph_key())
        if correlation_graph is None:
            correlation_data = build_correlation_view(ch1_analysis, ch2_analysis, fs, file_name)
        else:
            correlation_data = {
                "enabled": bool(state_get("correlation_enabled")),
                "max_correlation": correlation_data.get("max_correlation", 0.0),
                "delay_value": correlation_data.get("delay_value", 0.0),
                "delay_unit": correlation_data.get("delay_unit", "s"),
                "graph": correlation_graph,
                "delay_seconds": correlation_data.get("delay_seconds", 0.0),
            }

    cursor_data = build_cursor_view(
        ch1_analysis,
        ch2_analysis,
        math_result_analysis,
        ch1_visual,
        ch2_visual,
        math_result_visual,
        time_axis,
        fs,
    )

    if full_refresh or action_name == "cycle" or state_get("cycle_data") is None:
        cycle_data = build_cycle_view(ch1_analysis, ch2_analysis, math_result_analysis, fs)
    else:
        cycle_data = state_get("cycle_data")

    if full_refresh or action_name == "comparison" or action_name == "snapshot" or state_get("comparison_data") is None:
        comparison_data = build_comparison_view(file_name, measures)
    else:
        comparison_data = state_get("comparison_data")

    return {
        "file_path": file_path,
        "file_name": file_name,
        "config": config,
        "measures": measures,
        "ch1": ch1_visual,
        "ch2": ch2_visual,
        "math_result": math_result_visual,
        "ch1_analysis": ch1_analysis,
        "ch2_analysis": ch2_analysis,
        "math_result_analysis": math_result_analysis,
        "fs": fs,
        "time_axis": time_axis,
        "math_measures": math_measures,
        "fft_graph": fft_graph,
        "fft_data": fft_data,
        "statistics_data": statistics_data,
        "advanced_data": advanced_data,
        "calculus_data": calculus_data,
        "current_data": current_data,
        "transfer_data": transfer_data,
        "xy_data": xy_data,
        "total_current_data": total_current_data,
        "correlation_data": correlation_data,
        "cursor_data": cursor_data,
        "cycle_data": cycle_data,
        "comparison_data": comparison_data,
        "calibration_data": build_calibration_view(raw_ch1=raw_ch1, raw_ch2=raw_ch2, time_axis=time_axis),
        "main_graph": get_main_graph(time_axis, ch1_visual, ch2_visual, file_name, measures, file_path, ch1_name=state_get("ch1_name", "CH1"), ch2_name=state_get("ch2_name", "CH2")),
        "math_graph": get_math_graph(time_axis, math_result_visual, file_path, state_get("math_operation")),
        "ch1_name": state_get("ch1_name", "CH1"),
        "ch2_name": state_get("ch2_name", "CH2"),
    }


def store_enabled_views(context):
    if context["statistics_data"]["enabled"]:
        state_set("statistics_data", context["statistics_data"])
    if context["advanced_data"]["enabled"]:
        state_set("advanced_data", context["advanced_data"])
    if context["fft_data"]["enabled"]:
        state_set("fft_data", {k: v for k, v in context["fft_data"].items() if k not in {"frequencies_hz", "magnitudes"}})
    if context["calculus_data"]["enabled"]:
        state_set("calculus_data", {
            "channel": context["calculus_data"]["channel"],
            "derivative_peak": context["calculus_data"]["derivative_peak"],
            "integral_final": context["calculus_data"]["integral_final"],
        })
    if context["current_data"]["enabled"]:
        state_set("current_data", {
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
            "voltage_rms": context["current_data"].get("voltage_rms", 0.0),
            "apparent_power_va": context["current_data"].get("apparent_power_va", 0.0),
            "active_power_w": context["current_data"].get("active_power_w", 0.0),
            "reactive_power_var": context["current_data"].get("reactive_power_var", 0.0),
            "power_factor": context["current_data"].get("power_factor", 0.0),
            "complex_power_real_w": context["current_data"].get("complex_power_real_w", 0.0),
            "complex_power_imag_var": context["current_data"].get("complex_power_imag_var", 0.0),
            "detected_frequency_hz": context["current_data"].get("detected_frequency_hz", 0.0),
            "inductor_initial_mode": context["current_data"].get("inductor_initial_mode", "zero"),
            "inductor_initial_value": context["current_data"].get("initial_current_value", 0.0),
            "inductor_initial_value_input": context["current_data"].get("inductor_initial_value_input", "0"),
            "warnings": context["current_data"].get("warnings", []),
        })
    if context["transfer_data"]["enabled"]:
        state_set("transfer_data", {
            "input_channel": context["transfer_data"]["input_channel"],
            "output_channel": context["transfer_data"]["output_channel"],
            "vin_rms": context["transfer_data"].get("vin_rms", 0.0),
            "vout_rms": context["transfer_data"].get("vout_rms", 0.0),
            "vin_vpp": context["transfer_data"].get("vin_vpp", 0.0),
            "vout_vpp": context["transfer_data"].get("vout_vpp", 0.0),
            "gain_rms": context["transfer_data"].get("gain_rms", 0.0),
            "gain_vpp": context["transfer_data"].get("gain_vpp", 0.0),
            "gain_db": context["transfer_data"].get("gain_db", 0.0),
            "phase_angle_deg": context["transfer_data"].get("phase_angle_deg", 0.0),
            "frequency_hz": context["transfer_data"].get("frequency_hz", 0.0),
            "delay_value": context["transfer_data"].get("delay_value", 0.0),
            "delay_unit": context["transfer_data"].get("delay_unit", "s"),
            "delay_seconds": context["transfer_data"].get("delay_seconds", 0.0),
            "correlation_peak": context["transfer_data"].get("correlation_peak", 0.0),
        })
    if context["xy_data"]["enabled"]:
        state_set("xy_data", {
            "x_channel": context["xy_data"]["x_channel"],
            "y_channel": context["xy_data"]["y_channel"],
            "sample_count": context["xy_data"]["sample_count"],
            "x_min": context["xy_data"]["x_min"],
            "x_max": context["xy_data"]["x_max"],
            "y_min": context["xy_data"]["y_min"],
            "y_max": context["xy_data"]["y_max"],
            "x_rms": context["xy_data"]["x_rms"],
            "y_rms": context["xy_data"]["y_rms"],
            "correlation_coefficient": context["xy_data"]["correlation_coefficient"],
        })
    if context["total_current_data"]["enabled"]:
        state_set("total_current_data", {
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
            "voltage_rms": context["total_current_data"].get("voltage_rms", 0.0),
            "apparent_power_va": context["total_current_data"].get("apparent_power_va", 0.0),
            "active_power_w": context["total_current_data"].get("active_power_w", 0.0),
            "reactive_power_var": context["total_current_data"].get("reactive_power_var", 0.0),
            "power_factor": context["total_current_data"].get("power_factor", 0.0),
            "complex_power_real_w": context["total_current_data"].get("complex_power_real_w", 0.0),
            "complex_power_imag_var": context["total_current_data"].get("complex_power_imag_var", 0.0),
            "series_mismatch_rms": context["total_current_data"].get("series_mismatch_rms", 0.0),
            "warnings": context["total_current_data"].get("warnings", []),
        })
    if context["correlation_data"]["enabled"]:
        state_set("correlation_data", {
            "max_correlation": context["correlation_data"]["max_correlation"],
            "delay_value": context["correlation_data"]["delay_value"],
            "delay_unit": context["correlation_data"]["delay_unit"],
        })
    if context["cursor_data"]["enabled"]:
        state_set("cursor_data", {
            "mode": context["cursor_data"].get("mode", "single"),
            "channel": context["cursor_data"]["channel"],
            "signal_a": context["cursor_data"].get("signal_a", "X"),
            "signal_b": context["cursor_data"].get("signal_b", "Y"),
            "t1": context["cursor_data"]["t1"],
            "t2": context["cursor_data"]["t2"],
            "t1_input": context["cursor_data"]["t1_input"],
            "t2_input": context["cursor_data"]["t2_input"],
            "v1": context["cursor_data"]["v1"],
            "v2": context["cursor_data"]["v2"],
            "delta_t": context["cursor_data"]["delta_t"],
            "delta_t_unit": context["cursor_data"]["delta_t_unit"],
            "delta_v": context["cursor_data"]["delta_v"],
            "delta_phi": context["cursor_data"].get("delta_phi", 0.0),
            "period": context["cursor_data"].get("period", 0.0),
            "period_unit": context["cursor_data"].get("period_unit", "s"),
            "estimated_frequency": context["cursor_data"]["estimated_frequency"],
            "estimated_frequency_unit": context["cursor_data"]["estimated_frequency_unit"],
        })
    if context["cycle_data"]["enabled"]:
        state_set("cycle_data", context["cycle_data"])
    if context["comparison_data"]["enabled"]:
        state_set("comparison_data", context["comparison_data"])