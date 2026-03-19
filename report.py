# report.py - OPTIMIZADO Y REESTRUCTURADO

import os
import tempfile
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from typing import Optional, Union, List


# ==========================================================
# HELPERS GENERALES
# ==========================================================

ENG_SCALES = [
    (1e-12, 'p'), (1e-9, 'n'), (1e-6, 'µ'),
    (1e-3, 'm'), (1, ''), (1e3, 'k'), (1e6, 'M')
]


def to_numpy(arr):
    return np.array(arr) if arr is not None else np.array([])


def safe_max(val):
    return val if (val != 0 and not np.isnan(val)) else 1


def safe_range(min_val, max_val):
    return (min_val, max_val + 1e-9) if min_val == max_val else (min_val, max_val)


def is_empty_signal(signal):
    return signal is None or len(signal) == 0 or np.all(np.array(signal) == 0)


def scale_time_axis(t):
    if len(t) == 0:
        return t, ''

    max_t = np.max(np.abs(t))

    for factor, sym in ENG_SCALES:
        if max_t < factor * 1000:
            return t / factor, sym

    return t, ''


def save_figure(fig):
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        fig.savefig(
            tmp.name,
            format="png",
            bbox_inches="tight",
            facecolor=fig.get_facecolor(),
            dpi=150
        )
        return tmp.name


# ==========================================================
# FORMATEO DE MEDIDAS
# ==========================================================

def format_measure_value(key, channel, measures):

    value = measures[key][channel]

    if key in ["Vmax", "Vmin", "Vavg", "Vrms", "Vpp", "Vp"]:
        return f"{value} V"

    if key == "Freq":
        return f"{value * measures['freq_multiplier'][channel]} {measures['freq_units'][channel]}"

    if key == "Cycle":
        return f"{value * measures['cycle_multiplier'][channel]} {measures['cycle_units'][channel]}"

    if key == "Time+":
        return f"{value * measures['time_plus_multiplier'][channel]} {measures['time_plus_units'][channel]}"

    if key == "Time-":
        return f"{value * measures['time_minus_multiplier'][channel]} {measures['time_minus_units'][channel]}"

    if key in ["Duty+", "Duty-"]:
        return f"{value} %"

    return str(value)


# ==========================================================
# CONFIGURACIÓN DE EJES
# ==========================================================

def configure_axes(ax, ax2=None):
    ax.set_facecolor('#FFFFFF')
    for spine in ax.spines.values():
        spine.set_color('#000000')
        spine.set_linewidth(1)

    ax.grid(True, which='major', color='#C0C0C0', linewidth=0.6)
    ax.minorticks_on()
    ax.grid(True, which='minor', color='#E6E6E6', linewidth=0.4)
    ax.tick_params(colors='#000000')

    if ax2:
        ax2.set_facecolor('#FFFFFF')
        ax2.spines['right'].set_color('#000000')
        ax2.spines['right'].set_linewidth(1)
        ax2.grid(True, which='major', color='#C0C0C0', linewidth=0.6)
        ax2.minorticks_on()
        ax2.grid(True, which='minor', color='#E6E6E6', linewidth=0.4)
        ax2.tick_params(colors='#000000')


def configure_time_ticks(ax, t_scaled):
    if len(t_scaled) > 1:
        t_min, t_max = safe_range(np.min(t_scaled), np.max(t_scaled))
        ax.set_xticks(np.linspace(t_min, t_max, 19))


def configure_y_axes(ax, ax2, ch1, ch2, divisions=8):
    max1 = safe_max(np.max(np.abs(ch1)) if len(ch1) > 0 else 1) * 1.2
    max2 = safe_max(np.max(np.abs(ch2)) if len(ch2) > 0 else 1) * 1.2

    step1 = max1 / (divisions / 2)
    step2 = max2 / (divisions / 2)

    y1 = np.arange(-divisions/2, divisions/2 + 1) * step1
    y2 = np.arange(-divisions/2, divisions/2 + 1) * step2

    ax.set_ylim(y1[0], y1[-1])
    ax.set_yticks(y1)

    if ax2:
        ax2.set_ylim(y2[0], y2[-1])
        ax2.set_yticks(y2)


# ==========================================================
# GRÁFICA NORMAL
# ==========================================================

