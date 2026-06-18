# FNIRSI 1014D Analyzer

Desktop application for analyzing `.wav` captures exported by the FNIRSI 1014D oscilloscope. Decodes FNIRSI waveform files, reconstructs the visible oscilloscope trace, and exposes engineering analysis modules through a Flask + PyWebView desktop interface.

**Version:** 2.0.1

## Overview

This is not a media player for generic WAV audio. The tool is specialized for FNIRSI oscilloscope exports and focuses on post-processing, measurement review, graph generation, and report-oriented exports.

Current capabilities include:

- FNIRSI 1014D `.wav` parsing with trigger-aware waveform reconstruction
- oscilloscope configuration and measurement decoding
- MATH operations on `X` and `Y`
- FFT analysis with selectable channel, window, and scale
- statistics and advanced temporal metrics
- derivative and integral analysis (calculus)
- current estimation for resistor, capacitor, and inductor models
- total current synthesis from saved current snapshots
- transfer analysis between `Vin` and `Vout`
- X-Y mode
- channel correlation and delay estimation
- calibration and normalization controls
- manual cursors with draggable markers (single and dual mode)
- cycle analysis
- digital signal analysis (PWM, pulse counting, edge detection, logic levels)
- snapshot saving and comparison
- project save/load (persist and restore full analysis state)
- SVG graph download
- CSV export (signals, measurements, FFT)
- PDF report generation
- PNG graph downloads for supported modules
- LaTeX export for analysis summaries

## Repository Structure

```
.
├── app.py                 # Flask app and desktop launcher entry
├── desktop.py             # Minimal desktop bootstrap with error handling
├── web_routes.py          # HTTP routes, form handling, download endpoints
├── analysis_service.py    # Analysis orchestration, caching, module builders
├── state_store.py         # Shared app state, defaults, session management
├── file_analizer.py       # FNIRSI .wav parsing and metadata extraction
├── signal_analyzer.py     # Signal processing and engineering calculations
├── plot_maker.py          # Plot generation with matplotlib
├── report.py              # LaTeX export helpers
├── constants.py           # Color constants and channel definitions
├── version.py             # Application version (fixed: 2.0.1)
├── digital_analyzer.py    # Digital signal analysis (PWM, pulses, edges, logic)
├── export_service.py      # SVG, CSV, PDF export functions
├── project_service.py     # Project save/load/list
├── requirements.txt       # Python dependencies
├── app.spec               # PyInstaller configuration
├── installer.iss          # Inno Setup installer script
├── build.bat              # Build pipeline script
├── iniciar.bat            # Local setup and launch helper
├── comit.bat              # Git commit helper
├── templates/
│   ├── main.html          # Main UI template
│   ├── icon.ico           # Application icon
│   └── icon.png           # PNG version of the icon
└── static/
    ├── style.css          # Custom application styles
    ├── opencode.css       # OpenCode CSS framework
    ├── opencode.js        # OpenCode JavaScript framework
    └── icono.png          # Sidebar icon
```

## Analysis Modules

### Base oscilloscope view

- reconstructed `X` and `Y` traces
- oscilloscope configuration table
- oscilloscope measurement table
- PNG download of the main graph

### MATH

- `X + Y`
- `X - Y`
- `X * Y`
- `X / Y`

### FFT

- channel selection: `X`, `Y`, or `MATH`
- amplitude scale: linear or logarithmic
- selectable window: rectangular, Hann, Hamming, Blackman
- dominant frequency and amplitude
- top peaks
- harmonic summary
- THD estimate

### Statistics and advanced metrics

- mean, median, variance, standard deviation
- min, max, range, RMS, peak-to-peak
- rise time, fall time, overshoot, undershoot
- slew rate and crest factor

### Derivative and integral (calculus)

- derivative of `X`, `Y`, or `MATH`
- integral of `X`, `Y`, or `MATH`
- PNG download for both plots

### Current analysis

- resistor model: `i(t) = v(t) / R`
- capacitor model: `i(t) = C dv(t) / dt`
- inductor model: `i(t) = (1/L) integral(v) dt`
- selectable inductor initial condition
- RMS, mean, peak, phase, and power quantities
- current snapshot saving

### Total current

- sum of saved current snapshots from the current file
- alignment against a selected voltage channel
- frequency compatibility filtering
- total current and AC power summary

