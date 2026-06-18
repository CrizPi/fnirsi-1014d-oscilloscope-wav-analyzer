import sys
import traceback

from app import launch_desktop


if __name__ == "__main__":
    try:
        launch_desktop()
    except Exception:
        print("=" * 60, file=sys.stderr)
        print("ERROR CRÍTICO: La aplicación falló al iniciar.", file=sys.stderr)
        print("Tipo:", type(sys.exc_info()[1]).__name__, file=sys.stderr)
        print("Mensaje:", sys.exc_info()[1], file=sys.stderr)
        print(file=sys.stderr)
        traceback.print_exc()
        print("=" * 60, file=sys.stderr)
        print("Presione Enter para salir...", file=sys.stderr)
        input()
        sys.exit(1)
