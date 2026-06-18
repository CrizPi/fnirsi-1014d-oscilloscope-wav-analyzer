def _channel_label(channel_id, ch1_name="CH1", ch2_name="CH2"):
    if channel_id in ("X", "CH1"):
        return ch1_name
    if channel_id in ("Y", "CH2"):
        return ch2_name
    return str(channel_id)


def _latex_escape(value):
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "_": r"\_",
        "%": r"\%",
        "&": r"\&",
        "#": r"\#",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def generate_grafic_download(t, ch1, ch2, file_name, measures=None, scope_config=None, show_empty=False, ch1_name="CH1", ch2_name="CH2"):
    from plot_maker import generate_grafic_file
    return generate_grafic_file(t, ch1, ch2, file_name, measures=measures, scope_config=scope_config, show_empty=show_empty, ch1_name=ch1_name, ch2_name=ch2_name)


def generate_grafic_download_math(t, ch1, ch2, file_name, math_result=None, ch1_name="CH1", ch2_name="CH2"):
    from plot_maker import generate_grafic_file
    return generate_grafic_file(t, ch1, ch2, file_name, math_result=math_result, show_empty=True, ch1_name=ch1_name, ch2_name=ch2_name)


def generate_fft_grafic_download(
    frequencies_hz,
    magnitudes,
    file_name,
    channel_label,
    scale_mode="linear",
    dominant_frequency_hz=0.0,
):
    from plot_maker import generate_fft_grafic_file
    return generate_fft_grafic_file(
        frequencies_hz,
        magnitudes,
        file_name,
        channel_label,
        scale_mode=scale_mode,
        dominant_frequency_hz=dominant_frequency_hz,
    )


def generate_signal_analysis_download(t, signal, title, y_label):
    from plot_maker import generate_signal_analysis_grafic_file
    return generate_signal_analysis_grafic_file(t, signal, title, y_label)


def generate_correlation_grafic_download(lags_seconds, correlation, title, marker_x=None, marker_y=None):
    from plot_maker import generate_correlation_grafic_file
    return generate_correlation_grafic_file(lags_seconds, correlation, title, marker_x=marker_x, marker_y=marker_y)


def generate_current_grafic_download(t, voltage, current, title, voltage_channel=None):
    from plot_maker import generate_voltage_current_grafic_file
    return generate_voltage_current_grafic_file(t, voltage, current, title, voltage_channel=voltage_channel)


def generate_xy_grafic_download(x_signal, y_signal, title, x_label="X (V)", y_label="Y (V)"):
    from plot_maker import generate_xy_mode_grafic_file
    return generate_xy_mode_grafic_file(x_signal, y_signal, title, x_label=x_label, y_label=y_label)


def _caption_to_label(caption):
    """Convert a caption string to a LaTeX label (e.g. 'tab:oscilloscope-measurements')."""
    label = caption.strip().lower()
    label = "".join(c if c.isalnum() else "-" for c in label)
    label = "-".join(filter(None, label.split("-")))
    return f"tab:{label}" if label else "tab:table"


def generate_latex_table(rows, caption="Tabla", headers=("X", "Y")):
    has_third_column = bool(headers[1])
    has_unit_column = any(len(row) > 3 and row[3] for row in rows)
    num_val_cols = 2 if has_third_column else 1
    col_count = 1 + num_val_cols  # measure + value columns (units are now inline)

    # IEEE-style: left-aligned measure column, centered data columns
    col_spec = "l" + "c" * (col_count - 1)

    latex = r"""
\begin{table}[htbp]
\caption{""" + _latex_escape(caption) + r"""}
\label{""" + _caption_to_label(caption) + r"""}
\centering
\begin{tabular}{""" + col_spec + r"""}
\hline
"""

    if has_unit_column:
        if num_val_cols == 2:
            latex += f"Measure & {_latex_escape(headers[0])} & {_latex_escape(headers[1])} \\\\\n\\hline\n"
        else:
            latex += f"Measure & {_latex_escape(headers[0])} \\\\\n\\hline\n"
        for row in rows:
            measure = row[0]
            vals = list(row[1:1+num_val_cols])
            unit = _latex_escape(row[3]) if len(row) > 3 and row[3] else ""
            cells = " & ".join(
                f"{_latex_escape(v)} {unit}" if unit else _latex_escape(v)
                for v in vals
            )
            latex += f"{_latex_escape(measure)} & {cells} \\\\\n"
    elif has_third_column:
        latex += f"Measure & {_latex_escape(headers[0])} & {_latex_escape(headers[1])} \\\\\n\\hline\n"
        for row in rows:
            measure, value_1, value_2 = row[:3]
            latex += f"{_latex_escape(measure)} & {_latex_escape(value_1)} & {_latex_escape(value_2)} \\\\\n"
    else:
        latex += f"Measure & {_latex_escape(headers[0])} \\\\\n\\hline\n"
        for row in rows:
            measure, value_1 = row[0], row[1]
            latex += f"{_latex_escape(measure)} & {_latex_escape(value_1)} \\\\\n"

    latex += r"""
\hline
\end{tabular}
\end{table}
"""
    return latex


