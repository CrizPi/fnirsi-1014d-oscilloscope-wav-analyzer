# FNIRSI 1014D Analyzer

Desktop analyzer for `.wav` captures exported by the FNIRSI 1014D oscilloscope.

The app parses the oscilloscope file format, reconstructs the visible waveforms, and provides signal analysis modules for voltage, current, transfer behavior, correlation, FFT, cursors, and report export.

## Current Scope

This project currently includes:

- desktop UI built with Flask + `pywebview`
- parsing of FNIRSI header, measures, trigger metadata, and waveform blocks
- waveform reconstruction aligned to the oscilloscope screen behavior
- main graph with oscilloscope-like horizontal scaling using `time/div`
- MATH operations on filtered voltage signals
- FFT analysis
- statistics and advanced signal measures
- derivative and integral analysis
- current estimation for resistor, capacitor, and inductor models
- total current summation for saved current calculations from the current file
- AC power calculation for individual current and total current
- transfer analysis between `Vin` and `Vout`
- channel correlation
- manual cursors
- cycle analysis
- LaTeX export for most analysis sections
- PNG export for the main plot and analysis plots that generate images

## Project Structure

```text
.
|-- app.py               # Main Flask app, desktop launcher, routing, session state
|-- desktop.py           # Minimal desktop entry point
|-- file_analizer.py     # FNIRSI .wav parsing and metadata extraction
|-- signal_analyzer.py   # Signal processing, measures, current, power, transfer analysis
|-- plot_maker.py        # Matplotlib plot generation
|-- report.py            # LaTeX report/export helpers
|-- templates/
|   `-- main.html        # Main UI
|-- static/
|   `-- style.css        # UI styles
|-- requirements.txt
|-- app.spec             # PyInstaller spec
|-- installer.iss        # Inno Setup script
`-- iniciar.bat          # Local setup helper
```

## Supported Analysis Modules

### 1. Oscilloscope data view

- `X` and `Y` waveform display
- oscilloscope configuration table
- oscilloscope measurements table
- PNG export of the main graph

### 2. MATH

- `X + Y`
- `X - Y`
- `X * Y`
- `X / Y`

### 3. FFT

- channel selection: `X`, `Y`, or `MATH`
- linear/log magnitude scaling
- selectable window
- dominant frequency
- harmonic summary
- THD estimate

### 4. Statistics and advanced signal measures

- mean, variance, standard deviation, RMS, peak-to-peak
- rise time, fall time, overshoot, undershoot, slew rate, crest factor

### 5. Derivative and integral

- derivative and integral of `X`, `Y`, or `MATH`

### 6. Current analysis

- resistor model: `i(t) = v(t) / R`
- capacitor model: `i(t) = C dv(t) / dt`
- inductor model: `i(t) = (1/L) integral(v) dt`
- current waveform graph
- RMS, mean, peak, phase
- AC power:
  - apparent power `S`
  - active power `P`
  - reactive power `Q`
  - complex power `P + jQ`
  - power factor

### 7. Total current

- sum of saved current calculations from the current file
- alignment against a selected voltage reference
- total current graph
- total AC power against selected voltage

### 8. Transfer analysis

- choose `Vin` and `Vout` from `X`, `Y`, or `MATH`
- phase shift between input and output
- `Vout/Vin` ratio using RMS
- `Vout/Vin` ratio using peak-to-peak
- gain in dB
- equivalent delay
- correlation peak
- comparison graph

### 9. Correlation

- cross-correlation between `X` and `Y`
- delay estimate

### 10. Cursors and cycle analysis

- two manual time cursors with draggable overlay
- cycle count, average frequency, average period, average Vpp, average RMS

## Oscilloscope File Handling

The parser currently reads:

- channel voltage scale
- probe factor
- coupling
- `time/div`
- trigger type
- trigger edge
- trigger channel
- trigger 50%
- oscilloscope measurements
- visible waveform data and full waveform blocks

The current display pipeline is tuned to match the waveform as shown on the oscilloscope screen:

- visible waveform data is converted to volts using the oscilloscope measures
- trigger metadata is used to locate the visible window
- the displayed window is cropped symmetrically around the detected trigger reference
- the time axis is rebuilt using the oscilloscope `time/div`

## Run the Project

### Option 1: Desktop mode

```powershell
python app.py
```

By default the project runs in desktop mode and opens a `pywebview` window.

You can also use:

```powershell
python desktop.py
```

### Option 2: Server mode

```powershell
$env:FNIRSI_APP_MODE="server"
python app.py
```

This starts only the Flask server.

## Install Dependencies

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

Desktop packaging files are already included:

- [`app.spec`](/C:/Users/rance/OneDrive/Desktop/osciloscope_fnirsi_1014d_analizer/app.spec) for PyInstaller
- [`installer.iss`](/C:/Users/rance/OneDrive/Desktop/osciloscope_fnirsi_1014d_analizer/installer.iss) for Inno Setup

Typical build flow:

```powershell
pip install pyinstaller
pyinstaller --clean --noconfirm app.spec
```

## Known Limitations

- the project depends heavily on session state inside `app.py`; the app works, but the codebase is not yet strongly modularized
- there is no automated test suite yet
- some analysis modules still recompute data inside the request cycle instead of using a cleaner service layer
- desktop and web concerns still live together in `app.py`
- the environment in this workspace may contain an invalid or stale virtual environment path depending on the local machine setup

## Recommended Improvement Areas

Highest-value next steps:

1. Split `app.py` into smaller modules:
   - routes
   - state/session helpers
   - analysis orchestration
   - desktop launcher

2. Add automated tests for:
   - `.wav` parsing
   - trigger/window reconstruction
   - `raw -> volts` conversion
   - current and power analysis
   - transfer analysis

3. Separate display signals from analysis signals more explicitly:
   - display path for oscilloscope-like visualization
   - analysis path for measurements sensitive to filtering or differentiation

4. Replace session-heavy state with a clearer internal model for:
   - loaded file state
   - active modules
   - cached graph/analysis artifacts

5. Add validation fixtures:
   - real FNIRSI capture files
   - expected waveform screenshots
   - reference values for phase, gain, current, and power

6. Improve report/export coverage:
   - add graph download for transfer analysis
   - optionally generate a full multi-section report document

## License

This project is released under the MIT License.

See [`LICENSE`](/C:/Users/rance/OneDrive/Desktop/osciloscope_fnirsi_1014d_analizer/LICENSE).
