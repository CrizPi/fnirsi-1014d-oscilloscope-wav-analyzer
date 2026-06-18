import base64
import tempfile
from dataclasses import dataclass
from io import BytesIO
from typing import Optional, Tuple, Union

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.ticker import MultipleLocator, AutoMinorLocator

from constants import (
    CH1_COLOR_LIGHT,
    CHANNEL_COLORS,
    CHANNEL_COLORS_LIGHT,
    CHANNEL_COLORS_STR,
    CHANNEL_COLORS_STR_LIGHT,
    TRACE_COLOR_TEAL,
    TRACE_COLOR_TEAL_LIGHT,
    TRACE_COLOR_ORANGE,
    TRACE_COLOR_ORANGE_LIGHT,
    MARKER_COLOR_YELLOW,
    MARKER_COLOR_RED,
    Channel,
)

_PLOT_LEFT = 0.10
_PLOT_BOTTOM = 0.14
_PLOT_WIDTH = 0.85
_PLOT_HEIGHT = 0.76
_SQUARE_X_DIVS = 14
_SQUARE_Y_DIVS = 8
_FIG_WIDTH = 16  # Fixed reference width for all charts

# Pre-compute the canonical figure size so every chart uses the same dimensions.
# Formula:
#   cell_size  = (fig_width × PLOT_WIDTH) / 14   → width of one grid division
#   plot_height = cell_size × 8                   → height that makes cells square
#   fig_height  = plot_height / PLOT_HEIGHT       → total figure height
def _square_cell_figsize(fig_width=_FIG_WIDTH):
    """Return (fig_width, fig_height) so that every grid cell is a perfect square.

    The plot area spans _PLOT_WIDTH of the figure width and _PLOT_HEIGHT of the
    figure height.  With 14 horizontal and 8 vertical divisions the cell aspect
    ratio is square when:
        AlturaÁreaGráfico = (AnchoÁreaGráfico / 14) × 8
    """
    plot_width = fig_width * _PLOT_WIDTH          # usable pixel-inches wide
    cell_size  = plot_width / _SQUARE_X_DIVS      # width of one division
    plot_height = cell_size * _SQUARE_Y_DIVS      # height = cell × 8 rows
    fig_height  = plot_height / _PLOT_HEIGHT      # back to figure coordinates
    return (fig_width, fig_height)


# Canonical size used by every chart type for consistency
_SQUARE_FIGSIZE = _square_cell_figsize(_FIG_WIDTH)


def _apply_oscope_style(ax, is_light=False, ax2=None):
    if is_light:
        bg_color = "#FFFFFF"
        grid_major = "#B0B0B0"
        grid_minor = "#D8D8D8"
        tick_color = "#444444"
        spine_color = "#888888"
        center_line_color = "#888888"
    else:
        bg_color = "#0D0D14"
        grid_major = "#555566"
        grid_minor = "#25252E"
        tick_color = "#888899"
        spine_color = "#555566"
        center_line_color = "#6A6A7A"

    fig = ax.get_figure()
    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)
    ax.set_position([0.10, 0.14, 0.85, 0.76])

    for spine in ax.spines.values():
        spine.set_color(spine_color)
        spine.set_linewidth(0.8)

    ax.tick_params(colors=tick_color, labelsize=9)

    if ax2 is not None:
        ax2.set_facecolor(bg_color)
        ax2.spines["right"].set_color(spine_color)
        ax2.spines["right"].set_linewidth(0.8)
        ax2.tick_params(colors=tick_color, labelsize=9)

    return tick_color, bg_color, center_line_color, spine_color, grid_major, grid_minor


def _setup_oscope_grid(ax, grid_major_color, grid_minor_color, x_divs=14, y_divs=8, sub_divs=5, x_label_step=3, y_label_step=2, center_line_color=None, hide_labels=False):
    """Configure oscilloscope-style grid.

    The major tick positions (and therefore the y/x limits) are expected to
    have already been set by _setup_voltage_ticks / _setup_time_ticks so that
    each major division represents exactly one V/Div or s/Div step.  This
    function reads those ticks back rather than recomputing them from the axis
    limits, ensuring the grid lines land precisely on the physical division
    boundaries.
    """
    # Read the tick positions that were set by the axis-setup helpers.
    # fall back to limit-derived positions only when no ticks are available.
    major_xticks = ax.get_xticks()
    major_yticks = ax.get_yticks()

    x_min, x_max = ax.get_xlim()
    y_min, y_max = ax.get_ylim()

    # Guard: if ticks are missing or degenerate, rebuild from limits
    def _rebuild_x():
        x_abs = max(abs(x_min), abs(x_max), 1e-9)
        x_step = x_abs / (x_divs / 2)
        x_half = (x_divs / 2) * x_step
        return np.linspace(-x_half, x_half, x_divs + 1)

    def _rebuild_y():
        y_abs = max(abs(y_min), abs(y_max), 1e-9)
        y_step = y_abs / (y_divs / 2)
        y_half = (y_divs / 2) * y_step
        return np.linspace(-y_half, y_half, y_divs + 1)

    if major_xticks.size < 2:
        major_xticks = _rebuild_x()
    if major_yticks.size < 2:
        major_yticks = _rebuild_y()

    ax.set_xticks(major_xticks)
    ax.set_yticks(major_yticks)
    ax.set_xlim(major_xticks[0], major_xticks[-1])
    ax.set_ylim(major_yticks[0], major_yticks[-1])

    if hide_labels:
        ax.set_xticklabels([])
        ax.set_yticklabels([])
    else:
        x_lbls = [f"{v:.5g}" if i % x_label_step == 0 else "" for i, v in enumerate(major_xticks)]
        y_lbls = [f"{v:.5g}" if i % y_label_step == 0 else "" for i, v in enumerate(major_yticks)]
        ax.set_xticklabels(x_lbls)
        ax.set_yticklabels(y_lbls)

    # Minor ticks: sub_divs sub-divisions per major division
    if major_xticks.size >= 2:
        x_step = float(major_xticks[1] - major_xticks[0])
        ax.xaxis.set_minor_locator(MultipleLocator(x_step / sub_divs))
    if major_yticks.size >= 2:
        y_step = float(major_yticks[1] - major_yticks[0])
        ax.yaxis.set_minor_locator(MultipleLocator(y_step / sub_divs))

    ax.grid(True, which="major", color=grid_major_color, linewidth=0.5)
    ax.grid(True, which="minor", color=grid_minor_color, linewidth=0.2)

    if center_line_color is not None:
        ax.axhline(0, color=center_line_color, linewidth=1.5, linestyle="-", zorder=2.0)
        ax.axvline(0, color=center_line_color, linewidth=1.5, linestyle="-", zorder=2.0)


def _set_oscope_title(ax, title, color):
    pass


# Block-based header constants
# These values work for fontsize 9.5 in a 16-inch figure (figure-normalised coords).
_BCHAR_W = 0.0055    # average character width
_BSWATCH_W = 0.010   # ● swatch width
_BSPACE_W = 0.003    # single space width
_BGAP = 0.008        # gap between blocks
_BTIME_GAP = 0.003   # total extra gap around Time separator (split equally)


