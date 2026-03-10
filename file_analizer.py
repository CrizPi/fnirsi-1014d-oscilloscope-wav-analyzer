

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

    # ---------- VOLTAJE ----------
    volts = []
    units = []
    probe = []
    coupling = []

    for ch in range(2):

        v = voltList[header[4 + ch*10]]

        volts.append(v[0])
        units.append(v[1])

        probe.append([1,10,100][header[10 + ch*10]])
        coupling.append(["DC","AC"][header[8 + ch*10]])

    config["volts_div"] = volts
    config["units"] = units
    config["probe"] = probe
    config["coupling"] = coupling

    # ---------- TIEMPO ----------
    t = timeList[header[22]]

    config["time_div"] = t[0]
    config["time_units"] = t[1]
    config["time_multiplier"] = t[2]

    return config


measureList = [
"Vmax","Vmin","Vavg","Vrms","Vpp","Vp",
"Freq","Cycle","Time+","Time-","Duty+","Duty-"
]

def get_scope_measures(file):

    with open(file, "rb") as f:

        f.seek(208)
        m1 = f.read(48)   # CH1

        f.seek(256)
        m2 = f.read(48)   # CH2

    measures_raw = [m1, m2]

    results = {}

    for i, name in enumerate(measureList):

        ch_values = []

        for ch in range(2):

            ad = i * 4

            raw = measures_raw[ch][ad+3]*256 + measures_raw[ch][ad+2]

            # voltajes
            if i < 6:
                value = raw / 1024

            # frecuencia
            elif i == 6:
                value = raw

            # tiempos y ciclo
            else:
                value = raw

            ch_values.append(value)

        results[name] = ch_values

    return results


def get_scope_raw_data(file):

    with open(file, "rb") as f:

        f.seek(1000)
        ch1_raw = f.read(3000)

        f.seek(4000)
        ch2_raw = f.read(3000)

    ch1 = []
    ch2 = []

    for i in range(1500):

        v1 = ch1_raw[i*2] + 256 * ch1_raw[i*2 + 1]
        v2 = ch2_raw[i*2] + 256 * ch2_raw[i*2 + 1]

        ch1.append(v1)
        ch2.append(v2)

    return ch1, ch2

