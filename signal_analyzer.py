import numpy as np
from scipy.signal import butter, filtfilt, medfilt


WINDOW_FUNCTIONS = {
    "rectangular": lambda n: np.ones(n, dtype=float),
    "hann": np.hanning,
    "hamming": np.hamming,
    "blackman": np.blackman,
}


def _finite_signal(signal):
    signal = np.asarray(signal, dtype=float)
    return signal[np.isfinite(signal)]


def _replace_nonfinite(signal):
    signal = np.asarray(signal, dtype=float)
    if signal.size == 0:
        return signal

    finite_mask = np.isfinite(signal)
    if np.all(finite_mask):
        return signal
    if not np.any(finite_mask):
        return np.zeros_like(signal)

    indices = np.arange(signal.size, dtype=float)
    cleaned = signal.copy()
    cleaned[~finite_mask] = np.interp(indices[~finite_mask], indices[finite_mask], signal[finite_mask])
    return cleaned


def get_scope_fs_and_time(ch1, config, screen_divisions=14):
    """
    Calcula la frecuencia de muestreo y el vector de tiempo.
    """
    sample_count = len(ch1)
    time_div_s = config["time_div"] * config["time_multiplier"]
    if sample_count == 0 or time_div_s <= 0:
        return 0, np.array([])

    total_time = screen_divisions * time_div_s
    fs = sample_count / total_time
    return fs, np.arange(sample_count) / fs


def calculate_frequency(signal, fs):
    """
    Calcula la frecuencia de una senal con FFT y refinamiento por autocorrelacion.
    """
    freq_hz = _estimate_frequency_hz(signal, fs)
    if freq_hz <= 0:
        return 0, "Hz", 1
    return scale_frequency_value(freq_hz)


def scale_frequency_value(freq_hz):
    if freq_hz >= 1e6:
        return round(freq_hz / 1e6, 3), "MHz", 1e6
    if freq_hz >= 1e3:
        return round(freq_hz / 1e3, 3), "kHz", 1e3
    return round(freq_hz, 3), "Hz", 1


def _scale_time_value(time_seconds):
    if time_seconds >= 1:
        return round(time_seconds, 6), "s"
    if time_seconds >= 1e-3:
        return round(time_seconds * 1e3, 3), "ms"
    if time_seconds >= 1e-6:
        return round(time_seconds * 1e6, 3), "us"
    return round(time_seconds * 1e9, 3), "ns"


def _safe_rms(signal):
    signal = np.asarray(signal, dtype=float)
    if signal.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(signal ** 2)))


def _crossing_times(signal, fs, threshold, direction):
    signal = np.asarray(signal, dtype=float)
    if signal.size < 2 or fs <= 0:
        return []

    crossing_times = []
    for index in range(signal.size - 1):
        y0 = signal[index]
        y1 = signal[index + 1]
        if y1 == y0:
            continue

        if direction == "rising" and y0 < threshold <= y1:
            fraction = (threshold - y0) / (y1 - y0)
        elif direction == "falling" and y0 > threshold >= y1:
            fraction = (y0 - threshold) / (y0 - y1)
        else:
            continue

        crossing_times.append((index + fraction) / fs)

    return crossing_times


def _pair_crossings(start_times, end_times):
    pairs = []
    end_index = 0
    for start in start_times:
        while end_index < len(end_times) and end_times[end_index] <= start:
            end_index += 1
        if end_index >= len(end_times):
            break
        pairs.append(end_times[end_index] - start)
        end_index += 1
    return pairs


def _estimate_quantized_levels(signal):
    signal = np.asarray(signal, dtype=float)
    if signal.size == 0:
        return 0

    peak_to_peak = np.ptp(signal)
    if peak_to_peak <= 0:
        return 1

    rounded = np.round(signal, decimals=2)
    return int(np.unique(rounded).size)


def _plateau_ratio(signal):
    signal = np.asarray(signal, dtype=float)
    if signal.size < 3:
        return 0.0

    first_diff = np.abs(np.diff(signal))
    threshold = max(np.ptp(signal) * 0.015, 1e-6)
    return float(np.mean(first_diff < threshold))


