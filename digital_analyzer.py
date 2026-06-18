import numpy as np
from scipy.signal import medfilt


def _to_binary(signal, threshold=None):
    signal = np.asarray(signal, dtype=float)
    if signal.size == 0:
        return np.array([], dtype=int)
    if threshold is None:
        threshold = (float(np.max(signal)) + float(np.min(signal))) / 2.0
    return (signal >= threshold).astype(int)


def _clean_signal(signal):
    signal = np.asarray(signal, dtype=float)
    finite_mask = np.isfinite(signal)
    if not np.all(finite_mask):
        if not np.any(finite_mask):
            return np.zeros_like(signal)
        indices = np.arange(signal.size, dtype=float)
        cleaned = signal.copy()
        cleaned[~finite_mask] = np.interp(indices[~finite_mask], indices[finite_mask], signal[finite_mask])
        signal = cleaned
    if signal.size >= 5:
        signal = medfilt(signal, kernel_size=3)
    return signal


def _estimate_threshold(signal):
    signal = np.asarray(signal, dtype=float)
    if signal.size == 0:
        return 0.0
    return (float(np.max(signal)) + float(np.min(signal))) / 2.0


_LOGIC_FAMILIES = [
    (5.0, 3.5, 1.5, "5V CMOS"),
    (3.3, 2.0, 0.8, "3.3V CMOS/LVTTL"),
    (2.5, 1.7, 0.7, "2.5V CMOS"),
    (1.8, 1.2, 0.6, "1.8V CMOS"),
    (1.2, 0.8, 0.4, "1.2V CMOS"),
]

_TTL_VIH = 2.0
_TTL_VIL = 0.8


def _classify_logic_family(vih, vil, vhigh, vlow):
    for vcc, vih_ref, vil_ref, name in _LOGIC_FAMILIES:
        ratio = vhigh / vcc if vcc > 0 else 0
        if abs(vhigh - vcc) <= 0.75 * vcc or (ratio >= 0.7 and vih <= vih_ref * 1.2 and vil >= vil_ref * 0.8):
            return name
    if vih <= _TTL_VIH * 1.3 and vil >= _TTL_VIL * 0.7:
        return "TTL"
    return "Generic"


def analyze_pwm(signal, fs, threshold=None):
    signal = _clean_signal(signal)
    if signal.size < 4 or fs <= 0:
        return {"frequency_hz": 0.0, "duty_cycle_percent": 0.0, "period_s": 0.0, "pulse_count": 0}

    if threshold is None:
        threshold = _estimate_threshold(signal)

    binary = _to_binary(signal, threshold)
    transitions = np.diff(binary.astype(int))
    rising_indices = np.where(transitions == 1)[0]
    falling_indices = np.where(transitions == -1)[0]
    pulse_count = min(rising_indices.size, falling_indices.size)

    if pulse_count < 1:
        return {"frequency_hz": 0.0, "duty_cycle_percent": float(binary[0] * 100), "period_s": 0.0, "pulse_count": int(binary[0])}

    if rising_indices.size > 0 and falling_indices.size > 0:
        first = min(rising_indices[0], falling_indices[0])
        last = max(rising_indices[-1], falling_indices[-1])
        duration_samples = last - first
        if duration_samples > 0:
            periods_samples = np.diff(rising_indices)
            valid_periods = periods_samples[periods_samples > 0]
            if valid_periods.size > 0:
                avg_period_samples = float(np.mean(valid_periods))
                period_s = avg_period_samples / fs
                frequency_hz = 1.0 / period_s if period_s > 0 else 0.0
            else:
                period_s = duration_samples / fs
                frequency_hz = 1.0 / period_s if period_s > 0 else 0.0
        else:
            period_s = 0.0
            frequency_hz = 0.0

        high_samples = 0
        for r, f in zip(rising_indices, falling_indices):
            if f > r:
                high_samples += f - r
        duty_cycle_percent = (high_samples / duration_samples) * 100.0 if duration_samples > 0 else 0.0
    else:
        frequency_hz = 0.0
        period_s = 0.0
        duty_cycle_percent = 100.0 if binary[0] == 1 else 0.0

    return {
        "frequency_hz": round(frequency_hz, 2),
        "duty_cycle_percent": round(duty_cycle_percent, 1),
        "period_s": round(period_s, 6),
        "pulse_count": int(pulse_count),
    }


def count_pulses(signal, fs):
    signal = _clean_signal(signal)
    if signal.size < 4 or fs <= 0:
        return {"pulse_count": 0, "rising_edges": 0, "falling_edges": 0}

    threshold = _estimate_threshold(signal)
    binary = _to_binary(signal, threshold)
    transitions = np.diff(binary.astype(int))
    rising_edges = int(np.sum(transitions == 1))
    falling_edges = int(np.sum(transitions == -1))
    pulse_count = min(rising_edges, falling_edges)

    return {
        "pulse_count": pulse_count,
        "rising_edges": rising_edges,
        "falling_edges": falling_edges,
    }


def detect_edges(signal, fs):
    signal = _clean_signal(signal)
    if signal.size < 4 or fs <= 0:
        return {"rising_edges": [], "falling_edges": [], "total_edges": 0, "edge_rate_hz": 0.0}

    threshold = _estimate_threshold(signal)
    binary = _to_binary(signal, threshold)
    transitions = np.diff(binary.astype(int))

    rising_indices = np.where(transitions == 1)[0]
    falling_indices = np.where(transitions == -1)[0]

    rising_times = (rising_indices.astype(float) + 0.5) / fs
    falling_times = (falling_indices.astype(float) + 0.5) / fs

    total_edges = int(rising_indices.size + falling_indices.size)
    time_span = (signal.size - 1) / fs if fs > 0 else 1.0
    edge_rate_hz = total_edges / time_span if time_span > 0 else 0.0

    return {
        "rising_edges": rising_times.tolist(),
        "falling_edges": falling_times.tolist(),
        "total_edges": total_edges,
        "edge_rate_hz": round(edge_rate_hz, 1),
    }


def analyze_logic_levels(signal):
    signal = _clean_signal(signal)
    if signal.size < 4:
        return {
            "logic_family": "—",
            "high_level_v": 0.0,
            "low_level_v": 0.0,
            "mid_threshold_v": 0.0,
            "noise_margin_high_v": 0.0,
            "high_percent": 0.0,
        }

    threshold = _estimate_threshold(signal)
    binary = _to_binary(signal, threshold)
    high_mask = binary == 1
    low_mask = binary == 0

    high_samples = signal[high_mask]
    low_samples = signal[low_mask]

    if high_samples.size > 0:
        high_level_v = float(np.median(high_samples))
    else:
        high_level_v = float(np.max(signal))

    if low_samples.size > 0:
        low_level_v = float(np.median(low_samples))
    else:
        low_level_v = float(np.min(signal))

    vih = low_level_v + 0.7 * (high_level_v - low_level_v) if high_level_v > low_level_v else 0.0
    vil = low_level_v + 0.3 * (high_level_v - low_level_v) if high_level_v > low_level_v else 0.0
    mid_threshold_v = (vih + vil) / 2.0
    noise_margin_high_v = high_level_v - vih

    high_percent = float(np.sum(high_mask)) / signal.size * 100.0
    logic_family = _classify_logic_family(vih, vil, high_level_v, low_level_v)

    return {
        "logic_family": logic_family,
        "high_level_v": round(high_level_v, 3),
        "low_level_v": round(low_level_v, 3),
        "mid_threshold_v": round(mid_threshold_v, 3),
        "noise_margin_high_v": round(noise_margin_high_v, 3),
        "high_percent": round(high_percent, 1),
    }