def generate_measures_latex(measures, ch1_name="CH1", ch2_name="CH2"):
    rows = [
        ("Vmax", f"{measures['Vmax'][0]}", f"{measures['Vmax'][1]}", "V"),
        ("Vmin", f"{measures['Vmin'][0]}", f"{measures['Vmin'][1]}", "V"),
        ("Vavg", f"{measures['Vavg'][0]}", f"{measures['Vavg'][1]}", "V"),
        ("Vrms", f"{measures['Vrms'][0]}", f"{measures['Vrms'][1]}", "V"),
        ("Vpp", f"{measures['Vpp'][0]}", f"{measures['Vpp'][1]}", "V"),
        ("Vp", f"{measures['Vp'][0]}", f"{measures['Vp'][1]}", "V"),
        ("Freq", f"{measures['Freq'][0]}", f"{measures['Freq'][1]}", measures['freq_units'][0]),
        ("Cycle", f"{measures['Cycle'][0]}", f"{measures['Cycle'][1]}", measures['cycle_units'][0]),
        ("Time+", f"{measures['Time+'][0]}", f"{measures['Time+'][1]}", measures['time_plus_units'][0]),
        ("Time-", f"{measures['Time-'][0]}", f"{measures['Time-'][1]}", measures['time_minus_units'][0]),
        ("Duty+", f"{measures['Duty+'][0]}", f"{measures['Duty+'][1]}", "\\%"),
        ("Duty-", f"{measures['Duty-'][0]}", f"{measures['Duty-'][1]}", "\\%"),
    ]
    return generate_latex_table(rows, caption="Oscilloscope Measurements", headers=(ch1_name, ch2_name))


def generate_math_measures_latex(math_measures, operation=None):
    rows = [
        ("Vmax", f"{math_measures['Vmax']}", "", "V"),
        ("Vmin", f"{math_measures['Vmin']}", "", "V"),
        ("Vavg", f"{math_measures['Vavg']}", "", "V"),
        ("Vrms", f"{math_measures['Vrms']}", "", "V"),
        ("Vpp", f"{math_measures['Vpp']}", "", "V"),
        ("Vp", f"{math_measures['Vp']}", "", "V"),
        ("Freq", f"{math_measures['Freq']}", "", math_measures['freq_unit']),
        ("Cycle", f"{math_measures['Cycle']}", "", math_measures['cycle_unit']),
        ("Time+", f"{math_measures['Time+']}", "", math_measures['time_plus_unit']),
        ("Time-", f"{math_measures['Time-']}", "", math_measures['time_minus_unit']),
        ("Duty+", f"{math_measures['Duty+']}", "", "\\%"),
        ("Duty-", f"{math_measures['Duty-']}", "", "\\%"),
    ]
    caption = "Oscilloscope MATH Measurements"
    if operation:
        caption += f" ({operation})"
    return generate_latex_table(rows, caption=caption, headers=("Value", ""))