def _extract_pulse_statistics(binary_signal, fs):
    if fs <= 0 or binary_signal.size == 0:
        return 0.0, 0.0

    runs = []
    current_value = binary_signal[0]
    current_length = 1

    for value in binary_signal[1:]:
        if value == current_value:
            current_length += 1
            continue
        runs.append((current_value, current_length))
        current_value = value
        current_length = 1

    runs.append((current_value, current_length))

    positive_runs = [length / fs for state, length in runs if state]
    negative_runs = [length / fs for state, length in runs if not state]

    avg_positive = float(np.mean(positive_runs)) if positive_runs else 0.0
    avg_negative = float(np.mean(negative_runs)) if negative_runs else 0.0
    return avg_positive, avg_negative


def _estimate_frequency_hz(signal, fs):
    signal = _replace_nonfinite(signal)
    if signal.size < 4 or fs <= 0:
        return 0.0

    centered = signal - np.mean(signal)
    amplitude = np.ptp(centered)
    if amplitude <= 1e-12:
        return 0.0

    spectrum_freq_hz = _estimate_frequency_from_fft(centered, fs)
    autocorr_freq_hz = _estimate_frequency_from_autocorrelation(centered, fs, spectrum_freq_hz)

    if autocorr_freq_hz > 0:
        return autocorr_freq_hz
    return spectrum_freq_hz


def _estimate_frequency_from_fft(signal, fs):
    sample_count = signal.size
    if sample_count < 4 or fs <= 0:
        return 0.0

    window = np.hanning(sample_count)
    spectrum = np.fft.rfft(signal * window)
    frequencies_hz = np.fft.rfftfreq(sample_count, d=1 / fs)
    magnitudes = np.abs(spectrum)
    if magnitudes.size < 2:
        return 0.0

    magnitudes[0] = 0.0
    dominant_index = int(np.argmax(magnitudes))
    if dominant_index <= 0 or magnitudes[dominant_index] <= 0:
        return 0.0

    refined_index = _quadratic_peak_index(magnitudes, dominant_index)
    bin_width_hz = frequencies_hz[1] - frequencies_hz[0] if frequencies_hz.size > 1 else 0.0
    return max(0.0, refined_index * bin_width_hz)


def _estimate_frequency_from_autocorrelation(signal, fs, fft_frequency_hz=0.0):
    sample_count = signal.size
    if sample_count < 4 or fs <= 0:
        return 0.0

    autocorrelation = np.correlate(signal, signal, mode="full")[sample_count - 1 :]
    if autocorrelation.size < 3 or autocorrelation[0] <= 0:
        return 0.0

    autocorrelation = autocorrelation / autocorrelation[0]
    autocorrelation[0] = 0.0

    if fft_frequency_hz > 0:
        expected_lag = fs / fft_frequency_hz
        min_lag = max(1, int(expected_lag * 0.5))
        max_lag = min(sample_count - 2, int(expected_lag * 1.5))
    else:
        max_frequency = max(fs / 2.0, 1.0)
        min_frequency = max(fs / sample_count, 1.0 / max(sample_count / fs, 1e-12))
        min_lag = max(1, int(fs / max_frequency))
        max_lag = min(sample_count - 2, int(fs / min_frequency))

    if max_lag <= min_lag:
        return 0.0

    search = autocorrelation[min_lag : max_lag + 1]
    if search.size == 0:
        return 0.0

    relative_index = int(np.argmax(search))
    peak_index = min_lag + relative_index
    if autocorrelation[peak_index] <= 0:
        return 0.0

    refined_lag = _quadratic_peak_index(autocorrelation, peak_index)
    if refined_lag <= 0:
        return 0.0
    return fs / refined_lag


def _quadratic_peak_index(values, index):
    values = np.asarray(values, dtype=float)
    if index <= 0 or index >= values.size - 1:
        return float(index)

    left = values[index - 1]
    center = values[index]
    right = values[index + 1]
    denominator = left - 2 * center + right
    if abs(denominator) <= 1e-12:
        return float(index)
    return float(index + 0.5 * (left - right) / denominator)


def _resolve_window(window_type, sample_count):
    window_key = (window_type or "hann").lower()
    window_fn = WINDOW_FUNCTIONS.get(window_key, np.hanning)
    return window_key, window_fn(sample_count)


