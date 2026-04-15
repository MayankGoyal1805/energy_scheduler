// Energy Scheduler Dashboard - App.js

let globalState = {
  trials: 5,
  repetitions: 3,
  candidates: ["lavd"],
  workloads: ["cpu_bound"], // Default
  blockParams: {}
};

let logPollInterval = null;
let currentJobId = null;

const ELEMENTS = {
  globalTrials: document.getElementById("globalTrials"),
  globalRepetitions: document.getElementById("globalRepetitions"),
  candidateSelectors: document.getElementById("candidateSelectors"),
  workloadSelectors: document.getElementById("workloadSelectors"),
  runDashboardBtn: document.getElementById("runDashboardBtn"),
  stopPollingBtn: document.getElementById("stopPolling"),
  globalStatus: document.getElementById("globalStatus"),
  masterParetoChart: document.getElementById("masterParetoChart"),
  masterBarChart: document.getElementById("masterBarChart"),
  workflowBlocks: document.getElementById("workflowBlocks"),
  logStream: document.getElementById("logStream"),
  logJobId: document.getElementById("logJobId")
};

const PALETTE = ["#2563eb", "#14b8a6", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#84cc16"];

function unique(items) {
  return [...new Set(items)];
}

function toNumber(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function fmt(value, digits = 4) {
  const number = toNumber(value);
  return number === null ? "N/A" : number.toFixed(digits);
}

function readStateFromDOM() {
  globalState.trials = parseInt(ELEMENTS.globalTrials.value, 10);
  globalState.repetitions = parseInt(ELEMENTS.globalRepetitions.value, 10);
  const cands = Array.from(ELEMENTS.candidateSelectors.querySelectorAll("input:checked")).map(i => i.value);
  if(cands.length > 0) {
    globalState.candidates = cands;
  } else {
    const first = ELEMENTS.candidateSelectors.querySelector("input");
    if (first) {
      first.checked = true;
      globalState.candidates = [first.value];
    }
  }
  const wls = Array.from(ELEMENTS.workloadSelectors.querySelectorAll("input:checked")).map(i => i.value);
  globalState.workloads = wls;
  saveState();
}

function updateDOMFromState() {
  if(ELEMENTS.globalTrials) ELEMENTS.globalTrials.value = globalState.trials;
  if(ELEMENTS.globalRepetitions) ELEMENTS.globalRepetitions.value = globalState.repetitions;
  if(ELEMENTS.candidateSelectors) {
    const candInputs = ELEMENTS.candidateSelectors.querySelectorAll("input");
    candInputs.forEach(i => i.checked = globalState.candidates.includes(i.value));
  }
  if(ELEMENTS.workloadSelectors) {
    const wlInputs = ELEMENTS.workloadSelectors.querySelectorAll("input");
    wlInputs.forEach(i => i.checked = globalState.workloads.includes(i.value));
  }
}

function saveState() {
  localStorage.setItem("es_dashboard_state", JSON.stringify(globalState));
}

function loadState() {
  const s = localStorage.getItem("es_dashboard_state");
  if(s) {
    try {
      const parsed = JSON.parse(s);
      globalState = {
        ...globalState,
        ...parsed,
        blockParams: parsed.blockParams || {}
      };
    } catch(e) { console.error(e); }
  }
}

function setStatus(status) {
  if(ELEMENTS.globalStatus) ELEMENTS.globalStatus.textContent = status;
}

function initLogs(jobId) {
  currentJobId = jobId;
  if(ELEMENTS.logJobId) ELEMENTS.logJobId.textContent = `(Job: ${jobId})`;
  if(ELEMENTS.logStream) ELEMENTS.logStream.textContent = "Starting...\n";
  if(logPollInterval) clearInterval(logPollInterval);
  logPollInterval = setInterval(pollLogs, 1000);
}

async function pollLogs() {
  if(!currentJobId) return;
  try {
    const r = await fetch(`/jobs/${currentJobId}`);
    if(r.ok) {
      const d = await r.json();
      if(d.logs && d.logs.length > 0) {
        if(ELEMENTS.logStream) {
          ELEMENTS.logStream.textContent = d.logs.join("\n") + "\n";
          ELEMENTS.logStream.scrollTop = ELEMENTS.logStream.scrollHeight;
        }
      }
      if(d.status === "completed" || d.status === "failed") {
        clearInterval(logPollInterval);
        logPollInterval = null;
        if(d.status === "failed") setStatus("Job Failed");
      } 
    }
  } catch(e) {}
}

if(ELEMENTS.stopPollingBtn) {
  ELEMENTS.stopPollingBtn.addEventListener("click", () => {
    if(logPollInterval) {
      clearInterval(logPollInterval);
      logPollInterval = null;
      setStatus("Polling stopped");
    }
  });
}

async function fetchDropdownInfo() {
  try {
    const [listData, candidates] = await Promise.all([
      fetch("/workloads").then(r => r.json()),
      fetch("/sched-ext-candidates").then(r => r.json())
    ]);
    const wlist = Array.isArray(listData) && listData.length
      ? listData
      : ["cpu_bound", "interactive_short", "mixed", "bursty_periodic", "compression", "file_scan", "local_request_burst", "mixed_realistic"];
    if(ELEMENTS.workloadSelectors) {
      ELEMENTS.workloadSelectors.innerHTML = "";
      wlist.forEach(wl => {
        const lbl = document.createElement("label");
        lbl.className = "checkbox-label";
        const chk = document.createElement("input");
        chk.type = "checkbox"; chk.value = wl;
        lbl.appendChild(chk); lbl.appendChild(document.createTextNode(wl));
        ELEMENTS.workloadSelectors.appendChild(lbl);
      });
    }
    if(ELEMENTS.candidateSelectors) {
      ELEMENTS.candidateSelectors.innerHTML = "";
      const cands = Array.isArray(candidates) && candidates.length ? candidates : ["lavd", "cake", "bpfland"];
      unique(cands).forEach(cand => {
        const lbl = document.createElement("label");
        lbl.className = "checkbox-label";
        const chk = document.createElement("input");
        chk.type = "checkbox"; chk.value = cand;
        lbl.appendChild(chk); lbl.appendChild(document.createTextNode(cand));
        ELEMENTS.candidateSelectors.appendChild(lbl);
      });

      globalState.candidates = globalState.candidates.filter(item => cands.includes(item));
      if (!globalState.candidates.length && cands.length) {
        globalState.candidates = [cands[0]];
      }
    }
    updateDOMFromState();
  } catch(e) {
    console.error("Error fetching defaults", e);
    setStatus("Failed to load options");
  }
}

function createWorkflowBlock(wl) {
  const bp = globalState.blockParams[wl] || { tasks: 8, taskSeconds: 0.5 };
  const block = document.createElement("div");
  block.className = "workflow-block";
  block.id = `block-${wl}`;
  block.innerHTML = `
    <div class="block-header">
      <h3>${wl.replace(/_/g, " ")}</h3>
    </div>
    <div class="block-controls">
      <div class="input-group">
        <label>Tasks</label>
        <input type="number" min="1" id="tasks-${wl}" value="${bp.tasks}" />
      </div>
      <div class="input-group">
        <label>Task Seconds</label>
        <input type="number" step="0.01" min="0.01" id="tasksec-${wl}" value="${bp.taskSeconds}" />
      </div>
      <button class="primary-btn inline-btn" id="update-${wl}">Update Target</button>
    </div>
    <div class="block-charts">
      <div id="chart-pareto-${wl}" class="chart sub-chart"></div>
      <div id="chart-bar-${wl}" class="chart sub-chart"></div>
    </div>
    <div class="table-container">
      <table class="data-table" id="table-${wl}">
        <thead>
          <tr>
            <th>Scheduler</th>
            <th>Energy (J)</th>
            <th>Runtime (s)</th>
            <th>Energy Delta %</th>
            <th>Failed Trials</th>
          </tr>
        </thead>
        <tbody></tbody>
      </table>
    </div>
  `;
  if(ELEMENTS.workflowBlocks) ELEMENTS.workflowBlocks.appendChild(block);
  const btn = document.getElementById(`update-${wl}`);
  if(btn) btn.addEventListener("click", () => runSingleBlock(wl));
}

function processBlockData(wl, data) {
  if(!data || !data.rows) return;

  const rows = data.rows.filter(row => toNumber(row.median_runtime_s) !== null || toNumber(row.median_energy_j) !== null);
  const tableBody = document.querySelector(`#table-${wl} tbody`);
  if (tableBody) {
    tableBody.innerHTML = "";
    rows.forEach((row) => {
      const tr = document.createElement("tr");
      const delta = toNumber(row.median_delta_percent);
      const deltaClass = delta === null ? "neutral" : delta <= 0 ? "good" : "bad";
      tr.innerHTML = `
        <td>${row.label}</td>
        <td>${fmt(row.median_energy_j, 5)}</td>
        <td>${fmt(row.median_runtime_s, 5)}</td>
        <td class="${deltaClass}">${fmt(row.median_delta_percent, 2)}</td>
        <td>${row.failed_trials || 0}</td>
      `;
      tableBody.appendChild(tr);
    });
  }

  const scatterRows = rows.filter(row => toNumber(row.median_runtime_s) !== null && toNumber(row.median_energy_j) !== null);
  Plotly.newPlot(`chart-pareto-${wl}`, [
    {
      x: scatterRows.map(row => row.median_runtime_s),
      y: scatterRows.map(row => row.median_energy_j),
      mode: "markers+text",
      text: scatterRows.map(row => row.label),
      textposition: "top center",
      type: "scatter",
      marker: {
        size: 11,
        color: scatterRows.map((_, idx) => PALETTE[idx % PALETTE.length])
      }
    }
  ], {
    title: `${wl.replace(/_/g, " ")} Runtime vs Energy`,
    xaxis: { title: "Median Runtime (s)" },
    yaxis: { title: "Median Energy (J)" },
    margin: { t: 50, r: 20, b: 50, l: 55 }
  });

  const deltaRows = rows.filter(row => row.label !== "linux_default" && toNumber(row.median_delta_percent) !== null);
  Plotly.newPlot(`chart-bar-${wl}`, [
    {
      x: deltaRows.map(row => row.label),
      y: deltaRows.map(row => row.median_delta_percent),
      type: "bar",
      marker: {
        color: deltaRows.map(row => row.median_delta_percent <= 0 ? "#10b981" : "#ef4444")
      }
    }
  ], {
    title: "Energy Delta vs Baseline (%)",
    xaxis: { title: "Scheduler" },
    yaxis: { title: "Delta %", zeroline: true, zerolinecolor: "#64748b" },
    margin: { t: 50, r: 20, b: 50, l: 55 }
  });
}

function renderMasterCharts(rows) {
  if(!rows.length) {
    return;
  }

  const grouped = {};
  rows.forEach((row) => {
    if (!grouped[row.label]) {
      grouped[row.label] = { runtime: [], energy: [], delta: [] };
    }
    const runtime = toNumber(row.median_runtime_s);
    const energy = toNumber(row.median_energy_j);
    const delta = toNumber(row.median_delta_percent);
    if (runtime !== null) grouped[row.label].runtime.push(runtime);
    if (energy !== null) grouped[row.label].energy.push(energy);
    if (delta !== null) grouped[row.label].delta.push(delta);
  });

  const labels = Object.keys(grouped);
  const avgRuntime = labels.map(label => {
    const values = grouped[label].runtime;
    return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
  });
  const avgEnergy = labels.map(label => {
    const values = grouped[label].energy;
    return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
  });
  const avgDelta = labels.map(label => {
    const values = grouped[label].delta;
    return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
  });

  if(ELEMENTS.masterParetoChart) {
    Plotly.newPlot(ELEMENTS.masterParetoChart, [
      {
        x: avgRuntime,
        y: avgEnergy,
        text: labels,
        mode: "markers+text",
        textposition: "top center",
        type: "scatter",
        marker: {
          size: 14,
          color: labels.map((_, idx) => PALETTE[idx % PALETTE.length])
        }
      }
    ], {
      title: "Aggregate: Avg Runtime vs Avg Energy",
      xaxis:{title: "Runtime (s)"},
      yaxis:{title: "Energy (J)"},
      margin:{t:50, r: 20, b: 50, l: 55}
    });
  }

  const barLabels = labels.filter(label => label !== "linux_default");
  if(ELEMENTS.masterBarChart) {
    Plotly.newPlot(ELEMENTS.masterBarChart, [{
      x: barLabels,
      y: barLabels.map(label => avgDelta[labels.indexOf(label)]),
      type: "bar",
      marker: {
        color: barLabels.map(label => {
          const value = avgDelta[labels.indexOf(label)];
          if (value === null) return "#94a3b8";
          return value <= 0 ? "#10b981" : "#ef4444";
        })
      }
    }], {
      title: "Aggregate: Avg Energy Delta vs Baseline (%)",
      xaxis:{ title: "Scheduler" },
      yaxis:{ title: "Delta %", zeroline: true, zerolinecolor: "#64748b" },
      margin:{ t:50, r: 20, b: 50, l: 55 }
    });
  }
}

function gatherMasterData(responses) {
  const allRows = [];
  Object.keys(responses).forEach(wl => {
    const data = responses[wl];
    if(data && data.rows) {
      data.rows.forEach(r => allRows.push({ ...r, workload: wl }));
    }
  });
  renderMasterCharts(allRows);
}

async function doFetchMedian(queryBody) {
  let qResp = await fetch("/median-runs/query", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(queryBody)
  });
  if (qResp.ok) {
     let qData = await qResp.json();
     if(qData && Object.keys(qData).length > 0 && qData.rows && qData.rows.length > 0) {
       return qData;
     }
  }
  let jobResp = await fetch("/jobs/median-board", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...queryBody, save: true })
  });
  if (!jobResp.ok) throw new Error("Failed to start job");
  let jobData = await jobResp.json();
  initLogs(jobData.job_id);
  while(true) {
    await new Promise(r => setTimeout(r, 2000));
    let st = await fetch(`/jobs/${jobData.job_id}`);
    let sd = await st.json();
    if(sd.status === "completed") {
       return sd.result;
    } else if(sd.status === "failed") {
       throw new Error(sd.error || "Job failed");
    }
  }
}

