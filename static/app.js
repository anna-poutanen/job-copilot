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
  if (name === "today" && !todayLoaded) { todayLoaded = true; loadAgenda(); loadInbox(); }
  if (name === "todos") loadTodos();
  if (name === "pipeline") loadPipeline();
}

/* ---------- today ---------- */
let todayLoaded = false;

async function loadAgenda() {
  const box = $("agenda-list");
  box.innerHTML = `<p class="empty">Loading…</p>`;
  try {
    const a = await api("/api/agenda?days=1");
    if (!a.feeds_configured) {
      box.innerHTML = `<p class="empty">No calendars yet. Add ICS feed URLs in data/accounts.json.</p>`;
      return;
    }
    if (!a.events.length) {
      box.innerHTML = `<p class="empty">Nothing scheduled today (${a.feeds_ok}/${a.feeds_configured} feeds loaded).</p>`;
      return;
    }
    let html = "", lastDay = "";
    for (const e of a.events) {
      if (e.day !== lastDay) { html += `<p class="day-head">${esc(e.day)}</p>`; lastDay = e.day; }
      html += `<div class="agenda-item">
        <div class="agenda-time">${esc(e.time_label)}</div>
        <div class="agenda-body">
          <div class="t">${esc(e.title)}</div>
          <div class="m">${esc(e.calendar)}${e.location ? " · " + esc(e.location) : ""}</div>
        </div></div>`;
    }
    box.innerHTML = html;
  } catch (e) {
    box.innerHTML = `<p class="empty">${esc(e.message)}</p>`;
  }
}

async function loadInbox() {
  const box = $("inbox-list");
  box.innerHTML = `<p class="empty">Loading…</p>`;
  try {
    const d = await api("/api/inbox?days=2");
    if (!d.configured) {
      box.innerHTML = `<p class="empty">${esc(d.note)}</p>`;
      return;
    }
    let html = "";
    for (const acct of d.accounts) {
      html += `<p class="acct-head">${esc(acct.account)}</p>`;
      if (acct.error) { html += `<p class="acct-err">${esc(acct.error)}</p>`; continue; }
      if (!acct.messages.length) { html += `<p class="empty">No recent mail.</p>`; continue; }
      for (const m of acct.messages) {
        html += `<div class="mail-item">
          <div class="s">${esc(m.subject)}</div>
          <div class="f">${esc(m.from)}</div>
          ${m.snippet ? `<div class="snip">${esc(m.snippet)}</div>` : ""}
        </div>`;
      }
    }
    box.innerHTML = html;
  } catch (e) {
    box.innerHTML = `<p class="empty">${esc(e.message)}</p>`;
  }
}

$("btn-agenda").addEventListener("click", () => { loadAgenda(); if ($("show-inbox").checked) loadInbox(); });

$("btn-brief").addEventListener("click", async () => {
  const btn = $("btn-brief");
  btn.disabled = true;
  setNote($("today-note"), "Pulling your day together…");
  try {
    const res = await api("/api/briefing", {});
    $("brief-box").textContent = res.brief;
    $("brief-box").classList.remove("hidden");
    setNote($("today-note"), "", "good");
    if (res.agenda) renderAgendaFrom(res.agenda);
    if ($("show-inbox").checked) loadInbox();
  } catch (e) {
    setNote($("today-note"), e.message, "err");
  } finally {
    btn.disabled = false;
  }
});

function renderAgendaFrom(a) {
  // reuse loadAgenda's rendering by faking the box from returned data
  const box = $("agenda-list");
  if (!a.events || !a.events.length) return;
  let html = "", lastDay = "";
  for (const e of a.events) {
    if (e.day !== lastDay) { html += `<p class="day-head">${esc(e.day)}</p>`; lastDay = e.day; }
    html += `<div class="agenda-item"><div class="agenda-time">${esc(e.time_label)}</div>
      <div class="agenda-body"><div class="t">${esc(e.title)}</div>
      <div class="m">${esc(e.calendar)}${e.location ? " · " + esc(e.location) : ""}</div></div></div>`;
  }
  box.innerHTML = html;
}

/* ---------- to-dos ---------- */
function dueBadge(due) {
  if (!due) return "";
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const d = new Date(due + "T00:00:00");
  const days = Math.round((d - today) / 86400000);
  let cls = "", label = due;
  if (days < 0) { cls = "overdue"; label = `${due} · overdue`; }
  else if (days === 0) { cls = "soon"; label = "today"; }
  else if (days <= 3) { cls = "soon"; label = `${due} · ${days}d`; }
  return `<span class="due ${cls}">${esc(label)}</span>`;
}

async function loadTodos() {
  const box = $("todo-list");
  try {
    const { todos } = await api("/api/todos");
    if (!todos.length) { box.innerHTML = `<p class="empty">No tasks yet. Scan your email or add one above.</p>`; return; }
    box.innerHTML = todos.map((t) => `
      <div class="todo-item ${t.done ? "done" : ""}">
        <input type="checkbox" ${t.done ? "checked" : ""} data-done="${t.id}">
        <div class="todo-body">
          <div class="task">${esc(t.task)}</div>
          <div class="todo-meta">
            ${dueBadge(t.due)}
            ${t.priority && t.priority !== "normal" ? `<span class="prio ${esc(t.priority)}">${esc(t.priority)}</span>` : ""}
            ${t.source ? `<span class="todo-src">${esc(t.source)}</span>` : ""}
          </div>
        </div>
        <button class="x-btn" data-del-todo="${t.id}" title="Delete">×</button>
      </div>`).join("");
    box.querySelectorAll("[data-done]").forEach((c) =>
      c.addEventListener("change", async () => {
        await api("/api/todos/update", { id: Number(c.dataset.done), done: c.checked });
        loadTodos();
      }));
    box.querySelectorAll("[data-del-todo]").forEach((b) =>
      b.addEventListener("click", async () => {
        await api("/api/todos/delete", { id: Number(b.dataset.delTodo) });
        loadTodos();
      }));
  } catch (e) {
    box.innerHTML = `<p class="empty">${esc(e.message)}</p>`;
  }
}