def _find_top_fft_peaks(frequencies_hz, magnitudes, limit=5):
    if frequencies_hz.size == 0 or magnitudes.size == 0:
        return []

    if magnitudes.size < 3:
        indices = np.argsort(magnitudes)[::-1][:limit]
    else:
        indices = []
        for index in range(1, magnitudes.size - 1):
            if magnitudes[index] >= magnitudes[index - 1] and magnitudes[index] >= magnitudes[index + 1]:
                indices.append(index)
        if not indices:
            indices = list(range(magnitudes.size))
        indices = np.array(indices, dtype=int)
        indices = indices[np.argsort(magnitudes[indices])[::-1][:limit]]

    peaks = []
    for index in indices:
        freq_hz = float(frequencies_hz[index])
        amplitude = float(magnitudes[index])
        scaled_freq, unit, _ = scale_frequency_value(freq_hz)
        peaks.append(
            {
                "frequency_hz": freq_hz,
                "frequency": scaled_freq,
                "frequency_unit": unit,
                "magnitude": round(amplitude, 6),
            }
        )
    return peaks


def _calculate_harmonics(frequencies_hz, magnitudes, dominant_frequency_hz, harmonic_count=5):
    harmonics = []
    if dominant_frequency_hz <= 0 or frequencies_hz.size == 0 or magnitudes.size == 0:
        return harmonics

    for order in range(1, harmonic_count + 1):
        target_hz = dominant_frequency_hz * order
        if target_hz > frequencies_hz[-1]:
            break

        bin_width_hz = frequencies_hz[1] - frequencies_hz[0] if frequencies_hz.size > 1 else target_hz
        tolerance_hz = max(bin_width_hz * 2, target_hz * 0.03)
        mask = np.abs(frequencies_hz - target_hz) <= tolerance_hz
        candidate_indices = np.flatnonzero(mask)
        if candidate_indices.size == 0:
            index = int(np.argmin(np.abs(frequencies_hz - target_hz)))
        else:
            local_index = int(np.argmax(magnitudes[candidate_indices]))
            index = int(candidate_indices[local_index])

        harmonic_hz = float(frequencies_hz[index])
        harmonic_mag = float(magnitudes[index])
        scaled_freq, unit, _ = scale_frequency_value(harmonic_hz)
        harmonics.append(
            {
                "order": order,
                "frequency_hz": harmonic_hz,
                "frequency": scaled_freq,
                "frequency_unit": unit,
                "magnitude": round(harmonic_mag, 6),
            }
        )
    return harmonics


def _calculate_thd_percent(harmonics):
    if not harmonics:
        return 0.0

    fundamental = harmonics[0]["magnitude"]
    if fundamental <= 0:
        return 0.0

    harmonic_energy = sum(harmonic["magnitude"] ** 2 for harmonic in harmonics[1:])
    return round(float(np.sqrt(harmonic_energy) / fundamental * 100), 4)


def get_fft_spectrum(signal, fs, max_frequency=None, window_type="hann"):
    signal = _replace_nonfinite(signal)

    empty = {
        "frequencies_hz": np.array([]),
        "magnitudes": np.array([]),
        "dominant_frequency_hz": 0.0,
        "dominant_magnitude": 0.0,
        "dominant_frequency": 0.0,
        "dominant_frequency_unit": "Hz",
        "frequency_multiplier": 1,
        "window_type": (window_type or "hann").lower(),
        "top_peaks": [],
        "harmonics": [],
        "thd_percent": 0.0,
    }
    if signal.size < 2 or fs <= 0:
        return empty

    centered_signal = signal - np.mean(signal)
    window_key, window = _resolve_window(window_type, signal.size)
    windowed_signal = centered_signal * window

    spectrum = np.fft.rfft(windowed_signal)
    frequencies_hz = np.fft.rfftfreq(signal.size, d=1 / fs)
    magnitudes = (2.0 / np.sum(window)) * np.abs(spectrum)

    if frequencies_hz.size > 0:
        magnitudes[0] = 0.0

    if max_frequency is not None and max_frequency > 0:
        mask = frequencies_hz <= max_frequency
        frequencies_hz = frequencies_hz[mask]
        magnitudes = magnitudes[mask]

    if magnitudes.size == 0:
        return empty | {"window_type": window_key}

    dominant_index = int(np.argmax(magnitudes))
    dominant_frequency_hz = float(frequencies_hz[dominant_index])
    dominant_magnitude = float(magnitudes[dominant_index])
    dominant_frequency, dominant_unit, dominant_multiplier = scale_frequency_value(dominant_frequency_hz)
    top_peaks = _find_top_fft_peaks(frequencies_hz, magnitudes, limit=5)
    harmonics = _calculate_harmonics(frequencies_hz, magnitudes, dominant_frequency_hz, harmonic_count=5)

    return {
        "frequencies_hz": frequencies_hz,
        "magnitudes": magnitudes,
        "dominant_frequency_hz": dominant_frequency_hz,
        "dominant_magnitude": round(dominant_magnitude, 6),
        "dominant_frequency": dominant_frequency,
        "dominant_frequency_unit": dominant_unit,
        "frequency_multiplier": dominant_multiplier,
        "window_type": window_key,
        "top_peaks": top_peaks,
        "harmonics": harmonics,
        "thd_percent": _calculate_thd_percent(harmonics),
    }


