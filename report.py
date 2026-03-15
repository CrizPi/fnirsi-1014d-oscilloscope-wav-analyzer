# report.py - COMPLETO

import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import numpy as np
from flask import session
import os
from file_analizer import get_scope_measures, get_scope_raw_data_display
from signal_analyzer import get_scope_fs_and_time, convert_scope_data
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import tempfile


# ==========================================================
# FORMATEO DE MEDIDAS CON UNIDADES
# ==========================================================

def format_measure_value(key, channel, measures):

    value = measures[key][channel]

    if key in ["Vmax","Vmin","Vavg","Vrms","Vpp","Vp"]:
        return f"{value} V"

    if key == "Freq":
        unit = measures["freq_units"][channel]
        mult = measures["freq_multiplier"][channel]
        return f"{value*mult} {unit}"

    if key == "Cycle":
        unit = measures["cycle_units"][channel]
        mult = measures["cycle_multiplier"][channel]
        return f"{value*mult} {unit}"

    if key == "Time+":
        unit = measures["time_plus_units"][channel]
        mult = measures["time_plus_multiplier"][channel]
        return f"{value*mult} {unit}"

    if key == "Time-":
        unit = measures["time_minus_units"][channel]
        mult = measures["time_minus_multiplier"][channel]
        return f"{value*mult} {unit}"

    if key in ["Duty+","Duty-"]:
        return f"{value} %"

    return str(value)


# ==========================================================
# GENERACIÓN DE GRÁFICA PARA PDF
# ==========================================================

def generate_grafic_pdf(t, ch1, ch2, file_name, measures=None, show_empty=False):

    if len(t) > 0:

        max_t = np.max(np.abs(t))

        eng_scales = [
            (1e-12,'p'),
            (1e-9,'n'),
            (1e-6,'µ'),
            (1e-3,'m'),
            (1,''),
            (1e3,'k'),
            (1e6,'M')
        ]

        scale = 1
        prefix = ''

        for factor, sym in eng_scales:
            if max_t < factor*1000:
                scale = factor
                prefix = sym
                break

        t_scaled = np.array(t)/scale

    else:

        t_scaled = np.array(t)
        prefix = ''

    fig, ax = plt.subplots(figsize=(16,6))
    ax2 = ax.twinx()

    fig.patch.set_facecolor('#FFFFFF')
    ax.set_facecolor('#FFFFFF')
    ax2.set_facecolor('#FFFFFF')

    for spine in ax.spines.values():
        spine.set_color('#000000')
        spine.set_linewidth(1)

    ax2.spines['right'].set_color('#000000')
    ax2.spines['right'].set_linewidth(1)

    ax.grid(True, which='major', color='#C0C0C0', linestyle='-', linewidth=0.6)
    ax2.grid(True, which='major', color='#C0C0C0', linestyle='-', linewidth=0.6)

    ax.minorticks_on()
    ax.grid(True, which='minor', color='#E6E6E6', linewidth=0.4)

    ax2.minorticks_on()
    ax2.grid(True, which='minor', color='#E6E6E6', linewidth=0.4)

    ax.tick_params(colors='#000000')
    ax2.tick_params(colors='#000000')

    ax.set_xlabel(f"Time ({prefix}s)", color="#000000")
    ax.set_ylabel("Voltage X (V)", color="#000000")
    ax2.set_ylabel("Voltage Y (V)", color="#000000")

    # NUEVO: la grilla se dibuja debajo de todo
    ax.set_axisbelow(True)

    if len(t_scaled) > 1:

        t_min = np.min(t_scaled)
        t_max = np.max(t_scaled)

        horizontal_divisions = 18

        xticks = np.linspace(t_min, t_max, horizontal_divisions+1)

        ax.set_xticks(xticks)

    divisions = 8

    max1 = np.max(np.abs(ch1)) if len(ch1)>0 else 1
    max2 = np.max(np.abs(ch2)) if len(ch2)>0 else 1

    max1*=1.2
    max2*=1.2

    step1 = max1/(divisions/2)
    step2 = max2/(divisions/2)

    y_ticks1 = np.arange(-divisions/2,divisions/2+1)*step1
    y_ticks2 = np.arange(-divisions/2,divisions/2+1)*step2

    ax.set_ylim(y_ticks1[0],y_ticks1[-1])
    ax2.set_ylim(y_ticks2[0],y_ticks2[-1])

    ax.set_yticks(y_ticks1)
    ax2.set_yticks(y_ticks2)

    # NUEVO: fondo para etiquetas
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_bbox(dict(facecolor='white', edgecolor='none', pad=0.3))

    for label in ax2.get_yticklabels():
        label.set_bbox(dict(facecolor='white', edgecolor='none', pad=0.3))

    lines=[]

    line1, = ax.plot(t_scaled[:len(ch1)],ch1,color='#0033CC',linewidth=2,label='X')
    line2, = ax2.plot(t_scaled[:len(ch2)],ch2,color='#CC0000',linewidth=2,label='Y')

    lines.append(line1)
    lines.append(line2)

    leg = ax.legend(
        lines,
        ['X','Y'],
        loc='upper right',
        bbox_to_anchor=(1.00,1.00),
        ncol=2
)

    plt.setp(leg.get_texts(),color='#000000')

    leg.get_frame().set_facecolor('#FFFFFF')
    leg.get_frame().set_edgecolor('#000000')

    plt.title(file_name,color='#000000')

    with tempfile.NamedTemporaryFile(suffix='.png',delete=False) as tmp_file:

        plt.savefig(
            tmp_file.name,
            format="png",
            bbox_inches="tight",
            facecolor=fig.get_facecolor(),
            dpi=150
        )

        tmp_png_path = tmp_file.name

    plt.close()

    return tmp_png_path


