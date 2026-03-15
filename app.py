from flask import Flask, render_template, request, session, send_file  # <-- Agregar send_file
import numpy as np
import os
import uuid  # Para generar nombres únicos
from file_analizer import get_scope_config, get_scope_measures, get_scope_raw_data_display,get_scope_raw_data_complete
from plot_maker import generate_grafic
from signal_analyzer import get_scope_fs_and_time, calculate_frequency, convert_scope_data
from report import generate_scope_pdf_report


app = Flask(__name__)
app.secret_key = "contraseña1234"
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)



def cleanup_file():
    """Borra solo el archivo wav subido, no la gráfica"""
    file_path = session.get("file_wav")
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            print(f"Archivo eliminado: {file_path}")
        except Exception as e:
            print(f"Error al eliminar {file_path}: {e}")

def get_unique_filename():
    """Genera nombre único por sesión"""
    session_id = session.get('session_id', str(uuid.uuid4())[:8])
    session['session_id'] = session_id
    return f"{session_id}_{int(np.random.rand()*10000)}.wav"



@app.route('/', methods=['GET', 'POST'])
def main():
    # Valores por defecto
    default_config = {'volts_div': [0, 0], 'volt_units': ['V', 'V'], 'volt_multiplier': [1, 1], 'probe': [1, 1], 'coupling': ['DC', 'DC'],'time_div': 0, 'time_units': 'S', 'time_multiplier': 1}
    
    default_measures = {'Vmax': [0, 0], 'Vmin': [0, 0], 'Vavg': [0, 0], 'Vrms': [0, 0], 'Vpp': [0, 0], 'Vp': [0, 0], 'Freq': [0, 0],
                        'Cycle': [0, 0], 'Time+': [0, 0], 'Time-': [0, 0], 'Duty+': [0, 0], 'Duty-': [0, 0], 'freq_units': ['Hz', 'Hz'], 'freq_multiplier': [1, 1],
                        'cycle_units': ['S', 'Hz'], 'cycle_multiplier': [1, 1], 'time_plus_units': ['S', 'S'], 'time_minus_units': ['S', 'S'], 'time_plus_multiplier': [1, 1], 'time_minus_multiplier': [1, 1]}
    t_clear = np.arange(-375, 376)  
    ch_clear = np.zeros(750)

    measures=default_config


    # --- SUBIR ARCHIVO ---
    if request.method=="POST" and "upload-file" in request.form:
        file = request.files['file']
        if file and file.filename != "":
            # Si ya hay archivo previo, borrarlo
            old_file = session.get("file_wav")
            if old_file and os.path.exists(old_file):
                os.remove(old_file)
            
            # Guardar archivo con nombre fijo
            file_path = os.path.join(UPLOAD_FOLDER, "current.wav")
            file.save(file_path)
            # Procesar archivo
            config = get_scope_config(file_path)
            measures = get_scope_measures(file_path)
            ch1_disp, ch2_disp = get_scope_raw_data_display(file_path, measures)
            ch1_comp, ch2_comp = get_scope_raw_data_complete(file_path,measures)
            fs, t= get_scope_fs_and_time(ch1_disp, config)
            ch1_v_dips,ch2_v_dips= convert_scope_data(ch1_disp, ch2_disp, config, measures)

            vmax1=max(ch1_v_dips)
            vmax2=max(ch2_v_dips)
            vmin1=min(ch1_v_dips)
            vmin2=min(ch2_v_dips)
            vpp1=vmax1-vmin1
            vpp2=vmax2-vmin2
            print(f"ch1- vmax:{vmax1}, vmin:{vmin1}, vpp:{vpp1}")
            print(f"ch2- vmax:{vmax2}, vmin:{vmin2}, vpp:{vpp2}")
            
            # Guardar info ligera en sesión
            session["file_wav"] = file_path
            session["original_name"] = file.filename
            session["config"] = config
            session["measures"] = measures

    # --- RESET ---
    if request.method=="POST" and "reset" in request.form:
        cleanup_file() 
        session.clear()
        file_path = None
        file_name = "No File"
        config = default_config
        measures = default_measures
        t= t_clear  
        ch1_v_dips = ch_clear
        ch2_v_dips = ch_clear

    # --- LEER DATOS DE LA SESIÓN ---
    file_path = session.get("file_wav")     
    if file_path:
        config = session.get("config", default_config)
        measures = session.get("measures", default_measures)
        file_name = session.get("original_name", "No File")
        ch1_disp, ch2_disp = get_scope_raw_data_display(file_path, measures)
        ch1_v_dips,ch2_v_dips= convert_scope_data(ch1_disp, ch2_disp, config, measures)
        fs, t= get_scope_fs_and_time(ch1_disp, config)
    else:
        file_path = None
        file_name = "No File"
        config = default_config
        measures = default_measures
        t= t_clear  
        ch1_v_dips = ch_clear
        ch2_v_dips = ch_clear

    grafica1 = generate_grafic(t, ch1_v_dips, ch2_v_dips, file_name, measures)

    return render_template("main.html",
                           file=file_path,
                           file_name=file_name,
                           config=config,
                           measures=measures,
                           grafica=grafica1)


@app.route('/download_pdf')
def download_pdf():
    """Genera PDF y lo envía directamente al navegador"""
    file_path = session.get("file_wav")
    if not file_path or not os.path.exists(file_path):
        return "No hay archivo para generar PDF", 400
    
    # Generar PDF en memoria
    output_pdf_path = generate_scope_pdf_report(file_path)  # <-- Ya existe en report.py
    return send_file(output_pdf_path,
                     download_name=f"{session.get('original_name','Report')}.pdf",
                     mimetype="application/pdf",
                     as_attachment=True)



if __name__ == '__main__':
    app.run(debug=True)