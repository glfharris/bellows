# bellows

*A terminal-based ventilation simulator and waveform visualiser for anaesthesia and ICU education.*

`bellows` is a Python TUI for exploring mechanical ventilation waveforms in real time. It simulates a single-compartment lung with selectable pressure-volume mechanics and renders ventilator traces directly in the terminal.

It is intended for education, demonstration, and experimentation. It is **not** clinical software — see [Safety and scope](#safety-and-scope).

> Mechanical ventilation in your terminal.

![](bellows.webp)

---

## Running

```bash
uv run bellows
```

Python 3.13+ via `uv`. Dependencies (Textual) are pulled in automatically.

Startup options can seed the interactive simulator:

```bash
uv run bellows --mode PRVC --vt 450 --rr 16 --peep 8
uv run bellows tui --mode APRV --p-high 26 --p-low 5 --t-high 4 --t-low 0.6
```

---

## Controls

The left panel is the main control surface.

| Key              | Action                                                                   |
| ---------------- | ------------------------------------------------------------------------ |
| `up` / `down`    | Select a row in the left control panel                                   |
| `left` / `right` | Decrease / increase the selected setting                                 |
| `enter`          | Open a picker, or toggle the selected row (mode, preset, waveform, ...)  |
| `space`          | Pause / resume                                                           |
| `tab`            | Show / hide the left control panel                                       |
| `r`              | Reset simulation                                                         |
| `q`              | Quit                                                                     |

Ventilator setting changes are queued and applied at the next breath boundary, so changing mode or any ventilator setting does not distort the current breath mid-cycle. Patient parameter changes (lung model, compliance, resistance, presets) take effect immediately.

---

## Ventilator modes

| Mode  | What it does                                                                                                                                                       | Adjustable settings                  |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------ |
| VCV   | Volume control. Fixed inspiratory flow delivers the configured tidal volume.                                                                                       | `VT`, `RR`, `PEEP`, `I:E`            |
| PCV   | Pressure control. Decelerating flow toward a target inspiratory pressure above PEEP.                                                                               | `Pinsp`, `RR`, `PEEP`, `I:E`         |
| PRVC  | Pressure-regulated volume control. PCV-shaped breath; applied Pinsp adapts each breath to track a target VT. The applied Pinsp is shown next to the VT target.     | `VT` (target), `RR`, `PEEP`, `I:E`   |
| APRV  | Airway pressure release. Pressure alternates between `P_high` (held for `T_high`) and a brief release to `P_low` (for `T_low`). **Passive** — no spontaneous effort is modelled yet, so the trace shows only the mandatory pressure swings. | `P_high`, `P_low`, `T_high`, `T_low` |

---

## Patient model

The simulation uses a single-compartment lung driven by

```text
Paw = P_elastic(V, phase) + R * Flow
```

`P_elastic(V)` is the lung's *absolute* elastic recoil at volume `V`. PEEP is the airway pressure the ventilator holds at end-expiration; the lung settles to whatever volume satisfies `P_elastic(V_eq) = PEEP`. The volume trace shows absolute lung volume, so raising PEEP visibly shifts the trace baseline up (recruitment) and the operating point onto a different part of the PV curve.

### Lung models

| Model       | `P_elastic`                                  | What it's useful for                                                                                              |
| ----------- | -------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| Linear      | `V / C`                                      | Constant compliance, straight PV loop. Simplest model and the default.                                            |
| Venegas     | sigmoid `V(P) = a + b/(1 + exp(-(P-c)/d))`   | Lower inflection (recruitment) and upper plateau (overdistension). Driving pressure, "best PEEP", protective vent. |
| Venegas+H   | Venegas sigmoid + inflation/deflation offset | Adds hysteresis between limbs. Surfactant-deficient teaching cases, deflation-limb PEEP titration.                |

Live-edit parameters depend on the selected model:

| Model     | Live parameters                                   |
| --------- | ------------------------------------------------- |
| Linear    | compliance                                        |
| Venegas   | inflection, slope, recruitable volume             |
| Venegas+H | inflection, slope, recruitable volume, hysteresis |

Resistance and a patient preset are available across all models. Each model carries its own preset list (Linear: Normal / Stiff / Restrictive / Obstructed / Severe obstruction; Venegas variants add Recruitable ARDS / Non-recruitable ARDS / Surfactant-deficient). Manual edits change the displayed preset to `Custom`.

CO2 is a simplified capnography trace with EtCO2 shown in kPa — enough to make waveform changes plausible, not a complete model.

---

## Waveforms and numerics

Waveforms (fixed time axis, fixed y-axis ranges, smoother braille-cell rendering, selectable visibility, one-shot scale fit):

- pressure, cmH2O
- flow, L/min
- volume, mL (absolute)
- CO2, kPa — optional, hidden by default

Monitor numerics, computed from the last completed breath:

- `Ppeak` (cmH2O)
- `VT` (mL)
- `MV` (L/min) — uses the actual cycle length, so APRV's minute volume is correct
- `EtCO2` (kPa)

---

## Architecture

The simulation is decoupled from the UI so it can evolve independently.

```text
bellows/
    app.py                      Textual application and UI state

    simulation/
        engine.py               simulation loop, breath timing, stats
        state.py                settings, patient mechanics, samples
        lung_model.py           Linear / Venegas / Venegas+H
        presets.py              per-model patient presets

    ventilator/
        modes/
            base.py             VentilatorMode base, helpers, LastBreathStats
            vcv.py              volume control
            pcv.py              pressure control
            prvc.py             pressure-regulated volume control
            aprv.py             passive airway pressure release

    waveforms/
        buffers.py              timestamped rolling trace buffers

    ui/
        waveform.py             terminal waveform renderer

tests/
    helpers.py                  shared simulation test helpers
    modes/
        test_modes.py           directional tests for VCV / PCV / PRVC / APRV
    simulation/
        test_lung_model.py      lung-model and PEEP-recruitment tests
        test_state.py           settings, reset, and patient preset contracts
```

Design choices:

- simulation tick and render refresh are decoupled
- waveform buffers store timestamped samples; the UI observes them rather than owning physiology
- ventilator modes carry their own per-breath state via `on_activate` / `on_breath_end` hooks
- ventilator setting changes queue and apply at breath boundaries; patient changes apply immediately
- lung mechanics are pluggable behind a `LungModel` protocol

---

## Safety and scope

`bellows` is an educational simulator. It must not be used for:

- clinical decision-making
- ventilator setup
- patient monitoring
- diagnosis
- treatment recommendations

---

## Development

Run the test suite:

```bash
uv run python -m unittest discover tests
```

Quick compile check:

```bash
uv run python -m compileall bellows tests
```

Planned work, known limitations, and future-feature notes live in [TODO.md](TODO.md).