# ==========================================================
# GENERACIÓN DEL REPORTE PDF
# ==========================================================

def generate_scope_pdf_report(file_path):

    default_config = {
        'volts_div':[0,0],
        'volt_units':['V','V'],
        'volt_multiplier':[1,1],
        'probe':[1,1],
        'coupling':['DC','DC'],
        'time_div':0,
        'time_units':'S',
        'time_multiplier':1
    }

    config = session.get("config",default_config)

    file_name = session.get("original_name",os.path.basename(file_path))

    measures_actual = get_scope_measures(file_path)

    ch1_disp,ch2_disp = get_scope_raw_data_display(file_path,measures_actual)

    ch1_v_dips,ch2_v_dips = convert_scope_data(ch1_disp,ch2_disp,config,measures_actual)

    fs,t = get_scope_fs_and_time(ch1_disp,config)

    graph_path = generate_grafic_pdf(t,ch1_v_dips,ch2_v_dips,file_name,measures_actual)

    output_pdf = tempfile.NamedTemporaryFile(suffix='.pdf',delete=False)

    doc = SimpleDocTemplate(
        output_pdf.name,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles=getSampleStyleSheet()

    title_style=ParagraphStyle(
        'Title',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=16,
        alignment=1,
        spaceAfter=10
    )

    section_style=ParagraphStyle(
        'Section',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11,
        spaceAfter=6
    )

    normal_style=ParagraphStyle(
        'Normal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9
    )

    story=[]

    story.append(Paragraph("Oscilloscope Measurement Report",title_style))

    story.append(Paragraph(f"File: {file_name}",normal_style))

    story.append(Spacer(1,8))

    img = Image(graph_path,width=6.5*inch,height=2.6*inch)

    story.append(img)

    story.append(Spacer(1,10))

    story.append(Paragraph("Signal Measurements",section_style))

    measure_keys=[
        "Vmax","Vmin","Vavg","Vrms","Vpp","Vp",
        "Freq","Cycle","Time+","Time-","Duty+","Duty-"
    ]

    measures_data=[['Measurement','X','Y']]

    for key in measure_keys:

        ch1_value = format_measure_value(key,0,measures_actual)
        ch2_value = format_measure_value(key,1,measures_actual)

        measures_data.append([
            key,
            ch1_value,
            ch2_value
        ])

    measures_table=Table(measures_data)

    measures_table.setStyle(TableStyle([
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),8),
        ('ALIGN',(1,1),(-1,-1),'CENTER'),
        ('GRID',(0,0),(-1,-1),0.25,colors.grey)
    ]))

    story.append(measures_table)

    doc.build(story)

    os.unlink(graph_path)

    return output_pdf.name