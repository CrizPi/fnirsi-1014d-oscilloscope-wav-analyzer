import base64
import tempfile
from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from typing import Optional, Tuple, Union

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

XY_PLOT_LEFT = 0.138
XY_PLOT_RIGHT = 0.968
XY_PLOT_BOTTOM = 0.16
XY_PLOT_TOP = 0.90


def _apply_aligned_axis_limits(ax, x_values, y_values, symmetric_y=False):
    x_values = np.asarray(x_values if x_values is not None else [], dtype=float)
    y_values = np.asarray(y_values if y_values is not None else [], dtype=float)
    finite_x = x_values[np.isfinite(x_values)]
    finite_y = y_values[np.isfinite(y_values)]

    if finite_x.size > 1:
        x_min = float(np.min(finite_x))
        x_max = float(np.max(finite_x))
        if x_max > x_min:
            ax.set_xlim(x_min, x_max)
            ax.set_xticks(np.linspace(x_min, x_max, 11))

    if finite_y.size == 0:
        return

    if symmetric_y:
        max_abs = float(np.max(np.abs(finite_y)))
        max_abs = max(max_abs, 1e-9) * 1.12
        ax.set_ylim(-max_abs, max_abs)
        ax.set_yticks(np.linspace(-max_abs, max_abs, 9))
        return

    y_min = float(np.min(finite_y))
    y_max = float(np.max(finite_y))
    if y_max == y_min:
        y_max = y_min + 1e-9
    pad = (y_max - y_min) * 0.12
    ax.set_ylim(y_min - pad, y_max + pad)
    ax.set_yticks(np.linspace(y_min - pad, y_max + pad, 9))


class Channel(Enum):
    CH1 = "X"
    CH2 = "Y"
    MATH = "MATH"


@dataclass
class PlotConfig:
    figsize: Tuple[float, float] = (16, 6)
    bg_color: str = "#000000"
    grid_major_color: str = "#919191"
    grid_minor_color: str = "#2B2B2B"
    tick_color: str = "#919191"
    spine_color: str = "#919191"
    center_line_color: str = "#919191"
    grid_major_width: float = 0.6
    grid_minor_width: float = 0.4
    spine_width: float = 1.0
    line_width: float = 2.0
    divisions: int = 8
    dpi: int = 120