let globalBlockResponses = {};

async function runDashboard() {
  readStateFromDOM();
  if(ELEMENTS.workflowBlocks) ELEMENTS.workflowBlocks.innerHTML = "";
  if(globalState.workloads.length === 0) {
    alert("Select at least one workload.");
    return;
  }
  setStatus("Computing...");
  globalBlockResponses = {};
  for(const wl of globalState.workloads) {
    createWorkflowBlock(wl);
    const bp = globalState.blockParams[wl] || { tasks: 8, taskSeconds: 0.5 };
    const queryBody = {
      workload: wl,
      candidates: globalState.candidates.join(","),
      tasks: bp.tasks,
      task_seconds: bp.taskSeconds,
      repetitions: globalState.repetitions,
      trials: globalState.trials,
      perf_stat: false
    };
    try {
      const finalData = await doFetchMedian(queryBody);
      globalBlockResponses[wl] = finalData;
      processBlockData(wl, finalData);
    } catch(e) {
      console.error("Error with workload:", wl, e);
    }
  }
  gatherMasterData(globalBlockResponses);
  setStatus("Dashboard Ready");
}

async function runSingleBlock(wl) {
  const tEl = document.getElementById(`tasks-${wl}`);
  const tsEl = document.getElementById(`tasksec-${wl}`);
  const t = parseInt(tEl?.value || "8", 10);
  const ts = parseFloat(tsEl?.value || "0.5");
  globalState.blockParams[wl] = { tasks: t, taskSeconds: ts };
  saveState();
  setStatus(`Re-computing block ${wl}...`);
  const queryBody = {
    workload: wl,
    candidates: globalState.candidates.join(","),
    tasks: t,
    task_seconds: ts,
    repetitions: globalState.repetitions,
    trials: globalState.trials,
    perf_stat: false
  };
  try {
    const finalData = await doFetchMedian(queryBody);
    globalBlockResponses[wl] = finalData;
    processBlockData(wl, finalData);
    gatherMasterData(globalBlockResponses);
    setStatus("Dashboard Ready");
  } catch(e) {
    console.error(e);
    setStatus("Error computing block");
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  loadState();
  await fetchDropdownInfo();
  if (ELEMENTS.runDashboardBtn) {
    ELEMENTS.runDashboardBtn.addEventListener("click", runDashboard);
  }
});
