import numpy as np


class ScopeFileError(ValueError):
    pass


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


def _read_exact(file_path, offset, size):
    with open(file_path, "rb") as f:
        f.seek(offset)
        data = f.read(size)
    if len(data) != size:
        raise ScopeFileError(f"Archivo incompleto: se esperaban {size} bytes en offset {offset}.")
    return data


def _safe_lookup(sequence, index, description):
    if index < 0 or index >= len(sequence):
        raise ScopeFileError(f"Valor fuera de rango para {description}: {index}")
    return sequence[index]


def _scale_time_seconds(time_seconds):
    if time_seconds >= 1:
        return float(f"{time_seconds:.4g}"), "S", 1
    if time_seconds >= 1e-3:
        return float(f"{time_seconds * 1e3:.4g}"), "mS", 1e-3
    if time_seconds >= 1e-6:
        return float(f"{time_seconds * 1e6:.4g}"), "uS", 1e-6
    return float(f"{time_seconds * 1e9:.4g}"), "nS", 1e-9


def get_scope_config(file):

    header = _read_exact(file, 0, 208)

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

        v = _safe_lookup(voltList, header[4 + ch*10], f"volt/div canal {ch + 1}")

        volts_div = v[0]
        multiplier = v[2]

        volts.append(volts_div)
        units.append(v[1])
        multipliers.append(multiplier)

        probe_val = _safe_lookup([1, 10, 100], header[10 + ch*10], f"probe canal {ch + 1}")
        probe.append(probe_val)

        coupling.append(_safe_lookup(["DC", "AC"], header[8 + ch*10], f"coupling canal {ch + 1}"))

    config["volts_div"] = volts
    config["volt_units"] = units
    config["volt_multiplier"] = multipliers
    config["probe"] = probe
    config["coupling"] = coupling

    # -----------------------------
    # TIME DIV
    # -----------------------------
    t = _safe_lookup(timeList, header[22], "time/div")

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

    m1 = _read_exact(file, 208, 48)
    m2 = _read_exact(file, 256, 48)

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
    time_plus_units = [None, None]
    time_minus_units = [None, None]
    time_plus_multiplier = [None, None]
    time_minus_multiplier = [None, None]

    for ch in range(2):

        if freq_hz[ch] and freq_hz[ch] > 0:

            cycle = 1.0 / freq_hz[ch]

            cycle_val, cycle_units[ch], cycle_multiplier[ch] = _scale_time_seconds(cycle)
            cycle_values.append(cycle_val)

            duty_plus = max(0.0, float(results["Duty+"][ch]))
            duty_minus = max(0.0, float(results["Duty-"][ch]))
            duty_total = duty_plus + duty_minus

            if duty_total > 0:
                time_plus_seconds = cycle * (duty_plus / duty_total)
                time_minus_seconds = cycle * (duty_minus / duty_total)
            else:
                time_plus_seconds = cycle / 2
                time_minus_seconds = cycle / 2

            time_plus_value, time_plus_units[ch], time_plus_multiplier[ch] = _scale_time_seconds(time_plus_seconds)
            time_minus_value, time_minus_units[ch], time_minus_multiplier[ch] = _scale_time_seconds(time_minus_seconds)
            time_plus_values.append(time_plus_value)
            time_minus_values.append(time_minus_value)

        else:

            cycle_values.append(0.0)
            time_plus_values.append(0.0)
            time_minus_values.append(0.0)

            cycle_units[ch] = "Hz"
            cycle_multiplier[ch] = 1
            time_plus_units[ch] = "S"
            time_minus_units[ch] = "S"
            time_plus_multiplier[ch] = 1
            time_minus_multiplier[ch] = 1

    results["Cycle"] = cycle_values
    results["Time+"] = time_plus_values
    results["Time-"] = time_minus_values

    results["freq_units"] = freq_units
    results["freq_multiplier"] = freq_multiplier
    results["cycle_units"] = cycle_units
    results["cycle_multiplier"] = cycle_multiplier
    results["time_plus_units"] = time_plus_units
    results["time_minus_units"] = time_minus_units
    results["time_plus_multiplier"] = time_plus_multiplier
    results["time_minus_multiplier"] = time_minus_multiplier

    return results


def get_scope_raw_data_display(file, measures):

    ch1_raw = _read_exact(file, 7000, 1500)
    ch2_raw = _read_exact(file, 8500, 1500)

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

    ch1_raw = _read_exact(file, 1000, 3000)
    ch2_raw = _read_exact(file, 4000, 3000)

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