class OscilloscopePlotter:
    def __init__(self, config: Optional[PlotConfig] = None):
        self.config = config or PlotConfig()
        self._channel_colors = {
            Channel.CH1: "#ffff00",
            Channel.CH2: "#00e5ff",
            Channel.MATH: "#ff00ff",
        }
        self._light_channel_colors = {
            Channel.CH1: "#0b57d0",
            Channel.CH2: "#b3261e",
            Channel.MATH: "#6a1b9a",
        }

    def _get_channel_colors(self, is_light: bool):
        return self._light_channel_colors if is_light else self._channel_colors

    def _normalize_array(self, array: Optional[Union[list, np.ndarray]]) -> np.ndarray:
        return np.asarray(array if array is not None else [], dtype=float)

    def _is_empty_signal(self, signal: np.ndarray) -> bool:
        return signal.size == 0 or np.all(signal == 0)

    def _safe_range(self, min_val: float, max_val: float) -> Tuple[float, float]:
        if min_val == max_val:
            return min_val, min_val + 1e-9
        return min_val, max_val

    def _safe_max(self, value: float) -> float:
        if value == 0 or np.isnan(value):
            return 1.0
        return value

    def _get_time_scale(self, time_axis: np.ndarray) -> Tuple[np.ndarray, str]:
        if time_axis.size == 0:
            return time_axis, ""

        max_time = np.max(np.abs(time_axis))
        scales = [
            (1e-12, "p"),
            (1e-9, "n"),
            (1e-6, "u"),
            (1e-3, "m"),
            (1, ""),
            (1e3, "k"),
            (1e6, "M"),
        ]

        for factor, prefix in scales:
            if max_time < factor * 1000:
                return time_axis / factor, prefix

        return time_axis, ""

    def _get_configured_time_axis(self, time_axis: np.ndarray, scope_config) -> Tuple[np.ndarray, str, float]:
        if time_axis.size == 0:
            return time_axis, "", 1.0
        if not scope_config:
            time_scaled, prefix = self._get_time_scale(time_axis)
            return time_scaled, f"{prefix}s", 1.0

        unit = str(scope_config.get("time_units", "S"))
        multiplier = float(scope_config.get("time_multiplier", 1.0) or 1.0)
        return time_axis / multiplier, unit, multiplier

    def _setup_axes_style(self, ax, ax2=None, is_light=False):
        if is_light:
            bg_color = "#FFFFFF"
            grid_major = "#C0C0C0"
            grid_minor = "#E6E6E6"
            tick_color = "#000000"
            spine_color = "#000000"
        else:
            bg_color = self.config.bg_color
            grid_major = self.config.grid_major_color
            grid_minor = self.config.grid_minor_color
            tick_color = self.config.tick_color
            spine_color = self.config.spine_color

        fig = ax.get_figure()
        fig.patch.set_facecolor(bg_color)
        ax.set_facecolor(bg_color)

        for spine in ax.spines.values():
            spine.set_color(spine_color)
            spine.set_linewidth(self.config.spine_width)

        ax.grid(True, which="major", color=grid_major, linewidth=self.config.grid_major_width)
        ax.minorticks_on()
        ax.grid(True, which="minor", color=grid_minor, linewidth=self.config.grid_minor_width)
        ax.tick_params(colors=tick_color)

        if ax2 is not None:
            ax2.set_facecolor(bg_color)
            ax2.spines["right"].set_color(spine_color)
            ax2.spines["right"].set_linewidth(self.config.spine_width)
            ax2.tick_params(colors=tick_color)

        return tick_color

    def _setup_time_ticks(self, ax, time_scaled: np.ndarray, scope_config=None):
        if time_scaled.size <= 1:
            return

        if scope_config:
            time_div = float(scope_config.get("time_div", 0) or 0)
            if time_div > 0:
                ticks = np.arange(-7, 8, dtype=float) * time_div
                ax.set_xticks(ticks)
                ax.set_xlim(ticks[0], ticks[-1])
                return

        time_min, time_max = self._safe_range(np.min(time_scaled), np.max(time_scaled))
        ax.set_xticks(np.linspace(time_min, time_max, 19))

    def _setup_voltage_ticks(self, ax, ax2, ch1: np.ndarray, ch2: np.ndarray, math_result: np.ndarray, is_math_only: bool, scope_config=None):
        divisions = self.config.divisions

        if is_math_only:
            max_val = np.max(np.abs(math_result)) if math_result.size else 1
            max_val = self._safe_max(max_val) * 1.2
            step = self._safe_max(max_val / (divisions / 2))
            ticks = np.arange(-divisions / 2, divisions / 2 + 1) * step
            ax.set_ylim(ticks[0], ticks[-1])
            ax.set_yticks(ticks)
            return

        max1 = np.max(np.abs(ch1)) if not self._is_empty_signal(ch1) else 1
        max2 = np.max(np.abs(ch2)) if not self._is_empty_signal(ch2) else 1
        max1 = self._safe_max(max1) * 1.2
        max2 = self._safe_max(max2) * 1.2
        step1 = self._safe_max(max1 / (divisions / 2))
        step2 = self._safe_max(max2 / (divisions / 2))

        ticks1 = np.arange(-divisions / 2, divisions / 2 + 1) * step1
        ticks2 = np.arange(-divisions / 2, divisions / 2 + 1) * step2

        ax.set_ylim(ticks1[0], ticks1[-1])
        ax.set_yticks(ticks1)

        if ax2 is not None:
            ax2.set_ylim(ticks2[0], ticks2[-1])
            ax2.set_yticks(ticks2)

    def _draw_center_lines(self, ax, color: str):
        ax.axhline(0, color=color, linewidth=2)
        ax.axvline(0, color=color, linewidth=2)

    def _plot_channels(
        self,
        ax,
        ax2,
        time_scaled: np.ndarray,
        ch1: np.ndarray,
        ch2: np.ndarray,
        math_result: np.ndarray,
        show_empty: bool,
        is_math_only: bool,
        channel_colors,
    ):
        show_ch1 = not self._is_empty_signal(ch1) or show_empty
        show_ch2 = not self._is_empty_signal(ch2) or show_empty

        if is_math_only:
            ax.plot(
                time_scaled[: len(math_result)],
                math_result,
                color=channel_colors[Channel.MATH],
                linewidth=self.config.line_width,
            )
            return show_ch1, show_ch2

        if show_ch1:
            ax.plot(
                time_scaled[: len(ch1)],
                ch1,
                color=channel_colors[Channel.CH1],
                linewidth=self.config.line_width,
            )
        else:
            ax.plot([], [], color=channel_colors[Channel.CH1], linewidth=self.config.line_width)

        if ax2 is not None:
            if show_ch2:
                ax2.plot(
                    time_scaled[: len(ch2)],
                    ch2,
                    color=channel_colors[Channel.CH2],
                    linewidth=self.config.line_width,
                )
            else:
                ax2.plot([], [], color=channel_colors[Channel.CH2], linewidth=self.config.line_width)

        if math_result.size:
            ax.plot(
                time_scaled[: len(math_result)],
                math_result,
                color=channel_colors[Channel.MATH],
                linewidth=self.config.line_width,
            )

        return show_ch1, show_ch2

    def _add_legend(self, ax, ax2, tick_color: str, background_color: str, border_color: str, channel_colors):
        legend_lines = []
        legend_labels = []

        for channel in (Channel.CH1, Channel.CH2, Channel.MATH):
            color = channel_colors[channel]
            if channel == Channel.CH2 and ax2 is not None:
                line, = ax2.plot([], [], color=color, linewidth=self.config.line_width)
            else:
                line, = ax.plot([], [], color=color, linewidth=self.config.line_width)
            legend_lines.append(line)
            legend_labels.append(channel.value)

        legend = ax.legend(legend_lines, legend_labels, loc="upper right", bbox_to_anchor=(1.0, 1.0), ncol=3)
        plt.setp(legend.get_texts(), color=tick_color)
        legend.get_frame().set_facecolor(background_color)
        legend.get_frame().set_edgecolor(border_color)

    def create_figure(
        self,
        t: Optional[Union[list, np.ndarray]],
        ch1: Optional[Union[list, np.ndarray]],
        ch2: Optional[Union[list, np.ndarray]],
        file_name: str,
        scope_config=None,
        math_result: Optional[Union[list, np.ndarray]] = None,
        show_empty: bool = False,
        is_light: bool = False,
    ):
        time_axis = self._normalize_array(t)
        ch1_data = self._normalize_array(ch1)
        ch2_data = self._normalize_array(ch2)
        math_data = self._normalize_array(math_result)

        is_math_only = math_data.size > 0 and self._is_empty_signal(ch1_data) and self._is_empty_signal(ch2_data)
        time_scaled, time_unit_label, _ = self._get_configured_time_axis(time_axis, scope_config)

        fig, ax = plt.subplots(figsize=self.config.figsize)
        ax2 = None if is_math_only else ax.twinx()
        tick_color = self._setup_axes_style(ax, ax2, is_light=is_light)
        channel_colors = self._get_channel_colors(is_light)
        background_color = "#FFFFFF" if is_light else self.config.bg_color
        border_color = "#000000" if is_light else self.config.spine_color

        ax.set_xlabel(f"Time ({time_unit_label})", color=tick_color)
        if is_math_only:
            ax.set_ylabel("Math Result (V)", color=channel_colors[Channel.MATH])
        else:
            ax.set_ylabel("Voltage X (V)", color=channel_colors[Channel.CH1] if is_light else tick_color)
            if ax2 is not None:
                ax2.set_ylabel("Voltage Y (V)", color=channel_colors[Channel.CH2] if is_light else tick_color)

        self._setup_time_ticks(ax, time_scaled, scope_config=scope_config)
        self._setup_voltage_ticks(ax, ax2, ch1_data, ch2_data, math_data, is_math_only, scope_config=scope_config)
        self._draw_center_lines(ax, "#000000" if is_light else self.config.center_line_color)
        show_ch1, show_ch2 = self._plot_channels(
            ax, ax2, time_scaled, ch1_data, ch2_data, math_data, show_empty, is_math_only, channel_colors
        )

        if not is_math_only and not show_ch1 and not show_ch2 and not show_empty:
            ax.text(
                0.5,
                0.5,
                "No signal loaded",
                color=tick_color,
                fontsize=20,
                ha="center",
                va="center",
                transform=ax.transAxes,
            )

        self._add_legend(ax, ax2, tick_color, background_color, border_color, channel_colors)
        plt.title(file_name, color=tick_color)
        return fig

    def generate_plot_base64(
        self,
        t: Optional[Union[list, np.ndarray]],
        ch1: Optional[Union[list, np.ndarray]],
        ch2: Optional[Union[list, np.ndarray]],
        file_name: str,
        scope_config=None,
        math_result: Optional[Union[list, np.ndarray]] = None,
        show_empty: bool = False,
    ) -> str:
        fig = self.create_figure(t, ch1, ch2, file_name, scope_config=scope_config, math_result=math_result, show_empty=show_empty)
        buffer = BytesIO()
        fig.savefig(buffer, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), dpi=self.config.dpi)
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        plt.close(fig)
        return image_base64

    def generate_plot_file(
        self,
        t: Optional[Union[list, np.ndarray]],
        ch1: Optional[Union[list, np.ndarray]],
        ch2: Optional[Union[list, np.ndarray]],
        file_name: str,
        scope_config=None,
        math_result: Optional[Union[list, np.ndarray]] = None,
        show_empty: bool = False,
    ) -> str:
        fig = self.create_figure(
            t,
            ch1,
            ch2,
            file_name,
            scope_config=scope_config,
            math_result=math_result,
            show_empty=show_empty,
            is_light=True,
        )
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            fig.savefig(tmp_file.name, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), dpi=150)
            temp_path = tmp_file.name
        plt.close(fig)
        return temp_path