def _render_header(fig, title, items, is_light):
    """Render header with compact block-based layout.

    Each channel is rendered as a single visual block:
      ● CH1 500 mV/Div

    Blocks are built left-to-right from the right edge using left-aligned
    text, so the swatch is always immediately adjacent to the channel info.
    This replicates the CSS flexbox model used in the UI (.graph-label).
    """
    tc = "#000000" if is_light else "#888899"

    header_y0 = _PLOT_BOTTOM + _PLOT_HEIGHT
    header_cy = header_y0 + 0.018

    # Title aligned left
    fig.text(
        _PLOT_LEFT, header_cy, title,
        fontsize=12, fontweight="bold",
        ha="left", va="center",
        color=tc, transform=fig.transFigure, zorder=10,
    )

    # ── Estimate total width of all blocks ─────────────────────────────────
    # This lets us render left-to-right from the correct starting position.
    # total_w includes every gap (inter-block, Time-separator, and trailing)
    # so that start_x + total_w == right margin exactly.
    total_w = 0.0
    for item in items:
        txt = item.get("text", "")
        if not txt:
            continue
        if item.get("color"):
            total_w += _BSWATCH_W + _BSPACE_W + len(txt) * _BCHAR_W + _BGAP
        else:
            block_w = len(txt) * _BCHAR_W + _BGAP
            if txt.startswith("Time"):
                block_w += _BTIME_GAP   # space for the vertical bar
            total_w += block_w

    # ── Render blocks left-to-right ────────────────────────────────────────
    x = 1.0 - _PLOT_LEFT - total_w  # left edge of first block
    for item in items:
        txt = item.get("text", "")
        color = item.get("color")
        if not txt:
            continue

        # ── Time separator ─────────────────────────────────────────────────
        if txt.startswith("Time"):
            x += _BTIME_GAP * 0.5
            _sep = Line2D(
                [x, x], [header_cy - 0.025, header_cy + 0.025],
                color="#c0c0c0", linewidth=0.8,
                transform=fig.transFigure, zorder=10,
            )
            fig.add_artist(_sep)
            x += _BTIME_GAP * 0.5

        if color:
            # --- Single visual block: ● CH1 50 mV/Div ---
            # Swatch (left-aligned) immediately followed by channel text (left-aligned)
            fig.text(
                x, header_cy, "●",
                fontsize=9.5, ha="left", va="center",
                color=color, transform=fig.transFigure, zorder=10,
            )
            x += _BSWATCH_W + _BSPACE_W
            fig.text(
                x, header_cy, txt,
                fontsize=9.5, ha="left", va="center",
                color=tc, transform=fig.transFigure, zorder=10,
            )
            x += len(txt) * _BCHAR_W + _BGAP
        else:
            fig.text(
                x, header_cy, txt,
                fontsize=9.5, ha="left", va="center",
                color=tc, transform=fig.transFigure, zorder=10,
            )
            x += len(txt) * _BCHAR_W + _BGAP


def _render_download_header(fig, title, items, is_light=True):
    if not is_light:
        return
    _render_header(fig, title, items, is_light)


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


# ---------------------------------------------------------------------------
# Scale formatting helpers
# ---------------------------------------------------------------------------

def _fmt_value(value: float, unit: str) -> str:
    """Format a scale value with the given unit label, e.g. '500 mV/Div'."""
    return f"{value:g} {unit}/Div"


def _fmt_vdiv(value_v: float) -> str:
    """Auto-range a voltage-per-division value to V / mV / µV."""
    if value_v >= 1.0:
        return f"{value_v:.3g} V/Div"
    elif value_v >= 1e-3:
        return f"{value_v * 1e3:.3g} mV/Div"
    else:
        return f"{value_v * 1e6:.3g} µV/Div"


def _fmt_adiv(value_a: float) -> str:
    """Auto-range a current-per-division value to A / mA / µA."""
    if value_a >= 1.0:
        return f"{value_a:.3g} A/Div"
    elif value_a >= 1e-3:
        return f"{value_a * 1e3:.3g} mA/Div"
    else:
        return f"{value_a * 1e6:.3g} µA/Div"


def _fmt_tdiv(value_s: float) -> str:
    """Auto-range a time-per-division value to s / ms / µs / ns."""
    if value_s >= 1.0:
        return f"{value_s:.3g} s/Div"
    elif value_s >= 1e-3:
        return f"{value_s * 1e3:.3g} ms/Div"
    elif value_s >= 1e-6:
        return f"{value_s * 1e6:.3g} µs/Div"
    else:
        return f"{value_s * 1e9:.3g} ns/Div"


def _compute_vdiv_from_data(signal: np.ndarray, divisions: int = 8) -> float:
    """Estimate V/Div from the peak amplitude of a signal array."""
    if signal.size == 0 or np.all(signal == 0):
        return 1.0
    peak = float(np.max(np.abs(signal[np.isfinite(signal)])))
    if peak == 0:
        return 1.0
    return (peak * 1.2) / (divisions / 2)


# ---------------------------------------------------------------------------
# Status-bar typography — one source of truth for the top legend row.
# Every element (CH1, CH2, MATH, V/Div, s/Div) must use these values so
# the bar reads as a single visual unit with uniform hierarchy.
# ---------------------------------------------------------------------------
_STATUS_FONTSIZE   = 12      # pt — same for all status-bar labels
_STATUS_FONTWEIGHT = "normal"  # weight — uniform across channels and time base
_STATUS_ALPHA      = 1.0     # opacity — no dimming; every label is equally important
_STATUS_LINEWIDTH  = 3.5     # pt — colour-swatch line thickness in legend


@dataclass
class PlotConfig:
    figsize: Tuple[float, float] = _SQUARE_FIGSIZE
    bg_color: str = "#0D0D14"
    grid_major_color: str = "#555566"
    grid_minor_color: str = "#25252E"
    tick_color: str = "#888899"
    spine_color: str = "#555566"
    center_line_color: str = "#6A6A7A"
    grid_major_width: float = 0.5
    grid_minor_width: float = 0.25
    spine_width: float = 0.8
    line_width: float = 1.8
    divisions: int = 8
    dpi: int = 120