def calculate_signal_statistics(signal):
    signal = _finite_signal(signal)

    if signal.size == 0:
        return {
            "mean": 0.0,
            "std_dev": 0.0,
            "variance": 0.0,
            "median": 0.0,
            "min": 0.0,
            "max": 0.0,
            "range": 0.0,
            "rms": 0.0,
            "peak_to_peak": 0.0,
        }

    mean = float(np.mean(signal))
    std_dev = float(np.std(signal))
    variance = float(np.var(signal))
    median = float(np.median(signal))
    min_value = float(np.min(signal))
    max_value = float(np.max(signal))
    rms = float(np.sqrt(np.mean(signal ** 2)))
    peak_to_peak = float(np.ptp(signal))

    return {
        "mean": round(mean, 6),
        "std_dev": round(std_dev, 6),
        "variance": round(variance, 6),
        "median": round(median, 6),
        "min": round(min_value, 6),
        "max": round(max_value, 6),
        "range": round(max_value - min_value, 6),
        "rms": round(rms, 6),
        "peak_to_peak": round(peak_to_peak, 6),
    }


def calculate_cycle_analysis(signal, fs):
    signal = _replace_nonfinite(signal)
    empty = {
        "cycle_count": 0,
        "avg_frequency": 0.0,
        "avg_frequency_unit": "Hz",
        "avg_period": 0.0,
        "avg_period_unit": "s",
        "avg_vpp": 0.0,
        "avg_rms": 0.0,
        "enabled": False,
    }
    if signal.size < 4 or fs <= 0:
        return empty

    center = float(np.mean(signal))
    crossings = []
    for index in range(signal.size - 1):
        y0 = signal[index] - center
        y1 = signal[index + 1] - center
        if y0 < 0 <= y1 and y1 != y0:
            fraction = (-y0) / (y1 - y0)
            crossings.append(index + fraction)

    if len(crossings) < 2:
        return empty

    periods_samples = np.diff(crossings)
    periods_seconds = periods_samples / fs
    valid_periods = periods_seconds[periods_seconds > 0]
    if valid_periods.size == 0:
        return empty

    cycle_windows = []
    for start_cross, end_cross in zip(crossings[:-1], crossings[1:]):
        start_idx = int(np.floor(start_cross))
        end_idx = int(np.ceil(end_cross))
        if end_idx - start_idx >= 2:
            cycle_windows.append(signal[start_idx:end_idx])

    if not cycle_windows:
        return empty

    avg_period_seconds = float(np.mean(valid_periods))
    frequency_hz = _estimate_frequency_hz(signal, fs)
    avg_frequency_hz = frequency_hz if frequency_hz > 0 else (float(1.0 / avg_period_seconds) if avg_period_seconds > 0 else 0.0)
    avg_period_value, avg_period_unit = _scale_time_value(avg_period_seconds)
    avg_frequency_value, avg_frequency_unit, _ = scale_frequency_value(avg_frequency_hz)
    avg_vpp = float(np.mean([np.ptp(window) for window in cycle_windows]))
    avg_rms = float(np.mean([_safe_rms(window) for window in cycle_windows]))

    return {
        "cycle_count": len(cycle_windows),
        "avg_frequency": avg_frequency_value,
        "avg_frequency_unit": avg_frequency_unit,
        "avg_period": avg_period_value,
        "avg_period_unit": avg_period_unit,
        "avg_vpp": round(avg_vpp, 6),
        "avg_rms": round(avg_rms, 6),
        "enabled": True,
    }


