import numpy as np


voltList = [
    [5.0,"V",1],[2.5,"V",1],[1.0,"V",1],
    [500,"mV",0.001],[200,"mV",0.001],[100,"mV",0.001],[50,"mV",0.001]
]

timeList = [
[50,"S",1],[20,"S",1],[10,"S",1],[5,"S",1],[2,"S",1],[1,"S",1],
[500,"mS",.001],[200,"mS",.001],[100,"mS",.001],[50,"mS",.001],
[20,"mS",.001],[10,"mS",.001],[5,"mS",.001],[2,"mS",.001],[1,"mS",.001],
[500,"uS",1E-6],[200,"uS",1E-6],[100,"uS",1E-6],[50,"uS",1E-6],
[20,"uS",1E-6],[10,"uS",1E-6],[5,"uS",1E-6],[2,"uS",1E-6],[1,"uS",1E-6],
[500,"nS",1E-9],[200,"nS",1E-9],[100,"nS",1E-9],[50,"nS",1E-9],
[20,"nS",1E-9],[10,"nS",1E-9]
]

def get_scope_config(file):

    with open(file, "rb") as f:
        header = f.read(208)

    config = {}

    volts = []
    units = []
    multipliers = []
    probe = []
    coupling = []

    # -----------------------------
    # CONFIGURACIÓN POR CANAL
    # -----------------------------
    for ch in range(2):

        v = voltList[header[4 + ch*10]]

        volts_div = v[0]
        multiplier = v[2]

        volts.append(volts_div)
        units.append(v[1])
        multipliers.append(multiplier)

        probe_val = [1,10,100][header[10 + ch*10]]
        probe.append(probe_val)

        coupling.append(["DC","AC"][header[8 + ch*10]])

    config["volts_div"] = volts
    config["volt_units"] = units
    config["volt_multiplier"] = multipliers
    config["probe"] = probe
    config["coupling"] = coupling

    # -----------------------------
    # TIME DIV
    # -----------------------------
    t = timeList[header[22]]

    config["time_div"] = t[0]
    config["time_units"] = t[1]
    config["time_multiplier"] = t[2]

    return config



freqList = [
    ["mHz", 1e-3],
    ["Hz", 1],
    ["kHz", 1e3],
    ["MHz", 1e6]
]

measureList = [
    "Vmax", "Vmin", "Vavg", "Vrms", "Vpp", "Vp",
    "Freq", "Cycle", "Time+", "Time-", "Duty+", "Duty-"
]



