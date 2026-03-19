import numpy as np
from scipy.signal import butter, filtfilt, medfilt

# ===============================
# TIEMPO Y FRECUENCIA
# ===============================
def get_scope_fs_and_time(ch1, config, screen_divisions=14):
    """
    Calcula la frecuencia de muestreo y vector de tiempo
    """
    N = len(ch1)
    time_div_s = config["time_div"] * config["time_multiplier"]
    T_total = screen_divisions * time_div_s
    fs = N / T_total
    t = np.arange(N) / fs
    return fs, t


def calculate_frequency(signal, fs):
    """
    Calcula la frecuencia de un señal usando cruces por cero
    """
    signal = np.asarray(signal)
    center = (signal.max() + signal.min()) / 2
    signal_centered = signal - center
    zero_crossings = np.where(np.diff(np.signbit(signal_centered)))[0]

    if len(zero_crossings) < 2:
        return 0, "Hz", 1

    periods_samples = np.diff(zero_crossings)
    avg_period_samples = 2 * np.mean(periods_samples)  # ciclo completo
    freq_hz = fs / avg_period_samples

    # Escalar unidades
    if freq_hz >= 1e6:
        return round(freq_hz / 1e6, 1), "MHz", 1e6
    elif freq_hz >= 1e3:
        return round(freq_hz / 1e3, 1), "kHz", 1e3
    else:
        return round(freq_hz, 1), "Hz", 1


# ===============================
# CONVERSIÓN DE SEÑALES
# ===============================
def convert_scope_data(ch1, ch2, config, measures):
    """
    Convierte datos crudos del osciloscopio a voltajes reales
    """
    ch_real = []

    for ch_idx, raw in enumerate([ch1, ch2]):
        raw = np.asarray(raw, dtype=float)
        raw_max, raw_min = raw.max(), raw.min()
        vmax, vmin = measures["Vmax"][ch_idx], measures["Vmin"][ch_idx]

        if raw_max == raw_min:
            a, b = 1, 0
        else:
            a = (vmax - vmin) / (raw_max - raw_min)
            b = vmax - a * raw_max

        volts = a * raw + b
        volts *= config["probe"][ch_idx]
        ch_real.append(volts)

    return ch_real[0], ch_real[1]


# ===============================
# OPERACIONES MATEMÁTICAS
# ===============================
def apply_math_operation(ch1, ch2, operation):
    """
    Aplica operación matemática entre dos canales
    """
    if ch1 is None or ch2 is None:
        return None

    ch1, ch2 = np.asarray(ch1), np.asarray(ch2)

    if operation == "add":
        return ch1 + ch2
    elif operation == "sub":
        return ch1 - ch2
    elif operation == "mul":
        return ch1 * ch2
    elif operation == "div":
        ch2_safe = np.where(ch2 == 0, 1e-12, ch2)
        return ch1 / ch2_safe
    return None


