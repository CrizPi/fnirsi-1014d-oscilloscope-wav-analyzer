from flask import Flask, render_template, request, session, send_file, Response
import numpy as np
import os
import uuid

from file_analizer import (
    get_scope_config,
    get_scope_measures,
    get_scope_raw_data_display
)

from plot_maker import generate_grafic

from signal_analyzer import (
    get_scope_fs_and_time,
    convert_scope_data,
    apply_math_operation,
    calculate_math_measures,
    adaptive_scope_filter
)

from report import (
    generate_grafic_download,
    generate_measures_latex,
    generate_grafic_download_math,
    generate_math_measures_latex
)

# ----------------------------------------
# APP CONFIG
# ----------------------------------------
app = Flask(__name__)
app.secret_key = "contraseña1234"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ----------------------------------------
# CONSTANTES
# ----------------------------------------
DEFAULT_CONFIG = {
    'volts_div': [0, 0], 'volt_units': ['V', 'V'], 'volt_multiplier': [1, 1],
    'probe': [1, 1], 'coupling': ['DC', 'DC'],
    'time_div': 0, 'time_units': 'S', 'time_multiplier': 1
}

DEFAULT_MEASURES = {
    'Vmax': [0, 0], 'Vmin': [0, 0], 'Vavg': [0, 0], 'Vrms': [0, 0],
    'Vpp': [0, 0], 'Vp': [0, 0], 'Freq': [0, 0],
    'Cycle': [0, 0], 'Time+': [0, 0], 'Time-': [0, 0],
    'Duty+': [0, 0], 'Duty-': [0, 0],
    'freq_units': ['Hz', 'Hz'], 'freq_multiplier': [1, 1],
    'cycle_units': ['S', 'Hz'], 'cycle_multiplier': [1, 1],
    'time_plus_units': ['S', 'S'], 'time_minus_units': ['S', 'S'],
    'time_plus_multiplier': [1, 1], 'time_minus_multiplier': [1, 1]
}

DEFAULT_MATH_MEASURES = {
    "Vmax": 0, "Vmin": 0, "Vavg": 0, "Vrms": 0,
    "Vpp": 0, "Vp": 0,
    "Freq": 0, "freq_unit": "Hz",
    "Cycle": 0, "cycle_unit": "S",
    "Time+": 0, "time_plus_unit": "S",
    "Time-": 0, "time_minus_unit": "S",
    "Duty+": 0, "Duty-": 0,
}

T_CLEAR = np.arange(-375, 376)
CH_CLEAR = np.zeros(750)


# ----------------------------------------
# HELPERS
# ----------------------------------------
def cleanup_file():
    file_path = session.get("file_wav")
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"Error al eliminar {file_path}: {e}")


def get_unique_filename():
    return f"{uuid.uuid4().hex}.wav"


def load_signal_data(file_path, config, measures):
    """
    Carga, convierte y calcula tiempo/fs.
    """
    ch1, ch2 = get_scope_raw_data_display(file_path, measures)

    ch1_v, ch2_v = convert_scope_data(ch1, ch2, config, measures)
    fs, t = get_scope_fs_and_time(ch1, config)

    return ch1_v, ch2_v, fs, t


def apply_visual_filter(ch1, ch2, fs, math_result=None):
    """
    Aplica filtro SOLO visual.
    """
    ch1 = adaptive_scope_filter(ch1, fs)
    ch2 = adaptive_scope_filter(ch2, fs)

    if math_result is not None:
        math_result = adaptive_scope_filter(math_result, fs)

    return ch1, ch2, math_result


def process_math(ch1, ch2, fs):
    """
    Procesa operación matemática y medidas.
    """
    math_operation = session.get("math_operation")

    if not math_operation:
        return None, DEFAULT_MATH_MEASURES

    math_result = apply_math_operation(ch1, ch2, math_operation)
    math_measures = calculate_math_measures(math_result, fs)

    session["math_measures"] = math_measures

    return math_result, math_measures


