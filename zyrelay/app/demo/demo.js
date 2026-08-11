const API = "/api/v1";
const TIMELINE = [
  ["Upload", ["validate_input", "detect_file_type"]],
  ["GroundChoose", ["ground_choose", "create_ground_snapshot"]],
  ["ResourcePlan", ["build_resource_plan", "route_"]],
  ["Parser", ["parse_document"]],
  ["Layout", ["detect_layout", "run_layout"]],
  ["OCR", ["detect_ocr_requirement", "render_ocr_pages", "optional_ocr"]],
  ["Table", ["run_table_recognition"]],
  ["NER", ["run_ner"]],
  ["Rule Engine", ["run_existing_label_matching", "build_convention_", "normalize_text"]],
  ["Semantic Objects", ["build_semantic", "build_business_objects"]],
  ["Evidence Validation", ["validate_evidence", "validate_semantic"]],
  ["UOM Package", ["build_uom", "build_package", "save_result", "complete_execution"]],
];
const GROUPS = [
  ["entity", "Entities"], ["rule", "Rules"], ["relation", "Relations"],
  ["event", "Events"], ["business_object", "Business Objects"],
];

const state = { file: null, relay: null, execution: null, ground: null, resources: null, models: [], uom: null, objects: [], activeGroup: "entity", activeObject: null, activeUom: "processing", progressTimer: null };
const $ = (id) => document.getElementById(id);

document.addEventListener("DOMContentLoaded", () => {
  bindFileInputs(); bindActions(); renderTimeline(); checkHealth();
});

function bindFileInputs() {
  const input = $("file-input"), zone = $("drop-zone");
  $("choose-file").addEventListener("click", (event) => { event.preventDefault(); input.click(); });
  input.addEventListener("change", () => setFile(input.files[0]));
  ["dragenter", "dragover"].forEach((name) => zone.addEventListener(name, (event) => { event.preventDefault(); zone.classList.add("dragging"); }));
  ["dragleave", "drop"].forEach((name) => zone.addEventListener(name, (event) => { event.preventDefault(); zone.classList.remove("dragging"); }));
  zone.addEventListener("drop", (event) => setFile(event.dataTransfer.files[0]));
}

function bindActions() {
  $("process-button").addEventListener("click", processDocument);
  $("show-architecture").addEventListener("click", () => $("architecture").hidden = false);
  $("hide-architecture").addEventListener("click", () => $("architecture").hidden = true);
  $("download-uom").addEventListener("click", downloadUom);
}

function setFile(file) {
  if (!file) return;
  const valid = /\.(pdf|docx)$/i.test(file.name);
  if (!valid) { setNote("Only PDF and DOCX files are supported.", true); return; }
  state.file = file;
  $("file-summary").className = "file-summary";
  $("file-summary").innerHTML = `<strong>${escapeHtml(file.name)}</strong><span>${formatBytes(file.size)} · ${file.type || file.name.split(".").pop().toUpperCase()} · Page count available after processing</span>`;
  $("process-button").disabled = false;
  setNote("Ready to submit to POST /api/v1/relay/process.");
}

async function processDocument() {
  if (!state.file) return;
  resetResultState();
  $("process-button").disabled = true;
  $("process-button").textContent = "Processing…";
  $("execution-title").textContent = "Processing document";
  $("execution-meta").textContent = "Submitting the document to the Relay pipeline.";
  setNote("The request is running. Actual status will be loaded from Relay when it completes.");
  startProgress();
  try {
    const form = new FormData();
    form.append("file", state.file);
    appendField(form, "enterprise_id", $("enterprise-id").value || "default");
    appendField(form, "team_id", $("team-id").value);
    appendField(form, "project_id", $("project-id").value);
    appendField(form, "mode", $("mode").value);
    appendField(form, "ground_profile_id", $("ground-profile").value);
    appendField(form, "enable_ocr", String($("enable-ocr").checked));
    appendField(form, "enable_layout_model", String($("enable-layout").checked));
    appendField(form, "output_detail", $("output-detail").value);
    const response = await fetch(`${API}/relay/process`, { method: "POST", body: form });
    const relay = await parseResponse(response);
    state.relay = relay;
    await loadExecutionData(relay);
    finishProgress(100);
    renderAllResults();
    $("execution-title").textContent = `Execution ${relay.status}`;
    $("execution-meta").textContent = `${relay.execution_id} · ${relay.document_id || "document ID pending"} · ${formatDuration(state.execution?.duration_ms)}`;
    setNote("Processing completed. Select a semantic object to inspect its evidence.");
  } catch (error) {
    finishProgress(100);
    $("execution-title").textContent = "Processing failed";
    $("execution-meta").textContent = error.message || "The Relay API returned an error.";
    renderTimeline(null, "failed");
    setNote(error.message || "Unable to process the document.", true);
  } finally {
    $("process-button").disabled = false;
    $("process-button").innerHTML = "Process document <span>→</span>";
  }
}

