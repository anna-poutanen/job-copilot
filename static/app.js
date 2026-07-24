const $ = (id) => document.getElementById(id);
const api = async (path, body) => {
  const opts = body
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
    : {};
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || `Request failed (${r.status})`);
  return data;
};
const setNote = (el, msg, kind = "") => { el.textContent = msg; el.className = "note " + kind; };
const esc = (s) => (s || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

/* ---------- tabs ---------- */
document.querySelectorAll(".tab").forEach((t) =>
  t.addEventListener("click", () => showTab(t.dataset.tab))
);
function showTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("is-active", t.dataset.tab === name));
  document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("is-active", p.id === name));
  if (name === "activity") loadLog();
}

/* ---------- status chips ---------- */
async function loadStatus() {
  try {
    const s = await api("/api/config");
    const chip = (label, ok) => `<span class="chip ${ok ? "ok" : "off"}"><span class="dot"></span>${label}: ${ok ? "ready" : "not set"}</span>`;
    $("status-chips").innerHTML =
      chip("LLM", s.llm_ready) +
      `<span class="chip ${s.llm_ready ? "ok" : "off"}"><span class="dot"></span>${esc(s.model)}</span>` +
      chip("Email", s.smtp_ready) +
      chip("Resume", s.resume_loaded) +
      (s.adzuna_ready ? chip("Adzuna", true) : "");
  } catch (e) {
    $("status-chips").innerHTML = `<span class="chip off"><span class="dot"></span>server unreachable</span>`;
  }
}

/* ---------- find jobs ---------- */
$("btn-search").addEventListener("click", async () => {
  const sources = [...document.querySelectorAll(".sources input:checked")].map((c) => c.value);
  const btn = $("btn-search");
  btn.disabled = true;
  setNote($("search-note"), "Searching feeds…");
  try {
    const res = await api("/api/jobs/search", {
      query: $("job-query").value.trim(),
      location: $("job-location").value.trim(),
      sources,
      limit: Number($("job-limit").value) || 60,
    });
    renderJobs(res.jobs);
    setNote($("search-note"), `${res.count} matches (checked ${res.checked}, ${res.added} new)`, "good");
  } catch (e) {
    setNote($("search-note"), e.message, "err");
  } finally {
    btn.disabled = false;
  }
});

function renderJobs(jobs) {
  const wrap = $("jobs-list");
  if (!jobs.length) { wrap.innerHTML = `<p class="empty">No matches. Try broader keywords, add sources, or clear the location filter.</p>`; return; }
  wrap.innerHTML = jobs.map((j, i) => `
    <div class="job">
      <h3>${esc(j.title)}</h3>
      <div class="meta">
        <span class="badge">${esc(j.source)}</span>
        <span>${esc(j.company) || "—"}</span>
        <span>${esc(j.location) || "location n/a"}</span>
      </div>
      <div class="row">
        <a href="${esc(j.url)}" target="_blank" rel="noopener">View posting ↗</a>
        <button class="link-btn" data-draft="${i}">Draft outreach →</button>
      </div>
    </div>`).join("");
  wrap.querySelectorAll("[data-draft]").forEach((b) =>
    b.addEventListener("click", () => draftFromJob(jobs[Number(b.dataset.draft)]))
  );
}

function draftFromJob(job) {
  $("o-company").value = job.company || "";
  $("o-role").value = job.title || "";
  $("o-url").value = job.url || "";
  showTab("outreach");
  $("o-company").scrollIntoView({ behavior: "smooth", block: "center" });
}

/* ---------- outreach ---------- */
$("btn-gen-outreach").addEventListener("click", async () => {
  const btn = $("btn-gen-outreach");
  if (!$("o-company").value.trim()) return setNote($("outreach-note"), "Add a company first.", "err");
  btn.disabled = true;
  setNote($("outreach-note"), "Researching + writing…");
  try {
    const res = await api("/api/generate/outreach", {
      company: $("o-company").value.trim(),
      role: $("o-role").value.trim(),
      contact_name: $("o-contact").value.trim(),
      job_url: $("o-url").value.trim(),
      company_url: $("o-research-url").value.trim(),
      do_research: $("o-research").checked,
    });
    $("out-subject").value = res.subject || "";
    $("out-email").value = res.email || "";
    $("out-dm").value = res.linkedin_dm || "";
    $("send-to").value = $("o-email").value.trim();
    $("outreach-output").classList.remove("hidden");
    setNote($("outreach-note"), "Draft ready — edit before sending.", "good");
  } catch (e) {
    setNote($("outreach-note"), e.message, "err");
  } finally {
    btn.disabled = false;
  }
});

