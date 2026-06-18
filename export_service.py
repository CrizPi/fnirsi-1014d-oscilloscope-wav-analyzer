import csv
import tempfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from plot_maker import OscilloscopePlotter


def export_graph_svg(time_axis, ch1, ch2, file_name, scope_config=None):
    plotter = OscilloscopePlotter()
    fig = plotter.create_figure(
        time_axis, ch1, ch2, file_name,
        scope_config=scope_config,
        is_light=True,
    )
    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
        fig.savefig(tmp.name, format="svg", bbox_inches="tight", facecolor=fig.get_facecolor())
        temp_path = tmp.name
    plt.close(fig)
    return temp_path


def export_signals_csv(time_axis, ch1, ch2, file_name, math_result=None, ch1_name="CH1", ch2_name="CH2"):
    time_axis = np.asarray(time_axis, dtype=float)
    ch1 = np.asarray(ch1, dtype=float)
    ch2 = np.asarray(ch2, dtype=float)
    if math_result is not None:
        math_result = np.asarray(math_result, dtype=float)
    length = min(len(time_axis), len(ch1), len(ch2))
    if math_result is not None:
        length = min(length, len(math_result))
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", newline="") as tmp:
        writer = csv.writer(tmp)
        if math_result is not None:
            writer.writerow(["Time (s)", f"{ch1_name} (V)", f"{ch2_name} (V)", "MATH (V)"])
            for i in range(length):
                writer.writerow([
                    f"{time_axis[i]:.9e}",
                    f"{ch1[i]:.6e}",
                    f"{ch2[i]:.6e}",
                    f"{math_result[i]:.6e}" if i < len(math_result) else "",
                ])
        else:
            writer.writerow(["Time (s)", f"{ch1_name} (V)", f"{ch2_name} (V)"])
            for i in range(length):
                writer.writerow([
                    f"{time_axis[i]:.9e}",
                    f"{ch1[i]:.6e}",
                    f"{ch2[i]:.6e}",
                ])
        temp_path = tmp.name
    return temp_path


def export_measurements_csv(measures, label, ch1_name="CH1", ch2_name="CH2"):
    ordered_keys = [
        "Vmax", "Vmin", "Vavg", "Vrms", "Vpp", "Vp",
        "Freq", "Cycle", "Time+", "Time-", "Duty+", "Duty-",
    ]
    unit_suffix = {"Duty+": "%", "Duty-": "%"}
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", newline="") as tmp:
        writer = csv.writer(tmp)
        writer.writerow(["Measure", ch1_name, ch2_name, "Unit"])
        for key in ordered_keys:
            if key not in measures:
                continue
            val_ch1 = str(measures[key][0]) if len(measures[key]) > 0 else ""
            val_ch2 = str(measures[key][1]) if len(measures[key]) > 1 else ""
            if key in unit_suffix:
                unit = unit_suffix[key]
            elif key in ("Freq",):
                unit = str(measures.get("freq_units", [""])[0]) if isinstance(measures.get("freq_units"), list) else str(measures.get("freq_units", ""))
            elif key in ("Cycle",):
                unit = str(measures.get("cycle_units", [""])[0]) if isinstance(measures.get("cycle_units"), list) else str(measures.get("cycle_units", ""))
            elif key in ("Time+",):
                unit = str(measures.get("time_plus_units", [""])[0]) if isinstance(measures.get("time_plus_units"), list) else str(measures.get("time_plus_units", ""))
            elif key in ("Time-",):
                unit = str(measures.get("time_minus_units", [""])[0]) if isinstance(measures.get("time_minus_units"), list) else str(measures.get("time_minus_units", ""))
            else:
                unit = "V"
            writer.writerow([key, val_ch1, val_ch2, unit])
        temp_path = tmp.name
    return temp_path


def export_fft_csv(frequencies_hz, magnitudes):
    frequencies_hz = np.asarray(frequencies_hz, dtype=float)
    magnitudes = np.asarray(magnitudes, dtype=float)
    length = min(len(frequencies_hz), len(magnitudes))
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", newline="") as tmp:
        writer = csv.writer(tmp)
        writer.writerow(["Frequency (Hz)", "Magnitude (V)"])
        for i in range(length):
            writer.writerow([f"{frequencies_hz[i]:.6e}", f"{magnitudes[i]:.6e}"])
        temp_path = tmp.name
    return temp_path