function appendField(form, name, value) { if (value) form.append(name, value); }

async function loadExecutionData(relay) {
  const executionId = relay.execution_id;
  const get = async (path, optional = false) => {
    const response = await fetch(path);
    if (!response.ok && optional) return null;
    return parseResponse(response);
  };
  const [execution, ground, resources, models, uom] = await Promise.all([
    get(`${API}/relay/executions/${encodeURIComponent(executionId)}`),
    get(`${API}/relay/executions/${encodeURIComponent(executionId)}/ground`),
    get(`${API}/relay/executions/${encodeURIComponent(executionId)}/resources`),
    get(`${API}/relay/executions/${encodeURIComponent(executionId)}/models`),
    relay.document_id ? get(`${API}/documents/${encodeURIComponent(relay.document_id)}/uom`, true) : Promise.resolve(null),
  ]);
  state.execution = execution; state.ground = ground; state.resources = resources; state.models = models || []; state.uom = uom;
  state.objects = collectSemanticObjects(uom, relay);
  const pageCount = uom?.source?.page_count ?? relay?.result?.document?.page_count;
  appendPageCount(pageCount);
  renderTimeline(execution);
}

function collectSemanticObjects(uom, relay) {
  const output = uom?.semantic_objects?.objects || relay?.result?.semantic_objects || [];
  const objects = [...output];
  const existing = new Set(objects.map((item) => item.object_id || item.candidate_id));
  for (const item of (uom?.bom?.business_objects || relay?.result?.business_objects || [])) {
    const id = item.object_id || item.candidate_id;
    if (!existing.has(id)) objects.push({ ...item, object_id: id, object_type: "business_object", provenance_id: item.provenance_id || null });
  }
  return objects;
}

function renderAllResults() {
  $("results").hidden = false;
  renderResultBadges(); renderObjects(); renderResources(); renderUom();
}

function renderResultBadges() {
  const source = state.uom?.source || state.relay?.result?.document || {};
  $("result-badges").innerHTML = [
    `Document: ${source.document_id || state.relay?.document_id || "—"}`,
    `Pages: ${source.page_count ?? "—"}`,
    `Objects: ${state.objects.length}`,
    `Status: ${state.relay?.status || "—"}`,
  ].map((item) => `<span class="badge">${escapeHtml(item)}</span>`).join("");
}

function renderTimeline(execution = state.execution, terminalStatus = null) {
  const records = execution?.steps || [];
  const html = TIMELINE.map(([label, matchers], index) => {
    const relevant = records.filter((item) => matchers.some((matcher) => item.step_name?.startsWith(matcher)));
    const capability = { Layout: "layout", OCR: "ocr", Table: "table_recognition", NER: "ner" }[label];
    const modelRecord = capability ? state.models.find((item) => item.capability === capability) : null;
    let status = "pending", duration = "";
    if (relevant.length) {
      const failed = relevant.find((item) => item.status === "failed");
      const skipped = relevant.every((item) => item.status === "skipped");
      status = failed ? "failed" : skipped ? "skipped" : relevant.some((item) => item.status === "running") ? "running" : "completed";
      duration = formatDuration(relevant.reduce((sum, item) => sum + (item.duration_ms || 0), 0));
    } else if (modelRecord) {
      status = modelRecord.status || "skipped";
      duration = formatDuration(modelRecord.duration_ms);
    } else if (execution?.status === "completed" || execution?.status === "partial") status = "skipped";
    else if (terminalStatus === "failed") status = index === 0 ? "failed" : "pending";
    const stateLabel = status === "pending" ? "Waiting" : status[0].toUpperCase() + status.slice(1);
    return `<div class="timeline-item ${status}"><span class="timeline-node"></span><div><strong>${label}</strong><small>${stateLabel}</small></div><em>${duration}</em></div>`;
  }).join("");
  $("timeline").innerHTML = html;
}