class OscilloscopePlotter:
    def __init__(self, config: Optional[PlotConfig] = None):
        self.config = config or PlotConfig()
        self._channel_colors = CHANNEL_COLORS
        self._light_channel_colors = CHANNEL_COLORS_LIGHT
        self.ch1_name = "CH1"
        self.ch2_name = "CH2"

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
        tick_color, bg_color, center_line_color, _, grid_major, grid_minor = _apply_oscope_style(ax, is_light=is_light, ax2=ax2)
        self._scope_center_line_color = center_line_color
        self._scope_grid_major = grid_major
        self._scope_grid_minor = grid_minor
        return tick_color

    def _setup_time_ticks(self, ax, time_scaled: np.ndarray, scope_config=None):
        """Set x-axis ticks so each division equals exactly one s/Div unit.

        time_scaled is already expressed in display units (i.e. divided by
        time_multiplier in _get_configured_time_axis).  The stored time_div
        value is the numeric part in those same display units (e.g. 1 for
        "1 mS" when multiplier=1e-3).  So we just use time_div directly as
        the per-division step and place 14 divisions centred on zero.
        """
        if time_scaled.size <= 1:
            return

        if scope_config:
            # time_div is the numeric value in display units (e.g. 1 mS → 1,
            # because the axis is already scaled to milliseconds).
            time_div = float(scope_config.get("time_div", 0) or 0)
            if time_div > 0:
                # 14 horizontal divisions: -7 … +7
                ticks = np.arange(-7, 8, dtype=float) * time_div
                ax.set_xticks(ticks)
                ax.set_xlim(ticks[0], ticks[-1])
                return

        # Fallback: 14 divisions centred on zero, spanning the data
        max_abs = max(abs(float(np.min(time_scaled))), abs(float(np.max(time_scaled))), 1e-9)
        ticks = np.linspace(-max_abs, max_abs, _SQUARE_X_DIVS + 1)
        ax.set_xticks(ticks)
        ax.set_xlim(ticks[0], ticks[-1])

    def _setup_voltage_ticks(self, ax, ax2, ch1: np.ndarray, ch2: np.ndarray, math_result: np.ndarray, is_math_only: bool, scope_config=None):
        """Set y-axis ticks symmetric around zero so the origin (0 V) is at the
        vertical centre of the plot.

        When scope_config provides volts_div values those are used to create
        8 divisions (4 up, 4 down) centred on zero — matching real oscilloscope
        behaviour.  Without scope_config the range is derived from the signal's
        peak absolute value, still symmetric around zero.
        """
        divisions = self.config.divisions  # 8

        def _symmetric_ticks(sig: np.ndarray, vdiv: float = 0, margin: float = 0.10):
            if vdiv > 0:
                half_range = (divisions / 2) * vdiv
                return np.linspace(-half_range, half_range, divisions + 1)
            if sig.size == 0 or np.all(sig == 0):
                return np.linspace(-1.0, 1.0, divisions + 1)
            valid = sig[np.isfinite(sig)]
            if valid.size == 0:
                return np.linspace(-1.0, 1.0, divisions + 1)
            max_abs = max(abs(float(np.min(valid))), abs(float(np.max(valid))))
            max_abs = max(max_abs, 1e-9) * (1 + margin)
            return np.linspace(-max_abs, max_abs, divisions + 1)

        if scope_config:
            volts_div = scope_config.get("volts_div", [])
            volt_mult = scope_config.get("volt_multiplier", [1, 1])

        if is_math_only:
            vdiv = 0
            if scope_config:
                pass  # no volts_div for MATH; fall through to data-derived
            ticks = _symmetric_ticks(math_result, vdiv)
            ax.set_ylim(ticks[0], ticks[-1])
            ax.set_yticks(ticks)
            return

        if scope_config and len(volts_div) > 0:
            ch1_vdiv = float(volts_div[0]) * float(volt_mult[0]) if volts_div[0] else 0
            ticks1 = _symmetric_ticks(ch1, ch1_vdiv)
        else:
            ticks1 = _symmetric_ticks(ch1, 0)
        ax.set_ylim(ticks1[0], ticks1[-1])
        ax.set_yticks(ticks1)

        if ax2 is not None:
            if scope_config and len(volts_div) > 1:
                ch2_vdiv = float(volts_div[1]) * float(volt_mult[1]) if volts_div[1] else 0
                ticks2 = _symmetric_ticks(ch2, ch2_vdiv)
            else:
                ticks2 = _symmetric_ticks(ch2, 0)
            ax2.set_ylim(ticks2[0], ticks2[-1])
            ax2.set_yticks(ticks2)

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

    def _add_legend(self, ax, ax2, tick_color, background_color, border_color, channel_colors,
                    show_ch1=False, show_ch2=False, show_math=False,
                    ch1_vdiv: str = "", ch2_vdiv: str = "", math_vdiv: str = "",
                    tdiv: str = ""):
        """Render the oscilloscope status-bar legend.

        Layout (example):  ── CH1  500 mV/Div    ── CH2  1.00 V/Div    Time  1 ms/Div

        Typography is governed by the module-level _STATUS_* constants so that
        every element — channel names, V/Div values, and the time base — shares
        exactly the same font size, weight, and opacity.  The channel colour
        swatch is the only visual differentiator between entries.
        """
        pass

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
        bg_style, border_style = ("#FFFFFF", "#000000") if is_light else (self.config.bg_color, self.config.spine_color)
        background_color, border_color = bg_style, border_style

        # --- Compute scale labels for the status-bar legend -------------------
        if scope_config:
            volts_div = scope_config.get("volts_div", [])
            volt_mult = scope_config.get("volt_multiplier", [1, 1])
            ch1_vdiv_raw = float(volts_div[0]) if len(volts_div) > 0 else None
            ch2_vdiv_raw = float(volts_div[1]) if len(volts_div) > 1 else None
            ch1_vdiv_str = _fmt_vdiv(ch1_vdiv_raw * float(volt_mult[0])) if ch1_vdiv_raw is not None else ""
            ch2_vdiv_str = _fmt_vdiv(ch2_vdiv_raw * float(volt_mult[1])) if ch2_vdiv_raw is not None else ""
            time_div_raw = float(scope_config.get("time_div", 0) or 0)
            time_mult = float(scope_config.get("time_multiplier", 1))
            tdiv_str = _fmt_tdiv(time_div_raw * time_mult) if time_div_raw > 0 else ""
        else:
            # Fall back to deriving scale from the data itself
            ch1_vdiv_str = _fmt_vdiv(_compute_vdiv_from_data(ch1_data, self.config.divisions)) if not self._is_empty_signal(ch1_data) else ""
            ch2_vdiv_str = _fmt_vdiv(_compute_vdiv_from_data(ch2_data, self.config.divisions)) if not self._is_empty_signal(ch2_data) else ""
            math_vdiv_str = _fmt_vdiv(_compute_vdiv_from_data(math_data, self.config.divisions)) if math_data.size > 0 else ""
            if time_scaled.size > 1:
                total_span = float(np.max(time_scaled) - np.min(time_scaled))
                tdiv_str = _fmt_tdiv(total_span / _SQUARE_X_DIVS) if total_span > 0 else ""
            else:
                tdiv_str = ""

        if scope_config:
            math_vdiv_str = _fmt_vdiv(_compute_vdiv_from_data(math_data, self.config.divisions)) if math_data.size > 0 else ""

        # --- Suppress numeric X tick labels (time shown in status-bar legend) --
        ax.set_xticklabels([])
        ax.set_xlabel("")
        ax.set_ylabel("")
        if ax2 is not None:
            ax2.set_ylabel("")

        # --- Build ticks (grid positions) -------------------------------------
        self._setup_time_ticks(ax, time_scaled, scope_config=scope_config)
        self._setup_voltage_ticks(ax, ax2, ch1_data, ch2_data, math_data, is_math_only, scope_config=scope_config)

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

        has_math = math_data.size > 0

        _header_items = []
        if not is_math_only and show_ch1:
            label = self.ch1_name
            if ch1_vdiv_str:
                label += f" {ch1_vdiv_str}"
            _header_items.append({"text": label, "color": channel_colors[Channel.CH1]})
        if not is_math_only and show_ch2:
            label = self.ch2_name
            if ch2_vdiv_str:
                label += f" {ch2_vdiv_str}"
            _header_items.append({"text": label, "color": channel_colors[Channel.CH2]})
        if has_math:
            label = "MATH"
            if math_vdiv_str:
                label += f" {math_vdiv_str}"
            _header_items.append({"text": label, "color": channel_colors[Channel.MATH]})
        if tdiv_str:
            _header_items.append({"text": f"Time {tdiv_str}"})

        if is_light:
            _render_download_header(fig, file_name, _header_items, is_light=True)
        # Dark mode (UI): header is rendered as external HTML element above the graph.
        # No in-figure header is drawn so the canvas shows only the oscilloscope grid and traces.
        _setup_oscope_grid(ax, self._scope_grid_major, self._scope_grid_minor, center_line_color=self._scope_center_line_color, hide_labels=True)
        # ax2 (twinx) gets its Y-limits and Y-ticks from _setup_voltage_ticks.
        # Do NOT apply _setup_oscope_grid on ax2 — it would draw a second set of
        # horizontal grid lines at CH2's V/Div spacing, overlapping CH1's grid
        # and making it appear that traces span the wrong number of divisions.

        # Restore X-label suppression (grid setup may re-enable them).
        # Las etiquetas numéricas de los ejes Y (izquierdo CH1 y derecho CH2)
        # se ocultan para reducir el ruido visual; la escala interna no se altera.
        ax.set_xticklabels([])
        ax.set_yticklabels([])
        if ax2 is not None:
            ax2.set_yticklabels([])

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


