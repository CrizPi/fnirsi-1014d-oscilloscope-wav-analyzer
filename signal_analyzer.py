import numpy as np

from file_analizer import get_scope_config, get_scope_raw_data_display

def get_scope_fs_and_time(ch1, config, screen_divisions=14):

    N = len(ch1) 
    time_div_s = config["time_div"] * config["time_multiplier"]
    T_total = screen_divisions * time_div_s
    fs = N / T_total
    t = [i / fs for i in range(N)]
    return fs, t


def calculate_frequency(signal, fs):
    signal = np.array(signal)
    Vmax = np.max(signal)
    Vmin = np.min(signal)
    center = (Vmax + Vmin) / 2
    signal_centered = signal - center
    zero_crossings = np.where(np.diff(np.signbit(signal_centered)))[0]

    if len(zero_crossings) < 2:
        return 0 
    periods_samples = np.diff(zero_crossings)

    avg_period_samples = 2 * np.mean(periods_samples)

    freq = fs / avg_period_samples

    if freq >= 1e6:
        freq = freq / 1e6
        unit = "MHz"
        multiplier = 1e6
    elif freq >= 1e3:
        freq = freq / 1e3
        unit = "kHz"
        multiplier = 1e3
    else:
        freq = freq
        unit = "Hz"
        multiplier = 1

    freq = round(freq, 1)

    return freq, unit, multiplier

import numpy as np

def convert_scope_data(ch1, ch2, config, measures):

    channels = [ch1, ch2]
    ch_real = []

    for ch in range(2):

        raw = np.array(channels[ch], dtype=float)

        raw_max = raw.max()
        raw_min = raw.min()

        vmax = measures["Vmax"][ch]
        vmin = measures["Vmin"][ch]

        if raw_max == raw_min:
            a = 1
            b = 0
        else:
            a = (vmax - vmin) / (raw_max - raw_min)
            b = vmax - a * raw_max

        volts = a * raw + b

        volts = volts * config["probe"][ch]

        ch_real.append(volts)

    return ch_real[0], ch_real[1]