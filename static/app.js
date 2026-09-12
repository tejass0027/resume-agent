(() => {
  const STORAGE_KEY = "resume-screener-settings-v1";

  const el = (id) => document.getElementById(id);

  const providerSelect = el("provider");
  const apiKeyInput = el("api-key");
  const apiKeyLabel = el("api-key-label");
  const keyHelp = el("key-help");
  const toggleKeyBtn = el("toggle-key");
  const modelInput = el("model");
  const maxConcurrencyInput = el("max-concurrency");
  const maxConcurrencyValue = el("max-concurrency-value");
  const maxRetriesInput = el("max-retries");
  const maxRetriesValue = el("max-retries-value");
  const jobDescriptionInput = el("job-description");
  const filesInput = el("files");
  const fileListEl = el("file-list");
  const runBtn = el("run-btn");
  const progressWrap = el("progress-wrap");
  const progressFill = el("progress-fill");
  const progressText = el("progress-text");
  const warningsEl = el("warnings");
  const resultsSection = el("results");
  const metricsEl = el("metrics");
  const leaderboardBody = document.querySelector("#leaderboard tbody");
  const detailsEl = el("details");
  const exportBtn = el("export-btn");
  const taglineEl = el("tagline");

  let providers = {};
  let lastResults = [];

  function loadSettings() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
    } catch {
      return {};
    }
  }

  function saveSettings(partial) {
    try {
      const current = loadSettings();
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...current, ...partial }));
    } catch {
      /* localStorage unavailable; settings just won't persist */
    }
  }

  function updateRunButtonState() {
    const hasKey = apiKeyInput.value.trim().length > 0;
    const hasJD = jobDescriptionInput.value.trim().length > 0;
    const hasFiles = filesInput.files.length > 0;
    runBtn.disabled = !(hasKey && hasJD && hasFiles);
  }

  function renderFileList() {
    fileListEl.innerHTML = "";
    Array.from(filesInput.files).forEach((f) => {
      const li = document.createElement("li");
      li.textContent = `${f.name} (${(f.size / 1024).toFixed(1)} KB)`;
      fileListEl.appendChild(li);
    });
  }

  async function loadProviders() {
    const res = await fetch("/api/providers");
    providers = await res.json();
    providerSelect.innerHTML = "";
    Object.keys(providers).forEach((name) => {
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      providerSelect.appendChild(opt);
    });

    const saved = loadSettings();
    if (saved.provider && providers[saved.provider]) {
      providerSelect.value = saved.provider;
    }
    onProviderChange(true);
  }

  function onProviderChange(isInitialLoad) {
    const name = providerSelect.value;
    const info = providers[name];
    if (!info) return;

    apiKeyLabel.textContent = info.key_label;
    keyHelp.textContent = info.key_help;
    taglineEl.textContent = `Evidence-based resume screening at scale, powered by ${name}.`;

    const saved = loadSettings();
    const perProvider = saved.perProvider || {};
    const providerSaved = perProvider[name] || {};

    apiKeyInput.value = providerSaved.apiKey || "";
    modelInput.value = providerSaved.model || info.default_model;

    if (!isInitialLoad) {
      saveSettings({ provider: name });
    }
    updateRunButtonState();
  }

  function persistProviderField(field, value) {
    const name = providerSelect.value;
    const saved = loadSettings();
    const perProvider = saved.perProvider || {};
    perProvider[name] = { ...perProvider[name], [field]: value };
    saveSettings({ perProvider });
  }

  function restoreGeneralSettings() {
    const saved = loadSettings();
    if (typeof saved.jobDescription === "string") {
      jobDescriptionInput.value = saved.jobDescription;
    }
    if (typeof saved.maxConcurrency === "number") {
      maxConcurrencyInput.value = saved.maxConcurrency;
    }
    if (typeof saved.maxRetries === "number") {
      maxRetriesInput.value = saved.maxRetries;
    }
    maxConcurrencyValue.textContent = maxConcurrencyInput.value;
    maxRetriesValue.textContent = maxRetriesInput.value;
  }

  providerSelect.addEventListener("change", () => onProviderChange(false));

  apiKeyInput.addEventListener("input", () => {
    persistProviderField("apiKey", apiKeyInput.value);
    updateRunButtonState();
  });

  modelInput.addEventListener("input", () => {
    persistProviderField("model", modelInput.value);
  });

  jobDescriptionInput.addEventListener("input", () => {
    saveSettings({ jobDescription: jobDescriptionInput.value });
    updateRunButtonState();
  });

  maxConcurrencyInput.addEventListener("input", () => {
    maxConcurrencyValue.textContent = maxConcurrencyInput.value;
    saveSettings({ maxConcurrency: Number(maxConcurrencyInput.value) });
  });

  maxRetriesInput.addEventListener("input", () => {
    maxRetriesValue.textContent = maxRetriesInput.value;
    saveSettings({ maxRetries: Number(maxRetriesInput.value) });
  });

  filesInput.addEventListener("change", () => {
    renderFileList();
    updateRunButtonState();
  });

  toggleKeyBtn.addEventListener("click", () => {
    const showing = apiKeyInput.type === "text";
    apiKeyInput.type = showing ? "password" : "text";
    toggleKeyBtn.textContent = showing ? "show" : "hide";
  });

  function addWarning(message) {
    const div = document.createElement("div");
    div.className = "warning";
    div.textContent = message;
    warningsEl.appendChild(div);
  }

  function statusCount(results, status) {
    return results.filter((r) => r.status === status).length;
  }

  function renderResults(results) {
    lastResults = results;
    results.sort((a, b) => (b.match_score ?? 0) - (a.match_score ?? 0));

    resultsSection.hidden = false;

    metricsEl.innerHTML = "";
    const metrics = [
      ["Total Candidates", results.length],
      ["Shortlisted", statusCount(results, "Shortlisted")],
      ["Flagged", statusCount(results, "Flagged")],
      ["Rejected", statusCount(results, "Rejected") + statusCount(results, "Error")],
    ];
    metrics.forEach(([label, value]) => {
      const div = document.createElement("div");
      div.className = "metric";
      div.innerHTML = `<div class="value">${value}</div><div class="label">${label}</div>`;
      metricsEl.appendChild(div);
    });

    leaderboardBody.innerHTML = "";
    results.forEach((r) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(r.candidate_name ?? "Unknown")}</td>
        <td>${escapeHtml(r.filename ?? "")}</td>
        <td>${r.match_score ?? "?"}</td>
        <td><span class="status-badge status-${r.status}">${r.status ?? "?"}</span></td>
        <td>${r.years_experience_estimated ?? "-"}</td>
      `;
      leaderboardBody.appendChild(tr);
    });

    detailsEl.innerHTML = "";
    results.forEach((r) => {
      const details = document.createElement("details");
      details.className = "candidate";
      const summary = document.createElement("summary");
      summary.textContent = `${r.candidate_name ?? "Unknown"} — ${r.match_score ?? "?"}% — ${r.status ?? "?"}`;
      details.appendChild(summary);

      const body = document.createElement("div");
      let html = `<p><strong>File:</strong> ${escapeHtml(r.filename ?? "")}</p>`;
      if (r.years_experience_estimated !== null && r.years_experience_estimated !== undefined) {
        html += `<p><strong>Estimated years of experience:</strong> ${r.years_experience_estimated}</p>`;
      }
      html += `<div class="section-title">Strengths</div><ul>${(r.strengths || []).map((s) => `<li>${escapeHtml(s)}</li>`).join("")}</ul>`;
      html += `<div class="section-title">Weaknesses / Gaps</div><ul>${(r.weaknesses || []).map((s) => `<li>${escapeHtml(s)}</li>`).join("")}</ul>`;

      if (r.must_haves_met && r.must_haves_met.length) {
        html += `<div class="section-title">Must-Have Requirements</div><ul>${r.must_haves_met
          .map((item) => `<li>${item.met ? "✅" : "❌"} ${escapeHtml(item.requirement)} — <span class="evidence">${escapeHtml(item.evidence)}</span></li>`)
          .join("")}</ul>`;
      }
      if (r.nice_to_haves_met && r.nice_to_haves_met.length) {
        html += `<div class="section-title">Nice-to-Have Requirements</div><ul>${r.nice_to_haves_met
          .map((item) => `<li>${item.met ? "✅" : "➖"} ${escapeHtml(item.requirement)} — <span class="evidence">${escapeHtml(item.evidence)}</span></li>`)
          .join("")}</ul>`;
      }

      body.innerHTML = html;
      details.appendChild(body);
      detailsEl.appendChild(details);
    });
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str ?? "";
    return div.innerHTML;
  }

  function resultsToCsv(results) {
    const columns = [
      "candidate_name",
      "filename",
      "match_score",
      "status",
      "years_experience_estimated",
      "strengths",
      "weaknesses",
    ];
    const rows = [columns.join(",")];
    results.forEach((r) => {
      const row = columns.map((col) => {
        let value = r[col];
        if (Array.isArray(value)) value = value.join("; ");
        if (value === null || value === undefined) value = "";
        value = String(value).replace(/"/g, '""');
        return `"${value}"`;
      });
      rows.push(row.join(","));
    });
    return rows.join("\n");
  }

  exportBtn.addEventListener("click", () => {
    const csv = resultsToCsv(lastResults);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "resume_screening_results.csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  });

  runBtn.addEventListener("click", async () => {
    warningsEl.innerHTML = "";
    resultsSection.hidden = true;
    runBtn.disabled = true;

    const formData = new FormData();
    formData.append("provider", providerSelect.value);
    formData.append("api_key", apiKeyInput.value);
    formData.append("model", modelInput.value);
    formData.append("job_description", jobDescriptionInput.value);
    formData.append("max_concurrency", maxConcurrencyInput.value);
    formData.append("max_retries", maxRetriesInput.value);
    Array.from(filesInput.files).forEach((f) => formData.append("files", f));

    progressWrap.hidden = false;
    progressFill.style.width = "0%";
    progressText.textContent = "Starting screening...";

    try {
      const response = await fetch("/api/screen", { method: "POST", body: formData });
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();
        for (const line of lines) {
          if (!line.trim()) continue;
          handleEvent(JSON.parse(line));
        }
      }
      if (buffer.trim()) {
        handleEvent(JSON.parse(buffer));
      }
    } catch (err) {
      addWarning(`Request failed: ${err.message}`);
    } finally {
      progressWrap.hidden = true;
      updateRunButtonState();
    }
  });

  function handleEvent(event) {
    if (event.type === "progress") {
      const pct = event.total ? (event.done / event.total) * 100 : 0;
      progressFill.style.width = `${pct}%`;
      progressText.textContent = `Screened ${event.done}/${event.total} resumes...`;
    } else if (event.type === "extraction_error") {
      addWarning(`Skipped ${event.filename}: ${event.message}`);
    } else if (event.type === "error") {
      addWarning(event.message);
    } else if (event.type === "done") {
      renderResults(event.results);
    }
  }

  loadProviders().then(() => {
    restoreGeneralSettings();
    renderFileList();
    updateRunButtonState();
  });
})();
