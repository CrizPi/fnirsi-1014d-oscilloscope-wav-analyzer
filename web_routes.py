import os
import re

import numpy as np
from flask import Response, after_this_request, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

from analysis_service import (
    build_comparison_view,
    build_empty_view,
    build_total_current_view,
    get_calibration_settings,
    get_fft_download_data,
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
from plot_maker import generate_cursor_grafic_file
from report import (
    generate_advanced_measures_latex,
    generate_calibration_latex,
    generate_comparison_latex,
    generate_correlation_grafic_download,
    generate_correlation_latex,
    generate_current_grafic_download,
    generate_current_latex,
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
    generate_total_current_latex,
    generate_transfer_latex,
    generate_xy_grafic_download,
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
        "advanced": "module-advanced",
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


def prepare_download_data(action_name=None):
    try:
        return prepare_analysis_context(action_name)
    except (OSError, ScopeFileError, ValueError, ZeroDivisionError):
        return None


def register_routes(app):
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

                state_update(
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
                        "transfer_enabled": False,
                        "transfer_settings": DEFAULT_TRANSFER_SETTINGS.copy(),
                        "xy_enabled": False,
                        "xy_settings": DEFAULT_XY_SETTINGS.copy(),
                        "total_current_enabled": False,
                        "total_current_settings": DEFAULT_TOTAL_CURRENT_SETTINGS.copy(),
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
                toast_message = f"FFT applied on channel {state_get('fft_settings')['channel']}"
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
            toast_message = f"Derivative and integral applied on channel {state_get('calculus_settings')['channel']}"
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
                toast_message = (
                    f"Current analysis applied on channel {state_get('current_settings')['channel']} "
                    f"using {method_label} mode."
                )
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
            toast_message = (
                f"Transfer analysis applied: {state_get('transfer_settings')['input_channel']} -> "
                f"{state_get('transfer_settings')['output_channel']}"
            )
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
            toast_message = (
                f"X-Y mode applied: {state_get('xy_settings')['x_channel']} on X axis and "
                f"{state_get('xy_settings')['y_channel']} on Y axis."
            )
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
                toast_message = (
                    f"Total current analysis applied using voltage channel "
                    f"{state_get('total_current_settings')['voltage_channel']}."
                )
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
                state_set(
                    "calibration_settings",
                    {
                        "x_gain": x_gain,
                        "y_gain": y_gain,
                        "x_offset": x_offset,
                        "y_offset": y_offset,
                        "invert_x": request.form.get("invert_x") == "on",
                        "invert_y": request.form.get("invert_y") == "on",
                        "normalize": request.form.get("normalize") == "on",
                    },
                )
                state_set("calibration_enabled", True)
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
                state_set(
                    "cursor_settings",
                    {
                        "channel": request.form.get("cursor_channel", "X"),
                        "t1": raw_t1,
                        "t2": raw_t2,
                    },
                )
                state_set("cursor_enabled", True)
                toast_message = f"Cursors applied on channel {state_get('cursor_settings')['channel']}"
                toast_variant = "success"

        if request.method == "POST" and "cycle_apply" in request.form:
            action_name = "cycle"
            state_set("cycle_settings", {"channel": request.form.get("cycle_channel", "X")})
            state_set("cycle_enabled", True)
            toast_message = f"Cycle analysis applied on channel {state_get('cycle_settings')['channel']}"
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

        template_context = {
            "file": context["file_path"],
            "file_name": context["file_name"],
            "config": context["config"],
            "measures": context["measures"],
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
            "cycle_data": context["cycle_data"],
            "comparison_data": context["comparison_data"],
            "snapshots": state_get("snapshots", []),
            "current_snapshots": [
                item for item in state_get("current_snapshots", []) if item.get("file_name") == context["file_name"]
            ],
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
        return Response(generate_measures_latex(measures), mimetype="text/plain")

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
        return Response(generate_statistics_latex(statistics_data), mimetype="text/plain")

    @app.route("/download_advanced_latex")
    def download_advanced_latex():
        advanced_data = state_get("advanced_data")
        if not advanced_data:
            return "No hay datos de medidas avanzadas", 400
        return Response(generate_advanced_measures_latex(advanced_data), mimetype="text/plain")

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
        return Response(generate_fft_latex(fft_data), mimetype="text/plain")

    @app.route("/download_calibration_latex")
    def download_calibration_latex():
        return Response(generate_calibration_latex(get_calibration_settings()), mimetype="text/plain")

    @app.route("/download_current_latex")
    def download_current_latex():
        current_data = state_get("current_data")
        if not current_data:
            return "No hay analisis de corriente", 400
        return Response(generate_current_latex(current_data), mimetype="text/plain")

    @app.route("/download_transfer_latex")
    def download_transfer_latex():
        transfer_data = state_get("transfer_data")
        if not transfer_data:
            return "No hay analisis de transferencia", 400
        return Response(generate_transfer_latex(transfer_data), mimetype="text/plain")

    @app.route("/download_total_current_latex")
    def download_total_current_latex():
        total_current_data = state_get("total_current_data")
        if not total_current_data:
            return "No hay analisis de corriente total", 400
        return Response(generate_total_current_latex(total_current_data), mimetype="text/plain")

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
        cycle_data = state_get("cycle_data")
        if not cycle_data:
            return "No hay analisis por ciclo", 400
        return Response(generate_cycle_latex(cycle_data), mimetype="text/plain")

    @app.route("/download_comparison_latex")
    def download_comparison_latex():
        comparison_data = state_get("comparison_data")
        if not comparison_data:
            return "No hay comparacion", 400
        return Response(generate_comparison_latex(comparison_data), mimetype="text/plain")

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
        png_path = generate_fft_grafic_download(
            fft_data["frequencies_hz"],
            fft_data["magnitudes"],
            context["file_name"],
            fft_data["channel"],
            scale_mode=fft_data["scale"],
            dominant_frequency_hz=fft_data["dominant_frequency_hz"],
        )
        cleanup_temp_download(png_path)
        return send_file(
            png_path,
            mimetype="image/png",
            as_attachment=True,
            download_name=f"{context['file_name']}_fft_{fft_data['channel']}.png",
        )

    @app.route("/download_derivative_graph")
    def download_derivative_graph():
        if not state_get("calculus_enabled"):
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
        return send_file(
            png_path,
            mimetype="image/png",
            as_attachment=True,
            download_name=f"{context['file_name']}_derivative_{context['calculus_data']['channel']}.png",
        )

    @app.route("/download_integral_graph")
    def download_integral_graph():
        if not state_get("calculus_enabled"):
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
        return send_file(
            png_path,
            mimetype="image/png",
            as_attachment=True,
            download_name=f"{context['file_name']}_integral_{context['calculus_data']['channel']}.png",
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

        png_path = generate_xy_grafic_download(
            x_signal[:length],
            y_signal[:length],
            f"X-Y Mode {settings['x_channel']} vs {settings['y_channel']}",
            x_label=f"{settings['x_channel']} (V)",
            y_label=f"{settings['y_channel']} (V)",
        )
        cleanup_temp_download(png_path)
        return send_file(
            png_path,
            mimetype="image/png",
            as_attachment=True,
            download_name=f"{context['file_name']}_xy_{settings['x_channel']}_vs_{settings['y_channel']}.png",
        )
