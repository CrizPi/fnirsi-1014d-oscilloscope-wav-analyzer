from flask import Flask, render_template, request, session
import numpy as np
import os
import uuid  # Para generar nombres únicos
from file_analizer import get_scope_config, get_scope_measures, get_scope_raw_data
from plot_maker import generate_grafic,generate_empty_grafic
from signal_analyzer import get_scope_fs

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


app = Flask(__name__)
app.secret_key = "contraseña1234"
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def cleanup_file():
    """Borra solo el archivo wav subido"""
    file_path = session.get("file_wav")
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            print(f"Archivo eliminado: {file_path}")
        except Exception as e:
            print(f"Error al eliminar {file_path}: {e}")


@app.route('/', methods=['GET', 'POST'])
def main():
    # Valores por defecto
    default_config = {'volts_div':[0,0],'units':['V','V'],'probe':[1,1],
                      'coupling':['DC','DC'],'time_div':0,'time_units':'S','time_multiplier':0}
    default_measures = {'Vmax':[0,0],'Vmin':[0,0],'Vavg':[0,0],'Vrms':[0,0],
                        'Vpp':[0,0],'Vp':[0,0],'Freq':[0,0],'Cycle':[0,0],
                        'Time+':[0,0],'Time-':[0,0],'Duty+':[0,0],'Duty-':[0,0]}
    
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

            # Guardar info ligera en sesión
            session["file_wav"] = file_path
            session["original_name"] = file.filename
            session["config"] = config
            session["measures"] = measures

    # --- RESET ---
    if request.method=="POST" and "reset" in request.form:
        cleanup_file()  # Borra el archivo
        session.clear()
        file_path = None
        file_name = "No File"
        config = default_config
        measures = default_measures
        grafica1 = generate_empty_grafic()
        return render_template("main.html",
                               file=file_path,
                               file_name=file_name,
                               config=config,
                               measures=measures,
                               grafica=grafica1)

    # --- LEER DATOS DE LA SESIÓN ---
    file_path = session.get("file_wav")
    config = session.get("config", default_config)
    measures = session.get("measures", default_measures)
    file_name = session.get("original_name", "No File")

    # --- GENERAR GRÁFICA SOLO SI HAY ARCHIVO ---
    if file_path and os.path.exists(file_path):
        ch1, ch2 = get_scope_raw_data(file_path)
        grafica1 = generate_grafic(ch1, ch2, file_name)
    else:
        grafica1 = generate_empty_grafic()  # <-- aquí usamos la gráfica vacía

    return render_template("main.html",
                           file=file_path,
                           file_name=file_name,
                           config=config,
                           measures=measures,
                           grafica=grafica1)



if __name__ == '__main__':
    app.run(debug=True)