def generate_grafic(t, ch1, ch2, file_name, measures=None, scope_config=None, math_result=None, show_empty=False):
    plotter = OscilloscopePlotter()
    return plotter.generate_plot_base64(t, ch1, ch2, file_name, scope_config=scope_config, math_result=math_result, show_empty=show_empty)


def generate_grafic_file(t, ch1, ch2, file_name, measures=None, scope_config=None, math_result=None, show_empty=False):
    plotter = OscilloscopePlotter()
    return plotter.generate_plot_file(t, ch1, ch2, file_name, scope_config=scope_config, math_result=math_result, show_empty=show_empty)


def generate_fft_grafic(
    frequencies_hz,
    magnitudes,
    file_name,
    channel_label,
    scale_mode="linear",
    dominant_frequency_hz=0.0,
):
    frequencies_hz = np.asarray(frequencies_hz if frequencies_hz is not None else [], dtype=float)
    magnitudes = np.asarray(magnitudes if magnitudes is not None else [], dtype=float)

    fig, ax = plt.subplots(figsize=(16, 6))
    fig.patch.set_facecolor("#000000")
    ax.set_facecolor("#000000")

    for spine in ax.spines.values():
        spine.set_color("#919191")
        spine.set_linewidth(1.0)

    ax.grid(True, which="major", color="#919191", linewidth=0.6)
    ax.minorticks_on()
    ax.grid(True, which="minor", color="#2B2B2B", linewidth=0.4)
    ax.tick_params(colors="#919191")

    if frequencies_hz.size and magnitudes.size:
        ax.plot(frequencies_hz, magnitudes, color="#3fb1b1", linewidth=2.0)

        if scale_mode == "log":
            ax.set_yscale("log")
            positive = magnitudes[magnitudes > 0]
            if positive.size:
                ax.set_ylim(bottom=max(np.min(positive) * 0.8, 1e-9))

        if dominant_frequency_hz > 0:
            dominant_index = int(np.argmin(np.abs(frequencies_hz - dominant_frequency_hz)))
            dominant_magnitude = magnitudes[dominant_index]
            ax.scatter([dominant_frequency_hz], [dominant_magnitude], color="#f2e30f", s=50, zorder=3)
            ax.axvline(dominant_frequency_hz, color="#f2e30f", linestyle="--", linewidth=1.2)
    else:
        ax.text(
            0.5,
            0.5,
            "No spectral data available",
            color="#919191",
            fontsize=18,
            ha="center",
            va="center",
            transform=ax.transAxes,
        )

    ax.set_xlabel("Frequency (Hz)", color="#919191")
    ax.set_ylabel("Amplitude (V)", color="#919191")
    plt.title(f"FFT {channel_label}", color="#919191")

    buffer = BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), dpi=120)
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    plt.close(fig)
    return image_base64


