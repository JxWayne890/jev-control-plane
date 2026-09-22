const $ = (selector) => document.querySelector(selector);
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[character]));
const pretty = (value) => String(value ?? "unknown").replaceAll("_", " ");
let state = null;
let handoffPacket = null;

function setView(name) {
  document.querySelectorAll(".view").forEach((item) => item.classList.toggle("active", item.id === `view-${name}`));
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === name));
  const labels = {overview:"Overview",decisions:"Decisions",lab:"Test lab",models:"Model controls",projects:"Project and safety",results:"Results",handoff:"Handoffs"};
  $("#crumb-name").textContent = labels[name] || name;
  window.scrollTo({top:0,behavior:"smooth"});
}

function metric(label, value, note, icon, status = false) {
  return `<div class="metric"><div class="metric-top"><span>${esc(label)}</span><span class="metric-icon">${icon}</span></div><strong class="${status ? "status-word" : ""}">${esc(value)}</strong><small>${esc(note)}</small></div>`;
}

function counts(decisions) {
  return {
    total: decisions.length,
    jev: decisions.filter((item) => item.decision_provider === "jev").length,
    fallback: decisions.filter((item) => item.decision_provider === "local_fallback").length,
    applied: decisions.filter((item) => item.route_applied === true).length,
    blocked: decisions.filter((item) => item.external_writes_blocked === true).length,
  };
}

function timeLabel(value) {
  if (!value) return "Time unavailable";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString(undefined,{month:"short",day:"numeric",hour:"numeric",minute:"2-digit"});
}

function decisionRow(item, index) {
  const profile = item.model?.profile || "unknown";
  const risk = item.risk_level || "unknown";
  const runtime = item.runtime?.model || "not recorded";
  return `<button class="decision-row" data-decision="${index}"><span class="decision-symbol">${profile === "critical_review" ? "◆" : "◇"}</span><span class="decision-main"><strong>${esc(pretty(profile))}</strong><small>${esc(runtime)} · ${esc(timeLabel(item.decided_at))} · ${esc(pretty(item.decision_provider))}</small></span><span class="pill ${esc(risk)}">${esc(risk.toUpperCase())}</span></button>`;
}

function bars(items, field, color = "") {
  const totals = {};
  items.forEach((item) => { const key = field(item) || "unknown"; totals[key] = (totals[key] || 0) + 1; });
  const entries = Object.entries(totals).sort((a,b) => b[1] - a[1]);
  if (!entries.length) return `<div class="empty-state">No recorded decisions yet.</div>`;
  return entries.map(([name,count]) => `<div class="bar-item"><div class="bar-caption"><span>${esc(pretty(name))}</span><b>${count}</b></div><div class="bar-track"><div class="bar-fill ${color} bar-${Math.max(10,Math.round(10*count/items.length)*10)}"></div></div></div>`).join("");
}

function details(rows) {
  return rows.map(([label,value,warn]) => `<div class="detail-row"><span>${esc(label)}</span><span class="${warn ? "warn" : ""}">${esc(value)}</span></div>`).join("");
}

function renderOverview() {
  const list = state.decisions;
  const result = counts(list);
  const connected = state.connection.router_endpoint_configured && state.connection.router_token_configured;
  $("#overview-metrics").innerHTML = metric("Decisions recorded",result.total,"Current local log window","◫") + metric("JEV decisions",result.jev,"Confirmed decision provider","✧") + metric("Local fallbacks",result.fallback,"Always labeled explicitly","↺") + metric("Router status",connected ? "Configured" : "Needs setup",connected ? "Endpoint and token present" : "Local rules remain available","●",true);
  $("#recent-list").innerHTML = list.length ? list.slice().reverse().slice(0,5).map((item,index) => decisionRow(item,list.length-1-index)).join("") : `<div class="empty-state">No decisions in the selected log yet. Try the test lab or connect a plugin data directory.</div>`;
  $("#profile-bars").innerHTML = bars(list,(item) => item.model?.profile);
  $("#history-list").innerHTML = list.length ? list.slice().reverse().map((item,index) => decisionRow(item,list.length-1-index)).join("") : `<div class="empty-state">No decision records available.</div>`;
  $("#result-metrics").innerHTML = metric("Recorded decisions",result.total,"Current visible log window","◫") + metric("JEV decisions",result.jev,"Verified provider field","✧") + metric("Routes applied",result.applied,"Logged delegated rewrites only","↗") + metric("External writes blocked",result.blocked,"Safety state in decision records","▣");
  $("#provider-bars").innerHTML = bars(list,(item) => item.decision_provider,"green");
  if (state.demo) { $("#demo-label").hidden = false; $("#banner").hidden = false; $("#banner").textContent = "Sample data mode. These example decisions are fictional and do not represent live routing or savings."; }
  else if (!state.connection.decision_log_available) { $("#banner").hidden = false; $("#banner").textContent = "No plugin data directory was found. Pass --data-dir to see recorded decisions from an installation."; }
  else { $("#banner").hidden = true; }
}

