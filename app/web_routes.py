import os
import re
import logging
from datetime import datetime

import numpy as np
from flask import Response, after_this_request, jsonify, render_template, request, send_file, send_from_directory
from werkzeug.utils import secure_filename

from analysis_service import (
    build_comparison_view,
    build_empty_view,
    build_total_current_view,
    get_calibration_settings,
    get_fft_download_data,
    get_transfer_settings,
    get_xy_settings,
    parse_fft_max_frequency,
    parse_float_field,
    parse_nonnegative_float_field,
    parse_positive_component_value,
    parse_uploaded_scope_file,
    prepare_analysis_context,
    save_current_snapshot,
    save_snapshot,
    store_enabled_views,
)
from file_analizer import ScopeFileError
from constants import CHANNEL_COLORS_STR, TRACE_COLOR_ORANGE, TRACE_COLOR_TEAL
from plot_maker import _fmt_vdiv, _fmt_tdiv, _compute_vdiv_from_data, generate_cursor_grafic_file
from report import (
    generate_advanced_measures_latex,
    generate_calibration_latex,
    generate_comparison_latex,
    generate_config_latex,
    generate_correlation_grafic_download,
    generate_correlation_latex,
    generate_current_grafic_download,
    generate_current_latex,
    generate_current_snapshots_latex,
    generate_cursor_latex,
    generate_cycle_latex,
    generate_fft_grafic_download,
    generate_fft_latex,
    generate_grafic_download,
    generate_grafic_download_math,
    generate_math_measures_latex,
    generate_measures_latex,
    generate_signal_analysis_download,
    generate_snapshots_latex,
    generate_statistics_latex,
    generate_total_current_latex,
    generate_transfer_latex,
    generate_xy_grafic_download,
    generate_xy_latex,
)
from state_store import (
    AJAX_MODULE_ACTIONS,
    DEFAULT_CALCULUS_SETTINGS,
    DEFAULT_CALIBRATION_SETTINGS,
    DEFAULT_CURSOR_SETTINGS,
    DEFAULT_CURRENT_SETTINGS,
    DEFAULT_CYCLE_SETTINGS,
    DEFAULT_FFT_SETTINGS,
    DEFAULT_TOTAL_CURRENT_SETTINGS,
    DEFAULT_TRANSFER_SETTINGS,
    DEFAULT_XY_SETTINGS,
    UPLOAD_FOLDER,
    cleanup_file,
    clear_client_state,
    clear_loaded_state,
    get_unique_filename,
    is_allowed_file,
    state_get,
    state_pop,
    state_set,
    state_update,
)


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
        "calculus": "module-calculus",
        "current": "module-current",
        "transfer": "module-transfer",
        "xy": "module-xy",
        "correlation": "module-correlation",
        "calibration": "module-calibration",
        "cursor": "module-cursor",
        "cycle": "module-cycle",
        "snapshot": "module-snapshots",
        "comparison": "module-snapshots",
        "digital_pwm": "module-digital",
        "digital_edges": "module-digital",
        "digital_pulses": "module-digital",
        "digital_logic": "module-digital",
        "project_save": None,
        "project_load": None,
        "project_list": None,
    }

    fragments = {
        "alertHost": extract_template_fragment(rendered_html, "alert-host"),
        "pageState": extract_template_fragment(rendered_html, "page-state"),
    }

    section_fragment = section_map.get(action_name)
    if section_fragment:
        fragments["moduleSection"] = extract_template_fragment(rendered_html, section_fragment)
        fragments["moduleSectionId"] = section_fragment

    if error_message:
        fragments["error"] = error_message

    return jsonify(fragments)


def _ch_label(ch):
    if ch in ("X", "CH1"):
        return state_get("ch1_name", "CH1")
    if ch in ("Y", "CH2"):
        return state_get("ch2_name", "CH2")
    return str(ch)


def prepare_download_data(action_name=None):
    try:
        return prepare_analysis_context(action_name)
    except (OSError, ScopeFileError, ValueError, ZeroDivisionError):
        return None


