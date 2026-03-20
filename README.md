# FNIRSI 1014D Analyzer Installer Variant

This folder is a separate copy of the main project prepared for desktop distribution on Windows.

The original project remains unchanged in:

```text
C:\Users\rance\OneDrive\Desktop\osciloscope_fnirsi_1014d_analizer
```

This copy is focused on producing:

- a standalone desktop `.exe`
- a Windows installer package

## What Changed in This Variant

Compared with the original project, this installer-oriented copy includes:

- a dedicated desktop launcher in [`desktop.py`](C:/Users/rance/OneDrive/Desktop/osciloscope_fnirsi_1014d_analizer_installer/desktop.py)
- a cleaner desktop startup flow in [`app.py`](C:/Users/rance/OneDrive/Desktop/osciloscope_fnirsi_1014d_analizer_installer/app.py)
- user data stored under `%LOCALAPPDATA%\FNIRSI1014DAnalyzer`
- an updated PyInstaller spec in [`app.spec`](C:/Users/rance/OneDrive/Desktop/osciloscope_fnirsi_1014d_analizer_installer/app.spec)
- an Inno Setup script in [`installer.iss`](C:/Users/rance/OneDrive/Desktop/osciloscope_fnirsi_1014d_analizer_installer/installer.iss)

## Runtime Behavior

The application still uses:

- Flask as the local backend
- `pywebview` as the desktop window
- Matplotlib, NumPy, and SciPy for analysis and plotting

However, temporary uploads are now intended to live in a user-scoped application data folder instead of depending on the project directory.

## Files of Interest

```text
.
|-- app.py              # Backend + reusable desktop launch helpers
|-- desktop.py          # Dedicated desktop entry point for packaging
|-- app.spec            # PyInstaller build spec for the desktop exe
|-- installer.iss       # Inno Setup script for the Windows installer
|-- templates/
|-- static/
|-- signal_analyzer.py
|-- plot_maker.py
|-- file_analizer.py
|-- report.py
`-- requirements.txt
```

## Build the Desktop Executable

Run these commands from this folder:

```powershell
cd C:\Users\rance\OneDrive\Desktop\osciloscope_fnirsi_1014d_analizer_installer
.\venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --clean --noconfirm app.spec
```

Expected output:

```text
dist\FNIRSI1014DAnalyzer.exe
```

## Run the Desktop Executable

```powershell
.\dist\FNIRSI1014DAnalyzer.exe
```

## Build the Windows Installer

After generating the `.exe`, open [`installer.iss`](C:/Users/rance/OneDrive/Desktop/osciloscope_fnirsi_1014d_analizer_installer/installer.iss) with Inno Setup and compile it.

Expected installer output:

```text
installer_output\FNIRSI1014DAnalyzerSetup.exe
```

## Notes

- This variant is intended specifically for Windows desktop distribution.
- It is still based on the same mathematical and visualization core as the original project.
- If you want an even cleaner separation, the next step would be splitting the backend into an app factory and keeping `desktop.py` as the only desktop entry point.

## License

This project is released under the MIT License.

See the [`LICENSE`](C:/Users/rance/OneDrive/Desktop/osciloscope_fnirsi_1014d_analizer_installer/LICENSE) file for details.