def generate_fft_grafic_file(
    frequencies_hz,
    magnitudes,
    file_name,
    channel_label,
    scale_mode="linear",
    dominant_frequency_hz=0.0,
):
    frequencies_hz = np.asarray(frequencies_hz if frequencies_hz is not None else [], dtype=float)
    magnitudes = np.asarray(magnitudes if magnitudes is not None else [], dtype=float)

    fig, ax = plt.subplots(figsize=(16, 6))
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")

    for spine in ax.spines.values():
        spine.set_color("#000000")
        spine.set_linewidth(1.0)

    ax.grid(True, which="major", color="#C0C0C0", linewidth=0.6)
    ax.minorticks_on()
    ax.grid(True, which="minor", color="#E6E6E6", linewidth=0.4)
    ax.tick_params(colors="#000000")

    if frequencies_hz.size and magnitudes.size:
        ax.plot(frequencies_hz, magnitudes, color="#0b57d0", linewidth=2.2)

        if scale_mode == "log":
            ax.set_yscale("log")
            positive = magnitudes[magnitudes > 0]
            if positive.size:
                ax.set_ylim(bottom=max(np.min(positive) * 0.8, 1e-9))

        if dominant_frequency_hz > 0:
            dominant_index = int(np.argmin(np.abs(frequencies_hz - dominant_frequency_hz)))
            dominant_magnitude = magnitudes[dominant_index]
            ax.scatter([dominant_frequency_hz], [dominant_magnitude], color="#b3261e", s=55, zorder=3)
            ax.axvline(dominant_frequency_hz, color="#b3261e", linestyle="--", linewidth=1.2)
    else:
        ax.text(
            0.5,
            0.5,
            "No spectral data available",
            color="#000000",
            fontsize=18,
            ha="center",
            va="center",
            transform=ax.transAxes,
        )

    ax.set_xlabel("Frequency (Hz)", color="#000000")
    ax.set_ylabel("Amplitude (V)", color="#000000")
    plt.title(f"FFT {channel_label}", color="#000000")

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
        fig.savefig(tmp_file.name, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), dpi=150)
        temp_path = tmp_file.name

    plt.close(fig)
    return temp_path