function showDecision(index) {
  const item = state.decisions[index];
  if (!item) return;
  document.querySelectorAll(".decision-row").forEach((row) => row.classList.toggle("selected",Number(row.dataset.decision) === index));
  $("#decision-detail").classList.remove("empty-state");
  $("#decision-detail").innerHTML = details([
    ["Decision provider",item.decision_provider],
    ["Decision model",item.decision_model],
    ["Model profile",item.model?.profile],
    ["Requested runtime",item.runtime?.model],
    ["Reasoning effort",item.runtime?.reasoning_effort],
    ["Scope",item.scope_status],
    ["Risk",item.risk_level],
    ["Thread",item.thread?.action],
    ["Worktree recommended",String(item.thread?.worktree_recommended ?? false)],
    ["Routing mode",item.routing_mode || "active"],
    ["Route applied",item.route_applied === undefined ? "not recorded" : String(item.route_applied)],
    ["Confirmation required",String(item.requires_confirmation)],
    ["External writes blocked",String(item.external_writes_blocked),item.external_writes_blocked],
    ["Repository match",String(item.repository?.matches ?? "unknown")],
    ["Warnings",(item.warnings || []).join(", ") || "none",(item.warnings || []).length > 0],
  ]);
}

function renderModels() {
  $("#model-grid").innerHTML = state.models.map((item) => `<div class="model-card"><small>ROUTING PROFILE</small><h3>${esc(pretty(item.profile))}</h3>${["codex","claude"].map((host) => `<form class="model-form" data-model-host="${host}" data-model-profile="${esc(item.profile)}"><label class="model-label" for="model-${host}-${esc(item.profile)}">${host === "codex" ? "CODEX" : "CLAUDE CODE"} <span>${esc(item.source[host])}</span></label><input id="model-${host}-${esc(item.profile)}" name="model" value="${esc(item[host])}" maxlength="100" aria-label="${host} model for ${esc(pretty(item.profile))}"><button type="submit" ${state.demo ? "disabled" : ""}>Save</button></form>`).join("")}</div>`).join("");
}

function renderProject() {
  const project = state.project;
  $("#project-detail").innerHTML = details([
    ["Client",project.client],["Project",project.name],["Phase",project.phase],
    ["Manifest",project.manifest || "missing",!project.manifest],["Routing mode",project.routing_mode],
    ["Required scope",project.required_scope?.join(", ") || "not listed"],
    ["Excluded scope",project.excluded_scope?.join(", ") || "none"],
    ["Definition of done",project.definition_of_done?.join("; ") || "not listed"],
  ]);
  $("#policy-detail").innerHTML = details([
    ["Production confirmation",String(project.policy?.production_requires_confirmation ?? true)],
    ["Destructive actions",project.policy?.destructive_actions || "not set"],
    ["Project warnings",project.warnings?.join(", ") || "none",(project.warnings || []).length > 0],
    ["Router endpoint",state.connection.router_endpoint_configured ? "configured" : "not configured"],
    ["Router token",state.connection.router_token_configured ? "present" : "not configured"],
  ]);
  $("#recipe-grid").innerHTML = state.recipes.map((recipe) => `<div class="recipe-card"><h3>${esc(recipe.name)}</h3><p>${esc(recipe.description)}</p><button class="text-link" data-recipe="${esc(recipe.id)}">Preview recipe →</button></div>`).join("");
}

