"""Textual application entry point."""

from __future__ import annotations

from dataclasses import dataclass, replace

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, OptionList, Static

from bellows.simulation.engine import VentilationSimulation
from bellows.simulation.lung_model import (
    LinearLung,
    LungModel,
    VenegasHysteresisLung,
    VenegasLung,
)
from bellows.simulation.presets import (
    LUNG_MODELS,
    PatientPreset,
    presets_for,
)
from bellows.simulation.metrics import BreathMetricsTracker
from bellows.simulation.state import (
    PatientMechanics,
    SimulationSample,
    VentilatorSettings,
)
from bellows.ventilator.registry import VENTILATOR_MODES
from bellows.waveforms.buffers import TraceBuffer
from bellows.ui.waveform import WaveformSpec, WaveformWidget


@dataclass(frozen=True)
class ControlRow:
    key: str
    label: str


@dataclass(frozen=True)
class ControlAction:
    method_name: str
    args: tuple[object, ...] = ()


@dataclass(frozen=True)
class ControlDefinition:
    key: str
    label: str
    decrease: ControlAction | None = None
    increase: ControlAction | None = None
    activate: ControlAction | None = None
    adjust_message: str | None = None

    def row(self) -> ControlRow:
        return ControlRow(self.key, self.label)


def _action(method_name: str, *args: object) -> ControlAction:
    return ControlAction(method_name, args)


CONTROL_DEFINITIONS: dict[str, ControlDefinition] = {
    "mode": ControlDefinition(
        "mode",
        "Mode",
        activate=_action("_open_mode_picker"),
        adjust_message="Mode: press enter to choose",
    ),
    "target": ControlDefinition(
        "target",
        "Target",
        decrease=_action("action_target_down"),
        increase=_action("action_target_up"),
    ),
    "rr": ControlDefinition(
        "rr",
        "RR",
        decrease=_action("action_rr_down"),
        increase=_action("action_rr_up"),
    ),
    "peep": ControlDefinition(
        "peep",
        "PEEP",
        decrease=_action("action_peep_down"),
        increase=_action("action_peep_up"),
    ),
    "ie": ControlDefinition(
        "ie",
        "I:E",
        decrease=_action("action_ie_shorter"),
        increase=_action("action_ie_longer"),
    ),
    "p_high": ControlDefinition(
        "p_high",
        "P_high",
        decrease=_action("action_p_high_down"),
        increase=_action("action_p_high_up"),
    ),
    "p_low": ControlDefinition(
        "p_low",
        "P_low",
        decrease=_action("action_p_low_down"),
        increase=_action("action_p_low_up"),
    ),
    "t_high": ControlDefinition(
        "t_high",
        "T_high",
        decrease=_action("action_t_high_down"),
        increase=_action("action_t_high_up"),
    ),
    "t_low": ControlDefinition(
        "t_low",
        "T_low",
        decrease=_action("action_t_low_down"),
        increase=_action("action_t_low_up"),
    ),
    "lung_model": ControlDefinition(
        "lung_model",
        "Lung model",
        activate=_action("_open_lung_model_picker"),
        adjust_message="Lung model: press enter to choose",
    ),
    "preset": ControlDefinition(
        "preset",
        "Preset",
        activate=_action("_open_patient_preset_picker"),
        adjust_message="Preset: press enter to choose",
    ),
    "compliance": ControlDefinition(
        "compliance",
        "Compliance",
        decrease=_action("action_compliance_down"),
        increase=_action("action_compliance_up"),
    ),
    "inflection": ControlDefinition(
        "inflection",
        "Inflection",
        decrease=_action("action_inflection_down"),
        increase=_action("action_inflection_up"),
    ),
    "slope": ControlDefinition(
        "slope",
        "Slope",
        decrease=_action("action_slope_down"),
        increase=_action("action_slope_up"),
    ),
    "recruitable": ControlDefinition(
        "recruitable",
        "Recruitable",
        decrease=_action("action_recruitable_down"),
        increase=_action("action_recruitable_up"),
    ),
    "hysteresis": ControlDefinition(
        "hysteresis",
        "Hysteresis",
        decrease=_action("action_hysteresis_down"),
        increase=_action("action_hysteresis_up"),
    ),
    "resistance": ControlDefinition(
        "resistance",
        "Resistance",
        decrease=_action("action_resistance_down"),
        increase=_action("action_resistance_up"),
    ),
    "autoscale": ControlDefinition(
        "autoscale",
        "Fit scales",
        decrease=_action("_fit_waveform_scales"),
        increase=_action("_fit_waveform_scales"),
        activate=_action("_fit_waveform_scales"),
    ),
    "pressure": ControlDefinition(
        "pressure",
        "Pressure",
        decrease=_action("_toggle_waveform", "pressure"),
        increase=_action("_toggle_waveform", "pressure"),
        activate=_action("_toggle_waveform", "pressure"),
    ),
    "flow": ControlDefinition(
        "flow",
        "Flow",
        decrease=_action("_toggle_waveform", "flow"),
        increase=_action("_toggle_waveform", "flow"),
        activate=_action("_toggle_waveform", "flow"),
    ),
    "volume": ControlDefinition(
        "volume",
        "Volume",
        decrease=_action("_toggle_waveform", "volume"),
        increase=_action("_toggle_waveform", "volume"),
        activate=_action("_toggle_waveform", "volume"),
    ),
    "co2": ControlDefinition(
        "co2",
        "CO2 trace",
        decrease=_action("_toggle_waveform", "co2"),
        increase=_action("_toggle_waveform", "co2"),
        activate=_action("_toggle_waveform", "co2"),
    ),
}