def calculate_advanced_measures(signal, fs):
    signal = _replace_nonfinite(signal)
    empty = {
        "rise_time": 0.0,
        "rise_time_unit": "s",
        "fall_time": 0.0,
        "fall_time_unit": "s",
        "overshoot": 0.0,
        "undershoot": 0.0,
        "slew_rate": 0.0,
        "slew_rate_unit": "V/s",
        "crest_factor": 0.0,
    }
    if signal.size < 2 or fs <= 0:
        return empty

    low_level = float(np.percentile(signal, 5))
    high_level = float(np.percentile(signal, 95))
    amplitude = high_level - low_level
    if abs(amplitude) < 1e-12:
        return empty

    threshold_10 = low_level + 0.1 * amplitude
    threshold_90 = low_level + 0.9 * amplitude

    rising_10 = _crossing_times(signal, fs, threshold_10, "rising")
    rising_90 = _crossing_times(signal, fs, threshold_90, "rising")
    falling_90 = _crossing_times(signal, fs, threshold_90, "falling")
    falling_10 = _crossing_times(signal, fs, threshold_10, "falling")

    rise_candidates = _pair_crossings(rising_10, rising_90)
    fall_candidates = _pair_crossings(falling_90, falling_10)
    rise_time = float(np.mean(rise_candidates)) if rise_candidates else 0.0
    fall_time = float(np.mean(fall_candidates)) if fall_candidates else 0.0
    rise_value, rise_unit = _scale_time_value(rise_time)
    fall_value, fall_unit = _scale_time_value(fall_time)

    max_value = float(np.max(signal))
    min_value = float(np.min(signal))
    overshoot = max(0.0, ((max_value - high_level) / amplitude) * 100)
    undershoot = max(0.0, ((low_level - min_value) / amplitude) * 100)

    derivative = np.gradient(signal, 1 / fs)
    slew_rate = float(np.max(np.abs(derivative))) if derivative.size else 0.0
    rms = _safe_rms(signal)
    crest_factor = (float(np.max(np.abs(signal))) / rms) if rms > 0 else 0.0

    return {
        "rise_time": rise_value,
        "rise_time_unit": rise_unit,
        "fall_time": fall_value,
        "fall_time_unit": fall_unit,
        "overshoot": round(overshoot, 3),
        "undershoot": round(undershoot, 3),
        "slew_rate": round(slew_rate, 3),
        "slew_rate_unit": "V/s",
        "crest_factor": round(crest_factor, 3),
    }


def calculate_derivative_integral(signal, fs):
    signal = _replace_nonfinite(signal)
    if signal.size < 2 or fs <= 0:
        return {
            "derivative": np.array([]),
            "integral": np.array([]),
            "derivative_peak": 0.0,
            "integral_final": 0.0,
        }

    dt = 1 / fs
    derivative = np.gradient(signal, dt)
    trapezoids = (signal[1:] + signal[:-1]) * 0.5 * dt
    integral = np.concatenate(([0.0], np.cumsum(trapezoids)))
    return {
        "derivative": derivative,
        "integral": integral,
        "derivative_peak": round(float(np.max(np.abs(derivative))), 6),
        "integral_final": round(float(integral[-1]), 6),
    }


def calculate_correlation_analysis(ch1, ch2, fs):
    ch1 = _replace_nonfinite(ch1)
    ch2 = _replace_nonfinite(ch2)

    if ch1.size == 0 or ch2.size == 0 or fs <= 0:
        return {
            "lags_seconds": np.array([]),
            "correlation": np.array([]),
            "max_correlation": 0.0,
            "delay_seconds": 0.0,
            "delay_value": 0.0,
            "delay_unit": "s",
        }

    length = min(ch1.size, ch2.size)
    sig1 = ch1[:length] - np.mean(ch1[:length])
    sig2 = ch2[:length] - np.mean(ch2[:length])

    correlation = np.correlate(sig1, sig2, mode="full")
    norm = np.std(sig1) * np.std(sig2) * length
    if norm > 0:
        correlation = correlation / norm

    lags = np.arange(-length + 1, length)
    max_index = int(np.argmax(np.abs(correlation))) if correlation.size else 0
    delay_seconds = float(lags[max_index] / fs) if correlation.size else 0.0
    max_correlation = float(correlation[max_index]) if correlation.size else 0.0
    delay_value, delay_unit = _scale_time_value(abs(delay_seconds))

    return {
        "lags_seconds": lags / fs,
        "correlation": correlation,
        "max_correlation": round(max_correlation, 6),
        "delay_seconds": delay_seconds,
        "delay_value": delay_value,
        "delay_unit": delay_unit,
    }


