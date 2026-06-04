let windowSeconds = 12;
const SWEEP_GAP_SECONDS = 0.45;
const buffers = {
  pressure: [],
  flow: [],
  volume: [],
};
const charts = {};
const chartSizes = {};
let currentBreath = 0;
let paused = false;
let pollInFlight = false;
let resizeQueued = false;

const controls = {
  mode: document.querySelector("#mode"),
  vt: document.querySelector("#vt"),
  pinsp: document.querySelector("#pinsp"),
  rr: document.querySelector("#rr"),
  peep: document.querySelector("#peep"),
  pHigh: document.querySelector("#pHigh"),
  pLow: document.querySelector("#pLow"),
  tHigh: document.querySelector("#tHigh"),
  tLow: document.querySelector("#tLow"),
  ieE: document.querySelector("#ieE"),
  riseTime: document.querySelector("#riseTime"),
  expValve: document.querySelector("#expValve"),
  lungModel: document.querySelector("#lungModel"),
  preset: document.querySelector("#preset"),
  compliance: document.querySelector("#compliance"),
  inflection: document.querySelector("#inflection"),
  slope: document.querySelector("#slope"),
  recruitable: document.querySelector("#recruitable"),
  hysteresis: document.querySelector("#hysteresis"),
  resistance: document.querySelector("#resistance"),
};

const chartSpecs = {
  pressure: {
    label: "Pressure",
    unit: "cmH2O",
    range: [0, 40],
    color: "#f5c451",
    anchorZero: true,
    fitStep: 5,
  },
  flow: {
    label: "Flow",
    unit: "L/min",
    range: [-50, 50],
    color: "#57c7ff",
    includeZero: true,
    symmetric: true,
    fitStep: 10,
  },
  volume: {
    label: "Volume",
    unit: "mL",
    range: [0, 1000],
    color: "#72d572",
    anchorZero: true,
    fitStep: 100,
  },
};
const chartRanges = Object.fromEntries(
  Object.entries(chartSpecs).map(([key, spec]) => [key, [...spec.range]]),
);

const colors = {
  pressure: "#f5c451",
  inspiration: "#f5c451",
  previous: "#4d5a54",
};

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

async function postJson(url, payload = {}) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

function appendSample(sample) {
  buffers.pressure.push([sample.time_s, sample.pressure_cm_h2o, sample.breath, sample.phase]);
  buffers.flow.push([sample.time_s, sample.flow_l_min, sample.breath, sample.phase]);
  buffers.volume.push([sample.time_s, sample.volume_ml, sample.breath, sample.phase]);
  currentBreath = sample.breath;
  trimBuffers(sample.time_s - windowSeconds);
}

function trimBuffers(minTime) {
  for (const points of Object.values(buffers)) {
    while (points.length && points[0][0] < minTime) points.shift();
  }
}

function editableSettings(state) {
  return state.pending_settings || state.settings;
}

function syncControls(state) {
  const settings = editableSettings(state);
  document.querySelector("#modeBadge").textContent = state.settings.mode;
  setControlValue(controls.mode, settings.mode);
  setControlValue(controls.vt, settings.vt_ml);
  setControlValue(controls.pinsp, settings.pinsp_cm_h2o);
  setControlValue(controls.rr, settings.rr_bpm);
  setControlValue(controls.peep, settings.peep_cm_h2o);
  setControlValue(controls.pHigh, settings.p_high_cm_h2o);
  setControlValue(controls.pLow, settings.p_low_cm_h2o);
  setControlValue(controls.tHigh, settings.t_high_s);
  setControlValue(controls.tLow, settings.t_low_s);
  setControlValue(controls.ieE, settings.ie_e);
  setControlValue(controls.riseTime, settings.pressure_rise_time_s * 1000.0);
  setControlValue(
    controls.expValve,
    settings.expiratory_valve_resistance_cm_h2o_s_per_l,
  );
  syncPatientControls(state.patient);
  updatePatientSummary(state.patient);
  updateSettingLabels(settings, state.patient);
  updateLabelsFromInputs();
  updateModeControlVisibility(settings.mode);
  const pendingText = state.pending_settings
    ? pendingSummary(state.pending_settings)
    : "None";
  document
    .querySelector("#pendingHeader")
    .closest(".status-item")
    .classList.toggle("pending-active", Boolean(state.pending_settings));
  document.querySelector("#pendingHeader").textContent = pendingText;
  paused = state.paused;
  document.querySelector("#pause").textContent = paused ? "Resume" : "Pause";
}