def generate_statistics_latex(statistics_data, ch1_name="CH1", ch2_name="CH2"):
    unit_map = {"Mean": "V", "Std Dev": "V", "Variance": "V$^2$", "Median": "V",
                "Min": "V", "Max": "V", "Range": "V", "RMS": "V", "Peak-to-Peak": "V"}
    if statistics_data.get("math_enabled"):
        latex = r"""
\begin{table}[htbp]
\caption{Signal Statistics}
\label{tab:signal-statistics}
\centering
\begin{tabular}{lccc}
\hline
Measure & """ + _latex_escape(ch1_name) + r""" & """ + _latex_escape(ch2_name) + r""" & MATH \\
\hline
"""
        stat_rows = [
            ("Mean", f"{statistics_data['X']['mean']}", f"{statistics_data['Y']['mean']}", f"{statistics_data['MATH']['mean']}"),
            ("Std Dev", f"{statistics_data['X']['std_dev']}", f"{statistics_data['Y']['std_dev']}", f"{statistics_data['MATH']['std_dev']}"),
            ("Variance", f"{statistics_data['X']['variance']}", f"{statistics_data['Y']['variance']}", f"{statistics_data['MATH']['variance']}"),
            ("Median", f"{statistics_data['X']['median']}", f"{statistics_data['Y']['median']}", f"{statistics_data['MATH']['median']}"),
            ("Min", f"{statistics_data['X']['min']}", f"{statistics_data['Y']['min']}", f"{statistics_data['MATH']['min']}"),
            ("Max", f"{statistics_data['X']['max']}", f"{statistics_data['Y']['max']}", f"{statistics_data['MATH']['max']}"),
            ("Range", f"{statistics_data['X']['range']}", f"{statistics_data['Y']['range']}", f"{statistics_data['MATH']['range']}"),
            ("RMS", f"{statistics_data['X']['rms']}", f"{statistics_data['Y']['rms']}", f"{statistics_data['MATH']['rms']}"),
            ("Peak-to-Peak", f"{statistics_data['X']['peak_to_peak']}", f"{statistics_data['Y']['peak_to_peak']}", f"{statistics_data['MATH']['peak_to_peak']}"),
        ]
        for measure, x_value, y_value, math_value in stat_rows:
            unit = _latex_escape(unit_map.get(measure, ""))
            sep = " " if unit else ""
            latex += f"{_latex_escape(measure)} & {_latex_escape(x_value)}{sep}{unit} & {_latex_escape(y_value)}{sep}{unit} & {_latex_escape(math_value)}{sep}{unit} \\\\\n"
        latex += r"""
\hline
\end{tabular}
\end{table}
"""
        return latex

    rows = [
        ("Mean", f"{statistics_data['X']['mean']}", f"{statistics_data['Y']['mean']}", "V"),
        ("Std Dev", f"{statistics_data['X']['std_dev']}", f"{statistics_data['Y']['std_dev']}", "V"),
        ("Variance", f"{statistics_data['X']['variance']}", f"{statistics_data['Y']['variance']}", "V$^2$"),
        ("Median", f"{statistics_data['X']['median']}", f"{statistics_data['Y']['median']}", "V"),
        ("Min", f"{statistics_data['X']['min']}", f"{statistics_data['Y']['min']}", "V"),
        ("Max", f"{statistics_data['X']['max']}", f"{statistics_data['Y']['max']}", "V"),
        ("Range", f"{statistics_data['X']['range']}", f"{statistics_data['Y']['range']}", "V"),
        ("RMS", f"{statistics_data['X']['rms']}", f"{statistics_data['Y']['rms']}", "V"),
        ("Peak-to-Peak", f"{statistics_data['X']['peak_to_peak']}", f"{statistics_data['Y']['peak_to_peak']}", "V"),
    ]
    return generate_latex_table(rows, caption="Signal Statistics", headers=(ch1_name, ch2_name))