def get_scope_measures(file):

    config = get_scope_config(file)
    time_multiplier = config["time_multiplier"]

    with open(file, "rb") as f:
        f.seek(208)
        m1 = f.read(48)
        f.seek(256)
        m2 = f.read(48)

    measures_raw = [m1, m2]
    results = {}

    freq_units = [None, None]
    freq_multiplier = [None, None]
    freq_hz = [None, None]

    for i, name in enumerate(measureList):

        ch_values = []

        for ch in range(2):

            ad = i * 4

            b0 = measures_raw[ch][ad]
            b1 = measures_raw[ch][ad+1]
            b2 = measures_raw[ch][ad+2]
            b3 = measures_raw[ch][ad+3]

            if i < 6:

                raw = b3 * 256 + b2
                value = raw / 1024

            elif i == 6:  # Frequency

                raw = (b1 << 24) | (b0 << 16) | (b3 << 8) | b2

                if time_multiplier >= 1e-3:
                    freq_hz[ch] = raw / 1000.0
                else:
                    freq_hz[ch] = raw

                if freq_hz[ch] >= 1e6:
                    value = freq_hz[ch] / 1e6
                    freq_units[ch] = "MHz"
                    freq_multiplier[ch] = 1e6
                elif freq_hz[ch] >= 1e3:
                    value = freq_hz[ch] / 1e3
                    freq_units[ch] = "kHz"
                    freq_multiplier[ch] = 1e3
                else:
                    value = freq_hz[ch]
                    freq_units[ch] = "Hz"
                    freq_multiplier[ch] = 1

            else:

                raw = b3 * 256 + b2
                value = raw

            if value > 0:
                value = float(f"{value:.4g}")

            ch_values.append(value)

        results[name] = ch_values

    # =============================
    # CORRECCIÓN DE SIGNO VOLTAJE
    # =============================

    for ch in range(2):

        vmax = results["Vmax"][ch]
        vmin = results["Vmin"][ch]
        vpp  = results["Vpp"][ch]
        vp   = results["Vp"][ch]

        # -------------------------
        # CASO DC (Vpp ≈ 0)
        # -------------------------
        if abs(vpp) < 0.01:

            if abs(vp - vmax) < 0.01:
                sign = 1
            elif abs(vp - vmin) < 0.01:
                sign = -1
            else:
                sign = 1

            vmax_real = sign * vmax
            vmin_real = sign * vmin

        # -------------------------
        # CASO NORMAL (tu método)
        # -------------------------
        else:

            combos = [
                (vmax, vmin),
                (vmax, -vmin),
                (-vmax, vmin),
                (-vmax, -vmin)
            ]

            best = (vmax, vmin)

            for a, b in combos:
                if abs((a - b) - vpp) < 0.01:
                    best = (a, b)
                    break

            vmax_real, vmin_real = best

        results["Vmax"][ch] = float(f"{vmax_real:.4g}")
        results["Vmin"][ch] = float(f"{vmin_real:.4g}")

        vavg = (vmax_real + vmin_real) / 2
        results["Vavg"][ch] = float(f"{vavg:.4g}")

    # =============================
    # CALCULOS DE TIEMPO
    # =============================

    cycle_values = []
    time_plus_values = []
    time_minus_values = []
    cycle_units = [None, None]
    cycle_multiplier = [None, None]
    time_units = [None, None]
    time_multiplier_new = [None, None]

    for ch in range(2):

        if freq_hz[ch] and freq_hz[ch] > 0:

            cycle = 1.0 / freq_hz[ch]

            if cycle >= 1:
                cycle_val = cycle
                cycle_units[ch] = "S"
                cycle_multiplier[ch] = 1
            elif cycle >= 1e-3:
                cycle_val = cycle * 1e3
                cycle_units[ch] = "mS"
                cycle_multiplier[ch] = 1e-3
            elif cycle >= 1e-6:
                cycle_val = cycle * 1e6
                cycle_units[ch] = "uS"
                cycle_multiplier[ch] = 1e-6
            else:
                cycle_val = cycle * 1e9
                cycle_units[ch] = "nS"
                cycle_multiplier[ch] = 1e-9

            cycle_val = float(f"{cycle_val:.4g}")

            cycle_values.append(cycle_val)

            time_plus_values.append(float(f"{cycle_val/2:.4g}"))
            time_minus_values.append(float(f"{cycle_val/2:.4g}"))

            time_units[ch] = cycle_units[ch]
            time_multiplier_new[ch] = cycle_multiplier[ch]

        else:

            cycle_values.append(0.0)
            time_plus_values.append(0.0)
            time_minus_values.append(0.0)

            cycle_units[ch] = "Hz"
            cycle_multiplier[ch] = 1
            time_units[ch] = "S"
            time_multiplier_new[ch] = 1

    results["Cycle"] = cycle_values
    results["Time+"] = time_plus_values
    results["Time-"] = time_minus_values

    results["freq_units"] = freq_units
    results["freq_multiplier"] = freq_multiplier
    results["cycle_units"] = cycle_units
    results["cycle_multiplier"] = cycle_multiplier
    results["time_plus_units"] = time_units
    results["time_minus_units"] = time_units
    results["time_plus_multiplier"] = time_multiplier_new
    results["time_minus_multiplier"] = time_multiplier_new

    return results


def get_scope_raw_data_display(file, measures):

    with open(file, "rb") as f:
        # CH1 data2: 7000 - 8499
        f.seek(7000)
        ch1_raw = f.read(1500)

        # CH2 data2: 8500 - 9999
        f.seek(8500)
        ch2_raw = f.read(1500)

    ch1 = []
    ch2 = []

    for i in range(750):

        v1 = int.from_bytes(ch1_raw[i*2:i*2+2], "little")
        v2 = int.from_bytes(ch2_raw[i*2:i*2+2], "little")

        ch1.append(v1)
        ch2.append(v2)

    # ---- Verificar si el canal está vacío según measures ----

    ch1_empty = all(measures[key][0] == 0 for key in ["Vmax","Vmin","Vavg","Vrms","Vpp","Vp"])
    ch2_empty = all(measures[key][1] == 0 for key in ["Vmax","Vmin","Vavg","Vrms","Vpp","Vp"])

    if ch1_empty:
        ch1 = [0] * len(ch1)

    if ch2_empty:
        ch2 = [0] * len(ch2)

    return ch1, ch2

def get_scope_raw_data_complete(file, measures):

    with open(file, "rb") as f:

        f.seek(1000)
        ch1_raw = f.read(3000)

        f.seek(4000)
        ch2_raw = f.read(3000)

    ch1 = []
    ch2 = []

    for i in range(1500):

        v1 = int.from_bytes(ch1_raw[i*2:i*2+2], "little")
        v2 = int.from_bytes(ch2_raw[i*2:i*2+2], "little")

        ch1.append(v1)
        ch2.append(v2)

    # ---- Verificar si el canal está vacío según measures ----

    ch1_empty = all(measures[key][0] == 0 for key in ["Vmax","Vmin","Vavg","Vrms","Vpp","Vp"])
    ch2_empty = all(measures[key][1] == 0 for key in ["Vmax","Vmin","Vavg","Vrms","Vpp","Vp"])

    if ch1_empty:
        ch1 = [0] * len(ch1)

    if ch2_empty:
        ch2 = [0] * len(ch2)

    return ch1, ch2
