"""Textual application entry point."""

from __future__ import annotations

from dataclasses import dataclass, replace

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Static

from bellows.simulation.engine import VentilationSimulation
from bellows.simulation.state import (
    PatientMechanics,
    SimulationSample,
    VentilatorSettings,
)
from bellows.waveforms.buffers import TraceBuffer
from bellows.ui.waveform import WaveformSpec, WaveformWidget


@dataclass
class BreathMetrics:
    current_breath: int | None = None
    current_min_volume_ml: float = 0.0
    current_max_volume_ml: float = 0.0
    current_peak_pressure_cm_h2o: float = 0.0
    current_etco2_kpa: float = 0.0
    completed_vt_ml: float | None = None
    completed_minute_volume_l_min: float | None = None
    completed_peak_pressure_cm_h2o: float | None = None
    completed_etco2_kpa: float | None = None


@dataclass(frozen=True)
class ControlRow:
    key: str
    label: str


class BellowsApp(App[None]):
    """ICU-ventilator inspired terminal simulator."""

    ENABLE_COMMAND_PALETTE = False

    CSS = """
    Screen {
        background: #050807;
        color: #d8e0dc;
    }

    #titlebar {
        height: 1;
        background: #111917;
        color: #d8e0dc;
        text-style: bold;
        padding: 0 1;
    }

    Footer {
        background: #111917;
        color: #aeb8b2;
    }

    #shell {
        height: 1fr;
    }

    #sidebar {
        width: 29;
        min-width: 29;
        background: #0d1412;
        border-right: solid #26332f;
        padding: 1;
    }

    #monitor {
        height: 1fr;
        padding: 1;
    }

    #status {
        height: 2;
        background: #101916;
        color: #d8e0dc;
        border-bottom: solid #26332f;
        padding: 0 1;
    }

    #numerics {
        height: 3;
        background: #07100e;
        color: #d8e0dc;
        border-bottom: solid #26332f;
        padding: 0 1;
    }

    #disclaimer {
        dock: bottom;
        height: 1;
        background: #211811;
        color: #f0b36a;
        text-style: bold;
    }

    .panel-title {
        color: #8fa69d;
        text-style: bold;
    }

    .value {
        color: #f4f7f5;
    }

    .muted {
        color: #748179;
    }
    """

    BINDINGS = [
        ("space", "toggle_pause", "Pause"),
        Binding("tab", "toggle_sidebar", "Panel", priority=True),
        Binding("ctrl+i", "toggle_sidebar", "Panel", show=False, priority=True),
        ("r", "reset", "Reset"),
        Binding("up", "select_previous_control", "Select up", show=False),
        Binding("down", "select_next_control", "Select down", show=False),
        Binding("left", "decrease_selected_control", "Decrease", show=False),
        Binding("right", "increase_selected_control", "Increase", show=False),
        Binding("enter", "activate_selected_control", "Toggle", show=False),
        Binding("m", "toggle_mode", "Mode", show=False),
        Binding("c", "toggle_co2", "CO2", show=False),
        Binding("-", "target_down", "Target-", show=False),
        Binding("minus", "target_down", "Target-", show=False),
        Binding("=", "target_up", "Target+", show=False),
        Binding("equals", "target_up", "Target+", show=False),
        Binding("+", "target_up", "Target+", show=False),
        Binding("plus", "target_up", "Target+", show=False),
        Binding("1", "rr_down", "RR-", show=False),
        Binding("2", "rr_up", "RR+", show=False),
        Binding("3", "peep_down", "PEEP-", show=False),
        Binding("4", "peep_up", "PEEP+", show=False),
        Binding("5", "ie_shorter", "I:E-", show=False),
        Binding("6", "ie_longer", "I:E+", show=False),
        Binding("7", "compliance_down", "C-", show=False),
        Binding("8", "compliance_up", "C+", show=False),
        Binding("9", "resistance_down", "R-", show=False),
        Binding("0", "resistance_up", "R+", show=False),
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.title = "bellows"
        self.sub_title = "VCV education simulator"
        self.simulation = VentilationSimulation()
        self.paused = False
        self.visible_window_s = 12.0
        self.dt_s = 0.01
        self.samples_per_render = 3
        self.buffers = {
            "pressure": TraceBuffer(2400),
            "flow": TraceBuffer(2400),
            "volume": TraceBuffer(2400),
            "co2": TraceBuffer(2400),
        }
        self.waveform_visible = {
            "pressure": True,
            "flow": True,
            "volume": True,
            "co2": False,
        }
        self.waveforms: dict[str, WaveformWidget] = {}
        self.status: Static | None = None
        self.numerics: Static | None = None
        self.sidebar: Static | None = None
        self.titlebar: Static | None = None
        self.sidebar_visible = True
        self.control_rows = [
            ControlRow("mode", "Mode"),
            ControlRow("target", "Target"),
            ControlRow("rr", "RR"),
            ControlRow("peep", "PEEP"),
            ControlRow("ie", "I:E"),
            ControlRow("compliance", "Compliance"),
            ControlRow("resistance", "Resistance"),
            ControlRow("pressure", "Pressure"),
            ControlRow("flow", "Flow"),
            ControlRow("volume", "Volume"),
            ControlRow("co2", "CO2 trace"),
        ]
        self.selected_control_index = 0
        self.metrics = BreathMetrics()
        self.message = "Ready"

    def compose(self) -> ComposeResult:
        yield Static(id="titlebar")
        with Horizontal(id="shell"):
            yield Static(id="sidebar")
            with Vertical(id="monitor"):
                yield Static(id="status")
                yield Static(id="numerics")
                pressure = WaveformWidget(
                    WaveformSpec("Pressure", "cmH2O", "#f5c451", 0.0, 40.0),
                    id="pressure",
                )
                flow = WaveformWidget(
                    WaveformSpec("Flow", "L/min", "#57c7ff", -60.0, 60.0),
                    id="flow",
                )
                volume = WaveformWidget(
                    WaveformSpec("Volume", "mL", "#72d572", 0.0, 650.0),
                    id="volume",
                )
                co2 = WaveformWidget(
                    WaveformSpec("CO2", "kPa", "#d78cff", 0.0, 7.0),
                    id="co2",
                )
                co2.display = self.waveform_visible["co2"]
                self.waveforms = {
                    "pressure": pressure,
                    "flow": flow,
                    "volume": volume,
                    "co2": co2,
                }
                yield pressure
                yield flow
                yield volume
                yield co2
        yield Static(
            "EDUCATIONAL SIMULATOR ONLY - not for clinical care",
            id="disclaimer",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.titlebar = self.query_one("#titlebar", Static)
        self.status = self.query_one("#status", Static)
        self.numerics = self.query_one("#numerics", Static)
        self.sidebar = self.query_one("#sidebar", Static)
        self._refresh_static_panels()
        self.set_interval(1 / 30, self._tick)

    def action_toggle_pause(self) -> None:
        self.paused = not self.paused
        self.message = "Paused" if self.paused else "Running"
        self._refresh_static_panels()

    def action_toggle_sidebar(self) -> None:
        self.sidebar_visible = not self.sidebar_visible
        if self.sidebar is not None:
            self.sidebar.display = self.sidebar_visible
        self.message = "Control panel shown" if self.sidebar_visible else "Control panel hidden"
        self._refresh_static_panels()

    def action_select_previous_control(self) -> None:
        self.selected_control_index = (
            self.selected_control_index - 1
        ) % len(self.control_rows)
        self._refresh_static_panels()

    def action_select_next_control(self) -> None:
        self.selected_control_index = (
            self.selected_control_index + 1
        ) % len(self.control_rows)
        self._refresh_static_panels()

    def action_decrease_selected_control(self) -> None:
        self._adjust_selected_control(-1)

    def action_increase_selected_control(self) -> None:
        self._adjust_selected_control(1)

    def action_activate_selected_control(self) -> None:
        key = self._selected_control_key()
        if key == "mode":
            self.action_toggle_mode()
        elif key in self.waveform_visible:
            self._toggle_waveform(key)
        else:
            self.message = f"{self.control_rows[self.selected_control_index].label}: use left/right"
            self._refresh_static_panels()

    def action_reset(self) -> None:
        self.simulation.reset()
        for buffer in self.buffers.values():
            buffer.clear()
        self.metrics = BreathMetrics()
        self.message = "Simulation reset"
        self._refresh_waveforms()
        self._refresh_static_panels()

    def action_toggle_mode(self) -> None:
        settings = self._editable_settings()
        mode = "PCV" if settings.mode == "VCV" else "VCV"
        self._set_settings(replace(settings, mode=mode), f"Mode {mode}")

    def action_toggle_co2(self) -> None:
        self._toggle_waveform("co2")

    def action_target_down(self) -> None:
        settings = self._editable_settings()
        if settings.mode == "PCV":
            value = max(5.0, settings.pinsp_cm_h2o - 1.0)
            self._set_settings(
                replace(settings, pinsp_cm_h2o=value),
                f"Pinsp {value:.0f} cmH2O",
            )
            return

        value = max(100.0, settings.vt_ml - 25.0)
        self._set_settings(replace(settings, vt_ml=value), f"VT {value:.0f} mL")

    def action_target_up(self) -> None:
        settings = self._editable_settings()
        if settings.mode == "PCV":
            value = min(40.0, settings.pinsp_cm_h2o + 1.0)
            self._set_settings(
                replace(settings, pinsp_cm_h2o=value),
                f"Pinsp {value:.0f} cmH2O",
            )
            return

        value = min(1000.0, settings.vt_ml + 25.0)
        self._set_settings(replace(settings, vt_ml=value), f"VT {value:.0f} mL")

    def action_rr_down(self) -> None:
        settings = self._editable_settings()
        value = max(4.0, settings.rr_bpm - 1.0)
        self._set_settings(replace(settings, rr_bpm=value), f"RR {value:.0f}/min")

    def action_rr_up(self) -> None:
        settings = self._editable_settings()
        value = min(40.0, settings.rr_bpm + 1.0)
        self._set_settings(replace(settings, rr_bpm=value), f"RR {value:.0f}/min")

    def action_peep_down(self) -> None:
        settings = self._editable_settings()
        value = max(0.0, settings.peep_cm_h2o - 1.0)
        self._set_settings(
            replace(settings, peep_cm_h2o=value),
            f"PEEP {value:.0f} cmH2O",
        )

    def action_peep_up(self) -> None:
        settings = self._editable_settings()
        value = min(25.0, settings.peep_cm_h2o + 1.0)
        self._set_settings(
            replace(settings, peep_cm_h2o=value),
            f"PEEP {value:.0f} cmH2O",
        )

    def action_ie_shorter(self) -> None:
        settings = self._editable_settings()
        value = max(1.0, settings.ie_e - 0.5)
        self._set_settings(replace(settings, ie_e=value), f"I:E 1:{value:g}")

    def action_ie_longer(self) -> None:
        settings = self._editable_settings()
        value = min(4.0, settings.ie_e + 0.5)
        self._set_settings(replace(settings, ie_e=value), f"I:E 1:{value:g}")

    def action_compliance_down(self) -> None:
        patient = self.simulation.patient
        value = max(0.01, patient.compliance_l_per_cm_h2o - 0.005)
        self._set_patient(
            replace(patient, compliance_l_per_cm_h2o=value),
            f"Compliance {value * 1000:.0f} mL/cmH2O",
        )

    def action_compliance_up(self) -> None:
        patient = self.simulation.patient
        value = min(0.12, patient.compliance_l_per_cm_h2o + 0.005)
        self._set_patient(
            replace(patient, compliance_l_per_cm_h2o=value),
            f"Compliance {value * 1000:.0f} mL/cmH2O",
        )

    def action_resistance_down(self) -> None:
        patient = self.simulation.patient
        value = max(2.0, patient.resistance_cm_h2o_s_per_l - 1.0)
        self._set_patient(
            replace(patient, resistance_cm_h2o_s_per_l=value),
            f"Resistance {value:.0f} cmH2O*s/L",
        )

    def action_resistance_up(self) -> None:
        patient = self.simulation.patient
        value = min(40.0, patient.resistance_cm_h2o_s_per_l + 1.0)
        self._set_patient(
            replace(patient, resistance_cm_h2o_s_per_l=value),
            f"Resistance {value:.0f} cmH2O*s/L",
        )

    def _adjust_selected_control(self, direction: int) -> None:
        key = self._selected_control_key()
        if key == "target":
            if direction < 0:
                self.action_target_down()
            else:
                self.action_target_up()
        elif key == "rr":
            if direction < 0:
                self.action_rr_down()
            else:
                self.action_rr_up()
        elif key == "peep":
            if direction < 0:
                self.action_peep_down()
            else:
                self.action_peep_up()
        elif key == "ie":
            if direction < 0:
                self.action_ie_shorter()
            else:
                self.action_ie_longer()
        elif key == "compliance":
            if direction < 0:
                self.action_compliance_down()
            else:
                self.action_compliance_up()
        elif key == "resistance":
            if direction < 0:
                self.action_resistance_down()
            else:
                self.action_resistance_up()
        elif key == "mode":
            self.action_toggle_mode()
        elif key in self.waveform_visible:
            self._toggle_waveform(key)

    def _selected_control_key(self) -> str:
        return self.control_rows[self.selected_control_index].key

    def _toggle_waveform(self, waveform: str) -> None:
        visible = not self.waveform_visible[waveform]
        if not visible and self._visible_waveform_count() <= 1:
            self.message = "At least one waveform must remain visible"
            self._refresh_static_panels()
            return

        self.waveform_visible[waveform] = visible
        if waveform in self.waveforms:
            self.waveforms[waveform].display = visible
        self.message = (
            f"{self._waveform_label(waveform)} waveform shown"
            if visible
            else f"{self._waveform_label(waveform)} waveform hidden"
        )
        self._refresh_static_panels()

    def _visible_waveform_count(self) -> int:
        return sum(1 for visible in self.waveform_visible.values() if visible)

    def _set_settings(self, settings: VentilatorSettings, message: str) -> None:
        self.simulation.queue_settings(settings)
        self.message = f"{message} queued for next breath"
        self._refresh_static_panels()

    def _set_patient(self, patient: PatientMechanics, message: str) -> None:
        self.simulation.patient = patient
        self.message = message
        self._refresh_static_panels()

    def _editable_settings(self) -> VentilatorSettings:
        return self.simulation.pending_settings or self.simulation.settings

    def _tick(self) -> None:
        settings_applied = False
        if not self.paused:
            for _ in range(self.samples_per_render):
                had_pending_settings = self.simulation.pending_settings is not None
                sample = self.simulation.step(self.dt_s)
                if had_pending_settings and self.simulation.pending_settings is None:
                    settings_applied = True
                self._record_metrics(sample)
                self.buffers["pressure"].append(sample.time_s, sample.pressure_cm_h2o)
                self.buffers["flow"].append(sample.time_s, sample.flow_l_min)
                self.buffers["volume"].append(sample.time_s, sample.volume_ml)
                self.buffers["co2"].append(sample.time_s, sample.co2_kpa)

        if settings_applied:
            self.message = "Ventilator settings applied"

        self._refresh_waveforms()
        self._refresh_static_panels()

    def _record_metrics(self, sample: SimulationSample) -> None:
        if self.metrics.current_breath != sample.breath:
            if self.metrics.current_breath is not None:
                self._finalize_current_breath()

            self.metrics.current_breath = sample.breath
            self.metrics.current_min_volume_ml = sample.volume_ml
            self.metrics.current_max_volume_ml = sample.volume_ml
            self.metrics.current_peak_pressure_cm_h2o = sample.pressure_cm_h2o
            self.metrics.current_etco2_kpa = sample.co2_kpa
            return

        self.metrics.current_min_volume_ml = min(
            self.metrics.current_min_volume_ml,
            sample.volume_ml,
        )
        self.metrics.current_max_volume_ml = max(
            self.metrics.current_max_volume_ml,
            sample.volume_ml,
        )
        self.metrics.current_peak_pressure_cm_h2o = max(
            self.metrics.current_peak_pressure_cm_h2o,
            sample.pressure_cm_h2o,
        )
        self.metrics.current_etco2_kpa = max(
            self.metrics.current_etco2_kpa,
            sample.co2_kpa,
        )

    def _finalize_current_breath(self) -> None:
        vt_ml = max(
            0.0,
            self.metrics.current_max_volume_ml - self.metrics.current_min_volume_ml,
        )
        self.metrics.completed_vt_ml = vt_ml
        self.metrics.completed_minute_volume_l_min = (
            vt_ml * self.simulation.settings.rr_bpm / 1000.0
        )
        self.metrics.completed_peak_pressure_cm_h2o = (
            self.metrics.current_peak_pressure_cm_h2o
        )
        self.metrics.completed_etco2_kpa = self.metrics.current_etco2_kpa

    def _refresh_waveforms(self) -> None:
        earliest = self.simulation.time_s - self.visible_window_s
        for name, widget in self.waveforms.items():
            widget.update_points(
                self.buffers[name].points_since(earliest),
                window_start_s=earliest,
                window_end_s=self.simulation.time_s,
            )

    def _refresh_static_panels(self) -> None:
        settings = self.simulation.settings
        pending = self.simulation.pending_settings
        patient = self.simulation.patient
        state = "PAUSED" if self.paused else "RUNNING"

        if self.titlebar is not None:
            self.titlebar.update(
                "bellows  |  terminal ventilation simulator  |  educational use only"
            )

        if self.status is not None:
            pending_note = "no pending changes"
            if pending is not None:
                pending_note = (
                    f"pending {pending.mode}  "
                    f"RR {pending.rr_bpm:.0f}  "
                    f"PEEP {pending.peep_cm_h2o:.0f}  "
                    f"I:E {pending.ie_i:.0f}:{pending.ie_e:g}"
                )
            self.status.update(
                "\n".join(
                    [
                        (
                            f"{state}  t={self.simulation.time_s:5.1f}s  "
                            f"breath {self.simulation.breath:03d}  "
                            f"{pending_note}"
                        ),
                        (
                            f"{self.message}  |  up/down select  left/right adjust  "
                            "enter toggle  space pause  tab panel  r reset  q quit"
                        ),
                    ]
                )
            )

        if self.numerics is not None:
            self.numerics.update(self._numerics_renderable())

        if self.sidebar is not None:
            pending_target_lines = []
            if pending is not None:
                pending_target = self._target_status(pending)
                if pending_target != self._target_status(settings):
                    pending_target_lines.append(
                        (
                            "  Pending    "
                            f"[#f4f7f5]{pending_target}[/]"
                        )
                    )

            sidebar_markup = "\n".join(
                [
                    "[bold #8fa69d]VENTILATOR[/]",
                    self._control_row(
                        "mode",
                        "Mode",
                        self._mode_text(settings, pending),
                    ),
                    self._control_row(
                        "target",
                        "Target",
                        self._target_status(settings),
                    ),
                    *pending_target_lines,
                    self._control_row(
                        "rr",
                        "RR",
                        self._setting_text(
                            settings.rr_bpm,
                            pending.rr_bpm if pending else None,
                            " /min",
                        ),
                    ),
                    self._control_row(
                        "peep",
                        "PEEP",
                        self._setting_text(
                            settings.peep_cm_h2o,
                            pending.peep_cm_h2o if pending else None,
                            " cmH2O",
                        ),
                    ),
                    self._control_row(
                        "ie",
                        "I:E",
                        self._ie_text(settings.ie_e, pending.ie_e if pending else None),
                    ),
                    "",
                    "[bold #8fa69d]PATIENT[/]",
                    self._control_row(
                        "compliance",
                        "Compliance",
                        f"{patient.compliance_l_per_cm_h2o * 1000:.0f} mL/cmH2O",
                    ),
                    self._control_row(
                        "resistance",
                        "Resistance",
                        f"{patient.resistance_cm_h2o_s_per_l:.0f} cmH2O*s/L",
                    ),
                    f"  EtCO2      [#f4f7f5]{patient.etco2_kpa:.1f} kPa[/]",
                    "",
                    "[bold #8fa69d]WAVEFORMS[/]",
                    self._control_row(
                        "pressure",
                        "Pressure",
                        self._visible_text("pressure"),
                    ),
                    self._control_row(
                        "flow",
                        "Flow",
                        self._visible_text("flow"),
                    ),
                    self._control_row(
                        "volume",
                        "Volume",
                        self._visible_text("volume"),
                    ),
                    self._control_row(
                        "co2",
                        "CO2",
                        self._visible_text("co2"),
                    ),
                    "",
                    "[bold #8fa69d]MODEL[/]",
                    "[#748179]Single compartment lung[/]",
                    "[#748179]Paw = V/C + Flow*R + PEEP[/]",
                    "",
                    "[bold #8fa69d]CONTROLS[/]",
                    "up/down    select",
                    "left/right adjust",
                    "enter      toggle",
                    "space      pause/resume",
                    "tab        show/hide panel",
                    "r          reset",
                    "q          quit",
                ]
            )
            self.sidebar.update(Text.from_markup(sidebar_markup))

    def _control_row(
        self,
        key: str,
        label: str,
        value: str,
    ) -> str:
        selected = key == self._selected_control_key()
        if selected:
            content = f"> {label:<10} {value}"
            return f"[black on #f0b36a]{content[:27]}[/]"
        return f"  {label:<10} [#f4f7f5]{value}[/]"

    def _numerics_renderable(self) -> Text:
        values = [
            (
                "Ppeak",
                self._format_metric(self.metrics.completed_peak_pressure_cm_h2o, 0, 4),
                "cmH2O",
                "#f5c451",
            ),
            (
                "VT",
                self._format_metric(self.metrics.completed_vt_ml, 0, 4),
                "mL",
                "#72d572",
            ),
            (
                "MV",
                self._format_metric(self.metrics.completed_minute_volume_l_min, 1, 4),
                "L/min",
                "#57c7ff",
            ),
            (
                "EtCO2",
                self._format_metric(self.metrics.completed_etco2_kpa, 1, 4),
                "kPa",
                "#d78cff",
            ),
        ]

        text = Text()
        text.append("MONITOR  last completed breath\n", style="bold #8fa69d")
        for index, (label, value, unit, color) in enumerate(values):
            if index:
                text.append("  ")
            text.append(f"{label} ", style="#8fa69d")
            text.append(value, style=f"bold {color}")
            text.append(f" {unit}", style="#748179")
        return text

    def _format_metric(
        self,
        value: float | None,
        decimals: int,
        width: int,
    ) -> str:
        if value is None:
            return "--".rjust(width)
        return f"{value:>{width}.{decimals}f}"

    def _setting_text(
        self,
        active: float,
        pending: float | None,
        unit: str,
    ) -> str:
        active_text = f"{active:g}"
        if pending is None or pending == active:
            return f"{active_text}{unit}"
        return f"{active_text} -> {pending:g}{unit}"

    def _mode_text(
        self,
        active: VentilatorSettings,
        pending: VentilatorSettings | None,
    ) -> str:
        if pending is None or pending.mode == active.mode:
            return active.mode
        return f"{active.mode} -> {pending.mode}"

    def _target_status(self, settings: VentilatorSettings) -> str:
        if settings.mode == "PCV":
            return f"Pinsp {settings.pinsp_cm_h2o:.0f} cmH2O"
        return f"VT {settings.vt_ml:.0f} mL"

    def _visible_text(self, waveform: str) -> str:
        return "shown" if self.waveform_visible[waveform] else "hidden"

    def _waveform_label(self, waveform: str) -> str:
        labels = {
            "pressure": "Pressure",
            "flow": "Flow",
            "volume": "Volume",
            "co2": "CO2",
        }
        return labels[waveform]

    def _ie_text(self, active_e: float, pending_e: float | None) -> str:
        active_text = f"1:{active_e:g}"
        if pending_e is None or pending_e == active_e:
            return active_text
        return f"{active_text} -> 1:{pending_e:g}"


def main() -> None:
    BellowsApp().run()


if __name__ == "__main__":
    main()