def generate_grafic(t, ch1, ch2, file_name, measures=None, scope_config=None, math_result=None, show_empty=False, ch1_name="CH1", ch2_name="CH2"):
    plotter = OscilloscopePlotter()
    plotter.ch1_name = ch1_name
    plotter.ch2_name = ch2_name
    return plotter.generate_plot_base64(t, ch1, ch2, file_name, scope_config=scope_config, math_result=math_result, show_empty=show_empty)


def generate_grafic_file(t, ch1, ch2, file_name, measures=None, scope_config=None, math_result=None, show_empty=False, ch1_name="CH1", ch2_name="CH2"):
    plotter = OscilloscopePlotter()
    plotter.ch1_name = ch1_name
    plotter.ch2_name = ch2_name
    return plotter.generate_plot_file(t, ch1, ch2, file_name, scope_config=scope_config, math_result=math_result, show_empty=show_empty)



# ---------------------------------------------------------------------------
# _build_secondary_figure — base única para todas las gráficas secundarias.
#
# Replica exactamente el patrón visual del OscilloscopePlotter.create_figure:
#   • Mismo contenedor (_SQUARE_FIGSIZE, posición del plot area)
#   • Cuadrícula 14×8 con celdas perfectamente cuadradas
#   • Origen (0,0) centrado mediante ticks simétricos
#   • Sin etiquetas numéricas, sin nombres de ejes, sin leyendas internas
#   • Header superior idéntico al de la gráfica principal (oscuro: vía
#     _set_oscope_title / claro: vía _render_download_header)
# ---------------------------------------------------------------------------

def _build_secondary_figure(
    x_data,
    y_data,
    title,
    header_items,
    trace_color_dark,
    trace_color_light,
    is_light,
    dpi,
    empty_message="No data available",
    extra_artists_fn=None,
    ax2_data=None,
    ax2_color_dark=None,
    ax2_color_light=None,
    ax2_unit="V",
    return_scale_info=False,
    suppress_auto_scale_labels=False,
):
    """Construye una figura secundaria con el estilo unificado de la gráfica principal.

    Parámetros
    ----------
    x_data, y_data        : arrays de datos para el trazo principal.
    title                 : texto del header (nombre del panel).
    header_items          : lista de dicts {text, color?} con indicadores de canal/escala.
                            Los valores V/div y s/div se calculan automáticamente y se
                            añaden al final del header — no es necesario incluirlos aquí.
    trace_color_dark/light: color del trazo en modo oscuro/claro.
    is_light              : True → modo claro (exportación), False → modo oscuro (UI).
    dpi                   : resolución de renderizado.
    empty_message         : texto cuando no hay datos.
    extra_artists_fn      : callable(ax, tick_color, is_light) para marcadores adicionales.
    ax2_data              : señal opcional en eje derecho (twinx).
    ax2_color_*           : color del trazo ax2 en cada modo.
    """
    x = np.asarray(x_data if x_data is not None else [], dtype=float)
    y = np.asarray(y_data if y_data is not None else [], dtype=float)

    # ── Figura y estilo base (idéntico al OscilloscopePlotter) ────────────────
    fig, ax = plt.subplots(figsize=_SQUARE_FIGSIZE, dpi=dpi)
    ax2 = ax.twinx() if ax2_data is not None else None
    tick_color, bg_color, center_line_color, _, grid_major, grid_minor = _apply_oscope_style(
        ax, is_light=is_light, ax2=ax2
    )

    # ── Trazado de datos ──────────────────────────────────────────────────────
    trace_color = trace_color_light if is_light else trace_color_dark
    has_data = x.size > 0 and y.size > 0

    # Valores de escala calculados desde los datos reales (para el header)
    vdiv_str   = ""   # V/div del eje Y principal
    vdiv2_str  = ""   # V/div del eje Y secundario (twinx)
    tdiv_str   = ""   # s/div del eje X

    if has_data:
        length = min(x.size, y.size)
        ax.plot(x[:length], y[:length], color=trace_color, linewidth=1.8)

        if ax2 is not None and ax2_data is not None:
            y2 = np.asarray(ax2_data, dtype=float)
            ax2_color = ax2_color_light if is_light else ax2_color_dark
            length2 = min(x.size, y2.size)
            ax2.plot(x[:length2], y2[:length2], color=ax2_color, linewidth=1.8)

        # ── Escala simétrica alrededor de (0,0) ───────────────────────────────
        # Eje X: 14 divisiones centradas en 0
        finite_x = x[np.isfinite(x)]
        if finite_x.size > 1:
            x_abs = max(abs(float(np.min(finite_x))), abs(float(np.max(finite_x))), 1e-9)
            x_step = x_abs / (_SQUARE_X_DIVS / 2)
            x_half = (_SQUARE_X_DIVS / 2) * x_step
            xticks = np.linspace(-x_half, x_half, _SQUARE_X_DIVS + 1)
            ax.set_xticks(xticks)
            ax.set_xlim(xticks[0], xticks[-1])
            # s/div: paso entre divisiones consecutivas
            tdiv_str = _fmt_tdiv(float(x_step))

        # Eje Y principal: 8 divisiones centradas en 0
        finite_y = y[np.isfinite(y)]
        if finite_y.size > 0:
            y_abs = max(abs(float(np.min(finite_y))), abs(float(np.max(finite_y))), 1e-9)
            y_abs *= 1.10  # margen igual al de la gráfica principal
            yticks = np.linspace(-y_abs, y_abs, _SQUARE_Y_DIVS + 1)
            ax.set_yticks(yticks)
            ax.set_ylim(yticks[0], yticks[-1])
            # V/div: paso entre divisiones verticales consecutivas
            vdiv_str = _fmt_vdiv(float(y_abs * 2) / _SQUARE_Y_DIVS)

        # Eje Y secundario (twinx)
        if ax2 is not None and ax2_data is not None:
            y2 = np.asarray(ax2_data, dtype=float)
            finite_y2 = y2[np.isfinite(y2)]
            if finite_y2.size > 0:
                y2_abs = max(abs(float(np.min(finite_y2))), abs(float(np.max(finite_y2))), 1e-9)
                y2_abs *= 1.10
                yticks2 = np.linspace(-y2_abs, y2_abs, _SQUARE_Y_DIVS + 1)
                ax2.set_yticks(yticks2)
                ax2.set_ylim(yticks2[0], yticks2[-1])
                _fmt_ax2 = _fmt_adiv if ax2_unit == "A" else _fmt_vdiv
                vdiv2_str = _fmt_ax2(float(y2_abs * 2) / _SQUARE_Y_DIVS)

        # Artistas adicionales (marcadores, líneas verticales, scatter…)
        if extra_artists_fn is not None:
            extra_artists_fn(ax, tick_color, is_light)

    else:
        ax.text(
            0.5, 0.5, empty_message,
            color=tick_color, fontsize=16,
            ha="center", va="center",
            transform=ax.transAxes,
        )

    # ── Cuadrícula 14×8 idéntica a la gráfica principal ──────────────────────
    _setup_oscope_grid(
        ax, grid_major, grid_minor,
        x_divs=_SQUARE_X_DIVS, y_divs=_SQUARE_Y_DIVS,
        center_line_color=center_line_color,
        hide_labels=True,
    )

    # ── Eliminar todas las etiquetas de ejes ──────────────────────────────────
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_xticklabels([])
    ax.set_yticklabels([])
    if ax2 is not None:
        ax2.set_ylabel("")
        ax2.set_yticklabels([])

    # ── Construir header con V/div y s/div calculados ─────────────────────────
    # Cada V/div se fusiona con el último item coloreado (canal) para formar
    # un bloque compacto como en la gráfica principal: "● V 500 mV/Div".
    # Los items sin color y Time/Div se añaden como items independientes.
    full_header = list(header_items or [])
    if not suppress_auto_scale_labels:
        vdiv_pool = [s for s in [vdiv_str, vdiv2_str] if s]
        vdiv_idx = 0
        merged = []
        for item in full_header:
            if item.get("color") and vdiv_idx < len(vdiv_pool):
                merged.append({"text": f"{item['text']} {vdiv_pool[vdiv_idx]}", "color": item["color"]})
                vdiv_idx += 1
            else:
                merged.append(item)
        for v in vdiv_pool[vdiv_idx:]:
            merged.append({"text": v})
        full_header = merged
        if tdiv_str:
            full_header.append({"text": f"Time {tdiv_str}"})

    # ── Renderizar header solo en modo claro (exportación) ───────────────────
    # En modo oscuro (UI) el header se renderiza como elemento HTML externo,
    # por lo que no se incluye dentro del canvas de matplotlib.
    if is_light:
        _render_header(fig, title, full_header, is_light=True)

    if return_scale_info:
        return fig, vdiv_str, vdiv2_str, tdiv_str
    return fig


