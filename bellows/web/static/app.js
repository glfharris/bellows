const WINDOW_SECONDS = 12;
const buffers = {
  pressure: [],
  flow: [],
  volume: [],
  co2: [],
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
  resistance: document.querySelector("#resistance"),
};

const chartSpecs = {
  pressure: { label: "Pressure", unit: "cmH2O", range: [0, 50], color: "#f5c451" },
  flow: { label: "Flow", unit: "L/min", range: [-100, 100], color: "#57c7ff" },
  volume: { label: "Volume", unit: "mL", range: [0, 1200], color: "#72d572" },
  co2: { label: "CO2", unit: "kPa", range: [0, 7], color: "#d78cff" },
};

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
  buffers.co2.push([sample.time_s, sample.co2_kpa, sample.breath, sample.phase]);
  currentBreath = sample.breath;
  trimBuffers(sample.time_s - WINDOW_SECONDS);
}

function trimBuffers(minTime) {
  for (const points of Object.values(buffers)) {
    while (points.length && points[0][0] < minTime) points.shift();
  }
}

function syncControls(state) {
  const settings = state.settings;
  document.querySelector("#modeBadge").textContent = settings.mode;
  controls.mode.value = settings.mode;
  controls.vt.value = settings.vt_ml;
  controls.pinsp.value = settings.pinsp_cm_h2o;
  controls.rr.value = settings.rr_bpm;
  controls.peep.value = settings.peep_cm_h2o;
  controls.resistance.value = state.patient.resistance_cm_h2o_s_per_l;
  document.querySelector("#vtValue").textContent = `${settings.vt_ml.toFixed(0)} mL`;
  document.querySelector("#pinspValue").textContent = `${settings.pinsp_cm_h2o.toFixed(0)} cmH2O`;
  document.querySelector("#rrValue").textContent = `${settings.rr_bpm.toFixed(0)}/min`;
  document.querySelector("#peepValue").textContent = `${settings.peep_cm_h2o.toFixed(0)} cmH2O`;
  document.querySelector("#resistanceValue").textContent = `${state.patient.resistance_cm_h2o_s_per_l.toFixed(0)} cmH2O*s/L`;
  document.querySelector("#pending").textContent = state.pending_settings
    ? `Pending ${state.pending_settings.mode}`
    : "No pending changes";
  paused = state.paused;
  document.querySelector("#pause").textContent = paused ? "Resume" : "Pause";
}

function updateStatus(state) {
  const sample = state.sample;
  document.querySelector("#clock").textContent = `t=${sample.time_s.toFixed(1)}s breath ${String(sample.breath).padStart(3, "0")}`;
  const summary = state.last_breath_summary;
  document.querySelector("#ppeakValue").textContent = summary
    ? summary.peak_pressure_cm_h2o.toFixed(0)
    : "--";
  document.querySelector("#vteValue").textContent = summary
    ? summary.vt_ml.toFixed(0)
    : "--";
  document.querySelector("#mvValue").textContent = summary
    ? summary.minute_volume_l_min.toFixed(1)
    : "--";
  document.querySelector("#etco2Value").textContent = summary
    ? summary.etco2_kpa.toFixed(1)
    : "--";
}

function createCharts() {
  for (const [key, spec] of Object.entries(chartSpecs)) {
    const element = document.querySelector(`#${key}`);
    const size = chartElementSize(element);
    chartSizes[key] = size;
    charts[key] = new uPlot(
      {
        title: `${spec.label} (${spec.unit})`,
        width: size.width,
        height: size.height,
        scales: {
          x: { time: false },
          y: { range: () => spec.range },
        },
        axes: [
          { stroke: "#4d5a54", grid: { stroke: "#1d2925" }, values: (_u, ticks) => ticks.map((tick) => `${(tick - latestSampleTime()).toFixed(0)}s`) },
          { stroke: "#4d5a54", grid: { stroke: "#1d2925" } },
        ],
        series: [{}, { label: spec.label, stroke: spec.color, width: 2 }],
        cursor: { show: false },
      },
      [[], []],
      element,
    );
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
  const start = latest - WINDOW_SECONDS;
  for (const [key, chart] of Object.entries(charts)) {
    const points = buffers[key].filter((point) => point[0] >= start);
    chart.setData([points.map((point) => point[0]), points.map((point) => point[1])]);
    chart.setScale("x", { min: start, max: latest });
  }
  drawPvLoop();
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
  return buffers.pressure.at(-1)?.[0] ?? WINDOW_SECONDS;
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
  controls.resistance.addEventListener("change", () => updatePatient({ resistance_cm_h2o_s_per_l: Number(controls.resistance.value) }));
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
