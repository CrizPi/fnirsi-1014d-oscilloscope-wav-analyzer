# FNIRSI 1014D Oscilloscope Analyzer

Desktop/web application for analyzing `.wav` captures exported from the **FNIRSI 1014D** oscilloscope.

The project reads waveform dumps, reconstructs both channels in voltage units, and provides a set of analysis tools focused on lab work, signal inspection, and report generation.

It can be used in two ways:

- as a local Python application with Flask + `pywebview`
- as a packaged Windows `.exe` built with **PyInstaller**

## Features

- Import `.wav` captures exported by the FNIRSI 1014D
- Parse oscilloscope configuration and built-in automatic measurements
- Display reconstructed time-domain waveforms for channels `X` and `Y`
- Math operations between channels:
  - `X + Y`
  - `X - Y`
  - `X × Y`
  - `X ÷ Y`
- FFT spectral analysis with:
  - selectable channel
  - linear/log amplitude scale
  - selectable window (`Rectangular`, `Hann`, `Hamming`, `Blackman`)
  - dominant frequency detection
  - top peaks
  - harmonic table
  - THD estimation
- Signal statistics:
  - mean
  - standard deviation
  - variance
  - median
  - min / max
  - range
  - RMS
  - peak-to-peak
- Advanced signal measurements:
  - rise time
  - fall time
  - overshoot
  - undershoot
  - slew rate
  - crest factor
- Derivative and integral analysis
- Cross-correlation between channels
- Manual cursor measurement with interactive draggable cursors
- Per-cycle analysis
- Calibration tools:
  - gain
  - offset
  - inversion
  - normalization
- Snapshots and comparison between analyses
- Export options:
  - PNG graphs
  - LaTeX tables/sections
- `pywebview` desktop window support
- PyInstaller packaging support for `.exe`

## Project Structure

```text
.
├─ app.py                # Main Flask app and pywebview launcher
├─ file_analizer.py      # FNIRSI file parsing and oscilloscope metadata extraction
├─ signal_analyzer.py    # Signal processing and numerical analysis
├─ plot_maker.py         # Plot generation for time-domain, FFT, correlation, cursors, etc.
├─ report.py             # LaTeX and downloadable report fragments
├─ templates/
│  └─ main.html          # Main user interface
├─ static/
│  └─ style.css          # Application styling
├─ uploads/              # Temporary uploaded files
├─ app.spec              # PyInstaller spec file
└─ requirements.txt      # Python dependencies
```

## Requirements

- Python `3.11` recommended
- Windows environment recommended for the current desktop packaging flow

Dependencies:

- `Flask`
- `Werkzeug`
- `numpy`
- `scipy`
- `matplotlib`
- `pywebview`

## Installation

### Option 1: virtual environment

```powershell
py -3.11 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Option 2: use the provided helper script

```powershell
iniciar.bat
```

## Running the Project

```powershell
python app.py
```

Current behavior:

- The Flask backend runs locally
- A `pywebview` desktop window opens automatically
- Temporary uploaded files are stored in `uploads/`
- `Reset` cleans uploaded files and session state
- Closing the desktop window also triggers upload cleanup

## Running the `.exe`

If you already built the desktop executable, you can run it directly from:

```text
dist/app.exe
```

That executable launches the same application in desktop mode, without needing to manually start Flask from the terminal.

## How to Use

1. Launch the application.
2. Upload a `.wav` file exported by the FNIRSI 1014D.
3. Review:
   - oscilloscope configuration
   - automatic measurements
   - main waveform graph
4. Open any analysis module:
   - `Math`
   - `FFT`
   - `Statistics`
   - `Advanced`
   - `Correlation`
   - `Derivative`
   - `Calibration`
   - `Cursors`
   - `Cycle`
   - `Snapshots`
5. Apply each analysis on demand.
6. Export LaTeX tables or PNG graphs where needed.

## Desktop Packaging

The repository already contains a PyInstaller spec file:

[`app.spec`](C:/Users/rance/OneDrive/Desktop/osciloscope_fnirsi_1014d_analizer/app.spec)

To build the executable:

```powershell
pyinstaller app.spec
```

Expected output:

- executable in `dist/`
- build files in `build/`

After packaging, the main distributable file is:

```text
dist/app.exe
```

If you want to distribute the project to other Windows users, this `.exe` is the desktop entry point you would share.

## Notes

- This project is tailored to the FNIRSI 1014D export format.
- Some analysis modules depend on previously loaded waveform data and selected settings.
- Download actions inside `pywebview` are handled through the native save dialog.
- The app is currently optimized for local desktop use rather than remote deployment.

## Future Improvements

- Dedicated JSON APIs per module for even lighter partial updates
- Automated tests for parsing and signal-processing functions
- More export formats
- Broader support for other oscilloscope file formats

## License

This project is released under the MIT License.

See the [`LICENSE`](C:/Users/rance/OneDrive/Desktop/osciloscope_fnirsi_1014d_analizer/LICENSE) file for details.
