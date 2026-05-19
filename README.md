# bellows

*A terminal-based ventilation simulator and waveform visualiser for anaesthesia and ICU education.*

`bellows` is a Python TUI for exploring mechanical ventilation waveforms in real time. It simulates a simple single-compartment lung model and renders ventilator traces directly in the terminal.

It is intended for education, demonstration, and experimentation. It is **not** clinical software.

> Mechanical ventilation in your terminal.

---

## Current Status

Early pre-MVP, but runnable.

Current capabilities:

- Textual-based terminal UI
- ICU-ventilator inspired dark interface
- VCV and PCV modes
- pressure, flow, and volume waveforms shown by default
- optional CO2 waveform, hidden by default
- fixed time axis and vertical scale on traces
- one-shot waveform scale fitting
- selectable left control panel
- pause/resume and reset
- live ventilator and patient setting adjustment
- patient mechanics presets
- breath-boundary application for ventilator setting changes
- monitor numerics from the last completed breath:
  - Ppeak
  - VT
  - MV
  - EtCO2

---

## Running Locally

Install dependencies and run with `uv`:

```bash
uv run bellows
```

The project currently targets Python 3.13+.

---

## Controls

The left panel is the main control surface.

| Key | Action |
| --- | --- |
| `up` / `down` | Select a row in the left control panel |
| `left` / `right` | Decrease / increase the selected setting |
| `enter` | Open a picker or toggle the selected row, such as mode, preset, or waveform visibility |
| `space` | Pause / resume |
| `tab` | Show / hide the left control panel |
| `r` | Reset simulation |
| `q` | Quit |

Ventilator setting changes are queued and applied at the next breath boundary, so changing RR, mode, PEEP, I:E, VT, or Pinsp does not distort the current breath mid-cycle.

---

## Ventilator Modes

### VCV

Volume control ventilation uses a fixed inspiratory flow to deliver the configured tidal volume.

Adjustable settings:

- VT
- RR
- PEEP
- I:E

### PCV

Pressure control ventilation uses a target inspiratory pressure above PEEP. Flow decelerates as the simulated lung fills.

Adjustable settings:

- Pinsp
- RR
- PEEP
- I:E

---

## Patient Model

The current model is deliberately simple:

```text
Paw = V / C + Flow * R + PEEP
```

Where:

- `Paw` is airway pressure
- `V` is lung volume above baseline
- `C` is compliance
- `Flow` is airway flow
- `R` is airway resistance
- `PEEP` is positive end-expiratory pressure

Adjustable patient parameters:

- preset
- compliance
- resistance

Built-in presets:

- Normal
- Stiff
- Restrictive
- Obstructed
- Severe obstruction

Manual compliance or resistance edits change the displayed preset to `Custom`.

CO2 is currently a simplified capnography trace with EtCO2 shown in kPa.

This is enough to make waveform changes plausible and useful for exploration, but it is not a physiologically complete model.

---

## Waveforms And Numerics

Waveforms:

- pressure, cmH2O
- flow, L/min
- volume, mL
- CO2, kPa, optional and hidden by default

The waveform view includes:

- rolling fixed-width time axis
- vertical scale
- fixed y-axis ranges with a panel action to fit scales to current traces
- smoother braille-cell trace rendering
- selectable visibility for each waveform

Monitor numerics report the last completed breath:

- `Ppeak`, cmH2O
- `VT`, mL
- `MV`, L/min
- `EtCO2`, kPa

---

## Architecture

The code is split so the simulation can evolve separately from the terminal UI.

```text
bellows/
    app.py                  Textual application and UI state

    simulation/
        engine.py           simulation loop and breath timing
        state.py            settings, patient mechanics, samples

    ventilator/
        modes/
            base.py         shared mode contract and helpers
            vcv.py          volume control ventilation
            pcv.py          pressure control ventilation

    waveforms/
        buffers.py          timestamped rolling trace buffers

    ui/
        waveform.py         terminal waveform renderer
```

Important design choices:

- simulation tick and render refresh are decoupled
- waveform buffers store timestamped samples
- ventilator modes are modular
- setting changes can be queued for breath boundaries
- the UI observes simulation samples rather than owning physiology

---

## Safety And Scope

`bellows` is an educational simulator.

It must not be used for:

- clinical decision-making
- ventilator setup
- patient monitoring
- diagnosis
- treatment recommendations

The app and docs should continue to make this explicit.

---

## TODO

Near-term:

- Add focused tests for simulation mechanics and mode switching
- Improve PCV/VCV transition behavior and pending-setting display
- Add richer patient presets and teaching notes
- Add event injection for bronchospasm, leak, and circuit disconnect
- Add an event log and waveform markers
- Improve layout behavior on narrow terminals
- Decide whether old direct shortcut keys should be removed entirely

Simulation:

- Improve CO2 model and dead-space behavior
- Add spontaneous respiratory effort
- Add leaks and circuit mechanics
- Add intrinsic PEEP and incomplete expiration
- Add plateau pressure and hold manoeuvres
- Add FiO2 as a setting if oxygenation is later modelled

Modes:

- PSV
- CPAP
- SIMV
- PRVC
- NIV / BiPAP-style support

Waveform tools:

- Pressure-volume loops
- Flow-volume loops
- Breath-by-breath trends
- Cursor inspection
- Annotations for setting changes and events
- Export waveform data

Teaching and scenarios:

- Scenario files
- Guided teaching mode
- Example cases
- Replay support

Possible future scenario format:

```yaml
name: Bronchospasm during anaesthesia
patient:
  preset: normal
ventilator:
  mode: VCV
  vt_ml: 500
  rr_bpm: 14
  peep_cm_h2o: 5
events:
  - at_s: 30
    type: bronchospasm
    severity: moderate
```

---

## Development Notes

Useful checks:

```bash
python -m compileall bellows main.py
```

When formal tests are added, they should focus first on directional behavior:

- lower compliance should increase VCV peak pressure
- higher resistance should alter inspiratory and expiratory flow
- higher PEEP should raise baseline pressure
- higher VT should increase delivered volume and pressure in VCV
- higher Pinsp should increase delivered volume in PCV
- queued ventilator settings should apply at the next breath boundary

---

## Licence

TBD.