# ---------------------------------------------------------------------------
# FFT
# ---------------------------------------------------------------------------
# The FFT graph has fundamentally different axis semantics from time-domain
# graphs: X is frequency (starts at 0, always positive), Y is spectral
# magnitude (starts at 0 for linear scale).  A dedicated builder is used
# instead of _build_secondary_figure so that:
#   • Axes are single-quadrant (origin at bottom-left, not centre).
#   • X ticks show formatted frequency labels (Hz / kHz / MHz) for readability.
#   • Y ticks show magnitude with appropriate units.
#   • Scale strings reported to the caller use Hz/Div and magnitude/Div
#     instead of the time-domain V/Div and s/Div nomenclature.
#   • The oscilloscope-style centre lines (axhline/axvline at 0) are omitted.
# ---------------------------------------------------------------------------

_FFT_X_DIVS = 10   # number of horizontal frequency divisions
_FFT_Y_DIVS = 8    # number of vertical magnitude divisions

# FFT-specific figure geometry — wider canvas gives more frequency resolution
# on screen; extra left margin makes room for the magnitude axis labels.
_FFT_FIG_WIDTH   = 16
_FFT_PLOT_LEFT   = 0.10
_FFT_PLOT_BOTTOM = 0.13
_FFT_PLOT_WIDTH  = 0.84
_FFT_PLOT_HEIGHT = 0.73

def _fft_figsize(fig_width=_FFT_FIG_WIDTH):
    """Return a figure size whose plot area has 10:5 (2:1) cell aspect ratio,
    optimised for frequency-domain data that reads naturally as a landscape
    spectrum."""
    plot_w = fig_width * _FFT_PLOT_WIDTH
    cell_w = plot_w / _FFT_X_DIVS
    plot_h = cell_w * (_FFT_Y_DIVS / 2.0)   # 2:1 cell aspect -> spectrum shape
    fig_h  = plot_h / _FFT_PLOT_HEIGHT
    return (fig_width, fig_h)

_FFT_FIGSIZE = _fft_figsize()


def _fmt_freq_div(hz_per_div: float) -> str:
    """Auto-range a frequency-per-division value to Hz / kHz / MHz."""
    if hz_per_div >= 1e6:
        return f"{hz_per_div / 1e6:.3g} MHz/Div"
    elif hz_per_div >= 1e3:
        return f"{hz_per_div / 1e3:.3g} kHz/Div"
    else:
        return f"{hz_per_div:.3g} Hz/Div"


def _fmt_mag_div(mag_per_div: float) -> str:
    """Auto-range a magnitude-per-division value to V / mV / µV."""
    if mag_per_div >= 1.0:
        return f"{mag_per_div:.3g} V/Div"
    elif mag_per_div >= 1e-3:
        return f"{mag_per_div * 1e3:.3g} mV/Div"
    else:
        return f"{mag_per_div * 1e6:.3g} µV/Div"


def _fmt_freq_label(hz: float) -> str:
    """Compact frequency label for axis ticks."""
    if hz == 0:
        return "0"
    if hz >= 1e6:
        v = hz / 1e6
        return f"{v:.3g}M"
    if hz >= 1e3:
        v = hz / 1e3
        return f"{v:.3g}k"
    return f"{hz:.3g}"