def generate_advanced_measures_latex(advanced_data, ch1_name="CH1", ch2_name="CH2"):
    latex = r"""
\begin{table}[htbp]
\caption{Advanced Signal Measures}
\label{tab:advanced-signal-measures}
\centering
\begin{tabular}{lccc}
\hline
Measure & """ + _latex_escape(ch1_name) + r""" & """ + _latex_escape(ch2_name) + r""" & MATH \\
\hline
"""
    def math_or_dash(key, subkey):
        if advanced_data.get("math_enabled"):
            v = advanced_data['MATH'].get(subkey, "-")
            u = advanced_data['MATH'].get(subkey + "_unit", "")
            return f"{v}" if u else f"{v}"
        return "-"
    math_enabled = advanced_data.get("math_enabled", False)
    rows = [
        ("Rise Time", f"{advanced_data['X']['rise_time']}", f"{advanced_data['Y']['rise_time']}", f"{advanced_data['MATH']['rise_time']}" if math_enabled else "-", advanced_data['X']['rise_time_unit']),
        ("Fall Time", f"{advanced_data['X']['fall_time']}", f"{advanced_data['Y']['fall_time']}", f"{advanced_data['MATH']['fall_time']}" if math_enabled else "-", advanced_data['X']['fall_time_unit']),
        ("Overshoot", f"{advanced_data['X']['overshoot']}", f"{advanced_data['Y']['overshoot']}", f"{advanced_data['MATH']['overshoot']}" if math_enabled else "-", "\\%"),
        ("Undershoot", f"{advanced_data['X']['undershoot']}", f"{advanced_data['Y']['undershoot']}", f"{advanced_data['MATH']['undershoot']}" if math_enabled else "-", "\\%"),
        ("Slew Rate", f"{advanced_data['X']['slew_rate']}", f"{advanced_data['Y']['slew_rate']}", f"{advanced_data['MATH']['slew_rate']}" if math_enabled else "-", advanced_data['X']['slew_rate_unit']),
        ("Crest Factor", f"{advanced_data['X']['crest_factor']}", f"{advanced_data['Y']['crest_factor']}", f"{advanced_data['MATH']['crest_factor']}" if math_enabled else "-", ""),
    ]
    for measure, x_value, y_value, math_value, unit in rows:
        unit_esc = _latex_escape(unit)
        sep = f" {unit_esc}" if unit_esc else ""
        latex += f"{_latex_escape(measure)} & {_latex_escape(x_value)}{sep} & {_latex_escape(y_value)}{sep} & {_latex_escape(math_value)}{sep} \\\\\n"
    latex += r"""
\hline
\end{tabular}
\end{table}
"""
    return latex


def generate_correlation_latex(correlation_data):
    rows = [
        ("Max Correlation", f"{correlation_data['max_correlation']}", ""),
        ("Delay", f"{correlation_data['delay_value']} {correlation_data['delay_unit']}", ""),
    ]
    return generate_latex_table(rows, caption="Channel Correlation", headers=("Value", ""))


def generate_fft_latex(fft_data, ch1_name="CH1", ch2_name="CH2"):
    lines = [
        r"\section*{FFT Analysis}",
        rf"Channel: {_latex_escape(_channel_label(fft_data.get('channel', 'X'), ch1_name, ch2_name))}\\",
        rf"Window: {_latex_escape(fft_data.get('window_type', 'hann'))}\\",
        rf"Dominant frequency: {_latex_escape(fft_data.get('dominant_frequency', 0))} {_latex_escape(fft_data.get('dominant_frequency_unit', 'Hz'))}\\",
        rf"Dominant amplitude: {_latex_escape(fft_data.get('dominant_magnitude', 0))} V\\",
        rf"THD: {_latex_escape(fft_data.get('thd_percent', 0))} \%",
        "",
        r"\begin{table}[htbp]",
        r"\caption{FFT Top Peaks}",
        r"\label{tab:fft-top-peaks}",
        r"\centering",
        r"\begin{tabular}{lcc}",
        r"\hline",
        r"Index & Frequency & Amplitude \\",
        r"\hline",
    ]
    for index, peak in enumerate(fft_data.get("top_peaks", []), start=1):
        lines.append(
            f"{index} & {_latex_escape(peak['frequency'])} {_latex_escape(peak['frequency_unit'])} & {_latex_escape(peak['magnitude'])} \\\\"
        )
    lines.extend([r"\hline", r"\end{tabular}", r"\end{table}", "", r"\begin{table}[htbp]", r"\caption{FFT Harmonics}", r"\label{tab:fft-harmonics}", r"\centering", r"\begin{tabular}{lcc}", r"\hline", r"Order & Frequency & Amplitude \\", r"\hline"])
    for harmonic in fft_data.get("harmonics", []):
        lines.append(
            f"{harmonic['order']} & {_latex_escape(harmonic['frequency'])} {_latex_escape(harmonic['frequency_unit'])} & {_latex_escape(harmonic['magnitude'])} \\\\"
        )
    lines.extend([r"\hline", r"\end{tabular}", r"\end{table}"])
    return "\n".join(lines)