function setControlValue(control, value) {
  if (document.activeElement === control) return;
  control.value = String(value);
}

function syncPatientControls(patient) {
  replaceOptions(controls.lungModel, patient.lung_models, patient.lung_model);
  replaceOptions(controls.preset, patient.presets, patient.preset);

  const params = patient.lung_parameters;
  setControlValue(controls.resistance, patient.resistance_cm_h2o_s_per_l);
  setControlValue(controls.compliance, params.compliance_ml_per_cm_h2o ?? 50);
  setControlValue(controls.inflection, params.inflection_cm_h2o ?? 18);
  setControlValue(controls.slope, params.slope_width_cm_h2o ?? 5);
  setControlValue(controls.recruitable, params.recruitable_volume_ml ?? 1200);
  setControlValue(controls.hysteresis, params.hysteresis_offset_cm_h2o ?? 3);

  document.querySelector('[data-model-row="compliance"]').hidden = patient.lung_model !== "Linear";
  document.querySelector('[data-model-row="inflection"]').hidden = patient.lung_model === "Linear";
  document.querySelector('[data-model-row="slope"]').hidden = patient.lung_model === "Linear";
  document.querySelector('[data-model-row="recruitable"]').hidden = patient.lung_model === "Linear";
  document.querySelector('[data-model-row="hysteresis"]').hidden = patient.lung_model !== "Venegas+H";
}

function updatePatientSummary(patient) {
  document.querySelector("#patientSummary").textContent = `${patient.lung_model} / ${patient.preset}`;
  document.querySelector("#mechanicsSummary").textContent = patientMechanicsSummary(patient);
}

function patientMechanicsSummary(patient) {
  const params = patient.lung_parameters;
  const resistance = `R ${patient.resistance_cm_h2o_s_per_l.toFixed(0)}`;
  if (patient.lung_model === "Linear") {
    return `${resistance} · C ${(params.compliance_ml_per_cm_h2o ?? 0).toFixed(0)} mL/cmH2O`;
  }
  const recruitable = params.recruitable_volume_ml ?? 0;
  const inflection = params.inflection_cm_h2o ?? 0;
  return `${resistance} · Vrec ${recruitable.toFixed(0)} mL · Pinf ${inflection.toFixed(0)}`;
}

function replaceOptions(select, values, selected) {
  const existing = Array.from(select.options).map((option) => option.value);
  if (existing.join("\n") !== values.join("\n")) {
    select.replaceChildren(...values.map((value) => new Option(value, value)));
  }
  setControlValue(select, selected);
}

function updateSettingLabels(settings, patient) {
  document.querySelector("#vtValue").textContent = `${settings.vt_ml.toFixed(0)} mL`;
  document.querySelector("#pinspValue").textContent = `${settings.pinsp_cm_h2o.toFixed(0)} cmH2O`;
  document.querySelector("#rrValue").textContent = `${settings.rr_bpm.toFixed(0)}/min`;
  document.querySelector("#peepValue").textContent = `${settings.peep_cm_h2o.toFixed(0)} cmH2O`;
  document.querySelector("#pHighValue").textContent = `${settings.p_high_cm_h2o.toFixed(0)} cmH2O`;
  document.querySelector("#pLowValue").textContent = `${settings.p_low_cm_h2o.toFixed(0)} cmH2O`;
  document.querySelector("#tHighValue").textContent = `${settings.t_high_s.toFixed(1)} s`;
  document.querySelector("#tLowValue").textContent = `${settings.t_low_s.toFixed(1)} s`;
  document.querySelector("#ieValue").textContent = `1:${settings.ie_e.toFixed(1).replace(".0", "")}`;
  document.querySelector("#riseTimeValue").textContent = `${(settings.pressure_rise_time_s * 1000.0).toFixed(0)} ms`;
  document.querySelector("#expValveValue").textContent = `${settings.expiratory_valve_resistance_cm_h2o_s_per_l.toFixed(0)} cmH2O*s/L`;
  document.querySelector("#resistanceValue").textContent = `${patient.resistance_cm_h2o_s_per_l.toFixed(0)} cmH2O*s/L`;

  const params = patient.lung_parameters;
  document.querySelector("#complianceValue").textContent = `${(params.compliance_ml_per_cm_h2o ?? 50).toFixed(0)} mL/cmH2O`;
  document.querySelector("#inflectionValue").textContent = `${(params.inflection_cm_h2o ?? 18).toFixed(0)} cmH2O`;
  document.querySelector("#slopeValue").textContent = `${(params.slope_width_cm_h2o ?? 5).toFixed(1)} cmH2O`;
  document.querySelector("#recruitableValue").textContent = `${(params.recruitable_volume_ml ?? 1200).toFixed(0)} mL`;
  document.querySelector("#hysteresisValue").textContent = `${(params.hysteresis_offset_cm_h2o ?? 3).toFixed(1)} cmH2O`;
}