def _build_fft_figure(
    frequencies_hz: np.ndarray,
    magnitudes: np.ndarray,
    channel_label: str,
    scale_mode: str,
    dominant_frequency_hz: float,
    is_light: bool,
    dpi: int,
    max_frequency_hz: float | None = None,
):
    """Build a frequency-domain figure optimised for FFT spectra.

    Returns
    -------
    fig            : matplotlib Figure
    hz_div_str     : formatted Hz/Div string for the HTML header (e.g. "1 kHz/Div")
    mag_div_str    : formatted Magnitude/Div string for the HTML header
    """
    # ── Determine trace colour from channel label ────────────────────────────
    _ch_key = channel_label.upper() if channel_label else ""
    if _ch_key in ("X", "CH1", "1"):
        trace_color = CHANNEL_COLORS_STR["X"] if not is_light else CHANNEL_COLORS_STR_LIGHT["X"]
    elif _ch_key in ("Y", "CH2", "2"):
        trace_color = CHANNEL_COLORS_STR["Y"] if not is_light else CHANNEL_COLORS_STR_LIGHT["Y"]
    elif _ch_key == "MATH":
        trace_color = CHANNEL_COLORS_STR["MATH"] if not is_light else CHANNEL_COLORS_STR_LIGHT["MATH"]
    else:
        trace_color = TRACE_COLOR_TEAL if not is_light else TRACE_COLOR_TEAL_LIGHT

    # ── Theme colours ────────────────────────────────────────────────────────
    if is_light:
        bg_color      = "#FFFFFF"
        grid_major    = "#C0C0C0"
        grid_minor    = "#E0E0E0"
        tick_color    = "#444444"
        spine_color   = "#888888"
        fill_color    = trace_color
        marker_color  = MARKER_COLOR_RED
        label_color   = "#444444"
        annot_bg      = "#F0F0F0"
        annot_fg      = "#222222"
        axis_lbl_col  = "#555555"
    else:
        bg_color      = "#0D0D14"
        grid_major    = "#2E2E3D"
        grid_minor    = "#1A1A24"
        tick_color    = "#888899"
        spine_color   = "#444455"
        fill_color    = trace_color
        marker_color  = MARKER_COLOR_YELLOW
        label_color   = "#888899"
        annot_bg      = "#1E1E2E"
        annot_fg      = "#E0E0F0"
        axis_lbl_col  = "#666677"

    has_data = frequencies_hz.size > 0 and magnitudes.size > 0
    nice_steps = [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]

    # ── FFT-specific figure geometry (wider, shorter than oscilloscope view) ─
    fig, ax = plt.subplots(figsize=_FFT_FIGSIZE, dpi=dpi)
    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)
    ax.set_position([_FFT_PLOT_LEFT, _FFT_PLOT_BOTTOM, _FFT_PLOT_WIDTH, _FFT_PLOT_HEIGHT])

    for spine in ax.spines.values():
        spine.set_color(spine_color)
        spine.set_linewidth(0.8)
    ax.tick_params(colors=tick_color, labelsize=8.5, length=3, width=0.7,
                   direction="out", pad=4)

    # ── Scale strings returned to the caller ─────────────────────────────────
    hz_div_str  = ""
    mag_div_str = ""

    if has_data:
        length = min(frequencies_hz.size, magnitudes.size)
        freq   = frequencies_hz[:length]
        mags   = magnitudes[:length]

        # ── Frequency axis (X) ───────────────────────────────────────────────
        finite_f   = freq[np.isfinite(freq) & (freq >= 0)]
        f_max      = float(np.max(finite_f)) if finite_f.size > 0 else 1.0
        f_max      = max(f_max, 1.0)
        f_max_ref  = float(max_frequency_hz) if (max_frequency_hz is not None and max_frequency_hz > 0) else f_max
        f_max_ref  = max(f_max_ref, f_max)
        hz_step    = f_max_ref / _FFT_X_DIVS
        x_limit    = f_max_ref
        xticks     = np.linspace(0, x_limit, _FFT_X_DIVS + 1)
        ax.set_xticks(xticks)
        ax.set_xlim(0, x_limit)
        hz_div_str = _fmt_freq_div(hz_step)

        x_labels = [_fmt_freq_label(v) for v in xticks]
        ax.set_xticklabels(x_labels, fontsize=8.5, color=label_color)

        # ── Magnitude axis (Y) ───────────────────────────────────────────────
        if scale_mode == "log":
            ax.set_yscale("log")
            pos_mags = mags[mags > 0]
            if pos_mags.size:
                if pos_mags.size >= 5:
                    p99_pos = float(np.percentile(pos_mags, 99))
                    actual_max_pos = float(np.max(pos_mags))
                    y_max_log = max(p99_pos * 2.0, actual_max_pos * 1.1)
                else:
                    y_max_log = float(np.max(pos_mags)) * 2.0
                y_min_log = max(float(np.min(pos_mags)) * 0.5, 1e-12)
                ax.set_ylim(y_min_log, y_max_log)
            mag_div_str = ""
            ax.yaxis.set_tick_params(labelsize=8, labelcolor=label_color)
        else:
            finite_m = mags[np.isfinite(mags)]
            if finite_m.size > 0:
                actual_max = float(np.max(finite_m))
                m_target = max(actual_max * 1.15, 1e-12)
                raw_ystep = m_target / _FFT_Y_DIVS
                if raw_ystep > 0:
                    mag_order = 10 ** np.floor(np.log10(raw_ystep))
                    for s in nice_steps:
                        candidate = mag_order * s
                        if candidate >= raw_ystep:
                            mag_step = max(candidate, 1e-12)
                            break
                    else:
                        mag_step = max(mag_order * 10, 1e-12)
                else:
                    mag_step = 1e-12
                y_max_nice = mag_step * _FFT_Y_DIVS
                if y_max_nice < actual_max:
                    y_max_nice = actual_max * 1.05
            else:
                y_max_nice = 1.0
                mag_step = 0.125
            yticks = np.linspace(0, y_max_nice, _FFT_Y_DIVS + 1)
            ax.set_yticks(yticks)
            ax.set_ylim(0, y_max_nice)
            mag_div_str = _fmt_mag_div(mag_step)

            # Y-axis magnitude labels — show auto-ranged compact values
            def _fmt_mag_tick(v):
                if v == 0:
                    return "0"
                if y_max_nice >= 1.0:
                    return f"{v:.3g}"
                elif y_max_nice >= 1e-3:
                    return f"{v * 1e3:.3g}m"
                else:
                    return f"{v * 1e6:.3g}µ"

            ax.set_yticklabels(
                [_fmt_mag_tick(v) for v in yticks],
                fontsize=8, color=label_color,
            )

        # ── Axis unit labels (inside the plot area, unobtrusive corners) ─────
        ax.text(
            0.995, 0.02, "Hz",
            transform=ax.transAxes,
            fontsize=8, color=axis_lbl_col,
            ha="right", va="bottom",
        )
        if scale_mode != "log":
            ax.text(
                0.005, 0.98, "V",
                transform=ax.transAxes,
                fontsize=8, color=axis_lbl_col,
                ha="left", va="top",
            )

        # ── Draw spectrum: filled area + line trace ───────────────────────────
        ax.fill_between(
            freq, 0, mags,
            color=fill_color, alpha=0.18, linewidth=0,
        )
        ax.plot(
            freq, mags,
            color=trace_color,
            linewidth=2.2,
            solid_capstyle="round",
        )

        # ── Dominant frequency marker + annotation ────────────────────────────
        if dominant_frequency_hz > 0:
            dom_idx = int(np.argmin(np.abs(freq - dominant_frequency_hz)))
            dom_mag = float(mags[dom_idx])
            ax.scatter(
                [dominant_frequency_hz], [dom_mag],
                color=marker_color, s=55, zorder=5, linewidths=0,
            )
            ax.axvline(
                dominant_frequency_hz,
                color=marker_color, linestyle="--",
                linewidth=0.9, alpha=0.65, zorder=2,
            )
            # Annotation label: freq value + magnitude
            freq_lbl = _fmt_freq_label(dominant_frequency_hz) + " Hz"
            mag_lbl  = _fmt_mag_div(dom_mag).replace("/Div", "")  # e.g. "3.2 mV"
            annot_text = f"{freq_lbl}\n{mag_lbl}"
            # Position label to the right unless peak is in the right 30 %
            rel_x = dominant_frequency_hz / x_limit if x_limit > 0 else 0.5
            ha_side = "left" if rel_x < 0.70 else "right"
            x_offset = 8 if ha_side == "left" else -8
            ax.annotate(
                annot_text,
                xy=(dominant_frequency_hz, dom_mag),
                xytext=(x_offset, 6),
                textcoords="offset points",
                fontsize=7.5,
                color=annot_fg,
                ha=ha_side, va="bottom",
                bbox=dict(
                    boxstyle="round,pad=0.3",
                    facecolor=annot_bg,
                    edgecolor=marker_color,
                    linewidth=0.8,
                    alpha=0.88,
                ),
                zorder=6,
            )

    else:
        ax.text(
            0.5, 0.5, "No spectral data available",
            color=tick_color, fontsize=16,
            ha="center", va="center",
            transform=ax.transAxes,
        )
        ax.set_xticklabels([])
        ax.set_yticklabels([])

    # ── Grid ──────────────────────────────────────────────────────────────────
    ax.grid(True, which="major", color=grid_major, linewidth=0.55, zorder=0)
    ax.grid(True, which="minor", color=grid_minor, linewidth=0.22, zorder=0)
    if has_data:
        if len(ax.get_xticks()) >= 2:
            x_step_minor = float(ax.get_xticks()[1] - ax.get_xticks()[0])
            ax.xaxis.set_minor_locator(MultipleLocator(x_step_minor / 5))
        if scale_mode != "log" and len(ax.get_yticks()) >= 2:
            y_step_minor = float(ax.get_yticks()[1] - ax.get_yticks()[0])
            ax.yaxis.set_minor_locator(MultipleLocator(y_step_minor / 5))

    ax.set_xlabel("")
    ax.set_ylabel("")

    # ── In-figure header (export/light mode only) ─────────────────────────────
    if is_light:
        tc = "#000000"
        header_y0 = _FFT_PLOT_BOTTOM + _FFT_PLOT_HEIGHT
        header_cy = header_y0 + 0.018
        fig.text(
            _FFT_PLOT_LEFT, header_cy, f"FFT {channel_label}",
            fontsize=12, fontweight="bold",
            ha="left", va="center",
            color=tc, transform=fig.transFigure, zorder=10,
        )
        scale_parts = [s for s in [mag_div_str, hz_div_str] if s]
        if scale_parts:
            # Render scale blocks from right to left
            x = 1.0 - _FFT_PLOT_LEFT
            for part in reversed(scale_parts):
                fig.text(
                    x, header_cy, part,
                    fontsize=9.5, ha="right", va="center",
                    color=tc, transform=fig.transFigure, zorder=10,
                )
                x -= len(part) * 0.0055 + 0.005

    return fig, hz_div_str, mag_div_str