def calculate_manual_measurement(signal, time_axis, t1, t2):
    signal = _replace_nonfinite(signal)
    time_axis = np.asarray(time_axis, dtype=float)
    empty = {
        "t1": 0.0,
        "t2": 0.0,
        "v1": 0.0,
        "v2": 0.0,
        "delta_t": 0.0,
        "delta_t_unit": "s",
        "delta_v": 0.0,
        "estimated_frequency": 0.0,
        "estimated_frequency_unit": "Hz",
        "enabled": False,
    }
    if signal.size == 0 or time_axis.size == 0 or signal.size != time_axis.size:
        return empty

    start = float(min(t1, t2))
    end = float(max(t1, t2))
    if end == start:
        return empty

    start = max(start, float(time_axis[0]))
    end = min(end, float(time_axis[-1]))
    if end <= start:
        return empty

    v1 = float(np.interp(start, time_axis, signal))
    v2 = float(np.interp(end, time_axis, signal))
    delta_t_seconds = end - start
    delta_t_value, delta_t_unit = _scale_time_value(delta_t_seconds)
    estimated_frequency_hz = 1.0 / delta_t_seconds if delta_t_seconds > 0 else 0.0
    estimated_frequency, estimated_frequency_unit, _ = scale_frequency_value(estimated_frequency_hz)

    return {
        "t1": round(start, 9),
        "t2": round(end, 9),
        "v1": round(v1, 6),
        "v2": round(v2, 6),
        "delta_t": delta_t_value,
        "delta_t_unit": delta_t_unit,
        "delta_v": round(v2 - v1, 6),
        "estimated_frequency": estimated_frequency,
        "estimated_frequency_unit": estimated_frequency_unit,
        "enabled": True,
    }


def convert_scope_data(ch1, ch2, config, measures):
    """
    Convierte datos crudos del osciloscopio a voltajes reales.
    """
    channels = []

    for channel_index, raw in enumerate([ch1, ch2]):
        raw = np.asarray(raw, dtype=float)
        if raw.size == 0:
            channels.append(raw)
            continue
        raw_max, raw_min = raw.max(), raw.min()
        vmax, vmin = measures["Vmax"][channel_index], measures["Vmin"][channel_index]

        if raw_max == raw_min:
            midpoint = (vmax + vmin) / 2
            volts = np.full_like(raw, midpoint * config["probe"][channel_index], dtype=float)
            channels.append(volts)
            continue
        else:
            scale = (vmax - vmin) / (raw_max - raw_min)
            offset = vmax - scale * raw_max

        volts = (scale * raw + offset) * config["probe"][channel_index]
        channels.append(volts)

    return channels[0], channels[1]


def apply_signal_calibration(ch1, ch2, settings):
    settings = settings or {}
    x_gain = float(settings.get("x_gain", 1.0))
    y_gain = float(settings.get("y_gain", 1.0))
    x_offset = float(settings.get("x_offset", 0.0))
    y_offset = float(settings.get("y_offset", 0.0))
    invert_x = bool(settings.get("invert_x"))
    invert_y = bool(settings.get("invert_y"))
    normalize = bool(settings.get("normalize"))

    ch1 = _replace_nonfinite(ch1)
    ch2 = _replace_nonfinite(ch2)

    calibrated_x = ch1 * x_gain + x_offset
    calibrated_y = ch2 * y_gain + y_offset

    if invert_x:
        calibrated_x = -calibrated_x
    if invert_y:
        calibrated_y = -calibrated_y

    if normalize:
        max_x = np.max(np.abs(calibrated_x)) if calibrated_x.size else 0
        max_y = np.max(np.abs(calibrated_y)) if calibrated_y.size else 0
        if max_x > 0:
            calibrated_x = calibrated_x / max_x
        if max_y > 0:
            calibrated_y = calibrated_y / max_y

    return calibrated_x, calibrated_y


def apply_math_operation(ch1, ch2, operation):
    """
    Aplica operacion matematica entre dos canales.
    """
    if ch1 is None or ch2 is None:
        return None

    ch1 = np.asarray(ch1, dtype=float)
    ch2 = np.asarray(ch2, dtype=float)

    if operation == "add":
        return ch1 + ch2
    if operation == "sub":
        return ch1 - ch2
    if operation == "mul":
        return ch1 * ch2
    if operation == "div":
        threshold = max(np.max(np.abs(ch2)) * 1e-9, 1e-12) if ch2.size else 1e-12
        valid = np.abs(ch2) > threshold
        result = np.full(ch1.shape, np.nan, dtype=float)
        np.divide(ch1, ch2, out=result, where=valid)
        return result
    return None