function updateModeControlVisibility(mode) {
  const visibleByMode = {
    VCV: ["vt", "rr", "peep"],
    PCV: ["pinsp", "rr", "peep"],
    PRVC: ["vt", "rr", "peep"],
    APRV: ["pHigh", "pLow", "tHigh", "tLow"],
  };
  const visible = new Set(["mode", ...(visibleByMode[mode] || visibleByMode.VCV)]);
  for (const card of document.querySelectorAll("[data-control-card]")) {
    card.hidden = !visible.has(card.dataset.controlCard);
  }
}

function pendingSummary(settings) {
  if (settings.mode === "APRV") {
    return `${settings.mode} P_high ${settings.p_high_cm_h2o.toFixed(0)}, P_low ${settings.p_low_cm_h2o.toFixed(0)}, T_high ${settings.t_high_s.toFixed(1)}, T_low ${settings.t_low_s.toFixed(1)}`;
  }
  const target = settings.mode === "PCV"
    ? `Pinsp ${settings.pinsp_cm_h2o.toFixed(0)}`
    : `VT ${settings.vt_ml.toFixed(0)}`;
  return `${settings.mode} ${target}, RR ${settings.rr_bpm.toFixed(0)}, PEEP ${settings.peep_cm_h2o.toFixed(0)}`;
}

function updateStatus(state) {
  const sample = state.sample;
  document.querySelector("#clock").textContent = `${sample.time_s.toFixed(1)}s`;
  document.querySelector("#breathStatus").textContent = String(sample.breath).padStart(3, "0");
  document.querySelector("#phaseStatus").textContent = sample.phase === "inspiration" ? "INSP" : "EXP";
  const summary = state.last_breath_summary;
  const previous = state.previous_breath_summary;
  updateMetric("ppeak", summary?.peak_pressure_cm_h2o, previous?.peak_pressure_cm_h2o, 0);
  updateMetric("pmean", summary?.mean_pressure_cm_h2o, previous?.mean_pressure_cm_h2o, 0);
  updateMetric("vte", summary?.vt_ml, previous?.vt_ml, 0);
  updateMetric("mv", summary?.minute_volume_l_min, previous?.minute_volume_l_min, 1);
}

function updateMetric(key, value, previous, decimals) {
  const valueElement = document.querySelector(`#${key}Value`);
  const deltaElement = document.querySelector(`#${key}Delta`);
  if (!Number.isFinite(value)) {
    valueElement.textContent = "--";
    deltaElement.textContent = "";
    deltaElement.className = "";
    return;
  }

  valueElement.textContent = value.toFixed(decimals);
  if (!Number.isFinite(previous)) {
    deltaElement.textContent = "";
    deltaElement.className = "";
    return;
  }

  const delta = value - previous;
  deltaElement.textContent = `(${delta >= 0 ? "+" : ""}${delta.toFixed(decimals)})`;
  deltaElement.className = delta > 0 ? "positive" : delta < 0 ? "negative" : "";
}