$("btn-extract").addEventListener("click", async () => {
  const btn = $("btn-extract");
  btn.disabled = true;
  setNote($("todo-note"), "Reading your inbox…");
  try {
    const res = await api("/api/todos/extract", {});
    setNote($("todo-note"), `Found ${res.added} new task${res.added === 1 ? "" : "s"} (scanned ${res.scanned || 0} emails).`, "good");
    loadTodos();
  } catch (e) {
    setNote($("todo-note"), e.message, "err");
  } finally {
    btn.disabled = false;
  }
});

$("btn-add-todo").addEventListener("click", async () => {
  const task = $("todo-task").value.trim();
  if (!task) return setNote($("todo-note"), "Type a task first.", "err");
  await api("/api/todos/add", { task, due: $("todo-due").value, priority: $("todo-prio").value });
  $("todo-task").value = ""; $("todo-due").value = "";
  setNote($("todo-note"), "Added.", "good");
  loadTodos();
});

/* ---------- pipeline ---------- */
const STAGE_LABEL = { saved: "Saved", applied: "Applied", interviewing: "Interviewing", offer: "Offer", rejected: "Rejected" };

async function loadPipeline() {
  const board = $("pipeline-board");
  try {
    const { stages, items } = await api("/api/pipeline");
    board.innerHTML = stages.map((stage) => {
      const inStage = items.filter((i) => i.status === stage);
      const cards = inStage.length
        ? inStage.map((j) => pipeCard(j, stages)).join("")
        : `<div class="col-empty">—</div>`;
      return `<div class="pipe-col">
        <h4>${STAGE_LABEL[stage] || stage}<span class="cnt">${inStage.length}</span></h4>
        ${cards}
      </div>`;
    }).join("");
    wirePipe(board);
  } catch (e) {
    board.innerHTML = `<p class="empty">${esc(e.message)}</p>`;
  }
}

function pipeCard(j, stages) {
  const opts = stages.map((s) => `<option value="${s}" ${s === j.status ? "selected" : ""}>${STAGE_LABEL[s] || s}</option>`).join("");
  return `<div class="pipe-card">
    <div class="t">${esc(j.title) || "(role)"}</div>
    <div class="c">${esc(j.company) || "—"}</div>
    <div class="foot">
      <select data-move="${j.id}">${opts}</select>
      <button class="x-btn" data-del-job="${j.id}" title="Remove">×</button>
    </div>
    ${j.url ? `<div style="margin-top:6px"><a href="${esc(j.url)}" target="_blank" rel="noopener">posting ↗</a></div>` : ""}
  </div>`;
}

function wirePipe(board) {
  board.querySelectorAll("[data-move]").forEach((sel) =>
    sel.addEventListener("change", async () => {
      await api("/api/jobs/update", { id: Number(sel.dataset.move), status: sel.value });
      loadPipeline();
    }));
  board.querySelectorAll("[data-del-job]").forEach((b) =>
    b.addEventListener("click", async () => {
      await api("/api/jobs/delete", { id: Number(b.dataset.delJob) });
      loadPipeline();
    }));
}

$("btn-add-app").addEventListener("click", async () => {
  const company = $("p-company").value.trim(), role = $("p-role").value.trim();
  if (!company && !role) return setNote($("pipe-note"), "Add a company or role.", "err");
  try {
    await api("/api/pipeline/add", { company, role, url: $("p-url").value.trim() });
    $("p-company").value = ""; $("p-role").value = ""; $("p-url").value = "";
    setNote($("pipe-note"), "Added to Saved.", "good");
    loadPipeline();
  } catch (e) {
    setNote($("pipe-note"), e.message, "err");
  }
});

/* ---------- status chips ---------- */
async function loadStatus() {
  try {
    const s = await api("/api/config");
    const chip = (label, ok) => `<span class="chip ${ok ? "ok" : "off"}"><span class="dot"></span>${label}: ${ok ? "ready" : "not set"}</span>`;
    $("status-chips").innerHTML =
      chip("LLM", s.llm_ready) +
      chip(`${s.calendars} cal`, s.calendars > 0) +
      chip(`${s.email_accounts} mail`, s.email_accounts > 0) +
      chip("Send", s.smtp_ready) +
      chip("Resume", s.resume_loaded);
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
        <button class="link-btn" data-track="${i}">Track →</button>
      </div>
    </div>`).join("");
  wrap.querySelectorAll("[data-draft]").forEach((b) =>
    b.addEventListener("click", () => draftFromJob(jobs[Number(b.dataset.draft)]))
  );
  wrap.querySelectorAll("[data-track]").forEach((b) =>
    b.addEventListener("click", async () => {
      const j = jobs[Number(b.dataset.track)];
      try {
        // find the stored job's id by matching, then track it
        const { jobs: stored } = await api("/api/jobs");
        const match = stored.find((s) => s.url === j.url && s.title === j.title);
        if (!match) { b.textContent = "not saved yet"; return; }
        await api("/api/pipeline/track", { id: match.id });
        b.textContent = "Tracked ✓"; b.disabled = true;
      } catch (e) { b.textContent = "error"; }
    })
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
showTab("today");