def register_routes(app):
    @app.context_processor
    def inject_version():
        from version import short_version, short_build, build_info
        return {
            "app_version": short_version(),
            "app_build": short_build(),
            "app_build_info": build_info(),
        }

    @app.route("/icon.png")
    def app_icon():
        return send_from_directory(app.template_folder, "icon.png")

    @app.route("/api/version")
    def api_version():
        from version import build_info
        return jsonify(build_info())

    @app.route("/", methods=["GET", "POST"])
    def main():
        error_message = None
        toast_message = state_pop("toast_message", None)
        toast_variant = state_pop("toast_variant", "success")
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

                clear_loaded_state()
                file_path = os.path.join(UPLOAD_FOLDER, get_unique_filename())
                uploaded_file.save(file_path)

                try:
                    config, measures = parse_uploaded_scope_file(file_path)
                except (OSError, ScopeFileError, IndexError, ValueError) as exc:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    return render_template("main.html", **build_empty_view(f"Archivo no valido: {exc}"))

                ch1_name = request.form.get("ch1_name", "CH1").strip() or "CH1"
                ch2_name = request.form.get("ch2_name", "CH2").strip() or "CH2"
                invert_x = request.form.get("invert_ch1") == "on"
                invert_y = request.form.get("invert_ch2") == "on"
                initial_cal_settings = DEFAULT_CALIBRATION_SETTINGS.copy()
                initial_cal_settings["invert_x"] = invert_x
                initial_cal_settings["invert_y"] = invert_y

                state_update(
                    {
                        "file_wav": file_path,
                        "original_name": secure_filename(uploaded_file.filename) or "scope_capture.wav",
                        "ch1_name": ch1_name,
                        "ch2_name": ch2_name,
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
                        "transfer_enabled": False,
                        "transfer_settings": DEFAULT_TRANSFER_SETTINGS.copy(),
                        "xy_enabled": False,
                        "xy_settings": DEFAULT_XY_SETTINGS.copy(),
                        "total_current_enabled": False,
                        "total_current_settings": DEFAULT_TOTAL_CURRENT_SETTINGS.copy(),
                        "correlation_enabled": False,
                        "calibration_enabled": False,
                        "calibration_settings": initial_cal_settings,
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
            state_set("math_operation", request.form.get("math_op"))
            if state_get("math_operation"):
                toast_message = f"Math applied: {state_get('math_operation').upper()}"
                toast_variant = "success"

        if request.method == "POST" and "fft_apply" in request.form:
            action_name = "fft"
            try:
                _, raw_max_frequency = parse_fft_max_frequency(request.form.get("fft_max_frequency"))
            except ValueError as exc:
                error_message = str(exc)
            else:
                state_set(
                    "fft_settings",
                    {
                        "channel": request.form.get("fft_channel", "X"),
                        "scale": request.form.get("fft_scale", "linear"),
                        "max_frequency": raw_max_frequency,
                        "window_type": request.form.get("fft_window_type", "hann"),
                    },
                )
                state_set("fft_enabled", True)
                toast_message = f"FFT applied on channel {_ch_label(state_get('fft_settings')['channel'])}"
                toast_variant = "success"

        if request.method == "POST" and "statistics_apply" in request.form:
            action_name = "statistics"
            state_set("statistics_enabled", True)
            toast_message = "Statistics applied."
            toast_variant = "success"

        if request.method == "POST" and "advanced_apply" in request.form:
            action_name = "advanced"
            state_set("advanced_enabled", True)
            toast_message = "Advanced measures applied."
            toast_variant = "success"

        if request.method == "POST" and "calculus_apply" in request.form:
            action_name = "calculus"
            state_set("calculus_enabled", True)
            state_set("calculus_settings", {"channel": request.form.get("calculus_channel", "X")})
            toast_message = f"Derivative and integral applied on channel {_ch_label(state_get('calculus_settings')['channel'])}"
            toast_variant = "success"

        if request.method == "POST" and "current_apply" in request.form:
            action_name = "current"
            try:
                _, normalized = parse_positive_component_value(
                    request.form.get("current_component_value"),
                    "valor del componente",
                )
                _, normalized_initial_current = parse_float_field(
                    request.form.get("current_inductor_initial_value"),
                    "corriente inicial del inductor",
                    default=0.0,
                )
            except ValueError as exc:
                error_message = str(exc)
            else:
                state_set("current_enabled", True)
                state_set(
                    "current_settings",
                    {
                        "channel": request.form.get("current_channel", "X"),
                        "method": request.form.get("current_method", "resistor"),
                        "component_value": normalized,
                        "inductor_initial_mode": request.form.get("current_inductor_initial_mode", "zero"),
                        "inductor_initial_value": normalized_initial_current or "0",
                    },
                )
                method_label = {
                    "resistor": "resistor",
                    "capacitor": "capacitor",
                    "inductor": "inductor",
                }.get(request.form.get("current_method", "resistor"), "component")
                toast_message = f"Current analysis applied on channel {_ch_label(state_get('current_settings')['channel'])} using {method_label} mode."
                toast_variant = "success"

        if request.method == "POST" and "current_save" in request.form:
            action_name = "current"
            state_set("current_enabled", True)
            pending_current_snapshot_name = (request.form.get("current_snapshot_name") or "").strip() or "Current snapshot"
            toast_variant = "success"

        if request.method == "POST" and "transfer_apply" in request.form:
            action_name = "transfer"
            state_set("transfer_enabled", True)
            state_set(
                "transfer_settings",
                {
                    "input_channel": request.form.get("transfer_input_channel", "X"),
                    "output_channel": request.form.get("transfer_output_channel", "Y"),
                },
            )
            inp = state_get('transfer_settings')['input_channel']
            outp = state_get('transfer_settings')['output_channel']
            inp_lbl = _ch_label(inp)
            outp_lbl = _ch_label(outp)
            toast_message = f"Transfer analysis applied: {inp_lbl} -> {outp_lbl}"
            toast_variant = "success"

        if request.method == "POST" and "xy_apply" in request.form:
            action_name = "xy"
            state_set("xy_enabled", True)
            state_set(
                "xy_settings",
                {
                    "x_channel": request.form.get("xy_x_channel", "X"),
                    "y_channel": request.form.get("xy_y_channel", "Y"),
                },
            )
            xch = state_get('xy_settings')['x_channel']
            ych = state_get('xy_settings')['y_channel']
            xch_lbl = _ch_label(xch)
            ych_lbl = _ch_label(ych)
            toast_message = f"X-Y mode applied: {xch_lbl} on X axis and {ych_lbl} on Y axis."
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
                state_set(
                    "total_current_settings",
                    {
                        "voltage_channel": request.form.get("total_current_voltage_channel", "X"),
                        "combination_mode": "parallel",
                        "frequency_tolerance_percent": tolerance_normalized or "5",
                    },
                )
                state_set("total_current_enabled", True)
                vch = state_get("total_current_settings")["voltage_channel"]
                vch_lbl = _ch_label(vch)
                toast_message = f"Total current analysis applied using voltage channel {vch_lbl}."
                toast_variant = "success"

        if request.method == "POST" and "correlation_apply" in request.form:
            action_name = "correlation"
            state_set("correlation_enabled", True)
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
                cal_settings = {
                    "x_gain": x_gain,
                    "y_gain": y_gain,
                    "x_offset": x_offset,
                    "y_offset": y_offset,
                    "invert_x": request.form.get("invert_x") == "on",
                    "invert_y": request.form.get("invert_y") == "on",
                    "normalize": request.form.get("normalize") == "on",
                }
                state_set("calibration_settings", cal_settings)
                state_set("calibration_enabled", False)
                toast_message = "Calibration preview updated."
                toast_variant = "success"

        if request.method == "POST" and "calibration_reset" in request.form:
            action_name = "calibration"
            state_set("calibration_settings", DEFAULT_CALIBRATION_SETTINGS.copy())
            state_set("calibration_enabled", False)
            toast_message = "Calibration reset to defaults."
            toast_variant = "success"

        if request.method == "POST" and "cursor_apply" in request.form:
            action_name = "cursor"
            raw_t1 = str(request.form.get("cursor_t1") or "").strip()
            raw_t2 = str(request.form.get("cursor_t2") or "").strip()
            cursor_mode = str(request.form.get("cursor_mode") or "single").strip()
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
                cursor_settings = {
                    "channel": request.form.get("cursor_channel", "X"),
                    "t1": raw_t1,
                    "t2": raw_t2,
                    "mode": cursor_mode,
                    "signal_a": request.form.get("cursor_signal_a", "X"),
                    "signal_b": request.form.get("cursor_signal_b", "Y"),
                }
                state_set("cursor_settings", cursor_settings)
                state_set("cursor_enabled", True)
                if cursor_mode == "dual":
                    toast_message = f"Dual cursors: {_ch_label(cursor_settings['signal_a'])} A / {_ch_label(cursor_settings['signal_b'])} B"
                else:
                    toast_message = f"Cursors applied on channel {_ch_label(cursor_settings['channel'])}"
                toast_variant = "success"

        if request.method == "POST" and "digital_pwm_apply" in request.form:
            action_name = "digital_pwm"
            try:
                from digital_analyzer import analyze_pwm
                from file_analizer import load_wav_channels
                ch1, ch2, fs = load_wav_channels(state_get("file_wav"))
                channel = request.form.get("digital_channel", "X")
                raw_threshold = request.form.get("digital_threshold", "").strip()
                threshold = float(raw_threshold) if raw_threshold else None
                signal = {"X": ch1, "Y": ch2, "MATH": np.array([])}.get(channel, ch1)
                pwm_result = analyze_pwm(signal, fs, threshold=threshold)
                state_set("digital_data", {"type": "pwm", "channel": channel, "result": pwm_result})
            except Exception as exc:
                error_message = f"PWM analysis error: {exc}"
            else:
                toast_message = f"PWM analysis on channel {_ch_label(channel)}"
                toast_variant = "success"

        if request.method == "POST" and "digital_pulses_apply" in request.form:
            action_name = "digital_pulses"
            try:
                from digital_analyzer import count_pulses
                from file_analizer import load_wav_channels
                ch1, ch2, fs = load_wav_channels(state_get("file_wav"))
                channel = request.form.get("digital_channel", "X")
                signal = {"X": ch1, "Y": ch2, "MATH": np.array([])}.get(channel, ch1)
                count_result = count_pulses(signal, fs)
                state_set("digital_data", {"type": "pulses", "channel": channel, "result": count_result})
            except Exception as exc:
                error_message = f"Pulse count error: {exc}"
            else:
                toast_message = f"Pulse count on channel {_ch_label(channel)}: {count_result.get('pulse_count', 0)} pulses"
                toast_variant = "success"

        if request.method == "POST" and "digital_edges_apply" in request.form and "digital_pulses_apply" not in request.form:
            action_name = "digital_edges"
            try:
                from digital_analyzer import detect_edges
                from file_analizer import load_wav_channels
                ch1, ch2, fs = load_wav_channels(state_get("file_wav"))
                channel = request.form.get("digital_channel", "X")
                signal = {"X": ch1, "Y": ch2, "MATH": np.array([])}.get(channel, ch1)
                edges_result = detect_edges(signal, fs)
                state_set("digital_data", {"type": "edges", "channel": channel, "result": edges_result})
            except Exception as exc:
                error_message = f"Edge detection error: {exc}"
            else:
                toast_message = f"Edge detection on channel {_ch_label(channel)}: {len(edges_result.get('rising_edges', []))} rising, {len(edges_result.get('falling_edges', []))} falling"
                toast_variant = "success"

        if request.method == "POST" and "digital_logic_apply" in request.form:
            action_name = "digital_logic"
            try:
                from digital_analyzer import analyze_logic_levels
                from file_analizer import load_wav_channels
                ch1, ch2, fs = load_wav_channels(state_get("file_wav"))
                channel = request.form.get("digital_channel", "X")
                signal = {"X": ch1, "Y": ch2, "MATH": np.array([])}.get(channel, ch1)
                logic_result = analyze_logic_levels(signal)
                state_set("digital_data", {"type": "logic", "channel": channel, "result": logic_result})
            except Exception as exc:
                error_message = f"Logic level analysis error: {exc}"
            else:
                toast_message = f"Logic level analysis on channel {_ch_label(channel)}"
                toast_variant = "success"

        if request.method == "POST" and "cycle_apply" in request.form:
            action_name = "cycle"
            state_set("cycle_settings", {"channel": request.form.get("cycle_channel", "X")})
            state_set("cycle_enabled", True)
            toast_message = f"Cycle analysis applied on channel {_ch_label(state_get('cycle_settings')['channel'])}"
            toast_variant = "success"

        if request.method == "POST" and "save_snapshot" in request.form:
            action_name = "snapshot"
            pending_snapshot_name = (request.form.get("snapshot_name") or "").strip() or "Snapshot"

        if request.method == "POST" and "compare_apply" in request.form:
            action_name = "comparison"
            state_set("comparison_snapshot_id", request.form.get("snapshot_id", ""))
            state_set("comparison_enabled", bool(state_get("comparison_snapshot_id")))
            if state_get("comparison_enabled"):
                toast_message = "Snapshot comparison applied."
                toast_variant = "success"

        if request.method == "POST" and "reset" in request.form:
            clear_loaded_state()
            clear_client_state()
            return render_template(
                "main.html",
                **build_empty_view(
                    toast_message="Workspace reset and uploads cleaned.",
                    toast_variant="success",
                ),
            )

        file_path = state_get("file_wav")
        if not file_path or not os.path.exists(file_path):
            rendered_html = render_template(
                "main.html",
                **build_empty_view(
                    error_message=error_message,
                    toast_message=toast_message,
                    toast_variant=toast_variant,
                ),
            )
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
                if save_current_snapshot(
                    pending_current_snapshot_name,
                    context["current_data"],
                    context["time_axis"],
                    context["file_name"],
                ):
                    context["total_current_data"] = build_total_current_view(
                        context["ch1_analysis"],
                        context["ch2_analysis"],
                        context["math_result_analysis"],
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
            rendered_html = render_template(
                "main.html",
                **build_empty_view(f"No se pudo procesar el archivo: {exc}"),
            )
            if is_ajax_request() and action_name in AJAX_MODULE_ACTIONS:
                return (
                    build_ajax_fragment_response(
                        rendered_html,
                        action_name,
                        error_message=f"No se pudo procesar el archivo: {exc}",
                    ),
                    400,
                )
            return rendered_html

        # Compute formatted V/Div and Time/Div strings for HTML graph headers
        _cfg = context.get("config", {})
        _vd = _cfg.get("volts_div", [0, 0])
        _vm = _cfg.get("volt_multiplier", [1, 1])
        _vu = _cfg.get("volt_units", ["V", "V"])
        _td = _cfg.get("time_div", 0)
        _tm = _cfg.get("time_multiplier", 1)
        ch1_vdiv_str = _fmt_vdiv(float(_vd[0]) * float(_vm[0])) if len(_vd) > 0 and _vd[0] else ""
        ch2_vdiv_str = _fmt_vdiv(float(_vd[1]) * float(_vm[1])) if len(_vd) > 1 and _vd[1] else ""
        tdiv_str = _fmt_tdiv(float(_td) * float(_tm)) if _td else ""
        _math_result = context.get("math_result")
        math_vdiv_str = _fmt_vdiv(_compute_vdiv_from_data(_math_result)) if _math_result is not None and len(_math_result) > 0 else ""

        # Per-channel V/Div-based voltage ranges for cursor (matching main graph:
        # each channel gets ±4 × its own V/Div, exactly 8 vertical divisions)
        _ch1_vdiv = float(_vd[0]) * float(_vm[0]) if len(_vd) > 0 and _vd[0] else 1.0
        _ch2_vdiv = float(_vd[1]) * float(_vm[1]) if len(_vd) > 1 and _vd[1] else 1.0
        cursor_ch = context["cursor_data"].get("channel", "X")
        cursor_mode = context["cursor_data"].get("mode", "single")
        if cursor_mode == "dual":
            cursor_voltage_min = -4 * _ch1_vdiv
            cursor_voltage_max = 4 * _ch1_vdiv
            cursor_vdiv_v = _ch1_vdiv
        elif cursor_ch == "MATH":
            vmax = context["cursor_data"].get("voltage_max", 0)
            vmin = context["cursor_data"].get("voltage_min", 0)
            _mvdiv = max((vmax - vmin) / 8 * 1.1, 0.001) if vmax > vmin else 1
            cursor_voltage_min = -4 * _mvdiv
            cursor_voltage_max = 4 * _mvdiv
            cursor_vdiv_v = _mvdiv
        else:
            idx = 0 if cursor_ch == "X" else 1
            _sel_vdiv = float(_vd[idx]) * float(_vm[idx]) if len(_vd) > idx and _vd[idx] else 1.0
            cursor_voltage_min = -4 * _sel_vdiv
            cursor_voltage_max = 4 * _sel_vdiv
            cursor_vdiv_v = _sel_vdiv
        cursor_config_tdiv_s = float(_td) * float(_tm) if _td else 0.001
        # Raw per-channel V/Div for JS to dynamically compute per-signal ranges
        cursor_vdiv_ch1 = _ch1_vdiv
        cursor_vdiv_ch2 = _ch2_vdiv
        logging.warning("CURSOR_VDIV: mode=%s ch=%s ch1_vdiv=%.6f ch2_vdiv=%.6f single_range=[%.6f,%.6f]",
            cursor_mode, cursor_ch, _ch1_vdiv, _ch2_vdiv,
            cursor_voltage_min, cursor_voltage_max)

        template_context = {
            "file": context["file_path"],
            "file_name": context["file_name"],
            "config": context["config"],
            "measures": context["measures"],
            "ch1_vdiv_str": ch1_vdiv_str,
            "ch2_vdiv_str": ch2_vdiv_str,
            "tdiv_str": tdiv_str,
            "math_vdiv_str": math_vdiv_str,
            "grafica": context["main_graph"],
            "grafica_math": context["math_graph"],
            "math_operation": state_get("math_operation"),
            "math_measures": context["math_measures"],
            "fft_graph": context["fft_graph"],
            "fft_data": context["fft_data"],
            "statistics_data": context["statistics_data"],
            "advanced_data": context["advanced_data"],
            "calculus_data": context["calculus_data"],
            "current_data": context["current_data"],
            "transfer_data": context["transfer_data"],
            "xy_data": context["xy_data"],
            "total_current_data": context["total_current_data"],
            "correlation_data": context["correlation_data"],
            "calibration_data": context["calibration_data"],
            "cursor_data": context["cursor_data"],
            "cursor_voltage_min": cursor_voltage_min,
            "cursor_voltage_max": cursor_voltage_max,
            "cursor_vdiv_v": cursor_vdiv_v,
            "cursor_vdiv_ch1": cursor_vdiv_ch1,
            "cursor_vdiv_ch2": cursor_vdiv_ch2,
            "cursor_config_tdiv_s": cursor_config_tdiv_s,
            "cycle_data": context["cycle_data"],
            "comparison_data": context["comparison_data"],
            "digital_data": state_get("digital_data", {}),
            "snapshots": state_get("snapshots", []),
            "current_snapshots": [
                item for item in state_get("current_snapshots", []) if item.get("file_name") == context["file_name"]
            ],
            "ch1_name": state_get("ch1_name", "CH1"),
            "ch2_name": state_get("ch2_name", "CH2"),
            "ch1_color": CHANNEL_COLORS_STR["X"],
            "ch2_color": CHANNEL_COLORS_STR["Y"],
            "math_color": CHANNEL_COLORS_STR["MATH"],
            "teal_color": TRACE_COLOR_TEAL,
            "orange_color": TRACE_COLOR_ORANGE,
            "error_message": error_message,
            "toast_message": toast_message,
            "toast_variant": toast_variant,
        }

        rendered_html = render_template("main.html", **template_context)
        if is_ajax_request() and action_name in AJAX_MODULE_ACTIONS:
            return build_ajax_fragment_response(rendered_html, action_name)

        return rendered_html

    @app.route("/download_latex")
    def download_latex():
        measures = state_get("measures")
        if not measures:
            return "No hay datos de medidas", 400
        return Response(generate_measures_latex(measures, ch1_name=state_get("ch1_name", "CH1"), ch2_name=state_get("ch2_name", "CH2")), mimetype="text/plain")

    @app.route("/download_math_latex")
    def download_math_latex():
        math_measures = state_get("math_measures")
        operation = state_get("math_operation")
        if not math_measures:
            return "No hay datos de medidas MATH", 400
        return Response(generate_math_measures_latex(math_measures, operation), mimetype="text/plain")

    @app.route("/download_statistics_latex")
    def download_statistics_latex():
        statistics_data = state_get("statistics_data")
        if not statistics_data:
            return "No hay datos estadisticos", 400
        return Response(generate_statistics_latex(statistics_data, ch1_name=state_get("ch1_name", "CH1"), ch2_name=state_get("ch2_name", "CH2")), mimetype="text/plain")

    @app.route("/download_advanced_latex")
    def download_advanced_latex():
        advanced_data = state_get("advanced_data")
        if not advanced_data:
            return "No hay datos de medidas avanzadas", 400
        return Response(generate_advanced_measures_latex(advanced_data, ch1_name=state_get("ch1_name", "CH1"), ch2_name=state_get("ch2_name", "CH2")), mimetype="text/plain")

    @app.route("/download_correlation_latex")
    def download_correlation_latex():
        correlation_data = state_get("correlation_data")
        if not correlation_data:
            return "No hay datos de correlacion", 400
        return Response(generate_correlation_latex(correlation_data), mimetype="text/plain")

    @app.route("/download_fft_latex")
    def download_fft_latex():
        fft_data = state_get("fft_data")
        if not fft_data:
            return "No hay datos FFT", 400
        return Response(generate_fft_latex(fft_data, ch1_name=state_get("ch1_name", "CH1"), ch2_name=state_get("ch2_name", "CH2")), mimetype="text/plain")

    @app.route("/download_calibration_latex")
    def download_calibration_latex():
        return Response(generate_calibration_latex(get_calibration_settings(), ch1_name=state_get("ch1_name", "CH1"), ch2_name=state_get("ch2_name", "CH2")), mimetype="text/plain")

    @app.route("/download_config_latex")
    def download_config_latex():
        config = state_get("config", {})
        return Response(generate_config_latex(config, ch1_name=state_get("ch1_name", "CH1"), ch2_name=state_get("ch2_name", "CH2")), mimetype="text/plain")

    @app.route("/download_current_snapshots_latex")
    def download_current_snapshots_latex():
        snapshots = state_get("current_snapshots", [])
        return Response(generate_current_snapshots_latex(snapshots), mimetype="text/plain")

    @app.route("/download_snapshots_latex")
    def download_snapshots_latex():
        snapshots = state_get("snapshots", [])
        return Response(generate_snapshots_latex(snapshots), mimetype="text/plain")

    @app.route("/download_current_latex")
    def download_current_latex():
        current_data = state_get("current_data")
        if not current_data:
            return "No hay analisis de corriente", 400
        return Response(generate_current_latex(current_data, ch1_name=state_get("ch1_name", "CH1"), ch2_name=state_get("ch2_name", "CH2")), mimetype="text/plain")

    @app.route("/download_transfer_latex")
    def download_transfer_latex():
        transfer_data = state_get("transfer_data")
        if not transfer_data:
            return "No hay analisis de transferencia", 400
        return Response(generate_transfer_latex(transfer_data, ch1_name=state_get("ch1_name", "CH1"), ch2_name=state_get("ch2_name", "CH2")), mimetype="text/plain")

    @app.route("/download_transfer_graph")
    def download_transfer_graph():
        if not state_get("transfer_enabled"):
            return "Primero debes aplicar Transfer", 400
        context = prepare_download_data("transfer")
        if not context:
            return "No hay archivo cargado", 400

        settings = get_transfer_settings()
        signals = {
            "X": np.asarray(context["ch1"], dtype=float),
            "Y": np.asarray(context["ch2"], dtype=float),
            "MATH": np.asarray(
                context["math_result"] if context["math_result"] is not None else np.array([]),
                dtype=float,
            ),
        }
        input_ch = settings.get("input_channel", "X")
        output_ch = settings.get("output_channel", "Y")
        inp_signal = signals.get(input_ch, context["ch1"])
        out_signal = signals.get(output_ch, context["ch2"])
        in_label = _ch_label(input_ch)
        out_label = _ch_label(output_ch)

        png_path = generate_grafic_download(
            np.asarray(context["time_axis"], dtype=float),
            inp_signal,
            out_signal,
            f"Transfer Analysis {in_label} vs {out_label}",
            show_empty=True,
            ch1_name=in_label,
            ch2_name=out_label,
        )
        cleanup_temp_download(png_path)
        return send_file(
            png_path,
            mimetype="image/png",
            as_attachment=True,
            download_name=f"{context['file_name']}_transfer_{in_label}_vs_{out_label}.png",
        )

    @app.route("/download_total_current_latex")
    def download_total_current_latex():
        total_current_data = state_get("total_current_data")
        if not total_current_data:
            return "No hay analisis de corriente total", 400
        return Response(generate_total_current_latex(total_current_data, ch1_name=state_get("ch1_name", "CH1"), ch2_name=state_get("ch2_name", "CH2")), mimetype="text/plain")

    @app.route("/download_cursor_latex")
    def download_cursor_latex():
        cursor_data = state_get("cursor_data")
        if not cursor_data:
            return "No hay medicion manual", 400
        return Response(generate_cursor_latex(cursor_data), mimetype="text/plain")

    @app.route("/download_cursor_graph")
    def download_cursor_graph():
        if not state_get("cursor_enabled"):
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

        # Dual mode: export both signals independently
        if cursor_data.get("mode") == "dual":
            from constants import CHANNEL_COLORS_STR_LIGHT
            sig_a_ch = cursor_data.get("signal_a", "X")
            sig_b_ch = cursor_data.get("signal_b", "Y")
            sig_a_data = signals.get(sig_a_ch, context["ch1"])
            sig_b_data = signals.get(sig_b_ch, context["ch2"])
            color_a = CHANNEL_COLORS_STR_LIGHT.get(sig_a_ch, CHANNEL_COLORS_STR_LIGHT["X"])
            color_b = CHANNEL_COLORS_STR_LIGHT.get(sig_b_ch, CHANNEL_COLORS_STR_LIGHT["Y"])
            _cfg = context.get("config", {})
            _vd = _cfg.get("volts_div", [0, 0])
            _vm = _cfg.get("volt_multiplier", [1, 1])
            _td = _cfg.get("time_div", 0)
            _tm = _cfg.get("time_multiplier", 1)
            ch_map = {"X": 0, "Y": 1}
            vdiv_a = float(_vd[ch_map[sig_a_ch]]) * float(_vm[ch_map[sig_a_ch]]) if sig_a_ch in ch_map and len(_vd) > ch_map[sig_a_ch] and _vd[ch_map[sig_a_ch]] else _compute_vdiv_from_data(sig_a_data)
            vdiv_b = float(_vd[ch_map[sig_b_ch]]) * float(_vm[ch_map[sig_b_ch]]) if sig_b_ch in ch_map and len(_vd) > ch_map[sig_b_ch] and _vd[ch_map[sig_b_ch]] else _compute_vdiv_from_data(sig_b_data)
            _tdiv_s = float(_td) * float(_tm) if _td else None
            # Scale t2's Y so both cursor markers render at correct positions
            # on A's Y-axis (t1 is already in A's coordinate system)
            _scale = vdiv_a / vdiv_b if vdiv_b > 0 else 1.0
            _v2_scaled = cursor_data["v2"] * _scale
            # Build dual header: channel A + V/Div A, channel B + V/Div B, Time
            _header_items = [
                {"text": f"{_ch_label(sig_a_ch)} {_fmt_vdiv(vdiv_a)}", "color": color_a},
                {"text": f"{_ch_label(sig_b_ch)} {_fmt_vdiv(vdiv_b)}", "color": color_b},
            ]
            if _td:
                _header_items.append({"text": f"Time {_fmt_tdiv(float(_td) * float(_tm))}"})
            png_path = generate_cursor_grafic_file(
                context["time_axis"],
                sig_a_data,
                "Cursor measurement (dual)",
                marker_points=[(cursor_data["t1"], cursor_data["v1"]), (cursor_data["t2"], _v2_scaled)],
                header_items=_header_items,
                vdiv_v=vdiv_a,
                tdiv_s=_tdiv_s,
                trace_color=color_a,
                signal_b=sig_b_data,
                trace_color_b=color_b,
                vdiv_v_b=vdiv_b,
                marker_points_b=[(cursor_data["t2"], cursor_data["v2"])],
            )
            cleanup_temp_download(png_path)
            return send_file(
                png_path,
                mimetype="image/png",
                as_attachment=True,
                download_name=f"{context['file_name']}_cursors_dual.png",
            )

        # --- Single mode (unchanged) ---
        selected_signal = signals.get(cursor_data["channel"], context["ch1"])
        ch_label = _ch_label(cursor_data["channel"])

        from constants import CHANNEL_COLORS_STR_LIGHT
        _trace_color = CHANNEL_COLORS_STR_LIGHT.get(cursor_data["channel"], CHANNEL_COLORS_STR_LIGHT["X"])

        _cfg = context.get("config", {})
        _vd = _cfg.get("volts_div", [0, 0])
        _vm = _cfg.get("volt_multiplier", [1, 1])
        _td = _cfg.get("time_div", 0)
        _tm = _cfg.get("time_multiplier", 1)

        ch_map = {"X": 0, "Y": 1}
        _header_items = []
        if cursor_data["channel"] in ch_map:
            idx = ch_map[cursor_data["channel"]]
            vdiv = _fmt_vdiv(float(_vd[idx]) * float(_vm[idx])) if len(_vd) > idx and _vd[idx] else ""
            ch_name = _ch_label(cursor_data["channel"])
            label = ch_name
            if vdiv:
                label += f" {vdiv}"
            _header_items.append({"text": label, "color": _trace_color})
        elif cursor_data["channel"] == "MATH":
            label = "MATH"
            if selected_signal.size:
                vdiv = _fmt_vdiv(_compute_vdiv_from_data(selected_signal))
                label += f" {vdiv}"
            _header_items.append({"text": label, "color": _trace_color})
        if _td:
            tdiv_str = _fmt_tdiv(float(_td) * float(_tm))
            _header_items.append({"text": f"Time {tdiv_str}"})

        _vdiv_v = None
        if cursor_data["channel"] in ch_map:
            idx = ch_map[cursor_data["channel"]]
            if len(_vd) > idx and _vd[idx]:
                _vdiv_v = float(_vd[idx]) * float(_vm[idx])
        elif cursor_data["channel"] == "MATH" and selected_signal.size:
            _vdiv_v = _compute_vdiv_from_data(selected_signal)
        _tdiv_s = float(_td) * float(_tm) if _td else None

        png_path = generate_cursor_grafic_file(
            context["time_axis"],
            selected_signal,
            f"Cursor measurement {ch_label}",
            marker_points=[(cursor_data["t1"], cursor_data["v1"]), (cursor_data["t2"], cursor_data["v2"])],
            header_items=_header_items,
            vdiv_v=_vdiv_v,
            tdiv_s=_tdiv_s,
            trace_color=_trace_color,
        )
        cleanup_temp_download(png_path)
        return send_file(
            png_path,
            mimetype="image/png",
            as_attachment=True,
            download_name=f"{context['file_name']}_cursors_{ch_label}.png",
        )

    @app.route("/download_cycle_latex")
    def download_cycle_latex():
        cycle_data = state_get("cycle_data")
        if not cycle_data:
            return "No hay analisis por ciclo", 400
        return Response(generate_cycle_latex(cycle_data), mimetype="text/plain")

    @app.route("/download_comparison_latex")
    def download_comparison_latex():
        comparison_data = state_get("comparison_data")
        if not comparison_data:
            return "No hay comparacion", 400
        return Response(generate_comparison_latex(comparison_data, ch1_name=state_get("ch1_name", "CH1"), ch2_name=state_get("ch2_name", "CH2")), mimetype="text/plain")

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
            ch1_name=context.get("ch1_name", "CH1"),
            ch2_name=context.get("ch2_name", "CH2"),
        )
        cleanup_temp_download(png_path)
        return send_file(
            png_path,
            mimetype="image/png",
            as_attachment=True,
            download_name=f"{context['file_name']}_graph.png",
        )

    @app.route("/download_math_graph")
    def download_math_graph():
        context = prepare_download_data()
        if not context:
            return "No hay archivo cargado o el archivo es invalido", 400
        if state_get("math_operation") is None:
            return "No hay operacion matematica activa", 400
        png_path = generate_grafic_download_math(
            context["time_axis"],
            [],
            [],
            f"MATH_{state_get('math_operation')}",
            math_result=context["math_result"],
        )
        cleanup_temp_download(png_path)
        return send_file(
            png_path,
            mimetype="image/png",
            as_attachment=True,
            download_name=f"{context['file_name']}_math_{state_get('math_operation')}.png",
        )

    @app.route("/download_fft_graph")
    def download_fft_graph():
        if not state_get("fft_enabled"):
            return "Primero debes aplicar la FFT", 400
        context = prepare_download_data()
        if not context:
            return "No hay archivo cargado o el archivo es invalido", 400
        fft_data = get_fft_download_data(
            context["ch1_analysis"],
            context["ch2_analysis"],
            context["math_result_analysis"],
            context["fs"],
        )
        ch_label = _ch_label(fft_data["channel"])
        png_path = generate_fft_grafic_download(
            fft_data["frequencies_hz"],
            fft_data["magnitudes"],
            context["file_name"],
            ch_label,
            scale_mode=fft_data["scale"],
            dominant_frequency_hz=fft_data["dominant_frequency_hz"],
        )
        cleanup_temp_download(png_path)
        return send_file(
            png_path,
            mimetype="image/png",
            as_attachment=True,
            download_name=f"{context['file_name']}_fft_{ch_label}.png",
        )

    @app.route("/download_derivative_graph")
    def download_derivative_graph():
        if not state_get("calculus_enabled"):
            return "Primero debes aplicar Derivative & Integral", 400
        context = prepare_download_data("calculus")
        if not context:
            return "No hay archivo cargado o el archivo es invalido", 400
        ch = context['calculus_data']['channel']
        ch_label = _ch_label(ch)
        png_path = generate_signal_analysis_download(
            context["time_axis"],
            context["calculus_data"]["derivative"],
            f"Derivative {ch_label}",
            "dV/dt (V/s)",
        )
        cleanup_temp_download(png_path)
        return send_file(
            png_path,
            mimetype="image/png",
            as_attachment=True,
            download_name=f"{context['file_name']}_derivative_{ch_label}.png",
        )

    @app.route("/download_integral_graph")
    def download_integral_graph():
        if not state_get("calculus_enabled"):
            return "Primero debes aplicar Derivative & Integral", 400
        context = prepare_download_data("calculus")
        if not context:
            return "No hay archivo cargado o el archivo es invalido", 400
        ch = context['calculus_data']['channel']
        ch_label = _ch_label(ch)
        png_path = generate_signal_analysis_download(
            context["time_axis"],
            context["calculus_data"]["integral"],
            f"Integral {ch_label}",
            "Integral (V*s)",
        )
        cleanup_temp_download(png_path)
        return send_file(
            png_path,
            mimetype="image/png",
            as_attachment=True,
            download_name=f"{context['file_name']}_integral_{ch_label}.png",
        )

    @app.route("/download_current_graph")
    def download_current_graph():
        if not state_get("current_enabled"):
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
        ch_label = _ch_label(current_data["channel"])
        png_path = generate_current_grafic_download(
            context["time_axis"],
            selected_signal,
            current_data["current"],
            f"Current Analysis {ch_label}",
            voltage_channel=current_data["channel"],
        )
        cleanup_temp_download(png_path)
        return send_file(
            png_path,
            mimetype="image/png",
            as_attachment=True,
            download_name=f"{context['file_name']}_current_{ch_label}.png",
        )

    @app.route("/download_total_current_graph")
    def download_total_current_graph():
        if not state_get("total_current_enabled"):
            return "No hay analisis de corriente total", 400

        context = prepare_download_data("current")
        if not context:
            return "No hay archivo cargado o el archivo es invalido", 400
        total_current_data = context["total_current_data"]
        if not total_current_data.get("enabled"):
            return "No hay analisis de corriente total", 400

        signals = {
            "X": context["ch1"],
            "Y": context["ch2"],
            "MATH": context["math_result"] if context["math_result"] is not None else np.array([]),
        }
        vch = total_current_data["voltage_channel"]
        vch_label = _ch_label(vch)
        voltage = signals.get(vch, context["ch1"])
        png_path = generate_current_grafic_download(
            context["time_axis"],
            voltage,
            total_current_data["current"],
            f"Total Current Analysis {vch_label}",
            voltage_channel=vch,
        )
        cleanup_temp_download(png_path)
        return send_file(
            png_path,
            mimetype="image/png",
            as_attachment=True,
            download_name=f"{context['file_name']}_total_current_{vch_label}.png",
        )

    @app.route("/download_correlation_graph")
    def download_correlation_graph():
        if not state_get("correlation_enabled"):
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
        return send_file(
            png_path,
            mimetype="image/png",
            as_attachment=True,
            download_name=f"{context['file_name']}_correlation.png",
        )

    @app.route("/download_xy_graph")
    def download_xy_graph():
        if not state_get("xy_enabled"):
            return "Primero debes aplicar X-Y mode", 400
        context = prepare_download_data("xy")
        if not context:
            return "No hay archivo cargado o el archivo es invalido", 400

        settings = get_xy_settings()
        signals = {
            "X": np.asarray(context["ch1"], dtype=float),
            "Y": np.asarray(context["ch2"], dtype=float),
            "MATH": np.asarray(
                context["math_result"] if context["math_result"] is not None else np.array([]),
                dtype=float,
            ),
        }
        x_signal = signals.get(settings["x_channel"], signals["X"])
        y_signal = signals.get(settings["y_channel"], signals["Y"])
        length = min(x_signal.size, y_signal.size)
        if length == 0:
            return "No hay datos X-Y disponibles", 400

        x_label = _ch_label(settings['x_channel'])
        y_label = _ch_label(settings['y_channel'])
        png_path = generate_xy_grafic_download(
            x_signal[:length],
            y_signal[:length],
            f"X-Y Mode {x_label} vs {y_label}",
            x_label=f"{x_label} (V)",
            y_label=f"{y_label} (V)",
        )
        cleanup_temp_download(png_path)
        return send_file(
            png_path,
            mimetype="image/png",
            as_attachment=True,
            download_name=f"{context['file_name']}_xy_{x_label}_vs_{y_label}.png",
        )

    @app.route("/download_xy_latex")
    def download_xy_latex():
        xy_data = state_get("xy_data")
        if not xy_data:
            return "No hay datos X-Y", 400
        return Response(generate_xy_latex(xy_data, ch1_name=state_get("ch1_name", "CH1"), ch2_name=state_get("ch2_name", "CH2")), mimetype="text/plain")

    @app.route("/download_graph_svg")
    def download_graph_svg():
        context = prepare_download_data()
        if not context:
            return "No hay archivo cargado o el archivo es invalido", 400
        from export_service import export_graph_svg
        svg_path = export_graph_svg(
            context["time_axis"],
            context["ch1"],
            context["ch2"],
            context["file_name"],
            scope_config=context["config"],
        )
        cleanup_temp_download(svg_path)
        return send_file(
            svg_path,
            mimetype="image/svg+xml",
            as_attachment=True,
            download_name=f"{context['file_name']}_graph.svg",
        )

    @app.route("/download_signals_csv")
    def download_signals_csv():
        context = prepare_download_data()
        if not context:
            return "No hay archivo cargado o el archivo es invalido", 400
        from export_service import export_signals_csv
        csv_path = export_signals_csv(
            context["time_axis"],
            context["ch1"],
            context["ch2"],
            context["file_name"],
            math_result=context["math_result"],
            ch1_name=context.get("ch1_name", "CH1"),
            ch2_name=context.get("ch2_name", "CH2"),
        )
        cleanup_temp_download(csv_path)
        return send_file(
            csv_path,
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"{context['file_name']}_signals.csv",
        )

    @app.route("/download_measurements_csv")
    def download_measurements_csv():
        measures = state_get("measures")
        if not measures:
            return "No hay datos de medidas", 400
        from export_service import export_measurements_csv
        csv_path = export_measurements_csv(measures, "measurements", ch1_name=state_get("ch1_name", "CH1"), ch2_name=state_get("ch2_name", "CH2"))
        cleanup_temp_download(csv_path)
        return send_file(
            csv_path,
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"measurements.csv",
        )

    @app.route("/download_fft_csv")
    def download_fft_csv():
        fft_data = state_get("fft_data")
        if not fft_data or not fft_data.get("enabled"):
            return "No hay datos FFT", 400
        from export_service import export_fft_csv
        csv_path = export_fft_csv(
            fft_data.get("frequencies_hz", np.array([])),
            fft_data.get("magnitudes", np.array([])),
        )
        cleanup_temp_download(csv_path)
        ch_lbl = _ch_label(fft_data.get('channel', 'X'))
        return send_file(
            csv_path,
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"fft_{ch_lbl}.csv",
        )

    @app.route("/download_report_pdf")
    def download_report_pdf():
        context = prepare_download_data()
        if not context:
            return "No hay archivo cargado o el archivo es invalido", 400
        from export_service import export_report_pdf
        pdf_path = export_report_pdf(
            context["time_axis"],
            context["ch1"],
            context["ch2"],
            context["file_name"],
            context["config"],
            context["measures"],
            fft_data=context["fft_data"],
            math_result=context["math_result"],
            statistics_data=context["statistics_data"],
            advanced_data=context["advanced_data"],
            ch1_name=context.get("ch1_name", "CH1"),
            ch2_name=context.get("ch2_name", "CH2"),
        )
        cleanup_temp_download(pdf_path)
        return send_file(
            pdf_path,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"{context['file_name']}_report.pdf",
        )

    @app.route("/project_save", methods=["POST"])
    def project_save():
        action_name = "project_save"
        name = request.form.get("project_name", "").strip()
        if not name:
            name = f"Project_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        from project_service import save_project
        path = save_project(name)
        state_set("toast_message", f"Project saved: {name}")
        state_set("toast_variant", "success")
        return jsonify({"success": True, "path": path, "name": name})

    @app.route("/project_load", methods=["POST"])
    def project_load():
        action_name = "project_load"
        file_wav_path = request.form.get("project_path", "").strip()
        if not file_wav_path:
            return jsonify({"success": False, "error": "No project path provided"}), 400
        from project_service import load_project
        result = load_project(file_wav_path)
        if "error" in result:
            return jsonify({"success": False, "error": result["error"]}), 400
        clear_loaded_state()
        state_set("toast_message", "Project loaded successfully")
        state_set("toast_variant", "success")
        return jsonify({"success": True})

    @app.route("/project_list")
    def project_list():
        from project_service import list_projects
        projects = list_projects()
        return jsonify({"projects": projects})