def generate_fft_grafic(
    frequencies_hz,
    magnitudes,
    file_name,
    channel_label,
    scale_mode="linear",
    dominant_frequency_hz=0.0,
    max_frequency_hz=None,
):
    frequencies_hz = np.asarray(frequencies_hz if frequencies_hz is not None else [], dtype=float)
    magnitudes     = np.asarray(magnitudes     if magnitudes     is not None else [], dtype=float)

    fig, hz_div_str, mag_div_str = _build_fft_figure(
        frequencies_hz      = frequencies_hz,
        magnitudes          = magnitudes,
        channel_label       = channel_label,
        scale_mode          = scale_mode,
        dominant_frequency_hz = dominant_frequency_hz,
        is_light            = False,
        dpi                 = 120,
        max_frequency_hz    = max_frequency_hz,
    )

    buffer = BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), dpi=120)
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    plt.close(fig)
    # Return (image, hz_div_str, mag_div_str) — callers that previously
    # received (image, vdiv_str, tdiv_str) now receive spectral scale strings.
    return image_base64, hz_div_str, mag_div_str


def generate_fft_grafic_file(
    frequencies_hz,
    magnitudes,
    file_name,
    channel_label,
    scale_mode="linear",
    dominant_frequency_hz=0.0,
    max_frequency_hz=None,
):
    frequencies_hz = np.asarray(frequencies_hz if frequencies_hz is not None else [], dtype=float)
    magnitudes     = np.asarray(magnitudes     if magnitudes     is not None else [], dtype=float)

    fig, _hz_div_str, _mag_div_str = _build_fft_figure(
        frequencies_hz      = frequencies_hz,
        magnitudes          = magnitudes,
        channel_label       = channel_label,
        scale_mode          = scale_mode,
        dominant_frequency_hz = dominant_frequency_hz,
        is_light            = True,
        dpi                 = 150,
        max_frequency_hz    = max_frequency_hz,
    )

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
        fig.savefig(tmp_file.name, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), dpi=150)
        temp_path = tmp_file.name
    plt.close(fig)
    return temp_path


# ---------------------------------------------------------------------------
# Signal analysis (derivative / integral)
# ---------------------------------------------------------------------------

def _channel_trace_colors(channel, is_light):
    """Return (trace_color_dark, trace_color_light) for a given channel."""
    ch = (channel or "").upper().replace("CH", "")
    if ch in ("X", "1"):
        return CHANNEL_COLORS_STR["X"], CHANNEL_COLORS_STR_LIGHT["X"]
    if ch in ("Y", "2"):
        return CHANNEL_COLORS_STR["Y"], CHANNEL_COLORS_STR_LIGHT["Y"]
    if ch == "MATH":
        return CHANNEL_COLORS_STR["MATH"], CHANNEL_COLORS_STR_LIGHT["MATH"]
    return TRACE_COLOR_TEAL, TRACE_COLOR_TEAL_LIGHT


def _channel_trace_color(channel, is_light):
    dark, light = _channel_trace_colors(channel, is_light)
    return light if is_light else dark


def generate_signal_analysis_grafic(t, signal, title, y_label, channel=None):
    _dark, _light = _channel_trace_colors(channel, False)
    fig, vdiv_str, _vdiv2, tdiv_str = _build_secondary_figure(
        x_data=t,
        y_data=signal,
        title=title,
        header_items=[{"text": y_label}] if y_label else [],
        trace_color_dark=_dark,
        trace_color_light=_light,
        is_light=False,
        dpi=120,
        empty_message="No data available",
        return_scale_info=True,
    )
    buffer = BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), dpi=120)
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    plt.close(fig)
    return image_base64, vdiv_str, tdiv_str


def generate_signal_analysis_grafic_file(t, signal, title, y_label, channel=None):
    _dark, _light = _channel_trace_colors(channel, True)
    fig = _build_secondary_figure(
        x_data=t,
        y_data=signal,
        title=title,
        header_items=[{"text": y_label}] if y_label else [],
        trace_color_dark=_dark,
        trace_color_light=_light,
        is_light=True,
        dpi=150,
        empty_message="No data available",
    )
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
        fig.savefig(tmp_file.name, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), dpi=150)
        temp_path = tmp_file.name
    plt.close(fig)
    return temp_path


# ---------------------------------------------------------------------------
# Voltage / Current (dual-axis)
# ---------------------------------------------------------------------------

def generate_voltage_current_grafic(t, voltage, current, title, voltage_channel=None):
    time_axis = np.asarray(t if t is not None else [], dtype=float)
    voltage   = np.asarray(voltage if voltage is not None else [], dtype=float)
    current   = np.asarray(current if current is not None else [], dtype=float)

    has_data = time_axis.size > 0 and voltage.size > 0 and current.size > 0

    v_dark, v_light = _channel_trace_colors(voltage_channel, False)
    header_items = [
        {"text": "V", "color": v_dark},
        {"text": "I", "color": TRACE_COLOR_ORANGE},
    ]

    fig, vdiv_str, vdiv2_str, tdiv_str = _build_secondary_figure(
        x_data=time_axis,
        y_data=voltage,
        title=title,
        header_items=header_items,
        trace_color_dark=v_dark,
        trace_color_light=v_light,
        is_light=False,
        dpi=120,
        empty_message="No current data available",
        ax2_data=current if has_data else None,
        ax2_color_dark=TRACE_COLOR_ORANGE,
        ax2_color_light=TRACE_COLOR_ORANGE_LIGHT,
        ax2_unit="A",
        return_scale_info=True,
    )
    buffer = BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), dpi=120)
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    plt.close(fig)
    return image_base64, vdiv_str, vdiv2_str, tdiv_str


def generate_voltage_current_grafic_file(t, voltage, current, title, voltage_channel=None):
    time_axis = np.asarray(t if t is not None else [], dtype=float)
    voltage   = np.asarray(voltage if voltage is not None else [], dtype=float)
    current   = np.asarray(current if current is not None else [], dtype=float)

    has_data = time_axis.size > 0 and voltage.size > 0 and current.size > 0

    v_dark, v_light = _channel_trace_colors(voltage_channel, True)
    header_items = [
        {"text": "V", "color": v_light},
        {"text": "I", "color": TRACE_COLOR_ORANGE_LIGHT},
    ]

    fig = _build_secondary_figure(
        x_data=time_axis,
        y_data=voltage,
        title=title,
        header_items=header_items,
        trace_color_dark=v_dark,
        trace_color_light=v_light,
        is_light=True,
        dpi=150,
        empty_message="No current data available",
        ax2_data=current if has_data else None,
        ax2_color_dark=TRACE_COLOR_ORANGE,
        ax2_color_light=TRACE_COLOR_ORANGE_LIGHT,
        ax2_unit="A",
    )
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
        fig.savefig(tmp_file.name, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), dpi=150)
        temp_path = tmp_file.name
    plt.close(fig)
    return temp_path