def generate_cursor_latex(cursor_data):
    rows = [
        ("t1", f"{cursor_data['t1']} s", ""),
        ("t2", f"{cursor_data['t2']} s", ""),
        ("V1", f"{cursor_data['v1']} V", ""),
        ("V2", f"{cursor_data['v2']} V", ""),
        ("Delta t", f"{cursor_data['delta_t']} {cursor_data['delta_t_unit']}", ""),
        ("Delta V", f"{cursor_data['delta_v']} V", ""),
        ("Estimated Freq", f"{cursor_data['estimated_frequency']} {cursor_data['estimated_frequency_unit']}", ""),
    ]
    return generate_latex_table(rows, caption="Manual Cursor Measurement", headers=("Value", ""))


def generate_cycle_latex(cycle_data):
    rows = [
        ("Cycles", f"{cycle_data['cycle_count']}", ""),
        ("Average Frequency", f"{cycle_data['avg_frequency']} {cycle_data['avg_frequency_unit']}", ""),
        ("Average Period", f"{cycle_data['avg_period']} {cycle_data['avg_period_unit']}", ""),
        ("Average Vpp", f"{cycle_data['avg_vpp']} V", ""),
        ("Average RMS", f"{cycle_data['avg_rms']} V", ""),
    ]
    return generate_latex_table(rows, caption="Cycle Analysis", headers=("Value", ""))


def generate_calibration_latex(calibration_settings, ch1_name="CH1", ch2_name="CH2"):
    rows = [
        (f"Gain {ch1_name}", calibration_settings.get("x_gain", 1), ""),
        (f"Gain {ch2_name}", calibration_settings.get("y_gain", 1), ""),
        (f"Offset {ch1_name}", f"{calibration_settings.get('x_offset', 0)} V", ""),
        (f"Offset {ch2_name}", f"{calibration_settings.get('y_offset', 0)} V", ""),
        (f"Invert {ch1_name}", calibration_settings.get("invert_x", False), ""),
        (f"Invert {ch2_name}", calibration_settings.get("invert_y", False), ""),
        ("Normalize", calibration_settings.get("normalize", False), ""),
    ]
    return generate_latex_table(rows, caption="Signal Calibration", headers=("Value", ""))


def generate_comparison_latex(comparison_data, ch1_name="CH1", ch2_name="CH2"):
    rows = [
        ("Snapshot", comparison_data.get("snapshot_name", "-"), ""),
        ("Current file", comparison_data.get("current_file", "-"), ""),
        ("Saved file", comparison_data.get("saved_file", "-"), ""),
        (f"Delta Vpp {ch1_name}", f"{comparison_data.get('delta_vpp_x', 0)} V", ""),
        (f"Delta Vpp {ch2_name}", f"{comparison_data.get('delta_vpp_y', 0)} V", ""),
        (f"Delta Freq {ch1_name}", f"{comparison_data.get('delta_freq_x', 0)} {comparison_data.get('delta_freq_x_unit', 'Hz')}", ""),
        (f"Delta Freq {ch2_name}", f"{comparison_data.get('delta_freq_y', 0)} {comparison_data.get('delta_freq_y_unit', 'Hz')}", ""),
    ]
    return generate_latex_table(rows, caption="Snapshot Comparison", headers=("Value", ""))


