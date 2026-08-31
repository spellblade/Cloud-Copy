(() => {
  // Dual-pane MEGA ↔ PikPak UI: auth, listings, queue, live job updates.

  const state = {
    direction: "mega_to_pikpak",
    auth: { mega: { connected: false }, pikpak: { connected: false } },
    left: { provider: "mega", parent: null, stack: [{ id: null, name: "Root" }], items: [], selected: new Set() },
    right: { provider: "pikpak", parent: null, stack: [{ id: null, name: "Root" }], items: [] },
    jobs: [],
  };

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  // --- Helpers ---

  function toast(msg, type = "ok") {
    // Brief status at the bottom-right; auto-hides.
    const el = $("#toast");
    el.textContent = msg;
    el.className = `toast ${type}`;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => el.classList.add("hidden"), 3500);
  }

  async function api(path, options = {}) {
    // JSON fetch wrapper; non-OK responses become Error with the API detail.
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    let data = null;
    const text = await res.text();
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { detail: text };
    }
    if (!res.ok) {
      const detail = data?.detail || data?.message || res.statusText;
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return data;
  }

  function fmtSize(n) {
    // File size for the SIZE column; empty/zero shows an em dash.
    if (n == null || n === 0) return "—";
    const units = ["B", "KB", "MB", "GB", "TB"];
    let i = 0;
    let v = Number(n);
    while (v >= 1024 && i < units.length - 1) {
      v /= 1024;
      i += 1;
    }
    return `${v.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
  }

  // --- Auth and transfer direction ---

  function applyDirection() {
    // Swap which cloud is source vs dest; resets both panes to root.
    if (state.direction === "mega_to_pikpak") {
      state.left.provider = "mega";
      state.right.provider = "pikpak";
      $("#leftTitle").textContent = "MEGA (source)";
      $("#rightTitle").textContent = "PikPak (destination)";
    } else {
      state.left.provider = "pikpak";
      state.right.provider = "mega";
      $("#leftTitle").textContent = "PikPak (source)";
      $("#rightTitle").textContent = "MEGA (destination)";
    }
    state.left.parent = null;
    state.left.stack = [{ id: null, name: "Root" }];
    state.left.selected = new Set();
    state.right.parent = null;
    state.right.stack = [{ id: null, name: "Root" }];
    updateTransferButton();
    loadPane("left");
    loadPane("right");
  }

  function setAuthUI() {
    // Show login forms or connected user; MEGA also shows the "2FA auto" hint.
    for (const p of ["mega", "pikpak"]) {
      const st = state.auth[p] || {};
      const badge = $(`#${p}Badge`);
      const form = $(`#${p}Login`);
      const connected = $(`#${p}Connected`);
      const user = $(`#${p}User`);
      if (st.connected) {
        badge.textContent = "online";
        badge.classList.add("online");
        form.classList.add("hidden");
        connected.classList.remove("hidden");
        user.textContent = st.username || "connected";
      } else {
        badge.textContent = "offline";
        badge.classList.remove("online");
        form.classList.remove("hidden");
        connected.classList.add("hidden");
      }
    }
    const megaHint = $("#megaTotpHint");
    if (megaHint) {
      if (state.auth.mega?.connected && state.auth.mega?.totp_configured) {
        megaHint.classList.remove("hidden");
        megaHint.textContent = "2FA auto (TOTP saved)";
      } else {
        megaHint.classList.add("hidden");
      }
    }
    updateTransferButton();
  }

  async function refreshAuth() {
    // Pull /api/auth/status and refresh badges/forms.
    state.auth = await api("/api/auth/status");
    setAuthUI();
  }

  // --- File panes ---

  function renderCrumbs(side) {
    // Breadcrumb buttons for the pane stack; click jumps back to that folder.
    const pane = state[side];
    const el = $(`#${side}Crumbs`);
    el.innerHTML = "";
    pane.stack.forEach((crumb, idx) => {
      if (idx > 0) {
        const sep = document.createElement("span");
        sep.textContent = "/";
        el.appendChild(sep);
      }
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = crumb.name;
      btn.addEventListener("click", () => {
        pane.stack = pane.stack.slice(0, idx + 1);
        pane.parent = crumb.id;
        pane.selected = new Set();
        loadPane(side);
      });
      el.appendChild(btn);
    });
  }

  function renderPane(side) {
    // Draw the file table. Left pane has checkboxes; folders enter on double-click.
    const pane = state[side];
    const body = $(`#${side}Body`);
    const empty = $(`#${side}Empty`);
    body.innerHTML = "";
    renderCrumbs(side);

    if (!state.auth[pane.provider]?.connected) {
      empty.textContent = `Connect ${pane.provider.toUpperCase()} to browse files.`;
      empty.classList.remove("hidden");
      return;
    }

    if (!pane.items.length) {
      empty.textContent = "This folder is empty.";
      empty.classList.remove("hidden");
      return;
    }
    empty.classList.add("hidden");

    for (const item of pane.items) {
      const tr = document.createElement("tr");
      if (side === "left" && pane.selected.has(item.id)) tr.classList.add("selected");

      const tdCheck = document.createElement("td");
      let cb = null;
      if (side === "left") {
        cb = document.createElement("input");
        cb.type = "checkbox";
        cb.checked = pane.selected.has(item.id);
        cb.title = item.is_dir
          ? "Select this folder to transfer it (with its contents)"
          : "Select this file to transfer it";
        cb.addEventListener("click", (e) => e.stopPropagation());
        cb.addEventListener("change", () => {
          setLeftSelected(item.id, cb.checked, tr, cb);
        });
        tdCheck.appendChild(cb);
      }
      tr.appendChild(tdCheck);

      const tdName = document.createElement("td");
      const wrap = document.createElement("div");
      wrap.className = `name-cell${item.is_dir ? " folder" : ""}`;
      wrap.innerHTML = `<span class="icon">${item.is_dir ? "📁" : "📄"}</span><span class="name-text"></span>`;
      const nameEl = wrap.querySelector(".name-text");
      nameEl.textContent = item.name;
      nameEl.title = item.is_dir
        ? `${item.name} — ${side === "left" ? "click to select, double-click to open" : "double-click to open"}`
        : item.name;
      if (item.is_dir) {
        let clickTimer;
        wrap.addEventListener("click", (e) => {
          // Delay so a double-click can cancel this and open the folder instead.
          if (side !== "left") return;
          if (e.detail !== 1) return;
          clearTimeout(clickTimer);
          clickTimer = setTimeout(() => {
            setLeftSelected(item.id, !state.left.selected.has(item.id), tr, cb);
          }, 280);
        });
        wrap.addEventListener("dblclick", () => {
          clearTimeout(clickTimer);
          enterFolder(side, item);
        });
      } else if (side === "left") {
        wrap.addEventListener("click", () => {
          setLeftSelected(item.id, !state.left.selected.has(item.id), tr, cb);
        });
      }
      tdName.appendChild(wrap);
      tr.appendChild(tdName);

      const tdSize = document.createElement("td");
      tdSize.className = "col-size";
      tdSize.textContent = item.is_dir ? "—" : fmtSize(item.size);
      tr.appendChild(tdSize);

      body.appendChild(tr);
    }
    updateTransferButton();
  }

  function enterFolder(side, item) {
    // Navigate into a folder; left-pane selection is cleared.
    const pane = state[side];
    pane.parent = item.id;
    pane.stack.push({ id: item.id, name: item.name });
    if (side === "left") pane.selected = new Set();
    loadPane(side);
  }

  async function loadPane(side) {
    // Fetch listing for the current parent; overlay shows Loading… until render.
    const pane = state[side];
    const empty = $(`#${side}Empty`);
    if (!state.auth[pane.provider]?.connected) {
      pane.items = [];
      renderPane(side);
      return;
    }
    empty.textContent = "Loading…";
    empty.classList.remove("hidden");
    try {
      const q = pane.parent ? `?parent=${encodeURIComponent(pane.parent)}` : "";
      const data = await api(`/api/files/${pane.provider}${q}`);
      pane.items = data.items || [];
      renderPane(side);
    } catch (err) {
      pane.items = [];
      empty.textContent = err.message;
      empty.classList.remove("hidden");
      toast(err.message, "error");
    }
  }

  function updateTransferButton() {
    // Enable Transfer only when both clouds are connected and the left pane has a selection.
    const btn = $("#transferBtn");
    const both =
      state.auth.mega?.connected && state.auth.pikpak?.connected;
    btn.disabled = !(both && state.left.selected.size > 0);
    const all = $("#leftSelectAll");
    if (all) {
      const n = state.left.items.length;
      all.checked = n > 0 && state.left.selected.size === n;
      all.indeterminate = state.left.selected.size > 0 && state.left.selected.size < n;
    }
  }

  function setLeftSelected(itemId, on, tr, cb) {
    // Toggle one source item (file or folder) and refresh the Transfer button.
    if (on) state.left.selected.add(itemId);
    else state.left.selected.delete(itemId);
    if (tr) tr.classList.toggle("selected", on);
    if (cb) cb.checked = on;
    updateTransferButton();
  }

  // --- Transfer jobs ---

  function failedStageLabel(job) {
    // Human stage for failed jobs (mirrors TransferJob.stage_label on the server).
    if (!job || !job.stage) return null;
    const src = job.direction === "mega_to_pikpak" ? "MEGA" : "PikPak";
    const dst = job.direction === "mega_to_pikpak" ? "PikPak" : "MEGA";
    const map = {
      download: `${src} download`,
      upload: `${dst} upload`,
      mkdir: "Create folder",
      listing: "List folder",
      auth: "Sign-in",
      queued: "Queue",
    };
    return map[job.stage] || job.stage;
  }

  function renderJobs() {
    // Job cards with status, message, progress, Cancel, and Retry.
    const list = $("#jobsList");
    if (!state.jobs.length) {
      list.innerHTML = `<p class="empty">No transfers yet.</p>`;
      return;
    }
    list.innerHTML = "";
    for (const job of state.jobs) {
      const card = document.createElement("div");
      card.className = "job-card";
      const dirLabel =
        job.direction === "mega_to_pikpak" ? "MEGA → PikPak" : "PikPak → MEGA";
      const pct = Math.max(0, Math.min(100, job.progress || 0));
      const stageLabel = failedStageLabel(job);
      const statusText =
        job.status === "failed" && stageLabel
          ? `failed · ${stageLabel}`
          : job.status;
      card.innerHTML = `
        <div class="job-top">
          <div class="job-title">${dirLabel} · ${job.source_ids.length} item(s)</div>
          <span class="job-status ${job.status}">${escapeHtml(statusText)}</span>
        </div>
        <div class="job-meta">
          ${job.current_file ? escapeHtml(job.current_file) + " · " : ""}
          ${escapeHtml(job.message || "")}
          ${job.error ? " · " + escapeHtml(job.error) : ""}
        </div>
        <div class="progress"><span style="width:${pct}%"></span></div>
        <div class="job-actions"></div>
      `;
      const actions = card.querySelector(".job-actions");
      if (job.status === "queued" || job.status === "running") {
        const cancel = document.createElement("button");
        cancel.className = "danger";
        cancel.textContent = "Cancel";
        cancel.addEventListener("click", async () => {
          cancel.disabled = true;
          cancel.textContent = "Cancelling…";
          try {
            const updated = await api(`/api/transfers/${job.id}/cancel`, {
              method: "POST",
            });
            upsertJob(updated);
            toast("Cancel requested");
          } catch (e) {
            cancel.disabled = false;
            cancel.textContent = "Cancel";
            toast(e.message, "error");
          }
        });
        actions.appendChild(cancel);
      }
      if (job.status === "failed" || job.status === "cancelled") {
        const retry = document.createElement("button");
        retry.className = "ghost";
        retry.textContent = "Retry";
        retry.addEventListener("click", async () => {
          try {
            await api(`/api/transfers/${job.id}/retry`, { method: "POST" });
          } catch (e) {
            toast(e.message, "error");
          }
        });
        actions.appendChild(retry);
      }
      list.appendChild(card);
    }
  }

  function escapeHtml(s) {
    // Escape job text interpolated into innerHTML.
    return String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function upsertJob(job) {
    // Insert or replace one job from a WS update, then re-render the list.
    const idx = state.jobs.findIndex((j) => j.id === job.id);
    if (idx >= 0) state.jobs[idx] = job;
    else state.jobs.unshift(job);
    renderJobs();
  }

  function connectWs() {
    // Live /ws/transfers: snapshot on open, per-job updates, reconnect after close.
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/transfers`);
    const status = $("#wsStatus");
    ws.addEventListener("open", () => {
      status.textContent = "live";
    });
    ws.addEventListener("close", () => {
      status.textContent = "reconnecting…";
      setTimeout(connectWs, 2000);
    });
    ws.addEventListener("message", (ev) => {
      let msg;
      try {
        msg = JSON.parse(ev.data);
      } catch {
        return;
      }
      if (msg.type === "snapshot") {
        state.jobs = msg.jobs || [];
        renderJobs();
      } else if (msg.type === "job") {
        upsertJob(msg.job);
        if (msg.job.status === "completed") {
          loadPane("right");
        }
      }
    });
  }

  // --- Event wiring ---

  (function setupTotpInfoTip() {
    // MEGA ⓘ: hover/focus opens the bubble; click pins it; Escape/outside click closes.
    const btn = $("#megaMfaInfo");
    const bubble = $("#megaMfaHint");
    const wrap = btn && btn.closest(".input-with-info-label");
    if (!btn || !bubble || !wrap) return;

    let closeTimer;
    let pinned = false;
    const isOpen = () => !bubble.classList.contains("hidden");

    const open = () => {
      // Show the bubble and mark the button expanded.
      clearTimeout(closeTimer);
      bubble.classList.remove("hidden");
      btn.setAttribute("aria-expanded", "true");
    };
    const close = () => {
      // Hide the bubble and clear the pin.
      clearTimeout(closeTimer);
      pinned = false;
      bubble.classList.add("hidden");
      btn.setAttribute("aria-expanded", "false");
    };
    const delayedClose = () => {
      // Short delay so moving from the icon onto the bubble does not close it.
      if (pinned) return;
      clearTimeout(closeTimer);
      closeTimer = setTimeout(() => {
        if (pinned) return;
        if (!wrap.matches(":hover") && !bubble.matches(":hover")) close();
      }, 150);
    };

    wrap.addEventListener("mouseenter", open);
    wrap.addEventListener("mouseleave", delayedClose);
    bubble.addEventListener("mouseenter", open);
    bubble.addEventListener("mouseleave", delayedClose);

    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (pinned) {
        close();
        return;
      }
      pinned = true;
      open();
    });

    document.addEventListener("click", (e) => {
      if (wrap.contains(e.target) || bubble.contains(e.target)) return;
      close();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") close();
    });
  })();

  // MEGA → PikPak vs PikPak → MEGA; swaps pane providers.
  $$(".dir-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      $$(".dir-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.direction = btn.dataset.dir;
      applyDirection();
    });
  });

  // MEGA login: password plus optional TOTP secret and/or one-shot 6-digit code.
  $("#megaLogin").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const mfa = String(fd.get("mfa_code") || "").trim();
    const totpSecret = String(fd.get("totp_secret") || "").trim();
    try {
      await api("/api/auth/mega", {
        method: "POST",
        body: JSON.stringify({
          username: fd.get("username"),
          password: fd.get("password"),
          mfa_code: mfa || null,
          totp_secret: totpSecret || null,
        }),
      });
      toast("Connected to MEGA");
      const mfaInput = e.target.querySelector('[name="mfa_code"]');
      const secretInput = e.target.querySelector('[name="totp_secret"]');
      if (mfaInput) mfaInput.value = "";
      if (secretInput) secretInput.value = "";
      await refreshAuth();
      applyDirection();
    } catch (err) {
      toast(err.message, "error");
    }
  });

  $("#pikpakLogin").addEventListener("submit", async (e) => {
    // PikPak is email/password only (no TOTP on this form).
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      await api("/api/auth/pikpak", {
        method: "POST",
        body: JSON.stringify({
          username: fd.get("username"),
          password: fd.get("password"),
        }),
      });
      toast("Connected to PikPak");
      await refreshAuth();
      applyDirection();
    } catch (err) {
      toast(err.message, "error");
    }
  });

  $$("[data-logout]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const provider = btn.dataset.logout;
      try {
        await api(`/api/auth/${provider}`, { method: "DELETE" });
        toast(`Logged out of ${provider}`);
        await refreshAuth();
        applyDirection();
      } catch (err) {
        toast(err.message, "error");
      }
    });
  });

  $$("[data-up]").forEach((btn) => {
    // Parent folder (Up); no-op at root.
    btn.addEventListener("click", () => {
      const side = btn.dataset.up;
      const pane = state[side];
      if (pane.stack.length <= 1) return;
      pane.stack.pop();
      const top = pane.stack[pane.stack.length - 1];
      pane.parent = top.id;
      if (side === "left") pane.selected = new Set();
      loadPane(side);
    });
  });

  $("#leftSelectAll").addEventListener("change", (e) => {
    // Check/uncheck every row in the current source folder.
    const on = e.target.checked;
    state.left.selected = new Set();
    if (on) {
      for (const item of state.left.items) state.left.selected.add(item.id);
    }
    renderPane("left");
  });

  $("#refreshBtn").addEventListener("click", () => {
    loadPane("left");
    loadPane("right");
  });

  $("#transferBtn").addEventListener("click", async () => {
    // Queue selected left-pane items into the current right-pane folder.
    const selected = state.left.items.filter((i) => state.left.selected.has(i.id));
    if (!selected.length) return;
    const source_meta = {};
    for (const item of selected) {
      source_meta[item.id] = { name: item.name, is_dir: item.is_dir, size: item.size };
    }
    try {
      await api("/api/transfers", {
        method: "POST",
        body: JSON.stringify({
          direction: state.direction,
          source_ids: selected.map((i) => i.id),
          dest_parent_id: state.right.parent,
          source_meta,
        }),
      });
      const nFolders = selected.filter((i) => i.is_dir).length;
      toast(
        nFolders
          ? `Transfer queued (${selected.length} item(s), including ${nFolders} folder(s))`
          : "Transfer queued"
      );
      state.left.selected = new Set();
      $("#leftSelectAll").checked = false;
      renderPane("left");
    } catch (err) {
      toast(err.message, "error");
    }
  });

  // --- Temp / data paths ---

  function fmtBytes(n) {
    // Byte size for the temp-folder line (0 B when empty).
    if (!n) return "0 B";
    const units = ["B", "KB", "MB", "GB"];
    let i = 0;
    let v = Number(n);
    while (v >= 1024 && i < units.length - 1) {
      v /= 1024;
      i += 1;
    }
    return `${v.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
  }

  async function refreshPaths() {
    // Show temp and data dirs under the jobs header.
    try {
      const p = await api("/api/system/paths");
      const line = $("#tempPathLine");
      if (line) {
        line.textContent = `Temp folder: ${p.temp_dir} (${fmtBytes(p.temp_bytes)}) · Data: ${p.data_dir}`;
      }
    } catch {
      // ignore
    }
  }

  $("#clearTempBtn").addEventListener("click", async () => {
    // Wipe leftover local-relay files; confirm first.
    if (
      !confirm(
        "Delete all local transfer temp files under the Cloud Copy temp folder?\n\n" +
          "Do this when no transfers are running (or after cancel)."
      )
    ) {
      return;
    }
    try {
      const res = await api("/api/system/clear-temp", { method: "POST" });
      toast(res.message || "Temp cleared");
      await refreshPaths();
    } catch (e) {
      toast(e.message, "error");
    }
  });

  // Boot: auth, panes, live jobs, temp path.
  (async () => {
    try {
      await refreshAuth();
    } catch (e) {
      toast(e.message, "error");
    }
    applyDirection();
    connectWs();
    refreshPaths();
    try {
      const data = await api("/api/transfers");
      state.jobs = data.jobs || [];
      renderJobs();
    } catch {
      // ignore
    }
  })();
})();
