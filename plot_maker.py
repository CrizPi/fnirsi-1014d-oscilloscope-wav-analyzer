import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
from io import BytesIO
import base64
import numpy as np

def generate_grafic(t, ch1, ch2, file_name, measures=None, show_empty=False):
    """
    Genera un gráfico tipo osciloscopio y devuelve la imagen en base64.

    Parámetros:
    - t: lista de tiempos
    - ch1, ch2: listas de voltajes de los canales
    - file_name: nombre del archivo para el título
    - measures: diccionario con medidas de la señal (opcional)
    - show_empty: fuerza a mostrar la grilla incluso si no hay señales
    """

    # -----------------------------
    # ESCALA DE INGENIERÍA PARA TIEMPO
    # -----------------------------
    if len(t) > 0:
        max_t = np.max(np.abs(t))

        eng_scales = [
            (1e-12, 'p'),
            (1e-9, 'n'),
            (1e-6, 'µ'),
            (1e-3, 'm'),
            (1, ''),
            (1e3, 'k'),
            (1e6, 'M')
        ]

        scale = 1
        prefix = ''

        for factor, sym in eng_scales:
            if max_t < factor*1000:
                scale = factor
                prefix = sym
                break

        t_scaled = np.array(t) / scale
    else:
        t_scaled = np.array(t)
        prefix = ''

    fig, ax = plt.subplots(figsize=(16,6))

    # Crear eje secundario para CH2
    ax2 = ax.twinx()

    # Fondo tipo osciloscopio
    fig.patch.set_facecolor('#000000')
    ax.set_facecolor('#000000')
    ax2.set_facecolor('#000000')

    # Bordes
    for spine in ax.spines.values():
        spine.set_color('#919191')
        spine.set_linewidth(1)

    ax2.spines['right'].set_color('#919191')
    ax2.spines['right'].set_linewidth(1)

    # Grid principal - FORZAR VISIBILIDAD EN AMBOS EJES
    ax.grid(True, which='major', color='#919191', linestyle='-', linewidth=0.6, axis='both', drawstyle='default')
    ax2.grid(True, which='major', color='#919191', linestyle='-', linewidth=0.6, axis='both', drawstyle='default')
    
    # Subdivisiones
    ax.minorticks_on()
    ax.grid(True, which='minor', color='#2B2B2B', linestyle='-', linewidth=0.4, axis='both')
    ax2.minorticks_on()
    ax2.grid(True, which='minor', color='#2B2B2B', linestyle='-', linewidth=0.4, axis='both')

    ax.tick_params(colors='#919191', which='both')
    ax2.tick_params(colors='#919191', which='both')

    ax.set_xlabel(f"Time ({prefix}s)", color="#919191")
    ax.set_ylabel("Voltage (V)", color="#ffff00")
    ax2.set_ylabel("Voltage (V)", color="#00e5ff")

    # -----------------------------
    # FIJAR 15 DIVISIONES DE TIEMPO
    # -----------------------------
    if len(t_scaled) > 1:
        t_min = np.min(t_scaled)
        t_max = np.max(t_scaled)

        horizontal_divisions = 18

        xticks = np.linspace(t_min, t_max, horizontal_divisions + 1)
        ax.set_xticks(xticks)

    # -----------------------------
    # ESCALAS VERTICALES (MODIFICADO)
    # -----------------------------
    divisions = 8  # divisiones verticales (simula osciloscopio)

    max1 = np.max(np.abs(ch1)) if len(ch1) > 0 else 1
    max2 = np.max(np.abs(ch2)) if len(ch2) > 0 else 1

    # Aumentar un poco el rango para comprimir la señal
    max1 *= 1.2
    max2 *= 1.2

    step1 = max1 / (divisions/2)
    step2 = max2 / (divisions/2)

    y_ticks1 = np.arange(-divisions/2, divisions/2 + 1) * step1
    y_ticks2 = np.arange(-divisions/2, divisions/2 + 1) * step2

    ax.set_ylim(y_ticks1[0], y_ticks1[-1])
    ax2.set_ylim(y_ticks2[0], y_ticks2[-1])

    ax.set_yticks(y_ticks1)
    ax2.set_yticks(y_ticks2)
    # Línea central más gruesa (0)
    ax.axhline(0, color='#919191', linewidth=2)
    ax.axvline(0, color='#919191', linewidth=2)

    # -----------------------------
    # VALIDACIÓN DE CANALES
    # -----------------------------
    show_ch1 = True
    show_ch2 = True

    if measures is not None:
        keys = [
            "Vmax","Vmin","Vavg","Vrms","Vpp","Vp",
            "Freq","Cycle","Time+","Time-","Duty+","Duty-"
        ]
        if all(measures[k][0] == 0 for k in keys):
            show_ch1 = False
        if all(measures[k][1] == 0 for k in keys):
            show_ch2 = False

    lines = []

    # -----------------------------
    # CH1
    # -----------------------------
    if (show_ch1 or show_empty) and len(ch1) > 0:
        line1, = ax.plot(
            t_scaled[:len(ch1)],
            ch1,
            color='#ffff00',
            linewidth=2,
            label='X'
        )
    else:
        line1, = ax.plot([], [], color='#ffff00', linewidth=2, label='X')
    lines.append(line1)

    # -----------------------------
    # CH2
    # -----------------------------
    if (show_ch2 or show_empty) and len(ch2) > 0:
        line2, = ax2.plot(
            t_scaled[:len(ch2)],
            ch2,
            color='#00e5ff',
            linewidth=2,
            label='Y'
        )
    else:
        line2, = ax2.plot([], [], color='#00e5ff', linewidth=2, label='Y')
    lines.append(line2)

    # Si no hay señales y no se fuerza grilla vacía, mostrar texto
    if not show_ch1 and not show_ch2 and not show_empty:
        ax.text(
            0.5, 0.5,
            "No signal loaded",
            color="#919191",
            fontsize=20,
            ha="center",
            va="center",
            transform=ax.transAxes
        )

    # Leyenda
    leg = ax.legend(
        lines,
        ['X','Y'],
        loc='upper right',
        bbox_to_anchor=(1.00, 1.00),
        ncol=2
    )
    
    plt.setp(leg.get_texts(), color='#919191')
    leg.get_frame().set_facecolor('#000000')
    leg.get_frame().set_edgecolor('#919191')

    # Título
    plt.title(file_name, color='#919191')

    # Guardar en buffer y convertir a base64
    buffer = BytesIO()
    plt.savefig(buffer, format="png", bbox_inches="tight", facecolor=fig.get_facecolor())
    buffer.seek(0)

    img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    plt.close()

    return img_base64