def export_report_pdf(time_axis, ch1, ch2, file_name, config, measures, fft_data=None, math_result=None, statistics_data=None, advanced_data=None, ch1_name="CH1", ch2_name="CH2"):
    from matplotlib.backends.backend_pdf import PdfPages
    from plot_maker import _build_fft_figure

    time_axis = np.asarray(time_axis, dtype=float)
    ch1 = np.asarray(ch1, dtype=float)
    ch2 = np.asarray(ch2, dtype=float)
    if math_result is not None:
        math_result = np.asarray(math_result, dtype=float)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        pdf_path = tmp.name

    with PdfPages(pdf_path) as pdf:
        plotter = OscilloscopePlotter()
        fig = plotter.create_figure(
            time_axis, ch1, ch2, file_name,
            scope_config=config,
            is_light=True,
        )
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        fig2, ax2 = plt.subplots(figsize=(8.5, 11))
        ax2.axis("off")
        _draw_measurements_table(ax2, measures, ch1_name, ch2_name)
        pdf.savefig(fig2, bbox_inches="tight")
        plt.close(fig2)

        if fft_data and fft_data.get("enabled"):
            fft_freq = np.asarray(fft_data.get("frequencies_hz", []), dtype=float)
            fft_mag = np.asarray(fft_data.get("magnitudes", []), dtype=float)
            if fft_freq.size > 0 and fft_mag.size > 0:
                fig3 = _build_fft_figure(
                    fft_freq, fft_mag,
                    fft_data.get("channel", "X"),
                    fft_data.get("scale", "linear"),
                    fft_data.get("dominant_frequency_hz", 0.0),
                    is_light=True,
                    dpi=120,
                    max_frequency_hz=fft_data.get("max_frequency_hz"),
                )[0]
                pdf.savefig(fig3, bbox_inches="tight")
                plt.close(fig3)

        if statistics_data and statistics_data.get("enabled"):
            fig4, ax4 = plt.subplots(figsize=(8.5, 11))
            ax4.axis("off")
            _draw_statistics_table(ax4, statistics_data, ch1_name, ch2_name)
            pdf.savefig(fig4, bbox_inches="tight")
            plt.close(fig4)

    return pdf_path


def _draw_measurements_table(ax, measures, ch1_name, ch2_name):
    rows = [
        ["Measure", ch1_name, ch2_name, "Unit"],
        ["Vmax", _mv(measures, "Vmax", 0), _mv(measures, "Vmax", 1), "V"],
        ["Vmin", _mv(measures, "Vmin", 0), _mv(measures, "Vmin", 1), "V"],
        ["Vavg", _mv(measures, "Vavg", 0), _mv(measures, "Vavg", 1), "V"],
        ["Vrms", _mv(measures, "Vrms", 0), _mv(measures, "Vrms", 1), "V"],
        ["Vpp", _mv(measures, "Vpp", 0), _mv(measures, "Vpp", 1), "V"],
        ["Vp", _mv(measures, "Vp", 0), _mv(measures, "Vp", 1), "V"],
        ["Freq", _mv(measures, "Freq", 0), _mv(measures, "Freq", 1), _mu(measures, "freq_units")],
        ["Cycle", _mv(measures, "Cycle", 0), _mv(measures, "Cycle", 1), _mu(measures, "cycle_units")],
        ["Time+", _mv(measures, "Time+", 0), _mv(measures, "Time+", 1), _mu(measures, "time_plus_units")],
        ["Time-", _mv(measures, "Time-", 0), _mv(measures, "Time-", 1), _mu(measures, "time_minus_units")],
        ["Duty+", _mv(measures, "Duty+", 0), _mv(measures, "Duty+", 1), "%"],
        ["Duty-", _mv(measures, "Duty-", 0), _mv(measures, "Duty-", 1), "%"],
    ]
    table = ax.table(cellText=rows, loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.5)
    for (i, j), cell in table.get_celld().items():
        if i == 0:
            cell.set_text_props(fontweight="bold")
    ax.set_title("Oscilloscope Measurements", fontsize=14, fontweight="bold")


def _draw_statistics_table(ax, statistics_data, ch1_name, ch2_name):
    ch1_stats = statistics_data.get("X", {})
    ch2_stats = statistics_data.get("Y", {})
    math_stats = statistics_data.get("MATH", {})
    has_math = statistics_data.get("math_enabled", False)
    headers = ["Measure", ch1_name, ch2_name]
    if has_math:
        headers.append("MATH")
    stat_keys = [
        ("Mean", "mean"), ("Std Dev", "std_dev"), ("Variance", "variance"),
        ("Median", "median"), ("Min", "min"), ("Max", "max"),
        ("Range", "range"), ("RMS", "rms"), ("Peak-to-Peak", "peak_to_peak"),
    ]
    rows = [headers]
    for label, key in stat_keys:
        row = [label, _sv(ch1_stats, key), _sv(ch2_stats, key)]
        if has_math:
            row.append(_sv(math_stats, key))
        rows.append(row)
    table = ax.table(cellText=rows, loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.5)
    for (i, j), cell in table.get_celld().items():
        if i == 0:
            cell.set_text_props(fontweight="bold")
    ax.set_title("Signal Statistics", fontsize=14, fontweight="bold")


def _mv(measures, key, idx):
    v = measures.get(key, ["", ""])
    return str(v[idx]) if len(v) > idx else ""


def _mu(measures, key):
    v = measures.get(key, [""])
    return str(v[0]) if isinstance(v, list) and len(v) > 0 else str(v)


def _sv(stats, key):
    return str(stats.get(key, ""))