def generate_current_latex(current_data, ch1_name="CH1", ch2_name="CH2"):
    method_labels = {
        "resistor": "Resistor (i(t)=v(t)/R)",
        "capacitor": "Capacitor (i(t)=C dv(t)/dt)",
        "inductor": "Inductor (i(t)=(1/L) integral v(t) dt)",
    }
    unit_labels = {
        "resistor": "ohm",
        "capacitor": "F",
        "inductor": "H",
    }
    method = current_data.get("method", "resistor")
    rows = [
        ("Channel", _channel_label(current_data.get("channel", "X"), ch1_name, ch2_name), ""),
        ("Method", method_labels.get(method, method), ""),
        ("Component value", f"{current_data.get('component_value', 0)} {unit_labels.get(method, '')}", ""),
        ("Initial condition", current_data.get("inductor_initial_mode", "zero"), ""),
        ("RMS voltage", f"{current_data.get('voltage_rms', 0)} V", ""),
        ("Mean current", f"{current_data.get('current_mean', 0)} A", ""),
        ("RMS current", f"{current_data.get('current_rms', 0)} A", ""),
        ("Max current", f"{current_data.get('current_max', 0)} A", ""),
        ("Min current", f"{current_data.get('current_min', 0)} A", ""),
        ("Peak-to-peak current", f"{current_data.get('current_peak_to_peak', 0)} A", ""),
        ("Phase angle", f"{current_data.get('phase_angle_deg', 0)} deg", ""),
        ("Apparent power", f"{current_data.get('apparent_power_va', 0)} VA", ""),
        ("Active power", f"{current_data.get('active_power_w', 0)} W", ""),
        ("Reactive power", f"{current_data.get('reactive_power_var', 0)} VAR", ""),
        ("Complex power", f"{current_data.get('complex_power_real_w', 0)} + j{current_data.get('complex_power_imag_var', 0)} VA", ""),
        ("Power factor", f"{current_data.get('power_factor', 0)}", ""),
    ]
    return generate_latex_table(rows, caption="Calculated Current Analysis", headers=("Value", ""))


def generate_transfer_latex(transfer_data, ch1_name="CH1", ch2_name="CH2"):
    rows = [
        ("Input channel", _channel_label(transfer_data.get("input_channel", "X"), ch1_name, ch2_name), ""),
        ("Output channel", _channel_label(transfer_data.get("output_channel", "Y"), ch1_name, ch2_name), ""),
        ("Vin RMS", f"{transfer_data.get('vin_rms', 0)} V", ""),
        ("Vout RMS", f"{transfer_data.get('vout_rms', 0)} V", ""),
        ("Vin Vpp", f"{transfer_data.get('vin_vpp', 0)} V", ""),
        ("Vout Vpp", f"{transfer_data.get('vout_vpp', 0)} V", ""),
        ("Vout/Vin RMS", f"{transfer_data.get('gain_rms', 0)}", ""),
        ("Vout/Vin Vpp", f"{transfer_data.get('gain_vpp', 0)}", ""),
        ("Gain", f"{transfer_data.get('gain_db', 0)} dB", ""),
        ("Phase angle", f"{transfer_data.get('phase_angle_deg', 0)} deg", ""),
        ("Delay", f"{transfer_data.get('delay_value', 0)} {transfer_data.get('delay_unit', 's')}", ""),
        ("Frequency", f"{transfer_data.get('frequency_hz', 0)} Hz", ""),
        ("Correlation peak", f"{transfer_data.get('correlation_peak', 0)}", ""),
    ]
    return generate_latex_table(rows, caption="Transfer Analysis", headers=("Value", ""))