CONVENTIONAL_SETTING_CONTROLS = ("target", "rr", "peep", "ie")
APRV_SETTING_CONTROLS = ("p_high", "p_low", "t_high", "t_low")
VENEGAS_PATIENT_CONTROLS = ("inflection", "slope", "recruitable")
WAVEFORM_CONTROLS = ("autoscale", "pressure", "flow", "volume", "co2")


class ChoiceModal(ModalScreen[str | None]):
    """Small modal picker for settings with discrete choices."""

    CSS = """
    ChoiceModal {
        align: center middle;
    }

    #choice-dialog {
        width: 38;
        height: auto;
        background: #0d1412;
        border: solid #f0b36a;
        padding: 1;
    }

    #choice-title {
        height: 1;
        color: #f0b36a;
        text-style: bold;
    }

    #choice-help {
        height: 1;
        color: #748179;
    }

    OptionList {
        height: auto;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(
        self,
        title: str,
        choices: list[str],
        *,
        current_index: int = 0,
    ) -> None:
        super().__init__()
        self.title_text = title
        self.choices = choices
        self.current_index = current_index
        self.option_list: OptionList | None = None

    def compose(self) -> ComposeResult:
        with Container(id="choice-dialog"):
            yield Static(self.title_text, id="choice-title")
            self.option_list = OptionList(*self.choices, id="choice-options")
            yield self.option_list
            yield Static("up/down select  enter choose  esc cancel", id="choice-help")

    def on_mount(self) -> None:
        if self.option_list is not None:
            self.option_list.highlighted = self.current_index
            self.option_list.focus()

    def on_option_list_option_selected(
        self,
        event: OptionList.OptionSelected,
    ) -> None:
        event.stop()
        self.dismiss(self.choices[event.option_index])

    def action_cancel(self) -> None:
        self.dismiss(None)


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

    def __init__(
        self,
        simulation: VentilationSimulation | None = None,
        patient_preset_name: str | None = None,
    ) -> None:
        super().__init__()
        self.title = "bellows"
        self.sub_title = "ventilation education simulator"
        self.simulation = simulation or VentilationSimulation()
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
        self.control_rows: list[ControlRow] = []
        self._rebuild_control_rows()
        self.selected_control_index = 0
        self.patient_preset_name = (
            patient_preset_name or self._matching_patient_preset_name()
        )
        self.patient_preset_index = self._patient_preset_index(
            self.patient_preset_name
        )
        self.metrics = BreathMetricsTracker(minimum_duration_s=self.dt_s)
        self.message = "Ready"

    def compose(self) -> ComposeResult:
        yield Static(id="titlebar")
        with Horizontal(id="shell"):
            yield Static(id="sidebar")
            with Vertical(id="monitor"):
                yield Static(id="status")
                yield Static(id="numerics")
                pressure = WaveformWidget(
                    WaveformSpec("Pressure", "cmH2O", "#f5c451", 0.0, 60.0),
                    id="pressure",
                )
                flow = WaveformWidget(
                    WaveformSpec("Flow", "L/min", "#57c7ff", -180.0, 80.0),
                    id="flow",
                )
                volume = WaveformWidget(
                    WaveformSpec("Volume", "mL", "#72d572", 0.0, 1500.0),
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
        definition = CONTROL_DEFINITIONS[key]
        if definition.activate is not None:
            self._run_control_action(definition.activate)
            return

        self.message = f"{definition.label}: use left/right"
        self._refresh_static_panels()

    def action_reset(self) -> None:
        self.simulation.reset()
        for buffer in self.buffers.values():
            buffer.clear()
        self.metrics = BreathMetricsTracker(minimum_duration_s=self.dt_s)
        self.message = "Simulation reset"
        self._refresh_waveforms()
        self._refresh_static_panels()

    def action_toggle_mode(self) -> None:
        settings = self._editable_settings()
        current = (
            settings.mode
            if settings.mode in VENTILATOR_MODES
            else VENTILATOR_MODES[0]
        )
        next_mode = VENTILATOR_MODES[
            (VENTILATOR_MODES.index(current) + 1) % len(VENTILATOR_MODES)
        ]
        self._set_settings(replace(settings, mode=next_mode), f"Mode {next_mode}")

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
        self._nudge_linear_compliance(-0.005)

    def action_compliance_up(self) -> None:
        self._nudge_linear_compliance(0.005)

    def _nudge_linear_compliance(self, delta: float) -> None:
        patient = self.simulation.patient
        if not isinstance(patient.lung_model, LinearLung):
            self.message = "Compliance is fixed: lung model is non-linear"
            self._refresh_static_panels()
            return
        value = max(0.01, min(0.12, patient.lung_model.compliance_l_per_cm_h2o + delta))
        self._set_patient(
            replace(patient, lung_model=LinearLung(compliance_l_per_cm_h2o=value)),
            f"Compliance {value * 1000:.0f} mL/cmH2O",
        )

    def action_inflection_down(self) -> None:
        self._nudge_venegas("inflection_cm_h2o", -1.0, 5.0, 40.0, "Inflection", " cmH2O")

    def action_inflection_up(self) -> None:
        self._nudge_venegas("inflection_cm_h2o", 1.0, 5.0, 40.0, "Inflection", " cmH2O")

    def action_slope_down(self) -> None:
        self._nudge_venegas("slope_width_cm_h2o", -0.5, 2.0, 15.0, "Slope", " cmH2O")

    def action_slope_up(self) -> None:
        self._nudge_venegas("slope_width_cm_h2o", 0.5, 2.0, 15.0, "Slope", " cmH2O")

    def action_recruitable_down(self) -> None:
        self._nudge_venegas(
            "recruitable_volume_l", -0.1, 0.3, 2.5, "Recruitable", " L",
        )

    def action_recruitable_up(self) -> None:
        self._nudge_venegas(
            "recruitable_volume_l", 0.1, 0.3, 2.5, "Recruitable", " L",
        )

    def action_hysteresis_down(self) -> None:
        self._nudge_venegas(
            "hysteresis_offset_cm_h2o", -0.5, 0.0, 10.0, "Hysteresis", " cmH2O",
        )

    def action_hysteresis_up(self) -> None:
        self._nudge_venegas(
            "hysteresis_offset_cm_h2o", 0.5, 0.0, 10.0, "Hysteresis", " cmH2O",
        )

    def _nudge_venegas(
        self,
        field_name: str,
        delta: float,
        low: float,
        high: float,
        label: str,
        unit: str,
    ) -> None:
        patient = self.simulation.patient
        lung = patient.lung_model
        if not isinstance(lung, (VenegasLung, VenegasHysteresisLung)):
            self.message = f"{label} only applies to Venegas lung models"
            self._refresh_static_panels()
            return
        if field_name == "hysteresis_offset_cm_h2o" and not isinstance(
            lung, VenegasHysteresisLung
        ):
            self.message = "Hysteresis only applies to Venegas+H"
            self._refresh_static_panels()
            return
        current = getattr(lung, field_name)
        value = max(low, min(high, current + delta))
        new_lung = replace(lung, **{field_name: value})
        formatted = f"{value:.1f}" if abs(delta) < 1.0 else f"{value:.0f}"
        self._set_patient(
            replace(patient, lung_model=new_lung),
            f"{label} {formatted}{unit}",
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

    def action_p_high_down(self) -> None:
        settings = self._editable_settings()
        value = max(settings.p_low_cm_h2o + 1.0, settings.p_high_cm_h2o - 1.0)
        self._set_settings(
            replace(settings, p_high_cm_h2o=value),
            f"P_high {value:.0f} cmH2O",
        )

    def action_p_high_up(self) -> None:
        settings = self._editable_settings()
        value = min(50.0, settings.p_high_cm_h2o + 1.0)
        self._set_settings(
            replace(settings, p_high_cm_h2o=value),
            f"P_high {value:.0f} cmH2O",
        )

    def action_p_low_down(self) -> None:
        settings = self._editable_settings()
        value = max(0.0, settings.p_low_cm_h2o - 1.0)
        self._set_settings(
            replace(settings, p_low_cm_h2o=value),
            f"P_low {value:.0f} cmH2O",
        )

    def action_p_low_up(self) -> None:
        settings = self._editable_settings()
        value = min(settings.p_high_cm_h2o - 1.0, settings.p_low_cm_h2o + 1.0)
        self._set_settings(
            replace(settings, p_low_cm_h2o=value),
            f"P_low {value:.0f} cmH2O",
        )

    def action_t_high_down(self) -> None:
        settings = self._editable_settings()
        value = max(0.5, settings.t_high_s - 0.5)
        self._set_settings(
            replace(settings, t_high_s=value),
            f"T_high {value:.1f} s",
        )

    def action_t_high_up(self) -> None:
        settings = self._editable_settings()
        value = min(10.0, settings.t_high_s + 0.5)
        self._set_settings(
            replace(settings, t_high_s=value),
            f"T_high {value:.1f} s",
        )

    def action_t_low_down(self) -> None:
        settings = self._editable_settings()
        value = max(0.2, settings.t_low_s - 0.1)
        self._set_settings(
            replace(settings, t_low_s=value),
            f"T_low {value:.1f} s",
        )

    def action_t_low_up(self) -> None:
        settings = self._editable_settings()
        value = min(2.0, settings.t_low_s + 0.1)
        self._set_settings(
            replace(settings, t_low_s=value),
            f"T_low {value:.1f} s",
        )

    def _adjust_selected_control(self, direction: int) -> None:
        key = self._selected_control_key()
        definition = CONTROL_DEFINITIONS[key]
        action = definition.decrease if direction < 0 else definition.increase
        if action is not None:
            self._run_control_action(action)
            return

        self.message = definition.adjust_message or f"{definition.label}: use enter"
        self._refresh_static_panels()

    def _run_control_action(self, action: ControlAction) -> None:
        method = getattr(self, action.method_name)
        method(*action.args)

    def _selected_control_key(self) -> str:
        return self.control_rows[self.selected_control_index].key

    def _rebuild_control_rows(self) -> None:
        """Build the sidebar row list from current vent mode + lung model.

        APRV swaps target/rr/peep/ie for p_high/p_low/t_high/t_low. The
        patient section shows model-appropriate rows (Compliance for Linear;
        Inflection/Slope/Recruitable for Venegas; plus Hysteresis offset for
        the hysteresis variant). On rebuild we preserve the selected row by
        key when possible.
        """

        previous_key = (
            self.control_rows[self.selected_control_index].key
            if self.control_rows
            else "mode"
        )

        settings = self._editable_settings()
        mode = settings.mode
        lung_model_name = self.simulation.patient.lung_model.name

        rows: list[ControlRow] = [CONTROL_DEFINITIONS["mode"].row()]
        if mode == "APRV":
            rows.extend(self._control_rows_for(APRV_SETTING_CONTROLS))
        else:
            rows.extend(self._control_rows_for(CONVENTIONAL_SETTING_CONTROLS))

        rows.extend(self._control_rows_for(("lung_model", "preset")))
        if lung_model_name == "Linear":
            rows.append(CONTROL_DEFINITIONS["compliance"].row())
        else:
            rows.extend(self._control_rows_for(VENEGAS_PATIENT_CONTROLS))
            if lung_model_name == "Venegas+H":
                rows.append(CONTROL_DEFINITIONS["hysteresis"].row())
        rows.append(CONTROL_DEFINITIONS["resistance"].row())

        rows.extend(self._control_rows_for(WAVEFORM_CONTROLS))
        self.control_rows = rows

        for index, row in enumerate(rows):
            if row.key == previous_key:
                self.selected_control_index = index
                return
        self.selected_control_index = 0

    def _control_rows_for(self, keys: tuple[str, ...]) -> list[ControlRow]:
        return [CONTROL_DEFINITIONS[key].row() for key in keys]

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

    def _fit_waveform_scales(self) -> None:
        for widget in self.waveforms.values():
            widget.fit_scale_to_points()
        self.message = "Waveform scales fitted"
        self._refresh_waveforms()
        self._refresh_static_panels()

    def _open_mode_picker(self) -> None:
        settings = self._editable_settings()
        choices = list(VENTILATOR_MODES)
        current_index = choices.index(settings.mode) if settings.mode in choices else 0
        self.push_screen(
            ChoiceModal("Ventilator mode", choices, current_index=current_index),
            self._select_mode,
        )

    def _select_mode(self, mode: str | None) -> None:
        if mode is None:
            self.message = "Mode unchanged"
            self._refresh_static_panels()
            return

        settings = self._editable_settings()
        if mode == settings.mode:
            self.message = f"Mode already {mode}"
            self._refresh_static_panels()
            return
        self._set_settings(replace(settings, mode=mode), f"Mode {mode}")

    def _open_patient_preset_picker(self) -> None:
        presets = presets_for(self.simulation.patient.lung_model.name)
        choices = [preset.name for preset in presets]
        current_index = 0
        for index, preset in enumerate(presets):
            if preset.name == self.patient_preset_name:
                current_index = index
                break
        self.push_screen(
            ChoiceModal("Patient preset", choices, current_index=current_index),
            self._select_patient_preset,
        )

    def _select_patient_preset(self, preset_name: str | None) -> None:
        if preset_name is None:
            self.message = "Patient preset unchanged"
            self._refresh_static_panels()
            return

        presets = presets_for(self.simulation.patient.lung_model.name)
        for index, preset in enumerate(presets):
            if preset.name == preset_name:
                self.patient_preset_index = index
                self._apply_patient_preset(preset)
                return

        self.message = "Patient preset unavailable"
        self._refresh_static_panels()

    def _open_lung_model_picker(self) -> None:
        choices = list(LUNG_MODELS)
        current_index = (
            choices.index(self.simulation.patient.lung_model.name)
            if self.simulation.patient.lung_model.name in choices
            else 0
        )
        self.push_screen(
            ChoiceModal("Lung model", choices, current_index=current_index),
            self._select_lung_model,
        )

    def _select_lung_model(self, name: str | None) -> None:
        if name is None:
            self.message = "Lung model unchanged"
            self._refresh_static_panels()
            return
        if name == self.simulation.patient.lung_model.name:
            self.message = f"Lung model already {name}"
            self._refresh_static_panels()
            return
        presets = presets_for(name)
        if not presets:
            self.message = f"No presets for {name}"
            self._refresh_static_panels()
            return
        self.patient_preset_index = 0
        self._apply_patient_preset(presets[0])
        self.message = f"Lung model {name}"
        self._refresh_static_panels()

    def _apply_patient_preset(self, preset: PatientPreset) -> None:
        previous_model = self.simulation.patient.lung_model.name
        self.patient_preset_name = preset.name
        self.simulation.patient = preset.mechanics
        if preset.mechanics.lung_model.name != previous_model:
            self._rebuild_control_rows()
        self.message = f"Patient preset {preset.name}"
        self._refresh_static_panels()

    def _matching_patient_preset_name(self) -> str:
        for preset in presets_for(self.simulation.patient.lung_model.name):
            if preset.mechanics == self.simulation.patient:
                return preset.name
        return "Custom"

    def _patient_preset_index(self, preset_name: str) -> int:
        presets = presets_for(self.simulation.patient.lung_model.name)
        for index, preset in enumerate(presets):
            if preset.name == preset_name:
                return index
        return 0

    def _set_settings(self, settings: VentilatorSettings, message: str) -> None:
        previous_mode = self._editable_settings().mode
        self.simulation.queue_settings(settings)
        if settings.mode != previous_mode:
            self._rebuild_control_rows()
        self.message = f"{message} queued for next breath"
        self._refresh_static_panels()

    def _set_patient(self, patient: PatientMechanics, message: str) -> None:
        previous_model = self.simulation.patient.lung_model.name
        self.simulation.patient = patient
        self.patient_preset_name = "Custom"
        if patient.lung_model.name != previous_model:
            self._rebuild_control_rows()
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
        self.metrics.observe(sample)

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
                pending_note = f"pending {pending.mode}  {self._pending_summary(pending)}"
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
                            "enter choose/toggle  space pause  tab panel  r reset  q quit"
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

            ventilator_section = [
                "[bold #8fa69d]VENTILATOR[/]",
                self._control_row(
                    "mode",
                    "Mode",
                    self._mode_text(settings, pending),
                ),
            ]
            display_mode = pending.mode if pending is not None else settings.mode
            if display_mode == "APRV":
                ventilator_section.extend(self._aprv_rows(settings, pending))
            else:
                ventilator_section.extend(
                    self._conventional_rows(settings, pending, pending_target_lines)
                )

            sidebar_markup = "\n".join(
                [
                    *ventilator_section,
                    "",
                    "[bold #8fa69d]PATIENT[/]",
                    self._control_row(
                        "lung_model",
                        "Lung model",
                        patient.lung_model.name,
                    ),
                    self._control_row(
                        "preset",
                        "Preset",
                        self.patient_preset_name,
                    ),
                    *self._lung_model_rows(patient.lung_model),
                    self._control_row(
                        "resistance",
                        "Resistance",
                        f"{patient.resistance_cm_h2o_s_per_l:.0f} cmH2O*s/L",
                    ),
                    f"  EtCO2      [#f4f7f5]{patient.etco2_kpa:.1f} kPa[/]",
                    "",
                    "[bold #8fa69d]WAVEFORMS[/]",
                    self._control_row(
                        "autoscale",
                        "Fit scales",
                        "now",
                    ),
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
                    "enter      choose/toggle",
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
        if settings.mode == "PRVC":
            applied = self.simulation.modes["PRVC"].applied_pinsp_cm_h2o
            return f"VT {settings.vt_ml:.0f} mL (applied {applied:.0f})"
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

    def _pending_summary(self, pending: VentilatorSettings) -> str:
        if pending.mode == "APRV":
            return (
                f"P_high {pending.p_high_cm_h2o:.0f}  "
                f"P_low {pending.p_low_cm_h2o:.0f}  "
                f"T_high {pending.t_high_s:.1f}  "
                f"T_low {pending.t_low_s:.1f}"
            )
        return (
            f"RR {pending.rr_bpm:.0f}  "
            f"PEEP {pending.peep_cm_h2o:.0f}  "
            f"I:E {pending.ie_i:.0f}:{pending.ie_e:g}"
        )

    def _conventional_rows(
        self,
        settings: VentilatorSettings,
        pending: VentilatorSettings | None,
        pending_target_lines: list[str],
    ) -> list[str]:
        return [
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
        ]

    def _lung_model_rows(self, lung_model: LungModel) -> list[str]:
        if isinstance(lung_model, LinearLung):
            return [
                self._control_row(
                    "compliance",
                    "Compliance",
                    f"{lung_model.compliance_l_per_cm_h2o * 1000:.0f} mL/cmH2O",
                )
            ]
        rows = [
            self._control_row(
                "inflection",
                "Inflection",
                f"{lung_model.inflection_cm_h2o:.0f} cmH2O",
            ),
            self._control_row(
                "slope",
                "Slope",
                f"{lung_model.slope_width_cm_h2o:.1f} cmH2O",
            ),
            self._control_row(
                "recruitable",
                "Recruitable",
                f"{lung_model.recruitable_volume_l * 1000:.0f} mL",
            ),
        ]
        if isinstance(lung_model, VenegasHysteresisLung):
            rows.append(
                self._control_row(
                    "hysteresis",
                    "Hysteresis",
                    f"{lung_model.hysteresis_offset_cm_h2o:.1f} cmH2O",
                )
            )
        return rows

    def _aprv_rows(
        self,
        settings: VentilatorSettings,
        pending: VentilatorSettings | None,
    ) -> list[str]:
        return [
            self._control_row(
                "p_high",
                "P_high",
                self._setting_text(
                    settings.p_high_cm_h2o,
                    pending.p_high_cm_h2o if pending else None,
                    " cmH2O",
                ),
            ),
            self._control_row(
                "p_low",
                "P_low",
                self._setting_text(
                    settings.p_low_cm_h2o,
                    pending.p_low_cm_h2o if pending else None,
                    " cmH2O",
                ),
            ),
            self._control_row(
                "t_high",
                "T_high",
                self._setting_text(
                    settings.t_high_s,
                    pending.t_high_s if pending else None,
                    " s",
                ),
            ),
            self._control_row(
                "t_low",
                "T_low",
                self._setting_text(
                    settings.t_low_s,
                    pending.t_low_s if pending else None,
                    " s",
                ),
            ),
        ]


def main() -> None:
    BellowsApp().run()


if __name__ == "__main__":
    main()