# ----------------------------------------
# ROUTES
# ----------------------------------------
@app.route('/', methods=['GET', 'POST'])
def main():

    math_result = None
    math_measures = DEFAULT_MATH_MEASURES.copy()

    # -----------------------------
    # UPLOAD
    # -----------------------------
    if request.method == "POST" and "upload-file" in request.form:
        file = request.files.get('file')

        if file and file.filename:
            cleanup_file()
            session.pop("math_operation", None)

            file_path = os.path.join(UPLOAD_FOLDER, get_unique_filename())
            file.save(file_path)

            session.update({
                "file_wav": file_path,
                "original_name": file.filename,
                "config": get_scope_config(file_path),
                "measures": get_scope_measures(file_path)
            })

    # -----------------------------
    # MATH OP
    # -----------------------------
    if request.method == "POST" and "math_op" in request.form:
        session["math_operation"] = request.form.get("math_op")

    # -----------------------------
    # RESET
    # -----------------------------
    if request.method == "POST" and "reset" in request.form:
        cleanup_file()
        session.clear()

    # -----------------------------
    # LOAD SESSION DATA
    # -----------------------------
    file_path = session.get("file_wav")

    if file_path and os.path.exists(file_path):

        config = session.get("config", DEFAULT_CONFIG)
        measures = session.get("measures", DEFAULT_MEASURES)
        file_name = session.get("original_name", "No File")

        ch1, ch2, fs, t = load_signal_data(file_path, config, measures)

        # MATH sin filtro
        math_result, math_measures = process_math(ch1, ch2, fs)

        # FILTRO visual
        ch1, ch2, math_result = apply_visual_filter(ch1, ch2, fs, math_result)

    else:
        file_name = "No File"
        config = DEFAULT_CONFIG
        measures = DEFAULT_MEASURES
        t = T_CLEAR
        ch1, ch2 = CH_CLEAR, CH_CLEAR

    # -----------------------------
    # GRÁFICAS
    # -----------------------------
    grafica = generate_grafic(t, ch1, ch2, file_name, measures)

    grafica_math = generate_grafic(
        t,
        [],
        [],
        "MATH",
        measures=None,
        math_result=math_result,
        show_empty=True
    )

    return render_template(
        "main.html",
        file=file_path,
        file_name=file_name,
        config=config,
        measures=measures,
        grafica=grafica,
        grafica_math=grafica_math,
        math_operation=session.get("math_operation"),
        math_measures=math_measures
    )


# ----------------------------------------
# DOWNLOADS
# ----------------------------------------
@app.route('/download_latex')
def download_latex():
    measures = session.get("measures")

    if not measures:
        return "No hay datos de medidas", 400

    return Response(
        generate_measures_latex(measures),
        mimetype="text/plain"
    )


@app.route('/download_math_latex')
def download_math_latex():
    math_measures = session.get("math_measures")
    operation = session.get("math_operation")

    if not math_measures:
        return "No hay datos de medidas MATH", 400

    return Response(
        generate_math_measures_latex(math_measures, operation),
        mimetype="text/plain"
    )


def prepare_download_data():
    """
    Reutilizable para descargas.
    """
    file_path = session.get("file_wav")

    if not file_path or not os.path.exists(file_path):
        return None

    config = session.get("config")
    measures = session.get("measures")

    ch1, ch2, fs, t = load_signal_data(file_path, config, measures)

    # filtro visual
    ch1 = adaptive_scope_filter(ch1, fs)
    ch2 = adaptive_scope_filter(ch2, fs)

    return ch1, ch2, fs, t, measures


@app.route('/download_graph')
def download_graph():

    data = prepare_download_data()
    if not data:
        return "No hay archivo cargado", 400

    ch1, ch2, fs, t, measures = data
    file_name = session.get("original_name", "graph")

    png_path = generate_grafic_download(t, ch1, ch2, file_name, measures)

    return send_file(
        png_path,
        mimetype="image/png",
        as_attachment=True,
        download_name=f"{file_name}_graph.png"
    )


@app.route('/download_math_graph')
def download_math_graph():

    data = prepare_download_data()
    if not data:
        return "No hay archivo cargado", 400

    ch1, ch2, fs, t, measures = data
    math_operation = session.get("math_operation")

    if not math_operation:
        return "No hay operación matemática activa", 400

    math_result = apply_math_operation(ch1, ch2, math_operation)
    math_result = adaptive_scope_filter(math_result, fs)

    file_name = session.get("original_name", "math")

    png_path = generate_grafic_download_math(
        t,
        [],
        [],
        f"MATH_{math_operation}",
        math_result=math_result
    )

    return send_file(
        png_path,
        mimetype="image/png",
        as_attachment=True,
        download_name=f"{file_name}_math_{math_operation}.png"
    )


# ----------------------------------------
# RUN
# ----------------------------------------
if __name__ == '__main__':
    app.run(debug=True)