function startProgress() {
  clearInterval(state.progressTimer); let progress = 6; setProgress(progress); renderTimelineForRunning();
  state.progressTimer = setInterval(() => { progress = Math.min(91, progress + (progress < 50 ? 6 : 2)); setProgress(progress); }, 700);
}
function finishProgress(value) { clearInterval(state.progressTimer); state.progressTimer = null; setProgress(value); }
function setProgress(value) { $("progress-bar").style.width = `${value}%`; $("progress-label").textContent = `${value}%`; }
function renderTimelineForRunning() { $("timeline").innerHTML = TIMELINE.map(([label], index) => `<div class="timeline-item ${index === 0 ? "running" : "pending"}"><span class="timeline-node"></span><div><strong>${label}</strong><small>${index === 0 ? "Running" : "Queued"}</small></div><em></em></div>`).join(""); }

function renderObjects() {
  if (!state.objects.length) { $("object-tabs").innerHTML = ""; $("semantic-list").innerHTML = '<div class="empty-state">No semantic objects were returned. Choose Full output detail to include detailed objects.</div>'; return; }
  if (!GROUPS.some(([key]) => key === state.activeGroup)) state.activeGroup = GROUPS[0][0];
  if (!state.objects.some((item) => item.object_type === state.activeGroup)) {
    state.activeGroup = GROUPS.find(([key]) => state.objects.some((item) => item.object_type === key))?.[0] || GROUPS[0][0];
  }
  $("object-tabs").innerHTML = GROUPS.map(([key, label]) => `<button class="tab ${key === state.activeGroup ? "active" : ""}" data-group="${key}" role="tab">${label} (${state.objects.filter((item) => item.object_type === key).length})</button>`).join("");
  $("object-tabs").querySelectorAll("button").forEach((button) => button.addEventListener("click", () => { state.activeGroup = button.dataset.group; renderObjects(); }));
  const items = state.objects.filter((item) => item.object_type === state.activeGroup);
  if (!items.length) { $("semantic-list").innerHTML = '<div class="empty-state">No objects in this group for the current document.</div>'; return; }
  $("semantic-list").innerHTML = items.map((item, index) => {
    const id = item.object_id || item.candidate_id || `${item.name}-${index}`;
    return `<button class="semantic-object ${state.activeObject?.__id === id ? "active" : ""}" data-id="${escapeHtml(id)}"><header><strong>${escapeHtml(item.name || "Unnamed object")}</strong><span class="object-type">${escapeHtml(item.object_type || "object")}</span></header><p>Confidence ${formatConfidence(item.confidence)} · Page ${item.page ?? "—"} · Block ${escapeHtml(item.block_id || "—")}</p></button>`;
  }).join("");
  $("semantic-list").querySelectorAll(".semantic-object").forEach((button) => button.addEventListener("click", () => {
    const item = items.find((candidate, index) => (candidate.object_id || candidate.candidate_id || `${candidate.name}-${index}`) === button.dataset.id);
    selectObject(item);
  }));
}

async function selectObject(object) {
  state.activeObject = { ...object, __id: object.object_id || object.candidate_id || object.name };
  renderObjects();
  const target = $("evidence-content"); target.className = "evidence-content"; target.innerHTML = '<div class="empty-state">Loading provenance…</div>';
  let provenance = null;
  try { if (object.provenance_id) provenance = await parseResponse(await fetch(`${API}/relay/provenance/${encodeURIComponent(object.provenance_id)}`)); }
  catch (error) { provenance = { evidence: [], warning: error.message }; }
  renderEvidence(object, provenance);
}

