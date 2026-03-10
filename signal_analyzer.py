def get_scope_fs(ch1, config):

    N = len(ch1)
    time_div_s = config["time_div"] * config["time_multiplier"]
    T_total = 10 * time_div_s
    print(N)
    fs = N / T_total

    return fs