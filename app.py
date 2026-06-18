import base64
import os
import socket
import time
from threading import Thread

from flask import Flask
import webview

from state_store import APP_NAME, BASE_DIR, cleanup_upload_folder, load_or_create_secret_key
from web_routes import register_routes


app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)
app.secret_key = load_or_create_secret_key()
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

register_routes(app)

MAIN_WINDOW = None


class DesktopApi:
    def save_download(self, filename, content_base64):
        if MAIN_WINDOW is None:
            return {"ok": False, "message": "Desktop window is not available."}

        try:
            save_dialog = getattr(getattr(webview, "FileDialog", None), "SAVE", None)
            if save_dialog is None:
                save_dialog = webview.SAVE_DIALOG
            file_path = MAIN_WINDOW.create_file_dialog(
                save_dialog,
                save_filename=filename or "download.bin",
            )
            if not file_path:
                return {"ok": False, "message": "Download canceled."}

            selected_path = file_path[0] if isinstance(file_path, (list, tuple)) else file_path
            data = base64.b64decode(content_base64.encode("utf-8"))
            with open(selected_path, "wb") as output_file:
                output_file.write(data)
            return {"ok": True, "message": f"Saved to {selected_path}"}
        except Exception as exc:
            return {"ok": False, "message": f"Download failed: {exc}"}


def run_flask_server(host="127.0.0.1", port=5000):
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)


def wait_for_server(host="127.0.0.1", port=5000, timeout_seconds=10):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def launch_desktop(host="127.0.0.1", port=5000, width=1200, height=800):
    global MAIN_WINDOW
    desktop_api = DesktopApi()

    flask_thread = Thread(target=run_flask_server, kwargs={"host": host, "port": port}, daemon=True)
    flask_thread.start()

    if not wait_for_server(host=host, port=port):
        raise RuntimeError(f"Flask server did not start on http://{host}:{port}")

    icon_path = os.path.join(BASE_DIR, "templates", "icon.ico")
    print(f"[DIAG] Directorio actual: {os.getcwd()}")
    print(f"[DIAG] Icono WinForms: {icon_path}")
    if os.path.exists(icon_path):
        size = os.path.getsize(icon_path)
        print(f"[DIAG] Icono encontrado ({size} bytes).")
    else:
        print(f"[DIAG] Icono NO encontrado. Se usará el ícono por defecto.")

    window = webview.create_window(
        APP_NAME,
        f"http://{host}:{port}",
        width=width,
        height=height,
        js_api=desktop_api,
    )
    MAIN_WINDOW = window

    def on_window_closed():
        cleanup_upload_folder()

    window.events.closed += on_window_closed

    if os.path.exists(icon_path):
        try:
            webview.start(icon=icon_path)
        except Exception as exc:
            print(f"[WARN] Error al cargar el ícono '{icon_path}': {exc}")
            print("[WARN] Iniciando sin ícono personalizado...")
            webview.start()
    else:
        webview.start()


if __name__ == "__main__":
    launch_desktop()