function createCharts() {
  for (const [key, spec] of Object.entries(chartSpecs)) {
    const element = document.querySelector(`#${key}`);
    const size = chartElementSize(element);
    chartSizes[key] = size;
    charts[key] = new uPlot(
      {
        width: size.width,
        height: size.height,
        scales: {
          x: { time: false },
          y: { range: () => chartRanges[key] },
        },
        axes: [
          {
            show: true,
            stroke: "#4d5a54",
            grid: { stroke: "#1d2925" },
            size: 0,
            gap: 0,
            ticks: { show: false },
            border: { show: false },
            values: () => [],
          },
          { stroke: "#4d5a54", grid: { stroke: "#1d2925" } },
        ],
        series: [{}, { label: spec.label, stroke: spec.color, width: 2 }],
        cursor: { show: false },
      },
      [[], []],
      element,
    );
    const label = document.createElement("div");
    label.className = "chart-label";
    label.textContent = `${spec.label} (${spec.unit})`;
    element.append(label);
  }

  const observer = new ResizeObserver(() => queueResizeCharts());
  for (const element of document.querySelectorAll(".chart")) observer.observe(element);
}

function queueResizeCharts() {
  if (resizeQueued) return;
  resizeQueued = true;
  requestAnimationFrame(() => {
    resizeQueued = false;
    resizeCharts();
  });
}

function resizeCharts() {
  for (const [key, chart] of Object.entries(charts)) {
    const element = document.querySelector(`#${key}`);
    const size = chartElementSize(element);
    const previous = chartSizes[key];
    if (!previous || previous.width !== size.width || previous.height !== size.height) {
      chartSizes[key] = size;
      chart.setSize(size);
    }
  }
  updateSharedTimeAxis();
  drawPvLoop();
}

function chartElementSize(element) {
  const rect = element.getBoundingClientRect();
  return {
    width: Math.max(120, Math.floor(rect.width - 2)),
    height: Math.max(80, Math.floor(rect.height - 2)),
  };
}

function updateCharts() {
  const latest = latestSampleTime();
  const start = latest - windowSeconds;
  for (const [key, chart] of Object.entries(charts)) {
    const points = buffers[key].filter((point) => point[0] >= start);
    const data = sweepChartData(points, sweepX(latest));
    chart.setData(data);
    chart.setScale("x", { min: 0, max: windowSeconds });
  }
  updateSharedTimeAxis();
  drawPvLoop();
}

function updateSharedTimeAxis() {
  const axis = document.querySelector("#sharedTimeAxis");
  const referenceChart = charts.volume || charts.pressure;
  if (!referenceChart) return;
  const left = referenceChart.bbox.left / devicePixelRatio;
  const width = referenceChart.bbox.width / devicePixelRatio;
  const ticks = [0, 0.25, 0.5, 0.75, 1];
  axis.replaceChildren(
    ...ticks.map((fraction) => {
      const label = document.createElement("span");
      label.style.left = `${left + fraction * width}px`;
      label.textContent = `${(fraction * windowSeconds).toFixed(0)}s`;
      return label;
    }),
  );
}

function sweepChartData(points, cursorS) {
  const byX = new Map();
  for (const point of points) {
    const x = sweepX(point[0]);
    if (!isInSweepGap(x, cursorS)) {
      byX.set(x, point[1]);
    }
  }

  const ordered = [...byX.entries()].sort((a, b) => a[0] - b[0]);
  const xs = [];
  const ys = [];
  for (const [x, y] of ordered) {
    if (xs.length && crossesSweepGap(xs.at(-1), x, cursorS)) {
      xs.push(cursorS);
      ys.push(null);
    }
    xs.push(x);
    ys.push(y);
  }
  return [xs, ys];
}

function sweepX(timeS) {
  return ((timeS % windowSeconds) + windowSeconds) % windowSeconds;
}

function isInSweepGap(x, cursorS) {
  const distance = Math.abs(x - cursorS);
  return Math.min(distance, windowSeconds - distance) <= SWEEP_GAP_SECONDS / 2;
}

function crossesSweepGap(startX, endX, cursorS) {
  if (endX < startX) return true;
  if (cursorS > startX && cursorS < endX) return true;
  const gapStart = cursorS - SWEEP_GAP_SECONDS / 2;
  const gapEnd = cursorS + SWEEP_GAP_SECONDS / 2;
  return gapStart > startX && gapEnd < endX;
}

function fitChartAxes() {
  const latest = latestSampleTime();
  const start = latest - windowSeconds;
  for (const key of Object.keys(charts)) {
    const values = buffers[key]
      .filter((point) => point[0] >= start)
      .map((point) => point[1]);
    if (!values.length) continue;
    chartRanges[key] = fittedRange(values, chartSpecs[key]);
  }
  updateCharts();
}

