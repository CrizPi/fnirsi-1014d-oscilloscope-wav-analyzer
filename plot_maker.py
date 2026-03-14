import numpy as np
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
from io import BytesIO
import base64



def generate_grafic(t, ch1, ch2, file_name, measures=None):

    import matplotlib.pyplot as plt
    from io import BytesIO
    import base64

    fig, ax = plt.subplots(figsize=(16,6))

    # Fondo tipo osciloscopio
    fig.patch.set_facecolor('#0a0a0a')
    ax.set_facecolor('#000000')

    # Bordes
    for spine in ax.spines.values():
        spine.set_color('#919191')
        spine.set_linewidth(1)

    # Grid principal
    ax.grid(True, which='major', color='#919191', linestyle='-', linewidth=0.6)

    # Subdivisiones
    ax.minorticks_on()
    ax.grid(True, which='minor', color='#2B2B2B', linestyle='-', linewidth=0.4)

    ax.tick_params(colors='#919191', which='both')

    ax.set_xlabel("Time (s)", color="#919191")
    ax.set_ylabel("Voltage (V)", color="#919191")

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
    if show_ch1 and len(ch1) > 0:
        line1, = ax.plot(
            t[:len(ch1)],
            ch1,
            color='#ffff00',
            linewidth=2,
            label='CH1'
        )
    else:
        # línea vacía solo para la leyenda
        line1, = ax.plot([], [], color='#ffff00', linewidth=2, label='CH1')

    lines.append(line1)

    # -----------------------------
    # CH2
    # -----------------------------
    if show_ch2 and len(ch2) > 0:
        line2, = ax.plot(
            t[:len(ch2)],
            ch2,
            color='#00e5ff',
            linewidth=2,
            label='CH2'
        )
    else:
        line2, = ax.plot([], [], color='#00e5ff', linewidth=2, label='CH2')

    lines.append(line2)

    # -----------------------------
    # Si no hay señales
    # -----------------------------
    if not show_ch1 and not show_ch2:
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
    leg = ax.legend(lines, ['CH1','CH2'], loc="upper right")

    plt.setp(leg.get_texts(), color='#919191')
    leg.get_frame().set_facecolor('#000000')
    leg.get_frame().set_edgecolor('#919191')

    # Título
    plt.title(file_name, color='#919191')

    buffer = BytesIO()
    plt.savefig(buffer, format="png", bbox_inches="tight",
                facecolor=fig.get_facecolor())
    buffer.seek(0)

    img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    plt.close()

    return img_base64



