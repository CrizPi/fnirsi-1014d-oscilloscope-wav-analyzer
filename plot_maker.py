import numpy as np
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
from io import BytesIO
import base64



def generate_grafic(ch1, ch2, file_name):

    fig, ax1 = plt.subplots(figsize=(16,6))

    fig.patch.set_facecolor('black')
    ax1.set_facecolor('black')

    ax1.grid(color='gray', linestyle='--', linewidth=0.5)
    ax1.tick_params(colors='white')

    # Si no hay datos
    if len(ch1) == 0 and len(ch2) == 0:
        ax1.text(
            0.5, 0.5,
            "No signal loaded",
            color="white",
            fontsize=20,
            ha="center",
            va="center",
            transform=ax1.transAxes
        )

    else:

        t1 = np.arange(len(ch1))
        t2 = np.arange(len(ch2))

        lines = []

        if len(ch1) > 0:
            line1, = ax1.plot(t1, ch1, color='yellow', label='CH1')
            lines.append(line1)

        if len(ch2) > 0:
            ax2 = ax1.twinx()
            ax2.set_facecolor('black')
            ax2.tick_params(colors='white')

            line2, = ax2.plot(t2, ch2, color='skyblue', label='CH2')
            lines.append(line2)

        if lines:
            labels = [l.get_label() for l in lines]
            leg = ax1.legend(lines, labels, loc="upper right")
            plt.setp(leg.get_texts(), color='white')
            leg.get_frame().set_facecolor('black')

    plt.title(file_name, color='white')

    buffer = BytesIO()
    plt.savefig(buffer, format="png")
    buffer.seek(0)

    img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    plt.close()

    return img_base64



def generate_empty_grafic(file_name="No signal"):
    fig, ax1 = plt.subplots(figsize=(16,6))
    fig.patch.set_facecolor('black')
    ax1.set_facecolor('black')
    ax1.grid(color='gray', linestyle='--', linewidth=0.5)
    ax1.tick_params(colors='white')

    # Ejes de ejemplo
    x = [0, 1]  # solo dos puntos para la línea horizontal

    # Canal 1 en 0
    line1, = ax1.plot(x, [0,0], color='yellow', label='CH1')
    
    # Canal 2 en 0 usando eje secundario
    ax2 = ax1.twinx()
    ax2.set_facecolor('black')
    ax2.tick_params(colors='white')
    line2, = ax2.plot(x, [0,0], color='skyblue', label='CH2')

    # Leyenda combinada
    lines = [line1, line2]
    labels = [l.get_label() for l in lines]
    leg = ax1.legend(lines, labels, loc="upper right")
    plt.setp(leg.get_texts(), color='white')
    leg.get_frame().set_facecolor('black')

    plt.title(file_name, color='white')

    # Guardar a base64
    buffer = BytesIO()
    plt.savefig(buffer, format="png")
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    plt.close()
    return img_base64