function resetChartAxes() {
  for (const [key, spec] of Object.entries(chartSpecs)) {
    chartRanges[key] = [...spec.range];
  }
  updateCharts();
}

function fittedRange(values, spec) {
  const low = Math.min(...values);
  const high = Math.max(...values);
  let minimum = low;
  let maximum = high;

  if (spec.anchorZero) minimum = Math.min(0, minimum);
  if (spec.includeZero || spec.symmetric) {
    minimum = Math.min(0, minimum);
    maximum = Math.max(0, maximum);
  }
  if (spec.symmetric) {
    const magnitude = Math.max(Math.abs(minimum), Math.abs(maximum), 1);
    minimum = -magnitude;
    maximum = magnitude;
  }

  const span = maximum - minimum;
  if (span <= 0.001) {
    const pad = Math.max(1, Math.abs(maximum) * 0.1);
    minimum -= pad;
    maximum += pad;
  } else {
    const pad = Math.max(span * 0.10, (spec.range[1] - spec.range[0]) * 0.025);
    minimum -= spec.anchorZero ? 0 : pad;
    maximum += pad;
  }

  if (spec.anchorZero) minimum = 0;
  if (spec.symmetric) {
    const magnitude = Math.max(Math.abs(minimum), Math.abs(maximum));
    minimum = -magnitude;
    maximum = magnitude;
  }
  return niceBounds(minimum, maximum, spec);
}

function niceBounds(minimum, maximum, spec) {
  if (spec.fitStep) {
    let niceMinimum = Math.floor(minimum / spec.fitStep) * spec.fitStep;
    let niceMaximum = Math.ceil(maximum / spec.fitStep) * spec.fitStep;
    if (spec.anchorZero) niceMinimum = 0;
    if (spec.includeZero || spec.symmetric) {
      niceMinimum = Math.min(0, niceMinimum);
      niceMaximum = Math.max(0, niceMaximum);
    }
    if (spec.symmetric) {
      const magnitude = Math.max(
        Math.abs(niceMinimum),
        Math.abs(niceMaximum),
        spec.fitStep,
      );
      niceMinimum = -magnitude;
      niceMaximum = magnitude;
    }
    if (niceMinimum === niceMaximum) niceMaximum = niceMinimum + spec.fitStep;
    return [niceMinimum, niceMaximum];
  }

  const span = Math.max(maximum - minimum, 0.001);
  const step = niceStep(span / 4);
  let niceMinimum = Math.floor(minimum / step) * step;
  let niceMaximum = Math.ceil(maximum / step) * step;

  if (spec.anchorZero) niceMinimum = 0;
  if (spec.includeZero || spec.symmetric) {
    niceMinimum = Math.min(0, niceMinimum);
    niceMaximum = Math.max(0, niceMaximum);
  }
  if (spec.symmetric) {
    const magnitude = Math.max(Math.abs(niceMinimum), Math.abs(niceMaximum), step);
    niceMinimum = -magnitude;
    niceMaximum = magnitude;
  }
  if (niceMinimum === niceMaximum) niceMaximum = niceMinimum + step;
  return [niceMinimum, niceMaximum];
}

function niceStep(value) {
  const exponent = Math.floor(Math.log10(Math.max(value, 0.001)));
  const base = 10 ** exponent;
  const fraction = value / base;
  if (fraction <= 1) return base;
  if (fraction <= 2) return 2 * base;
  if (fraction <= 5) return 5 * base;
  return 10 * base;
}

function resizeCanvas(canvas) {
  const rect = canvas.getBoundingClientRect();
  const scale = window.devicePixelRatio || 1;
  const width = Math.max(1, Math.floor(rect.width * scale));
  const height = Math.max(1, Math.floor(rect.height * scale));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
}

function drawPvLoop() {
  const canvas = document.querySelector("#pv");
  resizeCanvas(canvas);
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#07100e";
  ctx.fillRect(0, 0, width, height);
  drawGrid(ctx, width, height);
  ctx.fillStyle = colors.pressure;
  ctx.font = `${12 * (window.devicePixelRatio || 1)}px ui-sans-serif`;
  ctx.fillText("Volume / Pressure", 14, 22);

  drawBreathLoop(ctx, width, height, currentBreath - 1, colors.previous);
  drawBreathLoop(ctx, width, height, currentBreath, colors.inspiration);
}