def _generate_xy_plot(
    x_values,
    y_values,
    title,
    x_label,
    y_label,
    line_color,
    bg_color,
    major_grid_color,
    minor_grid_color,
    tick_color,
    message,
    dpi,
    marker_x=None,
    marker_y=None,
    vertical_lines=None,
    point_markers=None,
    vertical_line_color=None,
    point_marker_color=None,
):
    x_values = np.asarray(x_values if x_values is not None else [], dtype=float)
    y_values = np.asarray(y_values if y_values is not None else [], dtype=float)

    fig, ax = plt.subplots(figsize=(16, 6))
    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)
    ax.set_position([XY_PLOT_LEFT, XY_PLOT_BOTTOM, XY_PLOT_RIGHT - XY_PLOT_LEFT, XY_PLOT_TOP - XY_PLOT_BOTTOM])

    for spine in ax.spines.values():
        spine.set_color(tick_color)
        spine.set_linewidth(1.0)

    ax.grid(True, which="major", color=major_grid_color, linewidth=0.6)
    ax.minorticks_on()
    ax.grid(True, which="minor", color=minor_grid_color, linewidth=0.4)
    ax.tick_params(colors=tick_color)

    if x_values.size and y_values.size:
        ax.plot(x_values, y_values, color=line_color, linewidth=2.0)
        _apply_aligned_axis_limits(ax, x_values, y_values, symmetric_y=(np.min(y_values) < 0 < np.max(y_values)))
        if marker_x is not None and marker_y is not None:
            ax.scatter([marker_x], [marker_y], color="#f2e30f" if bg_color == "#000000" else "#b3261e", s=50, zorder=3)
        for line_x in vertical_lines or []:
            ax.axvline(
                line_x,
                color=vertical_line_color or ("#f2e30f" if bg_color == "#000000" else "#b3261e"),
                linestyle="--",
                linewidth=1.2,
            )
        for point_x, point_y in point_markers or []:
            ax.scatter([point_x], [point_y], color=point_marker_color or ("#ff7a00" if bg_color == "#000000" else "#d97706"), s=42, zorder=4)
    else:
        ax.text(0.5, 0.5, message, color=tick_color, fontsize=18, ha="center", va="center", transform=ax.transAxes)

    ax.set_xlabel(x_label, color=tick_color)
    ax.set_ylabel(y_label, color=tick_color)
    plt.title(title, color=tick_color)
    return fig


