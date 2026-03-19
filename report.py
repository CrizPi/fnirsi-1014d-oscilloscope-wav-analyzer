from plot_maker import (
    generate_correlation_grafic_file,
    generate_fft_grafic_file,
    generate_grafic_file,
    generate_signal_analysis_grafic_file,
)


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


def generate_grafic_download(t, ch1, ch2, file_name, measures=None, show_empty=False):
    return generate_grafic_file(t, ch1, ch2, file_name, measures=measures, show_empty=show_empty)


def generate_grafic_download_math(t, ch1, ch2, file_name, math_result=None):
    return generate_grafic_file(t, ch1, ch2, file_name, math_result=math_result, show_empty=True)


def generate_fft_grafic_download(
    frequencies_hz,
    magnitudes,
    file_name,
    channel_label,
    scale_mode="linear",
    dominant_frequency_hz=0.0,
):
    return generate_fft_grafic_file(
        frequencies_hz,
        magnitudes,
        file_name,
        channel_label,
        scale_mode=scale_mode,
        dominant_frequency_hz=dominant_frequency_hz,
    )


def generate_signal_analysis_download(t, signal, title, y_label):
    return generate_signal_analysis_grafic_file(t, signal, title, y_label)


def generate_correlation_grafic_download(lags_seconds, correlation, title, marker_x=None, marker_y=None):
    return generate_correlation_grafic_file(lags_seconds, correlation, title, marker_x=marker_x, marker_y=marker_y)


def generate_latex_table(rows, caption="Tabla", headers=("X", "Y")):
    has_third_column = bool(headers[1])

    if has_third_column:
        latex = r"""
\begin{table}[h]
\centering
\begin{tabular}{|c|c|c|}
\hline
"""
        latex += f"Measure & {_latex_escape(headers[0])} & {_latex_escape(headers[1])} \\\\\n\\hline\n"
    else:
        latex = r"""
\begin{table}[h]
\centering
\begin{tabular}{|c|c|}
\hline
"""
        latex += f"Measure & {_latex_escape(headers[0])} \\\\\n\\hline\n"

    for row in rows:
        if has_third_column:
            measure, value_1, value_2 = row
            latex += f"{_latex_escape(measure)} & {_latex_escape(value_1)} & {_latex_escape(value_2)} \\\\\n\\hline\n"
        else:
            measure, value_1, _ = row
            latex += f"{_latex_escape(measure)} & {_latex_escape(value_1)} \\\\\n\\hline\n"

    latex += f"""
\\end{{tabular}}
\\caption{{{_latex_escape(caption)}}}
\\end{{table}}
"""
    return latex


def generate_measures_latex(measures):
    rows = [
        ("Vmax", f"{measures['Vmax'][0]} V", f"{measures['Vmax'][1]} V"),
        ("Vmin", f"{measures['Vmin'][0]} V", f"{measures['Vmin'][1]} V"),
        ("Vavg", f"{measures['Vavg'][0]} V", f"{measures['Vavg'][1]} V"),
        ("Vrms", f"{measures['Vrms'][0]} Vrms", f"{measures['Vrms'][1]} Vrms"),
        ("Vpp", f"{measures['Vpp'][0]} Vpp", f"{measures['Vpp'][1]} Vpp"),
        ("Vp", f"{measures['Vp'][0]} Vp", f"{measures['Vp'][1]} Vp"),
        ("Freq", f"{measures['Freq'][0]} {measures['freq_units'][0]}", f"{measures['Freq'][1]} {measures['freq_units'][1]}"),
        ("Cycle", f"{measures['Cycle'][0]} {measures['cycle_units'][0]}", f"{measures['Cycle'][1]} {measures['cycle_units'][1]}"),
        ("Time+", f"{measures['Time+'][0]} {measures['time_plus_units'][0]}", f"{measures['Time+'][1]} {measures['time_plus_units'][1]}"),
        ("Time-", f"{measures['Time-'][0]} {measures['time_minus_units'][0]}", f"{measures['Time-'][1]} {measures['time_minus_units'][1]}"),
        ("Duty+", f"{measures['Duty+'][0]} \\%", f"{measures['Duty+'][1]} \\%"),
        ("Duty-", f"{measures['Duty-'][0]} \\%", f"{measures['Duty-'][1]} \\%"),
    ]
    return generate_latex_table(rows, caption="Oscilloscope Measurements")


def generate_math_measures_latex(math_measures, operation=None):
    rows = [
        ("Vmax", f"{math_measures['Vmax']} V", ""),
        ("Vmin", f"{math_measures['Vmin']} V", ""),
        ("Vavg", f"{math_measures['Vavg']} V", ""),
        ("Vrms", f"{math_measures['Vrms']} Vrms", ""),
        ("Vpp", f"{math_measures['Vpp']} Vpp", ""),
        ("Vp", f"{math_measures['Vp']} Vp", ""),
        ("Freq", f"{math_measures['Freq']} {math_measures['freq_unit']}", ""),
        ("Cycle", f"{math_measures['Cycle']} {math_measures['cycle_unit']}", ""),
        ("Time+", f"{math_measures['Time+']} {math_measures['time_plus_unit']}", ""),
        ("Time-", f"{math_measures['Time-']} {math_measures['time_minus_unit']}", ""),
        ("Duty+", f"{math_measures['Duty+']} \\%", ""),
        ("Duty-", f"{math_measures['Duty-']} \\%", ""),
    ]
    caption = "Oscilloscope MATH Measurements"
    if operation:
        caption += f" ({operation})"
    return generate_latex_table(rows, caption=caption, headers=("Value", ""))