# ---------------------------------------------------------------------------
# Correlation
# ---------------------------------------------------------------------------

def generate_correlation_grafic(lags_seconds, correlation, title, marker_x=None, marker_y=None):
    has_marker = marker_x is not None and marker_y is not None

    def _corr_extras(ax, tick_color, is_light):
        if has_marker:
            c = MARKER_COLOR_YELLOW if not is_light else MARKER_COLOR_RED
            ax.scatter([marker_x], [marker_y], color=c, s=50, zorder=3)

    fig, vdiv_str, _vdiv2, tdiv_str = _build_secondary_figure(
        x_data=lags_seconds,
        y_data=correlation,
        title=title,
        header_items=[{"text": "Correlation"}],
        trace_color_dark=TRACE_COLOR_TEAL,
        trace_color_light=TRACE_COLOR_TEAL_LIGHT,
        is_light=False,
        dpi=120,
        empty_message="No correlation data available",
        extra_artists_fn=_corr_extras,
        return_scale_info=True,
    )
    buffer = BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), dpi=120)
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    plt.close(fig)
    return image_base64, vdiv_str, tdiv_str


def generate_correlation_grafic_file(lags_seconds, correlation, title, marker_x=None, marker_y=None):
    has_marker = marker_x is not None and marker_y is not None

    def _corr_extras(ax, tick_color, is_light):
        if has_marker:
            ax.scatter([marker_x], [marker_y], color=MARKER_COLOR_RED, s=50, zorder=3)

    fig = _build_secondary_figure(
        x_data=lags_seconds,
        y_data=correlation,
        title=title,
        header_items=[{"text": "Correlation"}],
        trace_color_dark=TRACE_COLOR_TEAL,
        trace_color_light=TRACE_COLOR_TEAL_LIGHT,
        is_light=True,
        dpi=150,
        empty_message="No correlation data available",
        extra_artists_fn=_corr_extras,
    )
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
        fig.savefig(tmp_file.name, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), dpi=150)
        temp_path = tmp_file.name
    plt.close(fig)
    return temp_path


# ---------------------------------------------------------------------------
# X-Y Mode
# ---------------------------------------------------------------------------

def generate_xy_mode_grafic(x_signal, y_signal, title, x_label="X (V)", y_label="Y (V)", x_channel=None, y_channel=None):
    fig, vdiv_str, _vdiv2, tdiv_str = _build_secondary_figure(
        x_data=x_signal,
        y_data=y_signal,
        title=title,
        header_items=[{"text": f"X: {x_label}"}, {"text": f"Y: {y_label}"}],
        trace_color_dark=TRACE_COLOR_TEAL,
        trace_color_light=TRACE_COLOR_TEAL_LIGHT,
        is_light=False,
        dpi=120,
        empty_message="No X-Y data available",
        return_scale_info=True,
    )
    buffer = BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), dpi=120)
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    plt.close(fig)
    return image_base64, vdiv_str, tdiv_str


def generate_xy_mode_grafic_file(x_signal, y_signal, title, x_label="X (V)", y_label="Y (V)"):
    fig = _build_secondary_figure(
        x_data=x_signal,
        y_data=y_signal,
        title=title,
        header_items=[{"text": f"X: {x_label}"}, {"text": f"Y: {y_label}"}],
        trace_color_dark=TRACE_COLOR_TEAL,
        trace_color_light=TRACE_COLOR_TEAL_LIGHT,
        is_light=True,
        dpi=150,
        empty_message="No X-Y data available",
    )
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
        fig.savefig(tmp_file.name, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), dpi=150)
        temp_path = tmp_file.name
    plt.close(fig)
    return temp_path


# ---------------------------------------------------------------------------
# Cursor (exportación — siempre modo claro con header)
# ---------------------------------------------------------------------------

def generate_cursor_grafic_file(t, signal, title, marker_points=None, header_items=None, vdiv_v=None, tdiv_s=None, trace_color=CH1_COLOR_LIGHT,
                                signal_b=None, trace_color_b=None, vdiv_v_b=None, marker_points_b=None):
    marker_points   = marker_points   or []
    marker_points_b = marker_points_b or []
    header_items    = header_items    or []

    t      = np.asarray(t if t is not None else [], dtype=float)
    signal = np.asarray(signal if signal is not None else [], dtype=float)
    has_b  = signal_b is not None and trace_color_b is not None

    def _cursor_extras(ax, tick_color, is_light):
        for point_x, point_y in marker_points:
            ax.axvline(point_x, color=MARKER_COLOR_RED, linestyle="--", linewidth=1.0)
            ax.scatter([point_x], [point_y], color=MARKER_COLOR_RED, s=42, zorder=4)

    # Si se proveen vdiv/tdiv, sobreescribir ticks después de construir la figura.
    fig = _build_secondary_figure(
        x_data=t,
        y_data=signal,
        title=title,
        header_items=header_items,
        trace_color_dark=trace_color,
        trace_color_light=trace_color,
        is_light=True,
        dpi=150,
        empty_message="No cursor data available",
        extra_artists_fn=_cursor_extras if marker_points else None,
        suppress_auto_scale_labels=True,
    )

    # Aplicar escala física exacta si se suministra (respeta V/div y s/div reales)
    ax = fig.axes[0]
    if tdiv_s is not None and tdiv_s > 0:
        xticks = np.arange(-7, 8, dtype=float) * tdiv_s
        ax.set_xticks(xticks)
        ax.set_xlim(xticks[0], xticks[-1])
    if vdiv_v is not None and vdiv_v > 0:
        yticks = np.linspace(-4 * vdiv_v, 4 * vdiv_v, _SQUARE_Y_DIVS + 1)
        ax.set_yticks(yticks)
        ax.set_ylim(yticks[0], yticks[-1])

    # Dual mode: draw signal B scaled to match A's Y-axis range
    if has_b and vdiv_v is not None and vdiv_v > 0 and vdiv_v_b is not None and vdiv_v_b > 0:
        signal_b_arr = np.asarray(signal_b, dtype=float)
        scale = vdiv_v / vdiv_v_b
        scaled_b = signal_b_arr * scale
        length_b = min(t.size, scaled_b.size)
        ax.plot(t[:length_b], scaled_b[:length_b], color=trace_color_b, linewidth=1.8)
        # Draw signal B's cursor markers (scaled)
        for point_x, point_y in marker_points_b:
            scaled_y = point_y * scale
            ax.scatter([point_x], [scaled_y], color=trace_color_b, s=42, zorder=4, marker="s")
    elif has_b:
        # Fallback: no vdiv info, just plot raw
        signal_b_arr = np.asarray(signal_b, dtype=float)
        length_b = min(t.size, signal_b_arr.size)
        ax.plot(t[:length_b], signal_b_arr[:length_b], color=trace_color_b, linewidth=1.8)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
        fig.savefig(tmp_file.name, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), dpi=150)
        temp_path = tmp_file.name
    plt.close(fig)
    return temp_path