def generate_signal_analysis_grafic(t, signal, title, y_label):
    fig = _generate_xy_plot(
        t,
        signal,
        title,
        "Time (s)",
        y_label,
        "#3fb1b1",
        "#000000",
        "#919191",
        "#2B2B2B",
        "#919191",
        "No data available",
        120,
    )
    buffer = BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), dpi=120)
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    plt.close(fig)
    return image_base64


def generate_signal_analysis_grafic_file(t, signal, title, y_label):
    fig = _generate_xy_plot(
        t,
        signal,
        title,
        "Time (s)",
        y_label,
        "#0b57d0",
        "#FFFFFF",
        "#C0C0C0",
        "#E6E6E6",
        "#000000",
        "No data available",
        150,
    )
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
        fig.savefig(tmp_file.name, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), dpi=150)
        temp_path = tmp_file.name
    plt.close(fig)
    return temp_path


def _generate_voltage_current_plot(t, voltage, current, title, dpi, is_light=False):
    time_axis = np.asarray(t if t is not None else [], dtype=float)
    voltage = np.asarray(voltage if voltage is not None else [], dtype=float)
    current = np.asarray(current if current is not None else [], dtype=float)

    if is_light:
        bg_color = "#FFFFFF"
        grid_major = "#C0C0C0"
        grid_minor = "#E6E6E6"
        tick_color = "#000000"
        voltage_color = "#0b57d0"
        current_color = "#b3261e"
        border_color = "#000000"
    else:
        bg_color = "#000000"
        grid_major = "#919191"
        grid_minor = "#2B2B2B"
        tick_color = "#919191"
        voltage_color = "#ffff00"
        current_color = "#00e5ff"
        border_color = "#919191"

    fig, ax1 = plt.subplots(figsize=(16, 6), dpi=dpi)
    ax2 = ax1.twinx()
    fig.patch.set_facecolor(bg_color)
    ax1.set_facecolor(bg_color)
    ax2.set_facecolor(bg_color)

    for axis in (ax1, ax2):
        axis.grid(True, which="major", color=grid_major, linewidth=0.6)
        axis.minorticks_on()
        axis.grid(True, which="minor", color=grid_minor, linewidth=0.4)
        axis.tick_params(colors=tick_color)
        for spine in axis.spines.values():
            spine.set_color(tick_color)
            spine.set_linewidth(1.0)

    if time_axis.size and voltage.size and current.size:
        length = min(time_axis.size, voltage.size, current.size)
        ax1.plot(time_axis[:length], voltage[:length], color=voltage_color, linewidth=2.0, label="V")
        ax2.plot(time_axis[:length], current[:length], color=current_color, linewidth=2.0, label="I")
        _apply_aligned_axis_limits(ax1, time_axis[:length], voltage[:length], symmetric_y=True)
        _apply_aligned_axis_limits(ax2, time_axis[:length], current[:length], symmetric_y=True)
    else:
        ax1.text(0.5, 0.5, "No current data available", color=tick_color, fontsize=18, ha="center", va="center", transform=ax1.transAxes)

    ax1.axhline(0, color=tick_color, linewidth=2.0)
    ax1.axvline(0, color=tick_color, linewidth=2.0)

    ax1.set_xlabel("Time (s)", color=tick_color)
    ax1.set_ylabel("V", color=voltage_color if is_light else tick_color)
    ax2.set_ylabel("I", color=current_color if is_light else tick_color)
    ax1.tick_params(axis="y", colors=voltage_color if is_light else tick_color)
    ax2.tick_params(axis="y", colors=current_color if is_light else tick_color)
    plt.title(title, color=tick_color)

    voltage_line = plt.Line2D([], [], color=voltage_color, linewidth=2.0, label="V")
    current_line = plt.Line2D([], [], color=current_color, linewidth=2.0, label="I")
    legend = ax1.legend(
        handles=[voltage_line, current_line],
        loc="upper right",
        bbox_to_anchor=(1.0, 1.0),
        ncol=2,
        frameon=True,
        handlelength=2.6,
        handletextpad=0.6,
        columnspacing=1.8,
    )
    plt.setp(legend.get_texts(), color=tick_color)
    legend.get_frame().set_facecolor(bg_color)
    legend.get_frame().set_edgecolor(border_color)
    return fig