def generate_statistics_latex(statistics_data):
    if statistics_data.get("math_enabled"):
        latex = r"""
\begin{table}[h]
\centering
\begin{tabular}{|c|c|c|c|}
\hline
Measure & X & Y & MATH \\
\hline
"""
        rows = [
            ("Mean", f"{statistics_data['X']['mean']} V", f"{statistics_data['Y']['mean']} V", f"{statistics_data['MATH']['mean']} V"),
            ("Std Dev", f"{statistics_data['X']['std_dev']} V", f"{statistics_data['Y']['std_dev']} V", f"{statistics_data['MATH']['std_dev']} V"),
            ("Variance", f"{statistics_data['X']['variance']} V^2", f"{statistics_data['Y']['variance']} V^2", f"{statistics_data['MATH']['variance']} V^2"),
            ("Median", f"{statistics_data['X']['median']} V", f"{statistics_data['Y']['median']} V", f"{statistics_data['MATH']['median']} V"),
            ("Min", f"{statistics_data['X']['min']} V", f"{statistics_data['Y']['min']} V", f"{statistics_data['MATH']['min']} V"),
            ("Max", f"{statistics_data['X']['max']} V", f"{statistics_data['Y']['max']} V", f"{statistics_data['MATH']['max']} V"),
            ("Range", f"{statistics_data['X']['range']} V", f"{statistics_data['Y']['range']} V", f"{statistics_data['MATH']['range']} V"),
            ("RMS", f"{statistics_data['X']['rms']} V", f"{statistics_data['Y']['rms']} V", f"{statistics_data['MATH']['rms']} V"),
            ("Peak-to-Peak", f"{statistics_data['X']['peak_to_peak']} V", f"{statistics_data['Y']['peak_to_peak']} V", f"{statistics_data['MATH']['peak_to_peak']} V"),
        ]
        for measure, x_value, y_value, math_value in rows:
            latex += f"{_latex_escape(measure)} & {_latex_escape(x_value)} & {_latex_escape(y_value)} & {_latex_escape(math_value)} \\\\\n\\hline\n"
        latex += r"""
\end{tabular}
\caption{Signal Statistics}
\end{table}
"""
        return latex

    rows = [
        ("Mean", f"{statistics_data['X']['mean']} V", f"{statistics_data['Y']['mean']} V"),
        ("Std Dev", f"{statistics_data['X']['std_dev']} V", f"{statistics_data['Y']['std_dev']} V"),
        ("Variance", f"{statistics_data['X']['variance']} V^2", f"{statistics_data['Y']['variance']} V^2"),
        ("Median", f"{statistics_data['X']['median']} V", f"{statistics_data['Y']['median']} V"),
        ("Min", f"{statistics_data['X']['min']} V", f"{statistics_data['Y']['min']} V"),
        ("Max", f"{statistics_data['X']['max']} V", f"{statistics_data['Y']['max']} V"),
        ("Range", f"{statistics_data['X']['range']} V", f"{statistics_data['Y']['range']} V"),
        ("RMS", f"{statistics_data['X']['rms']} V", f"{statistics_data['Y']['rms']} V"),
        ("Peak-to-Peak", f"{statistics_data['X']['peak_to_peak']} V", f"{statistics_data['Y']['peak_to_peak']} V"),
    ]
    return generate_latex_table(rows, caption="Signal Statistics")