function drawBreathLoop(ctx, width, height, breath, color) {
  const volume = buffers.volume.filter((point) => point[2] === breath);
  if (volume.length < 2) return;
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5 * (window.devicePixelRatio || 1);
  ctx.beginPath();
  volume.forEach((volumePoint, index) => {
    const pressurePoint = buffers.pressure.find((point) => point[0] === volumePoint[0]);
    if (!pressurePoint) return;
    const x = map(volumePoint[1], 0, 1200, 34, width - 18);
    const y = map(pressurePoint[1], 0, 50, height - 28, 34);
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
}

function drawGrid(ctx, width, height) {
  ctx.strokeStyle = "#1d2925";
  ctx.lineWidth = window.devicePixelRatio || 1;
  ctx.beginPath();
  for (let i = 1; i < 4; i += 1) {
    const y = (height * i) / 4;
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
  }
  ctx.stroke();
}

function latestSampleTime() {
  return buffers.pressure.at(-1)?.[0] ?? windowSeconds;
}

function map(value, inputMin, inputMax, outputMin, outputMax) {
  const fraction = (value - inputMin) / Math.max(0.001, inputMax - inputMin);
  const bounded = Math.max(0, Math.min(1, fraction));
  return outputMin + bounded * (outputMax - outputMin);
}

async function poll() {
  if (pollInFlight) return;
  pollInFlight = true;
  try {
    const payload = await getJson("/api/samples?seconds=0.05&dt_s=0.01");
    payload.samples.forEach(appendSample);
    syncControls(payload.state);
    updateStatus(payload.state);
    updateCharts();
  } finally {
    pollInFlight = false;
  }
}

function wireControls() {
  controls.mode.addEventListener("change", () => updateSettings({ mode: controls.mode.value }));
  controls.vt.addEventListener("change", () => updateSettings({ vt_ml: Number(controls.vt.value) }));
  controls.pinsp.addEventListener("change", () => updateSettings({ pinsp_cm_h2o: Number(controls.pinsp.value) }));
  controls.rr.addEventListener("change", () => updateSettings({ rr_bpm: Number(controls.rr.value) }));
  controls.peep.addEventListener("change", () => updateSettings({ peep_cm_h2o: Number(controls.peep.value) }));
  controls.pHigh.addEventListener("change", () => updateSettings({ p_high_cm_h2o: Number(controls.pHigh.value) }));
  controls.pLow.addEventListener("change", () => updateSettings({ p_low_cm_h2o: Number(controls.pLow.value) }));
  controls.tHigh.addEventListener("change", () => updateSettings({ t_high_s: Number(controls.tHigh.value) }));
  controls.tLow.addEventListener("change", () => updateSettings({ t_low_s: Number(controls.tLow.value) }));
  controls.ieE.addEventListener("change", () => updateSettings({ ie_e: Number(controls.ieE.value) }));
  controls.riseTime.addEventListener("change", () => updateSettings({ pressure_rise_time_s: Number(controls.riseTime.value) / 1000.0 }));
  controls.expValve.addEventListener("change", () => updateSettings({ expiratory_valve_resistance_cm_h2o_s_per_l: Number(controls.expValve.value) }));
  controls.lungModel.addEventListener("change", () => updatePatient({ lung_model: controls.lungModel.value }));
  controls.preset.addEventListener("change", () => updatePatient({ preset: controls.preset.value }));
  controls.compliance.addEventListener("change", () => updatePatient({ compliance_ml_per_cm_h2o: Number(controls.compliance.value) }));
  controls.inflection.addEventListener("change", () => updatePatient({ inflection_cm_h2o: Number(controls.inflection.value) }));
  controls.slope.addEventListener("change", () => updatePatient({ slope_width_cm_h2o: Number(controls.slope.value) }));
  controls.recruitable.addEventListener("change", () => updatePatient({ recruitable_volume_ml: Number(controls.recruitable.value) }));
  controls.hysteresis.addEventListener("change", () => updatePatient({ hysteresis_offset_cm_h2o: Number(controls.hysteresis.value) }));
  controls.resistance.addEventListener("change", () => updatePatient({ resistance_cm_h2o_s_per_l: Number(controls.resistance.value) }));
  wireLiveLabels();
  document.querySelector("#fitAxes").addEventListener("click", fitChartAxes);
  document.querySelector("#resetAxes").addEventListener("click", resetChartAxes);
  document.querySelector("#windowSeconds").addEventListener("change", (event) => {
    windowSeconds = Number(event.target.value);
    const latest = latestSampleTime();
    trimBuffers(latest - windowSeconds);
    updateCharts();
  });
  document.querySelector("#advancedOpen").addEventListener("click", () => document.querySelector("#advancedDialog").showModal());
  document.querySelector("#modelOpen").addEventListener("click", () => document.querySelector("#modelDialog").showModal());
  document.querySelector("#pause").addEventListener("click", async () => {
    const state = await postJson("/api/pause", { paused: !paused });
    syncControls(state);
  });
  document.querySelector("#reset").addEventListener("click", async () => {
    const state = await postJson("/api/reset");
    for (const key of Object.keys(buffers)) buffers[key] = [];
    appendSample(state.sample);
    syncControls(state);
    updateStatus(state);
    updateCharts();
  });
}

function wireLiveLabels() {
  const labelInputs = [
    controls.vt,
    controls.pinsp,
    controls.rr,
    controls.peep,
    controls.pHigh,
    controls.pLow,
    controls.tHigh,
    controls.tLow,
    controls.ieE,
    controls.riseTime,
    controls.expValve,
    controls.resistance,
    controls.compliance,
    controls.inflection,
    controls.slope,
    controls.recruitable,
    controls.hysteresis,
  ];
  for (const input of labelInputs) {
    input.addEventListener("input", updateLabelsFromInputs);
  }
}

function updateLabelsFromInputs() {
  document.querySelector("#vtValue").textContent = `${Number(controls.vt.value).toFixed(0)} mL`;
  document.querySelector("#pinspValue").textContent = `${Number(controls.pinsp.value).toFixed(0)} cmH2O`;
  document.querySelector("#rrValue").textContent = `${Number(controls.rr.value).toFixed(0)}/min`;
  document.querySelector("#peepValue").textContent = `${Number(controls.peep.value).toFixed(0)} cmH2O`;
  document.querySelector("#pHighValue").textContent = `${Number(controls.pHigh.value).toFixed(0)} cmH2O`;
  document.querySelector("#pLowValue").textContent = `${Number(controls.pLow.value).toFixed(0)} cmH2O`;
  document.querySelector("#tHighValue").textContent = `${Number(controls.tHigh.value).toFixed(1)} s`;
  document.querySelector("#tLowValue").textContent = `${Number(controls.tLow.value).toFixed(1)} s`;
  document.querySelector("#ieValue").textContent = `1:${Number(controls.ieE.value).toFixed(1).replace(".0", "")}`;
  document.querySelector("#riseTimeValue").textContent = `${Number(controls.riseTime.value).toFixed(0)} ms`;
  document.querySelector("#expValveValue").textContent = `${Number(controls.expValve.value).toFixed(0)} cmH2O*s/L`;
  document.querySelector("#resistanceValue").textContent = `${Number(controls.resistance.value).toFixed(0)} cmH2O*s/L`;
  document.querySelector("#complianceValue").textContent = `${Number(controls.compliance.value).toFixed(0)} mL/cmH2O`;
  document.querySelector("#inflectionValue").textContent = `${Number(controls.inflection.value).toFixed(0)} cmH2O`;
  document.querySelector("#slopeValue").textContent = `${Number(controls.slope.value).toFixed(1)} cmH2O`;
  document.querySelector("#recruitableValue").textContent = `${Number(controls.recruitable.value).toFixed(0)} mL`;
  document.querySelector("#hysteresisValue").textContent = `${Number(controls.hysteresis.value).toFixed(1)} cmH2O`;
}

async function updateSettings(updates) {
  const state = await postJson("/api/settings", updates);
  syncControls(state);
}

async function updatePatient(updates) {
  const state = await postJson("/api/patient", updates);
  syncControls(state);
}

async function start() {
  if (!window.uPlot) throw new Error("uPlot did not load");
  createCharts();
  const state = await getJson("/api/state");
  appendSample(state.sample);
  syncControls(state);
  updateStatus(state);
  updateCharts();
  wireControls();
  setInterval(poll, 50);
}

start().catch((error) => {
  document.body.innerHTML = `<pre>${error.stack || error}</pre>`;
});