function renderEvidence(object, provenance) {
  const evidence = provenance?.evidence?.[0] || {};
  const text = evidence.text || object.attributes?.matched_text || object.name || "No source text returned.";
  const start = evidence.start_offset ?? object.offset?.start;
  const end = evidence.end_offset ?? object.offset?.end;
  const model = provenance?.model_details?.[0] || {};
  const rows = [
    ["Page", evidence.page_no ?? object.page ?? "—"], ["Block", evidence.block_id ?? object.block_id ?? "—"],
    ["Offset", start != null ? `${start}–${end ?? "—"}` : "—"], ["Rule", provenance?.rule_ids?.join(", ") || object.category || "—"],
    ["Ground", provenance?.ground_snapshot_id || object.ground_snapshot_id || "—"], ["Plugin", evidence.metadata?.resource_id || model.resource_id || "—"],
    ["Model", model.model_version || model.model_name || "—"], ["Provenance", provenance?.provenance_id || object.provenance_id || "—"],
  ];
  $("evidence-content").innerHTML = `<h4>${escapeHtml(object.name || "Semantic object")}</h4><div class="evidence-meta">${rows.map(([key, value]) => `<div><span>${key}</span>${escapeHtml(String(value))}</div>`).join("")}</div><div class="evidence-snippet">${highlightText(text, start, end)}</div>${provenance?.warning ? `<p class="request-note">${escapeHtml(provenance.warning)}</p>` : ""}<ul class="detail-list"><li><b>Source mentions</b>${escapeHtml((provenance?.source_mention_ids || object.source_mentions || []).join(", ") || "—")}</li><li><b>Validation</b>${escapeHtml((provenance?.validation_records || []).join(", ") || "—")}</li><li><b>Resource plan</b>${escapeHtml(provenance?.resource_plan_id || object.resource_plan_id || "—")}</li></ul>`;
}

function renderResources() {
  const plan = state.resources || {}, selection = state.ground?.selection || {}, snapshot = state.ground?.snapshot || {};
  const records = plan.selection_records || [];
  const modelRows = state.models.length ? state.models : records.map((item) => ({ capability: item.capability, resource_id: item.selected_resource_id, model_version: item.model_version, duration_ms: item.latency_ms, status: item.actual_execution ? "completed" : "skipped", fallback_used: item.fallback_used, skip_reason: item.skip_reason }));
  const fallback = records.filter((item) => item.fallback_used).map((item) => item.capability).join(", ") || "None";
  $("resource-content").className = "";
  $("resource-content").innerHTML = `<div class="resource-section"><h4>Ground profile</h4><p>${escapeHtml(selection.selected_profile_id || snapshot.profile_id || state.relay?.ground?.profile_id || "—")} · ${escapeHtml(selection.selected_profile_version || snapshot.profile_version || "—")}<br>${escapeHtml(selection.selection_reason || state.relay?.ground?.selection_reason || "")}</p></div><div class="resource-section"><h4>Resource plan</h4><p>${escapeHtml(plan.plan_id || state.relay?.resources?.plan_id || "—")} · Profile ${escapeHtml(plan.resource_profile_id || "—")}<br>Fallback resources: ${escapeHtml(fallback)}</p></div><table class="model-table"><thead><tr><th>Capability</th><th>Plugin / model</th><th>Status</th><th>Time</th></tr></thead><tbody>${modelRows.map((item) => `<tr><td>${escapeHtml(item.capability || "—")}</td><td>${escapeHtml(item.resource_id || "—")}<br><small>${escapeHtml(item.model_version || "")}${item.fallback_used ? " · fallback" : ""}</small></td><td><span class="state ${escapeHtml(item.status || "skipped")}">${escapeHtml(item.status || "skipped")}</span>${item.skip_reason ? `<br><small>${escapeHtml(item.skip_reason)}</small>` : ""}</td><td>${escapeHtml(formatDuration(item.duration_ms))}</td></tr>`).join("") || '<tr><td colspan="4">No model records returned.</td></tr>'}</tbody></table>`;
}

