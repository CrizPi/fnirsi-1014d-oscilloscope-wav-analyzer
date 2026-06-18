from dataclasses import dataclass


CH1_COLOR = "#ffff00"
CH2_COLOR = "#00e5ff"
MATH_COLOR = "#ff00ff"

CH1_COLOR_LIGHT = "#ffff80"

TRACE_COLOR_TEAL = "#17becf"
TRACE_COLOR_TEAL_LIGHT = "#9edae5"

TRACE_COLOR_ORANGE = "#ff7f0e"
TRACE_COLOR_ORANGE_LIGHT = "#fdae6b"

MARKER_COLOR_YELLOW = "#FFD700"
MARKER_COLOR_RED = "#FF4444"

CHANNEL_COLORS = {
    "X": (1.0, 1.0, 0.0),
    "Y": (0.0, 0.898, 1.0),
    "MATH": (1.0, 0.0, 1.0),
}

CHANNEL_COLORS_STR = {
    "X": CH1_COLOR,
    "Y": CH2_COLOR,
    "MATH": MATH_COLOR,
}

CHANNEL_COLORS_LIGHT = {
    "X": (1.0, 1.0, 0.502),
    "Y": (0.502, 0.941, 1.0),
    "MATH": (1.0, 0.502, 1.0),
}

CHANNEL_COLORS_STR_LIGHT = {
    "X": CH1_COLOR_LIGHT,
    "Y": "#80f0ff",
    "MATH": "#ff80ff",
}


@dataclass
class Channel:
    id: str
    label: str
    color: str

    CH1 = "X"
    CH2 = "Y"
    MATH = "MATH"