def generate_total_current_latex(total_current_data, ch1_name="CH1", ch2_name="CH2"):
    rows = [
        ("Voltage channel", _channel_label(total_current_data.get("voltage_channel", "X"), ch1_name, ch2_name), ""),
        ("Combination mode", total_current_data.get("combination_mode", "parallel"), ""),
        ("Frequency tolerance", f"{total_current_data.get('frequency_tolerance_percent', 5)} %", ""),
        ("Saved currents", total_current_data.get("saved_count", 0), ""),
        ("Rejected currents", total_current_data.get("incompatible_count", 0), ""),
        ("RMS voltage", f"{total_current_data.get('voltage_rms', 0)} V", ""),
        ("Mean total current", f"{total_current_data.get('total_current_mean', 0)} A", ""),
        ("RMS total current", f"{total_current_data.get('total_current_rms', 0)} A", ""),
        ("Max total current", f"{total_current_data.get('total_current_max', 0)} A", ""),
        ("Min total current", f"{total_current_data.get('total_current_min', 0)} A", ""),
        ("Peak-to-peak total current", f"{total_current_data.get('total_current_peak_to_peak', 0)} A", ""),
        ("Phase angle", f"{total_current_data.get('phase_angle_deg', 0)} deg", ""),
        ("Apparent power", f"{total_current_data.get('apparent_power_va', 0)} VA", ""),
        ("Active power", f"{total_current_data.get('active_power_w', 0)} W", ""),
        ("Reactive power", f"{total_current_data.get('reactive_power_var', 0)} VAR", ""),
        ("Complex power", f"{total_current_data.get('complex_power_real_w', 0)} + j{total_current_data.get('complex_power_imag_var', 0)} VA", ""),
        ("Power factor", f"{total_current_data.get('power_factor', 0)}", ""),
        ("Series mismatch RMS", f"{total_current_data.get('series_mismatch_rms', 0)} A", ""),
    ]
    return generate_latex_table(rows, caption="Total Current Analysis", headers=("Value", ""))


def generate_config_latex(config, ch1_name="CH1", ch2_name="CH2"):
    rows = [
        (f"Volt/div {ch1_name}", f"{config.get('volts_div', [0, 0])[0]} {config.get('volt_units', ['V', 'V'])[0]}/div", ""),
        (f"Volt/div {ch2_name}", f"{config.get('volts_div', [0, 0])[1]} {config.get('volt_units', ['V', 'V'])[1]}/div", ""),
        (f"Probe {ch1_name}", f"{config.get('probe', [1, 1])[0]}x", ""),
        (f"Probe {ch2_name}", f"{config.get('probe', [1, 1])[1]}x", ""),
        (f"Coupling {ch1_name}", config.get('coupling', ['DC', 'DC'])[0], ""),
        (f"Coupling {ch2_name}", config.get('coupling', ['DC', 'DC'])[1], ""),
        ("Time/div", f"{config.get('time_div', '')} {config.get('time_units', 'S')}/div", ""),
        ("Trigger", f"{config.get('trigger_type', '')} / {config.get('trigger_edge', '')} / {config.get('trigger_channel', '')}", ""),
    ]
    return generate_latex_table(rows, caption="Oscilloscope Configuration", headers=("Value", ""))


def generate_current_snapshots_latex(snapshots):
    rows = []
    for s in snapshots:
        rows.append((s.get("name", "-"), f"{s.get('current_rms', 0)} A ({s.get('frequency_hz', 0)} Hz)", ""))
    if not rows:
        rows.append(("No saved calculations", "-", ""))
    return generate_latex_table(rows, caption="Saved Current Calculations", headers=("Name", "Value"))


def generate_xy_latex(xy_data, ch1_name="CH1", ch2_name="CH2"):
    rows = [
        ("Samples", str(xy_data.get("sample_count", "-")), ""),
        (f"{ch1_name} range", f"{xy_data.get('x_min', '-')} to {xy_data.get('x_max', '-')} V", ""),
        (f"{ch2_name} range", f"{xy_data.get('y_min', '-')} to {xy_data.get('y_max', '-')} V", ""),
        ("Correlation", str(xy_data.get("correlation_coefficient", "-")), ""),
    ]
    return generate_latex_table(rows, caption="X-Y Mode Analysis", headers=("Value", ""))


def generate_snapshots_latex(snapshots):
    rows = []
    for s in snapshots:
        rows.append((s.get("name", "-"), f"{s.get('file_name', '-')} / {s.get('created_at', '-')}", ""))
    if not rows:
        rows.append(("No saved snapshots", "-", ""))
    return generate_latex_table(rows, caption="Saved Snapshots", headers=("Name", "Details"))