def generate_voltage_current_grafic(t, voltage, current, title):
    fig = _generate_voltage_current_plot(t, voltage, current, title, 120, is_light=False)
    buffer = BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), dpi=120)
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    plt.close(fig)
    return image_base64


def generate_voltage_current_grafic_file(t, voltage, current, title):
    fig = _generate_voltage_current_plot(t, voltage, current, title, 150, is_light=True)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
        fig.savefig(tmp_file.name, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), dpi=150)
        temp_path = tmp_file.name
    plt.close(fig)
    return temp_path


def generate_correlation_grafic(lags_seconds, correlation, title, marker_x=None, marker_y=None):
    fig = _generate_xy_plot(
        lags_seconds,
        correlation,
        title,
        "Lag (s)",
        "Correlation",
        "#3fb1b1",
        "#000000",
        "#919191",
        "#2B2B2B",
        "#919191",
        "No correlation data available",
        120,
        marker_x=marker_x,
        marker_y=marker_y,
    )
    buffer = BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), dpi=120)
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    plt.close(fig)
    return image_base64


def generate_correlation_grafic_file(lags_seconds, correlation, title, marker_x=None, marker_y=None):
    fig = _generate_xy_plot(
        lags_seconds,
        correlation,
        title,
        "Lag (s)",
        "Correlation",
        "#0b57d0",
        "#FFFFFF",
        "#C0C0C0",
        "#E6E6E6",
        "#000000",
        "No correlation data available",
        150,
        marker_x=marker_x,
        marker_y=marker_y,
    )
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
        fig.savefig(tmp_file.name, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), dpi=150)
        temp_path = tmp_file.name
    plt.close(fig)
    return temp_path


def generate_cursor_grafic(t, signal, title, marker_points=None):
    marker_points = marker_points or []
    vertical_lines = [point[0] for point in marker_points]
    fig = _generate_xy_plot(
        t,
        signal,
        title,
        "Time (s)",
        "Voltage (V)",
        "#3fb1b1",
        "#000000",
        "#919191",
        "#2B2B2B",
        "#919191",
        "No cursor data available",
        120,
        vertical_lines=vertical_lines,
        point_markers=marker_points,
        vertical_line_color="#ff8c42",
        point_marker_color="#ff8c42",
    )
    fig.subplots_adjust(left=0.10, right=0.985, bottom=0.16, top=0.90)
    buffer = BytesIO()
    fig.savefig(buffer, format="png", facecolor=fig.get_facecolor(), dpi=120)
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    plt.close(fig)
    return image_base64


def generate_cursor_grafic_file(t, signal, title, marker_points=None):
    marker_points = marker_points or []
    vertical_lines = [point[0] for point in marker_points]
    fig = _generate_xy_plot(
        t,
        signal,
        title,
        "Time (s)",
        "Voltage (V)",
        "#0b57d0",
        "#FFFFFF",
        "#C0C0C0",
        "#E6E6E6",
        "#000000",
        "No cursor data available",
        150,
        vertical_lines=vertical_lines,
        point_markers=marker_points,
        vertical_line_color="#d97706",
        point_marker_color="#d97706",
    )
    fig.subplots_adjust(left=0.10, right=0.985, bottom=0.16, top=0.90)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
        fig.savefig(tmp_file.name, format="png", facecolor=fig.get_facecolor(), dpi=150)
        temp_path = tmp_file.name
    plt.close(fig)
    return temp_path
