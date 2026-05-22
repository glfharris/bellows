# TODO

Tracking for planned work and known limitations. Items move to commits or get closed out as they're addressed.

---

## Near-term

- Improve PCV/VCV transition behaviour and pending-setting display
- Richer patient presets and teaching notes
- Event injection (bronchospasm, leak, circuit disconnect)
- Event log and waveform markers
- Better layout on narrow terminals
- Decide whether the old direct-shortcut keys should be removed entirely

## Simulation

- Improve the CO2 model — dead-space behaviour, mode-aware capnography (current trace assumes a normal inspiratory→expiratory cycle, which is wrong for APRV)
- Spontaneous respiratory effort
- Leaks and circuit mechanics
- Intrinsic PEEP and incomplete expiration
- Plateau pressure and inspiratory hold manoeuvres
- FiO2 as a setting if oxygenation is ever modelled
- Asymmetric hysteresis (currently a simple uniform offset between limbs)
- VCV high-pressure cutoff (Pmax) — real ventilators alarm and cycle to expiration; teaching value for the "VCV is dangerous on stiff lungs" lesson
- Hysteresis lung should switch limbs on flow direction during expiration toward a higher floor (PEEP step-up transients use the wrong limb today)

## Modes

- PSV
- CPAP
- SIMV
- NIV / BiPAP-style support
- Spontaneous effort during APRV release

## Waveform tools

- Pressure-volume loops
- Flow-volume loops
- Breath-by-breath trends
- Cursor inspection
- Annotations for setting changes and events
- Waveform export

## Teaching and scenarios

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

## Tests

Directional behaviours worth covering as the project grows:

- lower compliance should increase VCV peak pressure ✓
- higher resistance should alter inspiratory and expiratory flow ✓
- higher PEEP should raise baseline pressure ✓
- higher VT should increase delivered volume and pressure in VCV ✓
- higher Pinsp should increase delivered volume in PCV ✓
- PRVC applied Pinsp should converge so delivered VT tracks the target ✓
- PRVC applied Pinsp should drop when PEEP recruits a Venegas lung ✓
- APRV pressure should swing between P_low and P_high with the configured timing ✓
- queued ventilator settings should apply at the next breath boundary ✓

Items marked ✓ have at least one corresponding test in `tests/`.