def calculate_math_measures(signal, fs):
    """
    Calcula medidas matematicas sobre la senal MATH.
    """
    signal = _finite_signal(signal)
    if signal.size == 0:
        return {
            "Vmax": 0,
            "Vmin": 0,
            "Vavg": 0,
            "Vrms": 0,
            "Vpp": 0,
            "Vp": 0,
            "Freq": 0,
            "freq_unit": "Hz",
            "Cycle": 0,
            "cycle_unit": "s",
            "Time+": 0,
            "time_plus_unit": "s",
            "Time-": 0,
            "time_minus_unit": "s",
            "Duty+": 0,
            "Duty-": 0,
        }

    vmax = float(np.max(signal))
    vmin = float(np.min(signal))
    vavg = float(np.mean(signal))
    vrms = _safe_rms(signal)
    vpp = vmax - vmin
    vp = max(abs(vmax), abs(vmin))

    freq, freq_unit, freq_multiplier = calculate_frequency(signal, fs)
    freq_hz = freq * freq_multiplier
    period = 1 / freq_hz if freq_hz > 0 else 0
    cycle, cycle_unit = _scale_time_value(period)

    center = (vmax + vmin) / 2
    positive = signal - center > 0
    time_pos, time_neg = _extract_pulse_statistics(positive, fs)
    total_time = time_pos + time_neg
    duty_pos = (time_pos / total_time) * 100 if total_time > 0 else 0
    duty_neg = (time_neg / total_time) * 100 if total_time > 0 else 0
    time_pos_val, time_pos_unit = _scale_time_value(time_pos)
    time_neg_val, time_neg_unit = _scale_time_value(time_neg)

    return {
        "Vmax": round(vmax, 3),
        "Vmin": round(vmin, 3),
        "Vavg": round(vavg, 3),
        "Vrms": round(vrms, 3),
        "Vpp": round(vpp, 3),
        "Vp": round(vp, 3),
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


def butter_lowpass(signal, fs, cutoff_ratio=0.1, order=3):
    """
    Filtro Butterworth lowpass.
    """
    nyq = 0.5 * fs
    cutoff = nyq * cutoff_ratio
    if cutoff <= 0:
        return signal
    b, a = butter(order, cutoff / nyq, btype="low")
    return filtfilt(b, a, signal)


def anti_aliasing_filter(signal, strength=5):
    """
    Filtro suavizado tipo moving average.
    """
    kernel = np.ones(strength) / strength
    return np.convolve(signal, kernel, mode="same")


def detect_signal_type(signal, threshold=0.08):
    """
    Detecta si una senal es digital o analogica para el filtrado adaptativo.
    """
    signal = np.asarray(signal, dtype=float)
    diff = np.abs(np.diff(signal))
    ratio = np.sum(diff > threshold) / max(len(signal), 1)
    skew = np.mean(diff**3) / (np.std(diff)**3 + 1e-12)
    plateau_ratio = _plateau_ratio(signal)
    quantized_levels = _estimate_quantized_levels(signal)
    is_digital = (
        (ratio > 0.04 and plateau_ratio > 0.15 and quantized_levels <= 12)
        or (skew > 2.2 and plateau_ratio > 0.2)
    )
    return "digital" if is_digital else "analog"


def adaptive_scope_filter(signal, fs):
    """
    Aplica filtro adaptativo segun tipo de senal.
    """
    if signal is None or len(signal) < 10 or fs <= 0:
        return signal

    signal = np.asarray(signal, dtype=float)
    signal_type = detect_signal_type(signal)

    if signal_type == "digital":
        filtered = medfilt(signal, kernel_size=3)
        if fs > 500:
            filtered = butter_lowpass(filtered, fs, cutoff_ratio=0.45, order=1)
        return filtered

    peak_to_peak = np.ptp(signal)
    if peak_to_peak > 0.5:
        filtered = butter_lowpass(signal, fs, cutoff_ratio=0.10, order=3)
        filtered = anti_aliasing_filter(filtered, strength=4)
    else:
        filtered = butter_lowpass(signal, fs, cutoff_ratio=0.08, order=4)
        filtered = anti_aliasing_filter(filtered, strength=5)

    return filtered