function renderUom() {
  const uom = state.uom;
  const tabs = [["mom", "MOM"], ["som", "SOM"], ["bom", "BOM"], ["semantic_objects", "Semantic Objects"], ["processing", "Processing"], ["resources", "Resources"], ["ground", "Ground"], ["provenance", "Provenance"]];
  $("download-uom").disabled = !uom;
  $("uom-tabs").innerHTML = tabs.map(([key, label]) => `<button class="tab ${state.activeUom === key ? "active" : ""}" data-uom="${key}">${label}</button>`).join("");
  $("uom-tabs").querySelectorAll("button").forEach((button) => button.addEventListener("click", () => { state.activeUom = button.dataset.uom; renderUom(); }));
  const view = { mom: uom?.mom, som: uom?.som, bom: uom?.bom, semantic_objects: uom?.semantic_objects, processing: uom?.processing, resources: state.resources, ground: state.ground, provenance: state.activeObject ? { provenance_id: state.activeObject.provenance_id, hint: "Click the semantic object to load its detailed provenance." } : { hint: "Select a semantic object to inspect provenance." } }[state.activeUom];
  $("uom-tree").className = "json-tree";
  $("uom-tree").innerHTML = view ? jsonTree(view) : '<div class="empty-state">This output section is unavailable for the selected detail level.</div>';
}

function jsonTree(value, key = null) {
  const label = key == null ? "root" : escapeHtml(String(key));
  if (value === null || typeof value !== "object") return `<div><span class="json-key">${label}</span>: ${jsonValue(value)}</div>`;
  const entries = Array.isArray(value) ? value.map((item, index) => [index, item]) : Object.entries(value);
  return `<details open><summary><span class="json-key">${label}</span> ${Array.isArray(value) ? `[${entries.length}]` : `{${entries.length}}`}</summary>${entries.map(([childKey, child]) => jsonTree(child, childKey)).join("")}</details>`;
}
function jsonValue(value) { if (value === null) return '<span class="json-null">null</span>'; if (typeof value === "number" || typeof value === "boolean") return `<span class="json-number">${escapeHtml(String(value))}</span>`; return `<span class="json-string">"${escapeHtml(String(value))}"</span>`; }
function downloadUom() { if (!state.uom) return; const blob = new Blob([JSON.stringify(state.uom, null, 2)], { type: "application/json" }); const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = `${state.uom.package_id || state.relay?.execution_id || "zyrelay-uom"}.json`; link.click(); URL.revokeObjectURL(url); }

function appendPageCount(count) { const summary = $("file-summary"); const pageText = Number.isFinite(count) && count > 0 ? `${count} page${count === 1 ? "" : "s"}` : "Page count not available for this format"; summary.innerHTML = `${summary.innerHTML.replace(/ · Page count[^<]*/i, "")}<span> · ${pageText}</span>`; }
function resetResultState() { state.relay = state.execution = state.ground = state.resources = state.uom = null; state.models = []; state.objects = []; state.activeObject = null; $("results").hidden = true; }
function setNote(message, error = false) { const target = $("request-note"); target.textContent = message; target.style.color = error ? "var(--red)" : ""; }
async function checkHealth() { try { const health = await parseResponse(await fetch("/health")); $("service-state").textContent = `Service online · v${health.version}`; $("service-state").className = "status-dot ok"; } catch (_) { $("service-state").textContent = "Service unavailable"; $("service-state").className = "status-dot error"; } }
async function parseResponse(response) { const body = await response.json().catch(() => ({})); if (!response.ok) throw new Error(body.message || body.detail || body.error_code || `Request failed (${response.status})`); return body; }
function formatBytes(bytes) { if (!Number.isFinite(bytes)) return "—"; const units = ["B", "KB", "MB", "GB"]; let index = 0, value = bytes; while (value >= 1024 && index < units.length - 1) { value /= 1024; index += 1; } return `${value.toFixed(index ? 1 : 0)} ${units[index]}`; }
function formatDuration(value) { return Number.isFinite(value) ? (value >= 1000 ? `${(value / 1000).toFixed(value >= 10000 ? 1 : 2)} s` : `${Math.round(value)} ms`) : "—"; }
function formatConfidence(value) { return Number.isFinite(value) ? `${Math.round(value * 100)}%` : "—"; }
function escapeHtml(value) { return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]); }
function highlightText(text, start, end) { const source = String(text || ""); if (Number.isInteger(start) && Number.isInteger(end) && start >= 0 && end > start && end <= source.length) return `${escapeHtml(source.slice(0, start))}<mark>${escapeHtml(source.slice(start, end))}</mark>${escapeHtml(source.slice(end))}`; return escapeHtml(source); }