def generate_advanced_measures_latex(advanced_data):
    latex = r"""
\begin{table}[h]
\centering
\begin{tabular}{|c|c|c|c|}
\hline
Measure & X & Y & MATH \\
\hline
"""
    rows = [
        ("Rise Time", f"{advanced_data['X']['rise_time']} {advanced_data['X']['rise_time_unit']}", f"{advanced_data['Y']['rise_time']} {advanced_data['Y']['rise_time_unit']}", f"{advanced_data['MATH']['rise_time']} {advanced_data['MATH']['rise_time_unit']}" if advanced_data.get("math_enabled") else "-"),
        ("Fall Time", f"{advanced_data['X']['fall_time']} {advanced_data['X']['fall_time_unit']}", f"{advanced_data['Y']['fall_time']} {advanced_data['Y']['fall_time_unit']}", f"{advanced_data['MATH']['fall_time']} {advanced_data['MATH']['fall_time_unit']}" if advanced_data.get("math_enabled") else "-"),
        ("Overshoot", f"{advanced_data['X']['overshoot']} %", f"{advanced_data['Y']['overshoot']} %", f"{advanced_data['MATH']['overshoot']} %" if advanced_data.get("math_enabled") else "-"),
        ("Undershoot", f"{advanced_data['X']['undershoot']} %", f"{advanced_data['Y']['undershoot']} %", f"{advanced_data['MATH']['undershoot']} %" if advanced_data.get("math_enabled") else "-"),
        ("Slew Rate", f"{advanced_data['X']['slew_rate']} {advanced_data['X']['slew_rate_unit']}", f"{advanced_data['Y']['slew_rate']} {advanced_data['Y']['slew_rate_unit']}", f"{advanced_data['MATH']['slew_rate']} {advanced_data['MATH']['slew_rate_unit']}" if advanced_data.get("math_enabled") else "-"),
        ("Crest Factor", f"{advanced_data['X']['crest_factor']}", f"{advanced_data['Y']['crest_factor']}", f"{advanced_data['MATH']['crest_factor']}" if advanced_data.get("math_enabled") else "-"),
    ]
    for measure, x_value, y_value, math_value in rows:
        latex += f"{_latex_escape(measure)} & {_latex_escape(x_value)} & {_latex_escape(y_value)} & {_latex_escape(math_value)} \\\\\n\\hline\n"
    latex += r"""
\end{tabular}
\caption{Advanced Signal Measures}
\end{table}
"""
    return latex


def generate_correlation_latex(correlation_data):
    rows = [
        ("Max Correlation", f"{correlation_data['max_correlation']}", ""),
        ("Delay", f"{correlation_data['delay_value']} {correlation_data['delay_unit']}", ""),
    ]
    return generate_latex_table(rows, caption="Channel Correlation", headers=("Value", ""))


def generate_fft_latex(fft_data):
    lines = [
        r"\section*{FFT Analysis}",
        rf"Channel: {_latex_escape(fft_data.get('channel', 'X'))}\\",
        rf"Window: {_latex_escape(fft_data.get('window_type', 'hann'))}\\",
        rf"Dominant frequency: {_latex_escape(fft_data.get('dominant_frequency', 0))} {_latex_escape(fft_data.get('dominant_frequency_unit', 'Hz'))}\\",
        rf"Dominant amplitude: {_latex_escape(fft_data.get('dominant_magnitude', 0))} V\\",
        rf"THD: {_latex_escape(fft_data.get('thd_percent', 0))} \%",
        "",
        r"\subsection*{Top Peaks}",
        r"\begin{tabular}{|c|c|c|}",
        r"\hline",
        r"Index & Frequency & Amplitude \\",
        r"\hline",
    ]
    for index, peak in enumerate(fft_data.get("top_peaks", []), start=1):
        lines.append(
            f"{index} & {_latex_escape(peak['frequency'])} {_latex_escape(peak['frequency_unit'])} & {_latex_escape(peak['magnitude'])} \\\\"
        )
        lines.append(r"\hline")
    lines.extend([r"\end{tabular}", "", r"\subsection*{Harmonics}", r"\begin{tabular}{|c|c|c|}", r"\hline", r"Order & Frequency & Amplitude \\", r"\hline"])
    for harmonic in fft_data.get("harmonics", []):
        lines.append(
            f"{harmonic['order']} & {_latex_escape(harmonic['frequency'])} {_latex_escape(harmonic['frequency_unit'])} & {_latex_escape(harmonic['magnitude'])} \\\\"
        )
        lines.append(r"\hline")
    lines.append(r"\end{tabular}")
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


def generate_calibration_latex(calibration_settings):
    rows = [
        ("X Gain", calibration_settings.get("x_gain", 1), ""),
        ("Y Gain", calibration_settings.get("y_gain", 1), ""),
        ("X Offset", f"{calibration_settings.get('x_offset', 0)} V", ""),
        ("Y Offset", f"{calibration_settings.get('y_offset', 0)} V", ""),
        ("Invert X", calibration_settings.get("invert_x", False), ""),
        ("Invert Y", calibration_settings.get("invert_y", False), ""),
        ("Normalize", calibration_settings.get("normalize", False), ""),
    ]
    return generate_latex_table(rows, caption="Signal Calibration", headers=("Value", ""))


def generate_comparison_latex(comparison_data):
    rows = [
        ("Snapshot", comparison_data.get("snapshot_name", "-"), ""),
        ("Current file", comparison_data.get("current_file", "-"), ""),
        ("Saved file", comparison_data.get("saved_file", "-"), ""),
        ("Delta Vpp X", f"{comparison_data.get('delta_vpp_x', 0)} V", ""),
        ("Delta Vpp Y", f"{comparison_data.get('delta_vpp_y', 0)} V", ""),
        ("Delta Freq X", f"{comparison_data.get('delta_freq_x', 0)} {comparison_data.get('delta_freq_x_unit', 'Hz')}", ""),
        ("Delta Freq Y", f"{comparison_data.get('delta_freq_y', 0)} {comparison_data.get('delta_freq_y_unit', 'Hz')}", ""),
    ]
    return generate_latex_table(rows, caption="Snapshot Comparison", headers=("Value", ""))