/* live-send toggle changes the button */
$("send-live").addEventListener("change", (e) => {
  const btn = $("btn-send");
  btn.textContent = e.target.checked ? "Send for real" : "Preview send";
  btn.classList.toggle("live", e.target.checked);
});

$("btn-send").addEventListener("click", async () => {
  const to = $("send-to").value.trim();
  if (!to) return setNote($("send-note"), "Add a recipient email.", "err");
  const live = $("send-live").checked;
  if (live && !confirm(`Really send this email to ${to}?`)) return;
  const btn = $("btn-send");
  btn.disabled = true;
  setNote($("send-note"), live ? "Sending…" : "Previewing…");
  try {
    const res = await api("/api/email/send", {
      dry_run: !live,
      messages: [{ to, subject: $("out-subject").value, body: $("out-email").value }],
    });
    const r = res.results[0];
    if (r.status === "sent") setNote($("send-note"), "Sent ✓ (logged in Activity).", "good");
    else if (r.status === "preview") setNote($("send-note"), "Preview OK — valid + logged, not sent.", "good");
    else setNote($("send-note"), `${r.status}: ${r.detail || "check the address"}`, "err");
  } catch (e) {
    setNote($("send-note"), e.message, "err");
  } finally {
    btn.disabled = false;
  }
});

/* ---------- cover letter ---------- */
$("btn-gen-cover").addEventListener("click", async () => {
  const btn = $("btn-gen-cover");
  if ($("c-jd").value.trim().length < 40) return setNote($("cover-note"), "Paste the full job description.", "err");
  btn.disabled = true;
  setNote($("cover-note"), "Researching + writing…");
  try {
    const res = await api("/api/generate/cover-letter", {
      job_description: $("c-jd").value.trim(),
      company: $("c-company").value.trim(),
      company_url: $("c-url").value.trim(),
      do_research: $("c-research").checked,
    });
    $("cover-text").value = res.cover_letter || "";
    $("cover-output").classList.remove("hidden");
    setNote($("cover-note"), "Letter ready — edit as needed.", "good");
  } catch (e) {
    setNote($("cover-note"), e.message, "err");
  } finally {
    btn.disabled = false;
  }
});

/* ---------- copy buttons ---------- */
document.querySelectorAll("[data-copy]").forEach((b) =>
  b.addEventListener("click", async () => {
    await navigator.clipboard.writeText($(b.dataset.copy).value);
    const t = b.textContent; b.textContent = "Copied ✓";
    setTimeout(() => (b.textContent = t), 1400);
  })
);

/* ---------- activity log ---------- */
$("btn-refresh-log").addEventListener("click", loadLog);
async function loadLog() {
  try {
    const { log } = await api("/api/log");
    if (!log.length) { $("log-table").innerHTML = `<p class="empty">Nothing yet.</p>`; return; }
    $("log-table").innerHTML = `<table><thead><tr>
        <th>When</th><th>To</th><th>Subject</th><th>Mode</th><th>Status</th></tr></thead><tbody>` +
      log.map((e) => `<tr>
        <td>${new Date(e.sent_at * 1000).toLocaleString()}</td>
        <td>${esc(e.recipient)}</td>
        <td>${esc(e.subject)}</td>
        <td>${e.dry_run ? "preview" : "live"}</td>
        <td><span class="tag ${esc(e.status)}">${esc(e.status)}</span></td>
      </tr>`).join("") + `</tbody></table>`;
  } catch (e) {
    $("log-table").innerHTML = `<p class="empty">${esc(e.message)}</p>`;
  }
}

loadStatus();