def calculate_math_measures(signal, fs):
    """
    Calcula medidas matemáticas: Vmax, Vmin, Vrms, frecuencia, duty cycle, tiempos, etc.
    """
    signal = np.asarray(signal)
    Vmax, Vmin = signal.max(), signal.min()
    Vavg = signal.mean()
    Vrms = np.sqrt(np.mean(signal ** 2))
    Vpp = Vmax - Vmin
    Vp = max(abs(Vmax), abs(Vmin))

    freq, freq_unit, freq_multiplier = calculate_frequency(signal, fs)

    freq_hz = freq * freq_multiplier
    period = 1 / freq_hz if freq_hz != 0 else 0

    # Escalado de unidades de periodo
    if period >= 1:
        cycle, cycle_unit = round(period, 6), "s"
    elif period >= 1e-3:
        cycle, cycle_unit = round(period * 1e3, 3), "ms"
    elif period >= 1e-6:
        cycle, cycle_unit = round(period * 1e6, 3), "µs"
    else:
        cycle, cycle_unit = round(period * 1e9, 3), "ns"

    # Duty cycle
    center = (Vmax + Vmin) / 2
    positive = signal - center > 0
    time_step = 1 / fs
    time_pos = np.sum(positive) * time_step
    time_neg = np.sum(~positive) * time_step
    total_time = time_pos + time_neg
    duty_pos = (time_pos / total_time) * 100 if total_time > 0 else 0
    duty_neg = (time_neg / total_time) * 100 if total_time > 0 else 0

    def scale_time(t):
        if t >= 1:
            return round(t, 6), "s"
        elif t >= 1e-3:
            return round(t * 1e3, 3), "ms"
        elif t >= 1e-6:
            return round(t * 1e6, 3), "µs"
        else:
            return round(t * 1e9, 3), "ns"

    time_pos_val, time_pos_unit = scale_time(time_pos)
    time_neg_val, time_neg_unit = scale_time(time_neg)

    return {
        "Vmax": round(Vmax, 3),
        "Vmin": round(Vmin, 3),
        "Vavg": round(Vavg, 3),
        "Vrms": round(Vrms, 3),
        "Vpp": round(Vpp, 3),
        "Vp": round(Vp, 3),

        "Freq": freq,
        "freq_unit": freq_unit,

        "Cycle": cycle,
        "cycle_unit": cycle_unit,

        "Time+": time_pos_val,
        "time_plus_unit": time_pos_unit,
        "Time-": time_neg_val,
        "time_minus_unit": time_neg_unit,

        "Duty+": round(duty_pos, 2),
        "Duty-": round(duty_neg, 2),
    }


# ===============================
# FILTROS
# ===============================
def butter_lowpass(signal, fs, cutoff_ratio=0.1, order=3):
    """
    Filtro Butterworth lowpass
    """
    nyq = 0.5 * fs
    cutoff = nyq * cutoff_ratio
    if cutoff <= 0:
        return signal
    b, a = butter(order, cutoff / nyq, btype='low')
    return filtfilt(b, a, signal)


def anti_aliasing_filter(signal, strength=5):
    """
    Filtro suavizado tipo moving average
    """
    kernel = np.ones(strength) / strength
    return np.convolve(signal, kernel, mode='same')


# ===============================
# DETECCIÓN TIPO DE SEÑAL
# ===============================
def detect_signal_type(signal, threshold=0.08):
    """
    Detecta si una señal es digital o analógica
    """
    signal = np.asarray(signal)
    diff = np.abs(np.diff(signal))
    ratio = np.sum(diff > threshold) / len(signal)
    skew = np.mean(diff**3) / (np.std(diff)**3 + 1e-12)
    is_digital = (ratio > 0.04) or (skew > 1.5)

    print(f"DEBUG ratio={ratio:.3f}, skew={skew:.2f}, type={'digital' if is_digital else 'analog'}")
    return "digital" if is_digital else "analog"


def adaptive_scope_filter(signal, fs):
    """
    Aplica filtro adaptativo según tipo de señal (digital o analógica)
    """
    if signal is None or len(signal) < 10:
        return signal

    signal = np.asarray(signal)
    signal_type = detect_signal_type(signal)

    # DIGITAL
    if signal_type == "digital":
        filtered = medfilt(signal, kernel_size=3)
        if fs > 500:
            filtered = butter_lowpass(filtered, fs, cutoff_ratio=0.45, order=1)
        return filtered

    # ANALÓGICA
    Vpp = signal.max() - signal.min()
    if Vpp > 0.5:
        filtered = butter_lowpass(signal, fs, cutoff_ratio=0.10, order=3)
        filtered = anti_aliasing_filter(filtered, strength=4)
    else:
        filtered = butter_lowpass(signal, fs, cutoff_ratio=0.08, order=4)
        filtered = anti_aliasing_filter(filtered, strength=5)

    return filtered