def generate_grafic_download(t, ch1, ch2, file_name, measures=None, show_empty=False):

    t = to_numpy(t)
    ch1 = to_numpy(ch1)
    ch2 = to_numpy(ch2)

    t_scaled, prefix = scale_time_axis(t)

    fig, ax = plt.subplots(figsize=(16, 6))
    ax2 = ax.twinx()

    fig.patch.set_facecolor('#FFFFFF')

    configure_axes(ax, ax2)

    ax.set_xlabel(f"Time ({prefix}s)", color="#000000")
    ax.set_ylabel("Voltage X (V)", color="#000000")
    ax2.set_ylabel("Voltage Y (V)", color="#000000")

    configure_time_ticks(ax, t_scaled)
    configure_y_axes(ax, ax2, ch1, ch2)

    lines = []

    if len(ch1) > 0:
        l1, = ax.plot(t_scaled[:len(ch1)], ch1, color='#0033CC', linewidth=2, label='X')
        lines.append(l1)

    if len(ch2) > 0:
        l2, = ax2.plot(t_scaled[:len(ch2)], ch2, color='#CC0000', linewidth=2, label='Y')
        lines.append(l2)

    if lines:
        leg = ax.legend(lines, [l.get_label() for l in lines], loc='upper right')
        leg.get_frame().set_facecolor('#FFFFFF')
        leg.get_frame().set_edgecolor('#000000')

    plt.title(file_name, color='#000000')

    path = save_figure(fig)
    plt.close()

    return path


def generate_grafic_download_math(t: Optional[list], ch1: Optional[list], 
                                ch2: Optional[list], file_name: str,
                                math_result: Optional[list] = None) -> str:
    """
    Genera gráfico de osciloscopio con estilo blanco profesional.
    
    Args:
        t: Array de tiempo
        ch1: Señal canal 1 (azul)
        ch2: Señal canal 2 (rojo)  
        file_name: Nombre para título y referencia
        math_result: Señal matemática (magenta)
    
    Returns:
        Ruta temporal al archivo PNG generado
    """
    # Normalización de arrays
    t = np.array(t) if t is not None else np.array([])
    ch1 = np.array(ch1) if ch1 is not None else np.array([])
    ch2 = np.array(ch2) if ch2 is not None else np.array([])
    math_result = np.array(math_result) if math_result is not None else None
    
    # Determinar modo de visualización
    is_math_only = (math_result is not None and len(math_result) > 0 and 
                   is_empty_signal(ch1) and is_empty_signal(ch2))
    
    # Escala de tiempo
    t_scaled, time_prefix = get_time_scale(t)
    
    # Configurar figura
    fig, ax, ax2 = setup_figure(is_math_only)
    ax.set_xlabel(f"Time ({time_prefix}s)", color="#000000")
    
    # Ejes centrales
    ax.axhline(0, color='#000000', linewidth=1)
    ax.axvline(0, color='#000000', linewidth=1)
    
    # Configurar ticks
    setup_xticks(ax, t_scaled)
    setup_yticks(ax, ax2, ch1, ch2, math_result, is_math_only)
    
    # Plotear señales
    lines = plot_signals(ax, ax2, t_scaled, ch1, ch2, math_result, is_math_only)
    
    # Leyenda
    setup_legend(ax, lines)
    
    plt.title(file_name, color='#000000')
    
    # Exportar PNG
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        plt.savefig(tmp.name, format="png", bbox_inches="tight", 
                   facecolor=fig.get_facecolor(), dpi=150)
        path = tmp.name
    
    plt.close()
    return path


# ==========================================================
# LATEX (SIN CAMBIOS FUNCIONALES)
# ==========================================================

def generate_latex_table(rows, caption="Tabla", headers=("X", "Y")):
    """
    Genera código LaTeX para una tabla genérica.

    rows: lista de tuplas -> [(col1, col2, col3), ...]
    caption: título de la tabla
    headers: encabezados de columnas
    """

    for r in rows:
        if r[2]:
            latex = r"""
            \begin{table}[h]
            \centering
            \begin{tabular}{|c|c|c|}
            \hline
            """
        else:
            latex = r"""
            \begin{table}[h]
            \centering
            \begin{tabular}{|c|c|}
            \hline
            """


    # Encabezados
    if  headers[1]:
        latex += f"Measure & {headers[0]} & {headers[1]} \\\\\n\\hline\n"
    else:
        latex += f"Measure & {headers[0]} \\\\\n\\hline\n"

    # Filas
    for r in rows:
        if r[2]:
            latex += f"{r[0]} & {r[1]} & {r[2]} \\\\\n\\hline\n"
        else:
            latex += f"{r[0]} & {r[1]} \\\\\n\\hline\n"

    latex += f"""
\\end{{tabular}}
\\caption{{{caption}}}
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
        ("Duty-", f"{measures['Duty-'][0]} \\%", f"{measures['Duty-'][1]} \\%")
    ]

    caption = "Oscilloscope Measurements"

    return generate_latex_table(
        rows,
        caption=caption,
    )

def generate_math_measures_latex(math_measures, operation=None):
    """
    Genera tabla LaTeX para medidas MATH (una sola columna de datos).
    """

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
        ("Duty-", f"{math_measures['Duty-']} \\%", "")
    ]

    caption = "Oscilloscope MATH Measurements"
    if operation:
        caption += f" ({operation})"

    return generate_latex_table(
        rows,
        caption=caption,
        headers=("Value", "")
    )