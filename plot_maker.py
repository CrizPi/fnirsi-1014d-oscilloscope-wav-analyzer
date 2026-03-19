import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io import BytesIO
import base64
import numpy as np
from typing import Optional, Union, Tuple, List
from dataclasses import dataclass
from enum import Enum


class Channel(Enum):
    """Enum para identificar canales."""
    CH1 = 'X'
    CH2 = 'Y'
    MATH = 'MATH'


@dataclass
class PlotConfig:
    """Configuración del estilo del osciloscopio."""
    figsize: Tuple[float, float] = (16, 6)
    bg_color: str = '#000000'
    grid_major_color: str = '#919191'
    grid_minor_color: str = '#2B2B2B'
    tick_color: str = '#919191'
    spine_color: str = '#919191'
    center_line_color: str = '#919191'
    grid_major_width: float = 0.6
    grid_minor_width: float = 0.4
    spine_width: float = 1.0
    line_width: float = 2.0
    divisions: int = 8


@dataclass
class ChannelData:
    """Datos de un canal."""
    time: np.ndarray
    signal: Optional[np.ndarray] = None
    color: str = '#ffff00'
    label: str = Channel.CH1.value


class OscilloscopePlotter:
    """Generador de gráficos estilo osciloscopio."""
    
    def __init__(self, config: PlotConfig = None):
        self.config = config or PlotConfig()
        self._channel_colors = {
            Channel.CH1: '#ffff00',
            Channel.CH2: '#00e5ff', 
            Channel.MATH: '#ff00ff'
        }
    
    def _is_empty_signal(self, signal: Optional[Union[list, np.ndarray]]) -> bool:
        """Verifica si una señal está vacía."""
        if signal is None or len(signal) == 0:
            return True
        return np.all(np.array(signal) == 0)
    
    def _safe_range(self, min_val: float, max_val: float) -> Tuple[float, float]:
        """Asegura un rango válido para ejes."""
        if min_val == max_val:
            return min_val, min_val + 1e-9
        return min_val, max_val
    
    def _safe_max(self, val: float) -> float:
        """Valor máximo seguro."""
        if val == 0 or np.isnan(val):
            return 1.0
        return val
    
    def _normalize_arrays(self, *arrays: Optional[Union[list, np.ndarray]]) -> List[np.ndarray]:
        """Normaliza arrays a numpy."""
        return [np.array(arr) if arr is not None else np.array([]) for arr in arrays]
    
    def _get_time_scale(self, t: np.ndarray) -> Tuple[np.ndarray, str]:
        """Calcula escala de tiempo con prefijo ingenieril."""
        if len(t) == 0:
            return t, ''
        
        max_t = np.max(np.abs(t))
        eng_scales = [
            (1e-12, 'p'), (1e-9, 'n'), (1e-6, 'µ'),
            (1e-3, 'm'), (1, ''), (1e3, 'k'), (1e6, 'M')
        ]
        
        scale, prefix = 1, ''
        for factor, sym in eng_scales:
            if max_t < factor * 1000:
                scale, prefix = factor, sym
                break
        
        return t / scale if scale != 0 else t, prefix
    
    def _setup_axes_style(self, ax, ax2=None):
        """Configura estilo de los ejes."""
        fig = ax.get_figure()
        fig.patch.set_facecolor(self.config.bg_color)
        ax.set_facecolor(self.config.bg_color)
        
        if ax2:
            ax2.set_facecolor(self.config.bg_color)
        
        # Estilo de spines y grid
        for spine in ax.spines.values():
            spine.set_color(self.config.spine_color)
            spine.set_linewidth(self.config.spine_width)
        
        if ax2:
            ax2.spines['right'].set_color(self.config.spine_color)
        
        ax.grid(True, which='major', color=self.config.grid_major_color, linewidth=self.config.grid_major_width)
        ax.minorticks_on()
        ax.grid(True, which='minor', color=self.config.grid_minor_color, linewidth=self.config.grid_minor_width)
        ax.tick_params(colors=self.config.tick_color)
        
        if ax2:
            ax2.tick_params(colors=self.config.tick_color)
    
    def _setup_time_ticks(self, ax, t_scaled: np.ndarray):
        """Configura ticks de tiempo."""
        if len(t_scaled) > 1:
            t_min, t_max = np.min(t_scaled), np.max(t_scaled)
            t_min, t_max = self._safe_range(t_min, t_max)
            xticks = np.linspace(t_min, t_max, 19)
            ax.set_xticks(xticks)
    
    def _setup_voltage_ticks(self, ax, ax2, ch1: np.ndarray, ch2: np.ndarray, 
                           math_result: Optional[np.ndarray], is_math_only: bool):
        """Configura ticks de voltaje."""
        divisions = self.config.divisions
        
        if is_math_only:
            max_val = np.max(np.abs(math_result)) if len(math_result) > 0 else 1
            max_val = self._safe_max(max_val) * 1.2
            step = self._safe_max(max_val / (divisions / 2))
            y_ticks = np.arange(-divisions/2, divisions/2 + 1) * step
            ax.set_ylim(y_ticks[0], y_ticks[-1])
            ax.set_yticks(y_ticks)
        else:
            max1 = np.max(np.abs(ch1)) if not self._is_empty_signal(ch1) else 1
            max2 = np.max(np.abs(ch2)) if not self._is_empty_signal(ch2) else 1
            max1, max2 = self._safe_max(max1) * 1.2, self._safe_max(max2) * 1.2
            
            step1, step2 = self._safe_max(max1 / (divisions / 2)), self._safe_max(max2 / (divisions / 2))
            y_ticks1 = np.arange(-divisions/2, divisions/2 + 1) * step1
            y_ticks2 = np.arange(-divisions/2, divisions/2 + 1) * step2
            
            ax.set_ylim(y_ticks1[0], y_ticks1[-1])
            ax.set_yticks(y_ticks1)
            ax2.set_ylim(y_ticks2[0], y_ticks2[-1])
            ax2.set_yticks(y_ticks2)
    
    def _draw_center_lines(self, ax):
        """Dibuja líneas centrales."""
        ax.axhline(0, color=self.config.center_line_color, linewidth=2)
        ax.axvline(0, color=self.config.center_line_color, linewidth=2)
    
    def _plot_channels(self, ax, ax2, t_scaled: np.ndarray, ch1: np.ndarray, 
                      ch2: np.ndarray, math_result: np.ndarray, 
                      show_empty: bool, is_math_only: bool):
        """Dibuja las señales de los canales."""
        show_ch1 = not self._is_empty_signal(ch1) or show_empty
        show_ch2 = not self._is_empty_signal(ch2) or show_empty
        
        if is_math_only:
            ax.plot(t_scaled[:len(math_result)], math_result, 
                   color=self._channel_colors[Channel.MATH], linewidth=self.config.line_width)
        else:
            if show_ch1:
                ax.plot(t_scaled[:len(ch1)], ch1, color=self._channel_colors[Channel.CH1], 
                       linewidth=self.config.line_width)
            else:
                ax.plot([], [], color=self._channel_colors[Channel.CH1], linewidth=self.config.line_width)
            
            if show_ch2:
                ax2.plot(t_scaled[:len(ch2)], ch2, color=self._channel_colors[Channel.CH2], 
                        linewidth=self.config.line_width)
            else:
                ax2.plot([], [], color=self._channel_colors[Channel.CH2], linewidth=self.config.line_width)
            
            if math_result is not None and len(math_result) > 0:
                ax.plot(t_scaled[:len(math_result)], math_result, 
                       color=self._channel_colors[Channel.MATH], linewidth=self.config.line_width)
    
    def _add_no_signal_message(self, ax, show_ch1: bool, show_ch2: bool, show_empty: bool, is_math_only: bool):
        """Agrega mensaje cuando no hay señal."""
        if not is_math_only and not show_ch1 and not show_ch2 and not show_empty:
            ax.text(0.5, 0.5, "No signal loaded", color=self.config.tick_color, fontsize=20,
                   ha="center", va="center", transform=ax.transAxes)
    
    def _create_legend(self, ax, ax2):
        """Crea la leyenda fija."""
        legend_lines = []
        legend_labels = []
        
        # Líneas de leyenda para cada canal
        for channel in [Channel.CH1, Channel.CH2, Channel.MATH]:
            color = self._channel_colors[channel]
            if channel == Channel.CH2 and ax2:
                line, = ax2.plot([], [], color=color, linewidth=self.config.line_width)
            else:
                line, = ax.plot([], [], color=color, linewidth=self.config.line_width)
            legend_lines.append(line)
            legend_labels.append(channel.value)
        
        leg = ax.legend(legend_lines, legend_labels, loc='upper right', 
                       bbox_to_anchor=(1.00, 1.00), ncol=3)
        plt.setp(leg.get_texts(), color=self.config.tick_color)
        leg.get_frame().set_facecolor(self.config.bg_color)
        leg.get_frame().set_edgecolor(self.config.spine_color)
        return leg
    
    def generate_plot(self, t: Optional[Union[list, np.ndarray]], 
                     ch1: Optional[Union[list, np.ndarray]], 
                     ch2: Optional[Union[list, np.ndarray]], 
                     file_name: str,
                     measures: Optional[dict] = None,
                     math_result: Optional[Union[list, np.ndarray]] = None,
                     show_empty: bool = False) -> str:
        """
        Genera un gráfico tipo osciloscopio y devuelve la imagen en base64.
        
        Args:
            t: Array de tiempo
            ch1: Señal del canal 1 (amarillo)
            ch2: Señal del canal 2 (cian)
            file_name: Nombre del archivo para título
            measures: Mediciones (no usado actualmente)
            math_result: Resultado matemático (magenta)
            show_empty: Mostrar canales vacíos
        
        Returns:
            Imagen en base64
        """
        # Normalizar arrays
        t_norm, ch1_norm, ch2_norm, math_norm = self._normalize_arrays(t, ch1, ch2, math_result)
        
        # Detectar modo MATH puro
        is_math_only = (math_norm is not None and len(math_norm) > 0 and 
                       self._is_empty_signal(ch1_norm) and self._is_empty_signal(ch2_norm))
        
        # Escala de tiempo
        t_scaled, time_prefix = self._get_time_scale(t_norm)
        
        # Crear figura
        fig, ax = plt.subplots(figsize=self.config.figsize)
        ax2 = ax.twinx() if not is_math_only else None
        
        # Configurar estilo
        self._setup_axes_style(ax, ax2)
        
        # Configurar etiquetas
        ax.set_xlabel(f"Time ({time_prefix}s)", color=self.config.tick_color)
        if is_math_only:
            ax.set_ylabel("Math Result (V)", color=self._channel_colors[Channel.MATH])
        else:
            ax.set_ylabel("Voltage (V)", color=self._channel_colors[Channel.CH1])
            if ax2:
                ax2.set_ylabel("Voltage (V)", color=self._channel_colors[Channel.CH2])
        
        # Configurar ticks
        self._setup_time_ticks(ax, t_scaled)
        self._setup_voltage_ticks(ax, ax2, ch1_norm, ch2_norm, math_norm, is_math_only)
        
        # Líneas centrales
        self._draw_center_lines(ax)
        
        # Dibujar señales
        self._plot_channels(ax, ax2, t_scaled, ch1_norm, ch2_norm, math_norm, show_empty, is_math_only)
        
        # Mensaje sin señal
        show_ch1 = not self._is_empty_signal(ch1_norm)
        show_ch2 = not self._is_empty_signal(ch2_norm)
        self._add_no_signal_message(ax, show_ch1, show_ch2, show_empty, is_math_only)
        
        # Leyenda
        self._create_legend(ax, ax2)
        
        # Título
        plt.title(file_name, color=self.config.tick_color)
        
        # Exportar a base64
        buffer = BytesIO()
        plt.savefig(buffer, format="png", bbox_inches="tight", 
                   facecolor=fig.get_facecolor(), dpi=100)
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        plt.close()
        
        return img_base64


def generate_grafic(t, ch1, ch2, file_name, measures=None, math_result=None, show_empty=False):
    plotter = OscilloscopePlotter()
    return plotter.generate_plot(t, ch1, ch2, file_name, measures, math_result, show_empty)
