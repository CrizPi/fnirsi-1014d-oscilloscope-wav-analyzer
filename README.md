# FNIRSI 1014D Analyzer

Desktop application for analyzing `.wav` captures exported by the FNIRSI 1014D oscilloscope.

The project decodes FNIRSI waveform files, reconstructs the visible oscilloscope trace, and exposes engineering analysis modules through a Flask + PyWebView desktop interface.

## Overview

This is not a media player for generic WAV audio. The tool is specialized for FNIRSI oscilloscope exports and focuses on post-processing, measurement review, graph generation, and report-oriented exports.

Current capabilities include:

- full FNIRSI 1014D `.wav` parsing
- trigger-aware waveform reconstruction
- oscilloscope configuration and measurement decoding
- MATH operations on `X` and `Y`
- FFT analysis with selectable channel, window, and scale
- statistics and advanced temporal metrics
- derivative and integral analysis
- current estimation for resistor, capacitor, and inductor models
- total current synthesis from saved current snapshots
- transfer analysis between `Vin` and `Vout`
- X-Y mode
- channel correlation and delay estimation
- calibration and normalization controls
- manual cursors with draggable markers
- cycle analysis
- snapshot saving and comparison
- PNG graph downloads for supported modules
- LaTeX export for analysis summaries

## Repository Structure

```text
.
|-- app.py               # Flask app and desktop launcher entry
|-- desktop.py           # Minimal desktop bootstrap
|-- web_routes.py        # HTTP routes, form handling, download endpoints
|-- analysis_service.py  # Analysis orchestration, caching, module builders
|-- state_store.py       # Shared app state, defaults, cache helpers
|-- file_analizer.py     # FNIRSI .wav parsing and metadata extraction
|-- signal_analyzer.py   # Signal processing and engineering calculations
|-- plot_maker.py        # Plot generation with matplotlib
|-- report.py            # LaTeX export helpers
|-- templates/
|   `-- main.html        # Main UI
|-- static/
|   `-- style.css        # Styles
|-- requirements.txt
|-- app.spec             # PyInstaller configuration
|-- installer.iss        # Inno Setup installer script
`-- iniciar.bat          # Local setup helper
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

### Derivative and integral

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

### Cursors and cycle analysis

- manual time cursors with draggable overlay
- `t1`, `t2`, `V1`, `V2`, `delta t`, `delta V`
- estimated frequency from cursor distance
- cycle count, average frequency, average period, average Vpp, average RMS

### Snapshots and comparison

- save measurement snapshots from the active file
- compare the current file against a saved snapshot
- delta Vpp and delta frequency summary

## File Decoding and Reconstruction

The parser currently reads:

- channel voltage scale
- probe factor
- coupling mode
- `time/div`
- trigger type
- trigger edge
- trigger channel
- trigger 50% flag
- automatic oscilloscope measurements
- visible waveform block
- full raw waveform block

The visible waveform pipeline is tuned to match the oscilloscope screen as closely as possible:

- raw visible samples are mapped into volts using decoded measurements
- trigger metadata is used to locate the visible reference
- the window is cropped around the trigger-centered region
- the time axis is rebuilt from the oscilloscope `time/div`

## Running the Project

### Desktop mode

```powershell
python app.py
```

By default, `app.py` launches the local Flask backend and opens a native `pywebview` window.

You can also use:

```powershell
python desktop.py
```

### Server-only mode

```powershell
$env:FNIRSI_APP_MODE="server"
python app.py
```

This starts only the local Flask server on `127.0.0.1:5000`.

## Installing Dependencies

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Or use:

```powershell
iniciar.bat
```

## Packaging

Build support files are already included:

- [app.spec](C:\Users\rance\OneDrive\Documentos\fnirsi-1014d-oscilloscope-wav-analyzer\app.spec) for PyInstaller
- [installer.iss](C:\Users\rance\OneDrive\Documentos\fnirsi-1014d-oscilloscope-wav-analyzer\installer.iss) for Inno Setup

Typical build flow:

```powershell
pip install pyinstaller
pyinstaller --clean --noconfirm app.spec
```

## License

This project is released under the MIT License.

See [LICENSE](C:\Users\rance\OneDrive\Documentos\fnirsi-1014d-oscilloscope-wav-analyzer\LICENSE).