### Transfer analysis

- choose `Vin` and `Vout` from `X`, `Y`, or `MATH`
- RMS and peak-to-peak gain
- gain in dB
- phase shift
- equivalent delay
- normalized correlation peak

### X-Y mode

- choose the X-axis and Y-axis signals from `X`, `Y`, or `MATH`
- Lissajous-style waveform view
- sample count, ranges, RMS values, and correlation coefficient
- PNG download of the X-Y graph

### Correlation

- cross-correlation between `X` and `Y`
- delay estimate
- PNG and LaTeX export

### Calibration

- gain and offset for both channels
- optional inversion per channel
- optional normalization

### Cursors

- manual time cursors with draggable overlay
- single mode: `t1`, `t2`, `V1`, `V2`, `delta t`, `delta V`
- dual mode: independent signals on A and B cursors
- estimated frequency from cursor distance
- PNG download of cursor graph

### Cycle analysis

- cycle count, average frequency, average period, average Vpp, average RMS

### Digital analysis

- PWM analysis: frequency, duty cycle, period, pulse count
- pulse counting: rising/falling edge count
- edge detection: rising/falling edge timestamps, edge rate
- logic level analysis: family detection, high/low thresholds, noise margin

### Snapshots and comparison

- save measurement snapshots from the active file
- compare the current file against a saved snapshot
- delta Vpp and delta frequency summary

### Project save/load

- save the full analysis state to a JSON file
- load a previously saved project to restore state
- list saved projects

### Export formats

- SVG: vector graph download of the main oscilloscope view
- CSV: signal data (time, CH1, CH2, MATH), measurements, and FFT data
- PDF: multi-page report with main graph, measurements, FFT, and statistics
- PNG: per-module graph downloads (main, MATH, FFT, derivative, integral, current, transfer, X-Y, cursor)
- LaTeX: per-module LaTeX table generation for academic reports

## File Decoding and Reconstruction

The parser currently reads:

- channel voltage scale
- probe factor
- coupling mode
- `time/div`
- trigger type, edge, channel
- trigger 50% flag
- automatic oscilloscope measurements
- visible waveform block
- full raw waveform block

The visible waveform pipeline is tuned to match the oscilloscope screen as closely as possible:

- raw visible samples are mapped into volts using decoded measurements
- trigger metadata is used to locate the visible reference
- the window is cropped around the trigger-centered region
- the time axis is rebuilt from the oscilloscope `time/div`

## Requirements

- Python 3.8 or later
- Windows (uses `pywebview` with native WinForms window; server-only mode may work on other platforms)

## Installing Dependencies

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Or use the automated setup script:

```powershell
iniciar.bat
```

This creates a virtual environment, installs dependencies, and launches the application.

## Running

### Desktop mode

```powershell
python app.py
```

Launches the Flask backend and opens a native `pywebview` window.

```powershell
python desktop.py
```

Alternative entry point with detailed error reporting and graceful shutdown.

### Server-only mode

```powershell
$env:FNIRSI_APP_MODE="server"
python app.py
```

Starts only the Flask server on `127.0.0.1:5000` without opening a desktop window. Access the interface at `http://127.0.0.1:5000/`.

## Building the Executable

The project uses PyInstaller to generate a standalone `.exe` and Inno Setup to create an installer.

### Prerequisites

- Python 3.8+ with all dependencies installed
- PyInstaller (`pip install pyinstaller`)
- Inno Setup 6 installed at the default path

### Quick build

```powershell
build.bat
```

### Manual build steps

1. Install PyInstaller:

   ```powershell
   pip install pyinstaller
   ```

2. Clean previous builds:

   ```powershell
   rmdir /s /q build
   rmdir /s /q dist
   ```

3. Build the executable:

   ```powershell
   python -m PyInstaller app.spec
   ```

4. Copy the output:

   ```powershell
   xcopy /e /y dist\FNIRSI1014DAnalyzer\* dist\
   ```

5. (Optional) Create an installer with Inno Setup:

   ```powershell
   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
   ```

The standalone executable is located at:

```
dist\FNIRSI1014DAnalyzer.exe
```

The Inno Setup installer output is created at:

```
installer_output\FNIRSI1014DAnalyzerSetup.exe
```

## License

This project is released under the MIT License. See `LICENSE`.