async function postJson(url, payload) {
  const response = await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}

function renderPreview(item) {
  $("#lab-result").className = "";
  $("#lab-result").innerHTML = `<div class="route-hero"><small>RECOMMENDED PROFILE</small><strong>${esc(pretty(item.model?.profile))}</strong><span>${esc(item.runtime?.model)} · ${esc(item.runtime?.reasoning_effort)} reasoning · ${esc(pretty(item.decision_provider))}</span></div><div class="result-details">${details([
    ["Scope",item.scope_status],["Risk",item.risk_level],["Thread",item.thread?.action],
    ["Worktree",String(item.thread?.worktree_recommended)],
    ["Confirmation required",String(item.requires_confirmation)],
    ["External writes blocked",String(item.external_writes_blocked),item.external_writes_blocked],
    ["Routing mode",item.routing_mode],["Warnings",item.warnings?.join(", ") || "none",(item.warnings || []).length > 0],
  ])}</div>`;
}

async function loadState() {
  const response = await fetch("/api/state");
  if (!response.ok) throw new Error("Could not load dashboard data");
  state = await response.json();
  renderOverview(); renderModels(); renderProject();
}

document.addEventListener("click",async (event) => {
  const nav = event.target.closest("[data-view],[data-go]");
  if (nav) setView(nav.dataset.view || nav.dataset.go);
  const row = event.target.closest("[data-decision]");
  if (row) {showDecision(Number(row.dataset.decision)); setView("decisions");}
  const recipe = event.target.closest("[data-recipe]");
  if (recipe) {
    try {
      const result = await postJson("/api/recipe-preview",{recipe_id:recipe.dataset.recipe});
      $("#recipe-preview").innerHTML = `<pre>${esc(JSON.stringify({before:result.before,after:result.after},null,2))}</pre>`;
    } catch (error) {$("#recipe-preview").innerHTML = `<p class="error-message">${esc(error.message)}</p>`;}
  }
});

$("#refresh-button").addEventListener("click",() => loadState().catch((error) => alert(error.message)));
$("#lab-form").addEventListener("submit",async (event) => {
  event.preventDefault();
  $("#lab-result").className = "empty-state";
  $("#lab-result").textContent = "Calculating preview...";
  try {
    const result = await postJson("/api/preview",{prompt:$("#lab-prompt").value,host:$("#lab-host").value,use_jev:$("#lab-use-jev").checked});
    renderPreview(result);
  } catch (error) {$("#lab-result").className = "error-message";$("#lab-result").textContent = error.message;}
});
$("#handoff-form").addEventListener("submit",async (event) => {
  event.preventDefault();
  try {
    handoffPacket = await postJson("/api/handoff",{prompt:$("#handoff-prompt").value});
    $("#handoff-result").className = "packet-json";
    $("#handoff-result").textContent = JSON.stringify(handoffPacket,null,2);
    $("#download-handoff").hidden = false;
  } catch (error) {$("#handoff-result").className = "error-message";$("#handoff-result").textContent = error.message;}
});
$("#download-handoff").addEventListener("click",() => {
  if (!handoffPacket) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(handoffPacket,null,2)],{type:"application/json"}));
  const anchor = document.createElement("a");anchor.href = url;anchor.download = "jev-handoff.json";anchor.click();URL.revokeObjectURL(url);
});
document.addEventListener("submit",async (event) => {
  const form = event.target.closest("[data-model-host]");
  if (!form) return;
  event.preventDefault();
  const host = form.dataset.modelHost;
  const profile = form.dataset.modelProfile;
  const model = form.elements.model.value.trim();
  const current = state.models.find((item) => item.profile === profile)?.configured[host] ?? null;
  if (!window.confirm(`Save ${model} as the ${host} model for ${pretty(profile)} in this project's manifest?`)) return;
  try {
    await postJson("/api/model-map",{project_id:state.project.name,host,profile,model,expected_current:current});
    await loadState();
    $("#model-status").textContent = `Saved ${host} ${pretty(profile)} mapping in the project manifest.`;
  } catch (error) {$("#model-status").textContent = error.message;}
});
loadState().catch((error) => {$("#banner").hidden = false;$("#banner").textContent = error.message;});
