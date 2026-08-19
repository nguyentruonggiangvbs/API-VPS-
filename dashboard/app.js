
"use strict";

const $ = (selector, scope = document) => scope.querySelector(selector);
const $$ = (selector, scope = document) => [...scope.querySelectorAll(selector)];

const state = {
  apiKey: sessionStorage.getItem("apiVpsKey") || "",
  page: "overview",
  roots: [],
  currentRoot: "",
  currentPath: "",
  fileEntries: [],
  selectedFile: null,
  editorFile: null,
  historyPoints: 120,
  pollTimer: null,
  logLoader: null,
  logAutoTimer: null,
  searchTimer: null,
};

const pageMeta = {
  overview: ["TRUNG TÂM ĐIỀU KHIỂN", "Tổng quan"],
  monitoring: ["REALTIME MONITORING", "Đo lường"],
  files: ["FILE MANAGER", "Quản lý file"],
  docker: ["DOCKER MANAGER", "Docker"],
  deploy: ["DEPLOY MANAGER", "Triển khai"],
  backups: ["BACKUP MANAGER", "Sao lưu"],
  logs: ["LOGS CENTER", "Nhật ký"],
  settings: ["SYSTEM SETTINGS", "Cài đặt"],
};

document.addEventListener("DOMContentLoaded", boot);

async function boot() {
  bindGlobalEvents();
  if (state.apiKey) {
    try {
      await api("/api/auth/verify");
      showApplication();
      return;
    } catch (error) {
      sessionStorage.removeItem("apiVpsKey");
      state.apiKey = "";
    }
  }
  showLogin();
}

function bindGlobalEvents() {
  $("#loginForm").addEventListener("submit", handleLogin);
  $("#logoutButton").addEventListener("click", logout);
  $("#refreshButton").addEventListener("click", refreshCurrentPage);
  $("#openSidebar").addEventListener("click", () => $("#sidebar").classList.add("open"));
  $("#closeSidebar").addEventListener("click", closeSidebar);
  $("#sidebarScrim").addEventListener("click", closeSidebar);

  $$("[data-nav]").forEach((element) => {
    element.addEventListener("click", (event) => {
      event.preventDefault();
      navigate(element.dataset.nav);
    });
  });
  $$("[data-jump]").forEach((element) => {
    element.addEventListener("click", () => navigate(element.dataset.jump));
  });

  $("#historyRange").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-points]");
    if (!button) return;
    $$("#historyRange button").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    state.historyPoints = Number(button.dataset.points);
    loadMonitoring();
  });
  $("#refreshProcesses").addEventListener("click", loadProcesses);

  $("#fileRootSelect").addEventListener("change", () => {
    state.currentRoot = $("#fileRootSelect").value;
    state.currentPath = "";
    loadFiles();
  });
  $("#showHiddenFiles").addEventListener("change", loadFiles);
  $("#refreshFiles").addEventListener("click", loadFiles);
  $("#fileSearchInput").addEventListener("input", handleFileSearch);
  $("#newFolderButton").addEventListener("click", createFolder);
  $("#newFileButton").addEventListener("click", createFile);
  $("#fileUploadInput").addEventListener("change", uploadFile);

  $("#refreshDocker").addEventListener("click", loadDocker);
  $("#refreshProjects").addEventListener("click", loadDeploy);
  $("#backupForm").addEventListener("submit", createBackup);
  $("#refreshAudit").addEventListener("click", loadAudit);
  $("#auditSearch").addEventListener("input", debounceAudit);
  $("#auditOutcome").addEventListener("change", loadAudit);

  $$("[data-close-modal]").forEach((button) => button.addEventListener("click", closeGenericModal));
  $("#modalBackdrop").addEventListener("click", (event) => {
    if (event.target === $("#modalBackdrop")) closeGenericModal();
  });

  $("#closeEditor").addEventListener("click", closeEditor);
  $("#editorBackdrop").addEventListener("click", (event) => {
    if (event.target === $("#editorBackdrop")) closeEditor();
  });
  $("#fileEditor").addEventListener("input", updateEditorGutter);
  $("#fileEditor").addEventListener("scroll", syncEditorScroll);
  $("#fileEditor").addEventListener("keydown", editorTabKey);
  $("#saveEditor").addEventListener("click", saveEditor);
  $("#reloadEditor").addEventListener("click", reloadEditor);
  $("#downloadEditorFile").addEventListener("click", () => {
    if (state.editorFile) downloadFile(state.editorFile.path);
  });

  $("#closeLogModal").addEventListener("click", closeLogModal);
  $("#closeLogButton").addEventListener("click", closeLogModal);
  $("#logBackdrop").addEventListener("click", (event) => {
    if (event.target === $("#logBackdrop")) closeLogModal();
  });
  $("#refreshLogModal").addEventListener("click", async () => {
    if (state.logLoader) await state.logLoader();
  });

  window.addEventListener("hashchange", () => {
    if (!$("#appShell").classList.contains("is-hidden")) {
      navigate(location.hash.slice(1) || "overview", false);
    }
  });
  window.addEventListener("resize", () => {
    if (state.page === "overview") loadOverviewChart();
    if (state.page === "monitoring") loadMonitoringCharts();
  });
}

async function handleLogin(event) {
  event.preventDefault();
  const input = $("#apiKeyInput");
  const errorBox = $("#loginError");
  const button = event.submitter;
  const key = input.value.trim();
  errorBox.textContent = "";
  button.disabled = true;
  button.textContent = "Đang xác thực…";
  state.apiKey = key;
  try {
    await api("/api/auth/verify");
    sessionStorage.setItem("apiVpsKey", key);
    showApplication();
  } catch (error) {
    state.apiKey = "";
    errorBox.textContent = error.message || "Không thể kết nối VPS";
  } finally {
    button.disabled = false;
    button.innerHTML = '<svg><use href="#i-server"></use></svg>Kết nối VPS';
  }
}

function showLogin() {
  $("#loginScreen").classList.remove("is-hidden");
  $("#appShell").classList.add("is-hidden");
  setTimeout(() => $("#apiKeyInput").focus(), 80);
}

function showApplication() {
  $("#loginScreen").classList.add("is-hidden");
  $("#appShell").classList.remove("is-hidden");
  navigate(location.hash.slice(1) || "overview", false);
  startPolling();
}

function logout() {
  sessionStorage.removeItem("apiVpsKey");
  state.apiKey = "";
  clearInterval(state.pollTimer);
  showLogin();
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.apiKey) headers.set("Authorization", `Bearer ${state.apiKey}`);
  headers.set("Accept", "application/json");
  const payload = { ...options, headers };

  if (payload.body && !(payload.body instanceof FormData) && typeof payload.body !== "string") {
    headers.set("Content-Type", "application/json");
    payload.body = JSON.stringify(payload.body);
  }

  let response;
  try {
    response = await fetch(path, payload);
  } catch (error) {
    throw new Error("Không thể kết nối API‑VPS");
  }

  if (response.status === 401) {
    if (!path.includes("/auth/verify")) logout();
    throw new Error("API key không hợp lệ hoặc đã thay đổi");
  }

  const contentType = response.headers.get("content-type") || "";
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    if (contentType.includes("application/json")) {
      const data = await response.json().catch(() => ({}));
      detail = data.detail || detail;
    } else {
      detail = (await response.text()).slice(0, 300) || detail;
    }
    throw new Error(detail);
  }

  if (options.raw) return response;
  if (response.status === 204) return null;
  if (contentType.includes("application/json")) return response.json();
  return response.text();
}

function navigate(page, updateHash = true) {
  if (!pageMeta[page]) page = "overview";
  state.page = page;
  $$(".page").forEach((element) => element.classList.toggle("active", element.dataset.page === page));
  $$(".nav-item").forEach((element) => element.classList.toggle("active", element.dataset.nav === page));
  const [eyebrow, title] = pageMeta[page];
  $("#pageEyebrow").textContent = eyebrow;
  $("#pageTitle").textContent = title;
  if (updateHash && location.hash !== `#${page}`) history.pushState(null, "", `#${page}`);
  closeSidebar();
  refreshCurrentPage();
}

function closeSidebar() {
  $("#sidebar").classList.remove("open");
}

function startPolling() {
  clearInterval(state.pollTimer);
  state.pollTimer = setInterval(() => {
    if (document.hidden) return;
    if (state.page === "overview") loadOverview(true);
    if (state.page === "monitoring") loadMonitoring(true);
    if (state.page === "deploy") loadDeployJobs(true);
  }, 5000);
}

async function refreshCurrentPage(silent = false) {
  $("#refreshButton").classList.add("spinning");
  try {
    if (state.page === "overview") await loadOverview(silent);
    else if (state.page === "monitoring") await loadMonitoring(silent);
    else if (state.page === "files") await ensureFiles();
    else if (state.page === "docker") await loadDocker();
    else if (state.page === "deploy") await loadDeploy();
    else if (state.page === "backups") await loadBackups();
    else if (state.page === "logs") await loadAudit();
    else if (state.page === "settings") await loadSettings();
    updateSyncTime();
  } catch (error) {
    if (!silent) toast("Lỗi", error.message, "error");
  } finally {
    $("#refreshButton").classList.remove("spinning");
  }
}

function updateSyncTime() {
  $("#lastSync").textContent = new Date().toLocaleTimeString("vi-VN");
}

async function loadOverview(silent = false) {
  try {
    const data = await api("/api/overview");
    const metrics = data.metrics;
    $("#welcomeHostname").textContent = data.host.hostname;
    $("#welcomeOs").textContent = `${data.host.operating_system} · ${data.host.kernel}`;
    $("#sideHost").textContent = data.host.hostname;
    $("#sideVersion").textContent = `API‑VPS v${data.version}`;
    $("#uptimeValue").textContent = formatUptime(metrics.uptime_seconds);

    updateMetricCard("cpu", metrics.cpu.percent, `${metrics.cpu.count_logical || "--"} luồng · Load ${metrics.cpu.load_1}`);
    updateMetricCard("ram", metrics.memory.percent, `${formatBytes(metrics.memory.used)} / ${formatBytes(metrics.memory.total)}`);
    updateMetricCard("disk", metrics.disk.percent, `${formatBytes(metrics.disk.used)} / ${formatBytes(metrics.disk.total)}`);

    $("#networkDown").textContent = `${formatRate(metrics.network.receive_bytes_per_second)}`;
    $("#networkUp").textContent = `${formatRate(metrics.network.send_bytes_per_second)}`;
    $("#networkValue").textContent = formatRate(metrics.network.receive_bytes_per_second + metrics.network.send_bytes_per_second);

    renderAlerts(data.alerts);
    renderOverviewContainers(data.docker.containers);
    renderActivity(data.recent_activity);
    await loadOverviewChart();
    updateSyncTime();
  } catch (error) {
    if (!silent) throw error;
  }
}

function updateMetricCard(prefix, percent, meta) {
  $(`#${prefix}Value`).textContent = `${Number(percent).toFixed(1)}%`;
  $(`#${prefix}Progress`).style.width = `${Math.min(Math.max(percent, 0), 100)}%`;
  $(`#${prefix}Meta`).textContent = meta;
  const trend = $(`#${prefix}Trend`);
  if (trend) {
    trend.textContent = percent >= 90 ? "Nguy hiểm" : percent >= 75 ? "Tải cao" : "Ổn định";
    trend.className = `trend ${percent >= 90 ? "danger-text" : percent >= 75 ? "warning-text" : ""}`;
  }
}

function renderAlerts(alerts) {
  $("#alertCount").textContent = alerts.length;
  const box = $("#alertList");
  if (!alerts.length) {
    box.innerHTML = `<div class="alert-empty"><svg><use href="#i-check"></use></svg><strong>Mọi chỉ số đều ổn định</strong><small>Không có cảnh báo tài nguyên.</small></div>`;
    return;
  }
  box.innerHTML = alerts.map((alert) => `
    <div class="alert-item ${esc(alert.level)}">
      <svg><use href="#i-alert"></use></svg>
      <div><strong>${esc(alert.title)}</strong><small>${esc(alert.message)}</small></div>
    </div>`).join("");
}

function renderOverviewContainers(containers) {
  const box = $("#overviewContainers");
  if (!containers.length) {
    box.innerHTML = `<div class="alert-empty"><small>Không đọc được Docker container.</small></div>`;
    return;
  }
  box.innerHTML = containers.slice(0, 6).map((container) => `
    <div class="compact-container">
      <span class="container-status ${container.status === "running" ? "running" : ""}"></span>
      <div><strong>${esc(container.name)}</strong><small>${esc(container.image)}</small></div>
      <span class="mini-stat">${container.stats ? `${container.stats.cpu_percent.toFixed(1)}% CPU` : esc(container.status)}</span>
    </div>`).join("");
}

function renderActivity(events) {
  const box = $("#recentActivity");
  if (!events.length) {
    box.innerHTML = `<div class="alert-empty"><small>Chưa có hoạt động quản trị.</small></div>`;
    return;
  }
  box.innerHTML = events.map((event) => `
    <div class="activity-item">
      <span class="activity-icon"><svg><use href="#i-logs"></use></svg></span>
      <div><strong>${esc(humanAction(event.action))}</strong><small>${formatDate(event.timestamp)} · ${esc(event.outcome)}</small></div>
    </div>`).join("");
}

async function loadOverviewChart() {
  if (state.page !== "overview") return;
  const data = await api("/api/system/history?limit=120");
  drawLineChart($("#overviewChart"), [
    { values: data.points.map((point) => point.cpu.percent), color: css("--primary-2") },
    { values: data.points.map((point) => point.memory.percent), color: css("--blue") },
  ], { max: 100, suffix: "%" });
}

async function loadMonitoring(silent = false) {
  try {
    const [metrics, history] = await Promise.all([
      api("/api/system/metrics"),
      api(`/api/system/history?limit=${state.historyPoints}`),
    ]);
    $("#monitorCpu").textContent = `${metrics.cpu.percent.toFixed(1)}%`;
    $("#monitorRam").textContent = `${metrics.memory.percent.toFixed(1)}%`;
    renderMonitoringCharts(history.points);
    if (!silent) await loadProcesses();
    updateSyncTime();
  } catch (error) {
    if (!silent) throw error;
  }
}

async function loadMonitoringCharts() {
  if (state.page !== "monitoring") return;
  const history = await api(`/api/system/history?limit=${state.historyPoints}`);
  renderMonitoringCharts(history.points);
}

function renderMonitoringCharts(points) {
  drawLineChart($("#cpuChart"), [{ values: points.map((p) => p.cpu.percent), color: css("--primary-2") }], { max: 100, suffix: "%" });
  drawLineChart($("#ramChart"), [{ values: points.map((p) => p.memory.percent), color: css("--blue") }], { max: 100, suffix: "%" });
  drawLineChart($("#networkChart"), [
    { values: points.map((p) => p.network.receive_bytes_per_second), color: css("--cyan") },
    { values: points.map((p) => p.network.send_bytes_per_second), color: css("--pink") },
  ], { formatter: formatRate });
}

async function loadProcesses() {
  const tbody = $("#processTable");
  tbody.innerHTML = loadingRow(6);
  try {
    const data = await api("/api/system/processes?limit=50");
    tbody.innerHTML = data.processes.map((process) => `
      <tr>
        <td>${process.pid}</td>
        <td><strong>${esc(process.name)}</strong></td>
        <td>${esc(process.username)}</td>
        <td><span class="badge">${esc(process.status)}</span></td>
        <td>${process.cpu_percent.toFixed(1)}%</td>
        <td>${process.memory_percent.toFixed(1)}%</td>
      </tr>`).join("") || `<tr><td colspan="6">Không có dữ liệu tiến trình.</td></tr>`;
  } catch (error) {
    tbody.innerHTML = `<tr><td colspan="6">${esc(error.message)}</td></tr>`;
  }
}

async function ensureFiles() {
  if (!state.roots.length) {
    const data = await api("/api/files/roots");
    state.roots = data.roots.filter((root) => root.available);
    populateRootSelects();
    state.currentRoot = state.currentRoot || state.roots[0]?.alias || "";
  }
  await loadFiles();
}

function populateRootSelects() {
  const options = state.roots.map((root) => `<option value="${esc(root.alias)}">${esc(root.label)} · ${esc(root.path)}</option>`).join("");
  $("#fileRootSelect").innerHTML = options;
  $("#backupRoot").innerHTML = options;
  if (state.currentRoot) $("#fileRootSelect").value = state.currentRoot;
}

async function loadFiles(path = state.currentPath) {
  if (!state.currentRoot) return;
  const query = new URLSearchParams({
    root: state.currentRoot,
    path: path || "",
    show_hidden: $("#showHiddenFiles").checked ? "true" : "false",
  });
  const tbody = $("#fileTable");
  tbody.innerHTML = loadingRow(5);
  $("#fileEmpty").classList.add("is-hidden");
  try {
    const data = await api(`/api/files/list?${query}`);
    state.currentPath = data.path || "";
    state.fileEntries = data.entries;
    state.selectedFile = null;
    renderBreadcrumb();
    renderFileTable(data.entries);
    renderFileInspector(null);
    $("#fileRootSelect").value = state.currentRoot;
  } catch (error) {
    tbody.innerHTML = `<tr><td colspan="5">${esc(error.message)}</td></tr>`;
  }
}

function renderBreadcrumb() {
  const parts = state.currentPath ? state.currentPath.split("/") : [];
  const items = [{ label: state.currentRoot.toUpperCase(), path: "" }];
  parts.forEach((part, index) => items.push({ label: part, path: parts.slice(0, index + 1).join("/") }));
  $("#fileBreadcrumb").innerHTML = items.map((item, index) => `
    ${index ? '<svg><use href="#i-chevron"></use></svg>' : ""}
    <button data-path="${esc(item.path)}">${esc(item.label)}</button>`).join("");
  $$("#fileBreadcrumb button").forEach((button) => button.addEventListener("click", () => loadFiles(button.dataset.path)));
}

function renderFileTable(entries, searchMode = false) {
  const tbody = $("#fileTable");
  $("#fileEmpty").classList.toggle("is-hidden", Boolean(entries.length));
  tbody.innerHTML = entries.map((entry) => `
    <tr data-file-path="${attr(entry.path)}" data-kind="${attr(entry.kind)}">
      <td><div class="file-name-cell">
        <span class="file-type-icon ${entry.kind === "directory" ? "folder" : ""}"><svg><use href="#${entry.kind === "directory" ? "i-folder" : "i-file"}"></use></svg></span>
        <div><strong>${esc(entry.name)}</strong><small>${esc(entry.kind)}</small></div>
      </div></td>
      <td>${entry.kind === "directory" ? "—" : formatBytes(entry.size)}</td>
      <td>${formatDate(entry.modified_at)}</td>
      <td>${esc(entry.permissions || "—")}</td>
      <td><div class="row-actions">
        ${entry.kind === "file" && entry.editable ? '<button data-row-action="edit" title="Sửa"><svg><use href="#i-edit"></use></svg></button>' : ""}
        ${entry.kind === "file" ? '<button data-row-action="download" title="Tải xuống"><svg><use href="#i-download"></use></svg></button>' : ""}
        <button data-row-action="more" title="Chi tiết"><svg><use href="#i-eye"></use></svg></button>
      </div></td>
    </tr>`).join("");

  $$("tr[data-file-path]", tbody).forEach((row) => {
    const entry = entries.find((item) => item.path === row.dataset.filePath);
    row.addEventListener("click", (event) => {
      if (event.target.closest("button")) return;
      selectFile(entry, row);
    });
    row.addEventListener("dblclick", () => {
      if (entry.kind === "directory") loadFiles(entry.path);
      else if (entry.editable) openEditor(entry);
    });
    $$("[data-row-action]", row).forEach((button) => {
      button.addEventListener("click", () => {
        if (button.dataset.rowAction === "edit") openEditor(entry);
        else if (button.dataset.rowAction === "download") downloadFile(entry.path);
        else selectFile(entry, row);
      });
    });
  });

  if (searchMode) $("#fileEmpty").classList.toggle("is-hidden", Boolean(entries.length));
}

function selectFile(entry, row) {
  state.selectedFile = entry;
  $$("#fileTable tr").forEach((item) => item.classList.remove("selected"));
  if (row) row.classList.add("selected");
  renderFileInspector(entry);
}

function renderFileInspector(entry) {
  const box = $("#fileInspector");
  if (!entry) {
    box.innerHTML = `<div class="inspector-placeholder"><svg><use href="#i-file"></use></svg><h3>Chọn một file</h3><p>Thông tin và thao tác sẽ xuất hiện tại đây.</p></div>`;
    return;
  }
  box.innerHTML = `
    <div class="inspector-content">
      <div class="inspector-hero ${entry.kind === "directory" ? "folder" : ""}"><svg><use href="#${entry.kind === "directory" ? "i-folder" : "i-file"}"></use></svg></div>
      <h3>${esc(entry.name)}</h3><p>${esc(entry.path)}</p>
      <div class="detail-list">
        <div class="detail-row"><span>Loại</span><b>${esc(entry.kind)}</b></div>
        <div class="detail-row"><span>Kích thước</span><b>${entry.kind === "directory" ? "—" : formatBytes(entry.size)}</b></div>
        <div class="detail-row"><span>Cập nhật</span><b>${formatDate(entry.modified_at)}</b></div>
        <div class="detail-row"><span>Quyền</span><b>${esc(entry.permissions || "—")}</b></div>
      </div>
      <div class="inspector-actions">
        ${entry.kind === "directory" ? '<button class="btn primary" data-inspect-action="open"><svg><use href="#i-folder"></use></svg>Mở thư mục</button>' : ""}
        ${entry.kind === "file" && entry.editable ? '<button class="btn primary" data-inspect-action="edit"><svg><use href="#i-edit"></use></svg>Sửa file</button>' : ""}
        ${entry.kind === "file" ? '<button class="btn subtle" data-inspect-action="download"><svg><use href="#i-download"></use></svg>Tải xuống</button>' : ""}
        <button class="btn subtle" data-inspect-action="rename"><svg><use href="#i-edit"></use></svg>Đổi tên</button>
        <button class="btn danger" data-inspect-action="delete"><svg><use href="#i-trash"></use></svg>Xóa</button>
      </div>
    </div>`;
  $$("[data-inspect-action]", box).forEach((button) => button.addEventListener("click", () => {
    const action = button.dataset.inspectAction;
    if (action === "open") loadFiles(entry.path);
    if (action === "edit") openEditor(entry);
    if (action === "download") downloadFile(entry.path);
    if (action === "rename") renameEntry(entry);
    if (action === "delete") deleteEntry(entry);
  }));
}

function handleFileSearch() {
  clearTimeout(state.searchTimer);
  state.searchTimer = setTimeout(async () => {
    const query = $("#fileSearchInput").value.trim();
    if (!query) {
      await loadFiles();
      return;
    }
    if (query.length < 2) return;
    try {
      const params = new URLSearchParams({ root: state.currentRoot, path: state.currentPath, query });
      const data = await api(`/api/files/search?${params}`);
      renderFileTable(data.results, true);
      toast("Tìm kiếm", `${data.results.length} kết quả`, "success");
    } catch (error) {
      toast("Không thể tìm kiếm", error.message, "error");
    }
  }, 350);
}

async function openEditor(entry) {
  try {
    const params = new URLSearchParams({ root: state.currentRoot, path: entry.path });
    const data = await api(`/api/files/read?${params}`);
    state.editorFile = data;
    $("#editorTitle").textContent = data.name;
    $("#editorPath").textContent = `${data.root}:/${data.path}`;
    $("#editorState").textContent = data.read_only ? "Chỉ đọc" : "Đã đồng bộ";
    $("#fileEditor").value = data.content;
    $("#fileEditor").readOnly = data.read_only;
    $("#saveEditor").disabled = data.read_only;
    $("#editorBackdrop").classList.remove("is-hidden");
    updateEditorGutter();
    setTimeout(() => $("#fileEditor").focus(), 50);
  } catch (error) {
    toast("Không thể mở file", error.message, "error");
  }
}

function closeEditor() {
  $("#editorBackdrop").classList.add("is-hidden");
  state.editorFile = null;
}

async function saveEditor() {
  if (!state.editorFile) return;
  $("#saveEditor").disabled = true;
  $("#editorState").textContent = "Đang lưu…";
  try {
    const result = await api("/api/files/write", {
      method: "PUT",
      body: {
        root: state.editorFile.root,
        path: state.editorFile.path,
        content: $("#fileEditor").value,
        expected_mtime_ns: state.editorFile.mtime_ns,
        create: false,
      },
    });
    state.editorFile.mtime_ns = result.mtime_ns;
    $("#editorState").textContent = "Đã lưu";
    toast("Đã lưu", state.editorFile.path, "success");
    await loadFiles();
  } catch (error) {
    $("#editorState").textContent = "Lưu thất bại";
    toast("Không thể lưu file", error.message, "error");
  } finally {
    $("#saveEditor").disabled = state.editorFile?.read_only || false;
  }
}

async function reloadEditor() {
  if (!state.editorFile) return;
  const entry = { path: state.editorFile.path };
  await openEditor(entry);
}

function updateEditorGutter() {
  const editor = $("#fileEditor");
  const lines = editor.value.split("\n").length;
  $("#lineNumbers").textContent = Array.from({ length: lines }, (_, index) => index + 1).join("\n");
}

function syncEditorScroll() {
  $("#lineNumbers").scrollTop = $("#fileEditor").scrollTop;
}

function editorTabKey(event) {
  if (event.key !== "Tab") return;
  event.preventDefault();
  const editor = event.target;
  const start = editor.selectionStart;
  const end = editor.selectionEnd;
  editor.value = `${editor.value.slice(0, start)}  ${editor.value.slice(end)}`;
  editor.selectionStart = editor.selectionEnd = start + 2;
  updateEditorGutter();
}

async function createFolder() {
  const name = await formModal({
    eyebrow: "FILE MANAGER",
    title: "Tạo thư mục mới",
    fields: [{ name: "name", label: "Tên thư mục", placeholder: "new-folder", required: true }],
    confirmText: "Tạo thư mục",
  });
  if (!name) return;
  const path = joinPath(state.currentPath, name.name);
  try {
    await api("/api/files/directory", { method: "POST", body: { root: state.currentRoot, path } });
    toast("Đã tạo thư mục", path, "success");
    await loadFiles();
  } catch (error) {
    toast("Không thể tạo thư mục", error.message, "error");
  }
}

async function createFile() {
  const values = await formModal({
    eyebrow: "FILE MANAGER",
    title: "Tạo file mới",
    fields: [{ name: "name", label: "Tên file", placeholder: "example.txt", required: true }],
    confirmText: "Tạo và mở",
  });
  if (!values) return;
  const path = joinPath(state.currentPath, values.name);
  try {
    const result = await api("/api/files/write", {
      method: "PUT",
      body: { root: state.currentRoot, path, content: "", create: true },
    });
    toast("Đã tạo file", path, "success");
    await loadFiles();
    await openEditor({ path: result.path });
  } catch (error) {
    toast("Không thể tạo file", error.message, "error");
  }
}

async function uploadFile() {
  const input = $("#fileUploadInput");
  const file = input.files[0];
  if (!file) return;
  const form = new FormData();
  form.append("root", state.currentRoot);
  form.append("path", state.currentPath);
  form.append("overwrite", "false");
  form.append("upload", file);
  try {
    await api("/api/files/upload", { method: "POST", body: form });
    toast("Upload thành công", file.name, "success");
    await loadFiles();
  } catch (error) {
    toast("Upload thất bại", error.message, "error");
  } finally {
    input.value = "";
  }
}

async function renameEntry(entry) {
  const values = await formModal({
    eyebrow: "FILE MANAGER",
    title: "Đổi tên",
    fields: [{ name: "name", label: "Tên mới", value: entry.name, required: true }],
    confirmText: "Đổi tên",
  });
  if (!values || values.name === entry.name) return;
  try {
    await api("/api/files/rename", {
      method: "POST",
      body: { root: state.currentRoot, path: entry.path, new_name: values.name },
    });
    toast("Đã đổi tên", values.name, "success");
    await loadFiles();
  } catch (error) {
    toast("Không thể đổi tên", error.message, "error");
  }
}

async function deleteEntry(entry) {
  const confirmed = await confirmModal({
    eyebrow: "XÓA DỮ LIỆU",
    title: `Xóa ${entry.name}?`,
    message: entry.kind === "directory"
      ? "Toàn bộ file bên trong thư mục sẽ bị xóa. Hành động này không thể hoàn tác."
      : "File sẽ bị xóa vĩnh viễn khỏi VPS.",
    confirmText: "Xóa vĩnh viễn",
    danger: true,
  });
  if (!confirmed) return;
  try {
    await api("/api/files", {
      method: "DELETE",
      body: { root: state.currentRoot, path: entry.path, recursive: entry.kind === "directory", confirmation: "DELETE" },
    });
    toast("Đã xóa", entry.name, "success");
    await loadFiles();
  } catch (error) {
    toast("Không thể xóa", error.message, "error");
  }
}

async function downloadFile(path) {
  try {
    const params = new URLSearchParams({ root: state.currentRoot, path });
    const response = await api(`/api/files/download?${params}`, { raw: true });
    const blob = await response.blob();
    triggerDownload(blob, filenameFromPath(path));
  } catch (error) {
    toast("Không thể tải file", error.message, "error");
  }
}

async function loadDocker() {
  const grid = $("#containerGrid");
  grid.innerHTML = `<div class="panel skeleton" style="height:240px"></div><div class="panel skeleton" style="height:240px"></div>`;
  try {
    const data = await api("/api/docker/containers?include_stats=true");
    renderDockerSummary(data.containers);
    renderContainers(data.containers);
  } catch (error) {
    grid.innerHTML = `<div class="panel"><p>${esc(error.message)}</p></div>`;
  }
}

function renderDockerSummary(containers) {
  const running = containers.filter((c) => c.status === "running").length;
  const stopped = containers.length - running;
  const cpu = containers.reduce((sum, c) => sum + (c.stats?.cpu_percent || 0), 0);
  const memory = containers.reduce((sum, c) => sum + (c.stats?.memory_usage || 0), 0);
  $("#dockerSummary").innerHTML = [
    ["Tổng container", containers.length, "i-box"],
    ["Đang chạy", running, "i-check"],
    ["Đã dừng", stopped, "i-power"],
    ["RAM Docker", formatBytes(memory), "i-monitor"],
  ].map(([label, value, icon]) => `<div class="summary-card"><span class="summary-icon"><svg><use href="#${icon}"></use></svg></span><div><strong>${value}</strong><small>${label}</small></div></div>`).join("");
}

function renderContainers(containers) {
  $("#containerGrid").innerHTML = containers.map((container) => {
    const stats = container.stats || {};
    const ports = (container.ports || []).filter((p) => p.host_port).map((p) => `${p.host_port} → ${p.container}`).join(" · ") || "Không public port";
    return `
      <article class="container-card">
        <div class="container-card-body">
          <div class="container-card-head">
            <div class="container-ident"><span class="container-logo"><svg><use href="#i-box"></use></svg></span><div><strong>${esc(container.name)}</strong><small>${esc(container.image)}</small></div></div>
            <span class="badge ${esc(container.status)}">${esc(container.status)}</span>
          </div>
          <div class="mini-metrics">
            <div class="mini-metric"><span>CPU</span><strong>${stats.cpu_percent != null ? `${stats.cpu_percent.toFixed(1)}%` : "—"}</strong></div>
            <div class="mini-metric"><span>RAM</span><strong>${stats.memory_usage != null ? formatBytes(stats.memory_usage) : "—"}</strong></div>
            <div class="mini-metric"><span>Network ↓</span><strong>${stats.network_received != null ? formatBytes(stats.network_received) : "—"}</strong></div>
            <div class="mini-metric"><span>Health</span><strong>${esc(container.health || "—")}</strong></div>
          </div>
          <div class="port-list">${esc(ports)}</div>
          ${container.protected ? '<div class="protected-note"><svg><use href="#i-check"></use></svg>Container hệ thống được bảo vệ</div>' : ""}
        </div>
        <div class="card-actions">
          <button class="btn subtle small" data-container-log="${attr(container.name)}"><svg><use href="#i-logs"></use></svg>Logs</button>
          ${container.protected ? "" : container.status === "running"
            ? `<button class="btn subtle small" data-container-action="restart" data-container="${attr(container.name)}"><svg><use href="#i-refresh"></use></svg>Restart</button><button class="btn danger small" data-container-action="stop" data-container="${attr(container.name)}">Stop</button>`
            : `<button class="btn primary small" data-container-action="start" data-container="${attr(container.name)}">Start</button>`}
        </div>
      </article>`;
  }).join("") || `<div class="panel"><p>Chưa có container.</p></div>`;

  $$("[data-container-log]").forEach((button) => button.addEventListener("click", () => openContainerLogs(button.dataset.containerLog)));
  $$("[data-container-action]").forEach((button) => button.addEventListener("click", () => runContainerAction(button.dataset.container, button.dataset.containerAction)));
}

async function runContainerAction(container, action) {
  const confirmed = await confirmModal({
    eyebrow: "DOCKER ACTION",
    title: `${humanAction(action)} ${container}?`,
    message: action === "stop" ? "Dịch vụ sẽ ngừng hoạt động cho đến khi được bật lại." : "Container sẽ được khởi động lại trong vài giây.",
    confirmText: humanAction(action),
    danger: action === "stop",
  });
  if (!confirmed) return;
  try {
    await api(`/api/docker/containers/${encodeURIComponent(container)}/action`, { method: "POST", body: { action } });
    toast("Docker", `${container}: ${action} thành công`, "success");
    await loadDocker();
  } catch (error) {
    toast("Docker thất bại", error.message, "error");
  }
}

async function openContainerLogs(container) {
  await openLogModal({
    eyebrow: "DOCKER LOG",
    title: container,
    loader: async () => {
      const data = await api(`/api/docker/containers/${encodeURIComponent(container)}/logs?tail=500`);
      return data.logs || "Không có log.";
    },
  });
}

async function loadDeploy() {
  const grid = $("#projectGrid");
  grid.innerHTML = `<div class="panel skeleton" style="height:230px"></div>`;
  try {
    const data = await api("/api/projects");
    renderProjects(data.projects);
    await loadDeployJobs();
  } catch (error) {
    grid.innerHTML = `<div class="panel"><p>${esc(error.message)}</p></div>`;
  }
}

function renderProjects(projects) {
  $("#projectGrid").innerHTML = projects.map((project) => {
    const status = project.status || {};
    return `
      <article class="project-card">
        <div class="project-card-body">
          <div class="project-card-head"><div class="container-ident"><span class="project-logo"><svg><use href="#i-rocket"></use></svg></span><div><strong>${esc(project.name)}</strong><small>${esc(project.id)}</small></div></div><span class="badge ${status.available ? "success" : "failed"}">${status.available ? "Ready" : "Unavailable"}</span></div>
          <div class="project-info">
            <div><span>Nhánh</span><b>${esc(status.branch || project.branch)}</b></div>
            <div><span>Commit</span><b>${esc((status.current_sha || "—").slice(0, 12))}</b></div>
            <div><span>Chế độ</span><b>${esc(project.mode)}</b></div>
            <div><span>Dữ liệu local</span><b>${status.dirty ? "Có thay đổi" : "Sạch"}</b></div>
          </div>
          ${status.error ? `<p class="form-error">${esc(status.error)}</p>` : ""}
          ${project.protected ? '<div class="protected-note"><svg><use href="#i-check"></use></svg>Chỉ cập nhật bằng scripts/update.sh</div>' : ""}
        </div>
        <div class="card-actions">
          <button class="btn primary small" data-deploy="${attr(project.id)}" ${!project.enabled || project.protected || !status.available ? "disabled" : ""}><svg><use href="#i-rocket"></use></svg>Deploy</button>
        </div>
      </article>`;
  }).join("") || `<article class="panel"><p>Chưa có dự án trong <code>config/projects.json</code>.</p></article>`;
  $$("[data-deploy]").forEach((button) => button.addEventListener("click", () => deployProject(button.dataset.deploy)));
}

async function deployProject(projectId) {
  const confirmed = await confirmModal({
    eyebrow: "PRODUCTION DEPLOY",
    title: `Triển khai ${projectId}?`,
    message: "API‑VPS sẽ đồng bộ Git, build, khởi động dịch vụ, health check và tự rollback nếu lỗi.",
    confirmText: "Triển khai ngay",
  });
  if (!confirmed) return;
  try {
    const job = await api(`/api/projects/${encodeURIComponent(projectId)}/deploy`, { method: "POST", body: { confirmation: "DEPLOY" } });
    toast("Đã bắt đầu triển khai", `Job ${job.id.slice(0, 8)}`, "success");
    await loadDeployJobs();
    await openJobLog(job.id);
  } catch (error) {
    toast("Không thể triển khai", error.message, "error");
  }
}

async function loadDeployJobs(silent = false) {
  try {
    const data = await api("/api/jobs?kind=deploy&limit=50");
    $("#deployJobTable").innerHTML = data.jobs.map((job) => `
      <tr>
        <td>${formatDate(job.created_at)}</td>
        <td><strong>${esc(job.target)}</strong></td>
        <td><span class="badge ${job.state === "running" ? "running-job" : esc(job.state)}">${esc(job.state)}</span></td>
        <td>${esc(job.message)}</td>
        <td><button class="text-btn" data-job-log="${attr(job.id)}">Xem log</button></td>
      </tr>`).join("") || `<tr><td colspan="5">Chưa có lần triển khai nào.</td></tr>`;
    $$("[data-job-log]").forEach((button) => button.addEventListener("click", () => openJobLog(button.dataset.jobLog)));
  } catch (error) {
    if (!silent) toast("Không thể tải lịch sử deploy", error.message, "error");
  }
}

async function openJobLog(jobId) {
  await openLogModal({
    eyebrow: "DEPLOYMENT JOB",
    title: `Job ${jobId.slice(0, 8)}`,
    autoRefresh: true,
    loader: async () => {
      const job = await api(`/api/jobs/${jobId}`);
      return `[${job.state}] ${job.message}\n\n${job.log || "Chưa có log."}`;
    },
  });
}

async function loadBackups() {
  if (!state.roots.length) {
    const roots = await api("/api/files/roots");
    state.roots = roots.roots.filter((root) => root.available);
    populateRootSelects();
  }
  const data = await api("/api/backups");
  renderBackups(data.backups);
}

async function createBackup(event) {
  event.preventDefault();
  try {
    const job = await api("/api/backups", {
      method: "POST",
      body: {
        root: $("#backupRoot").value,
        path: $("#backupPath").value.trim(),
        label: $("#backupLabel").value.trim() || "manual",
      },
    });
    toast("Đang tạo backup", `Job ${job.id.slice(0, 8)}`, "success");
    await openJobLog(job.id);
    setTimeout(loadBackups, 3000);
  } catch (error) {
    toast("Không thể tạo backup", error.message, "error");
  }
}

function renderBackups(backups) {
  $("#backupGrid").innerHTML = backups.map((backup) => `
    <article class="backup-card">
      <div class="backup-card-body">
        <div class="backup-card-head"><div class="container-ident"><span class="backup-logo"><svg><use href="#i-backup"></use></svg></span><div><strong>${esc(backup.label)}</strong><small>${formatDate(backup.created_at)}</small></div></div><span class="badge ${backup.available ? "success" : "failed"}">${backup.available ? "Ready" : "Missing"}</span></div>
        <div class="backup-info">
          <div><span>Nguồn</span><b>${esc(`${backup.source?.root || ""}:/${backup.source?.path || ""}`)}</b></div>
          <div><span>Kích thước</span><b>${formatBytes(backup.size || 0)}</b></div>
          <div><span>ID</span><b>${esc(backup.id.slice(0, 12))}</b></div>
        </div>
      </div>
      <div class="card-actions">
        <button class="btn subtle small" data-backup-download="${attr(backup.id)}"><svg><use href="#i-download"></use></svg>Tải</button>
        <button class="btn subtle small" data-backup-restore="${attr(backup.id)}">Khôi phục</button>
        <button class="btn danger small" data-backup-delete="${attr(backup.id)}"><svg><use href="#i-trash"></use></svg></button>
      </div>
    </article>`).join("") || `<article class="panel"><p>Chưa có bản sao lưu.</p></article>`;
  $$("[data-backup-download]").forEach((button) => button.addEventListener("click", () => downloadBackup(button.dataset.backupDownload)));
  $$("[data-backup-restore]").forEach((button) => button.addEventListener("click", () => restoreBackup(button.dataset.backupRestore)));
  $$("[data-backup-delete]").forEach((button) => button.addEventListener("click", () => deleteBackup(button.dataset.backupDelete)));
}

async function downloadBackup(id) {
  try {
    const response = await api(`/api/backups/${id}/download`, { raw: true });
    const blob = await response.blob();
    const disposition = response.headers.get("content-disposition") || "";
    const match = disposition.match(/filename="?([^"]+)"?/i);
    triggerDownload(blob, match?.[1] || `${id}.tar.gz`);
  } catch (error) {
    toast("Không thể tải backup", error.message, "error");
  }
}

async function restoreBackup(id) {
  const values = await formModal({
    eyebrow: "RESTORE BACKUP",
    title: "Chọn vị trí khôi phục",
    fields: [
      { name: "root", label: "Root alias", type: "select", options: state.roots.map((root) => ({ value: root.alias, label: `${root.label} · ${root.path}` })) },
      { name: "path", label: "Đường dẫn đích", placeholder: "restored/project", required: true },
      { name: "overwrite", label: "Ghi đè nếu đã tồn tại", type: "checkbox" },
    ],
    confirmText: "Khôi phục",
  });
  if (!values) return;
  const confirmed = await confirmModal({
    eyebrow: "XÁC NHẬN KHÔI PHỤC",
    title: "Khôi phục dữ liệu từ backup?",
    message: values.overwrite ? "Dữ liệu hiện có tại đích có thể bị thay thế." : "API‑VPS sẽ chỉ khôi phục khi đích chưa có dữ liệu.",
    confirmText: "Khôi phục ngay",
    danger: Boolean(values.overwrite),
  });
  if (!confirmed) return;
  try {
    const job = await api(`/api/backups/${id}/restore`, {
      method: "POST",
      body: {
        target_root: values.root,
        target_path: values.path,
        overwrite: Boolean(values.overwrite),
        confirmation: "RESTORE",
      },
    });
    toast("Đang khôi phục", `Job ${job.id.slice(0, 8)}`, "success");
    await openJobLog(job.id);
  } catch (error) {
    toast("Không thể khôi phục", error.message, "error");
  }
}

async function deleteBackup(id) {
  const confirmed = await confirmModal({
    eyebrow: "DELETE BACKUP",
    title: "Xóa bản sao lưu?",
    message: "File nén và manifest sẽ bị xóa vĩnh viễn.",
    confirmText: "Xóa backup",
    danger: true,
  });
  if (!confirmed) return;
  try {
    await api(`/api/backups/${id}`, { method: "DELETE", body: { confirmation: "DELETE" } });
    toast("Đã xóa backup", id.slice(0, 8), "success");
    await loadBackups();
  } catch (error) {
    toast("Không thể xóa backup", error.message, "error");
  }
}

let auditTimer;
function debounceAudit() {
  clearTimeout(auditTimer);
  auditTimer = setTimeout(loadAudit, 350);
}

async function loadAudit() {
  const params = new URLSearchParams({ limit: "500" });
  const search = $("#auditSearch").value.trim();
  const outcome = $("#auditOutcome").value;
  if (search) params.set("search", search);
  if (outcome) params.set("outcome", outcome);
  const data = await api(`/api/audit?${params}`);
  $("#auditTable").innerHTML = data.events.map((event) => `
    <tr>
      <td>${formatDate(event.timestamp)}</td>
      <td><strong>${esc(humanAction(event.action))}</strong></td>
      <td><span class="badge ${esc(event.outcome)}">${esc(event.outcome)}</span></td>
      <td>${esc(event.client_ip || "—")}</td>
      <td><div class="details-json" title="${attr(JSON.stringify(event.details || {}))}">${esc(JSON.stringify(event.details || {}))}</div></td>
    </tr>`).join("") || `<tr><td colspan="5">Không có sự kiện phù hợp.</td></tr>`;
}

async function loadSettings() {
  const data = await api("/api/settings");
  const roots = data.managed_roots.map((root) => `<div><span>${esc(root.alias)}</span><b>${esc(root.path)}${root.read_only ? " · RO" : ""}</b></div>`).join("");
  $("#settingsGrid").innerHTML = `
    <article class="settings-card"><p class="eyebrow">PHIÊN BẢN</p><div class="settings-value">v${esc(data.version)}</div><p>API‑VPS Control Center</p></article>
    <article class="settings-card"><p class="eyebrow">API SECURITY</p><div class="settings-value">${data.security.api_key_configured ? "Đã bật" : "Chưa an toàn"}</div><p>API key luôn được ẩn khỏi giao diện.</p></article>
    <article class="settings-card"><p class="eyebrow">GIỚI HẠN UPLOAD</p><div class="settings-value">${formatBytes(data.limits.max_upload_bytes)}</div><p>Mỗi file upload qua dashboard.</p></article>
    <article class="settings-card"><p class="eyebrow">MANAGED ROOTS</p><div class="settings-list">${roots}</div></article>
    <article class="settings-card"><p class="eyebrow">MONITORING</p><div class="settings-list"><div><span>Chu kỳ</span><b>${data.metrics.interval_seconds}s</b></div><div><span>Điểm lịch sử</span><b>${data.metrics.history_points}</b></div></div></article>
    <article class="settings-card"><p class="eyebrow">PROTECTED</p><div class="settings-value">${esc(data.security.self_container_protected)}</div><p>Không thể dừng từ dashboard.</p></article>`;
}

async function openLogModal({ eyebrow, title, loader, autoRefresh = false }) {
  clearInterval(state.logAutoTimer);
  state.logLoader = async () => {
    try {
      const content = await loader();
      const viewer = $("#logViewer");
      const nearBottom = viewer.scrollHeight - viewer.scrollTop - viewer.clientHeight < 80;
      viewer.textContent = content;
      if (nearBottom) viewer.scrollTop = viewer.scrollHeight;
    } catch (error) {
      $("#logViewer").textContent = `LỖI: ${error.message}`;
    }
  };
  $("#logEyebrow").textContent = eyebrow;
  $("#logTitle").textContent = title;
  $("#logViewer").textContent = "Đang tải log…";
  $("#logBackdrop").classList.remove("is-hidden");
  await state.logLoader();
  if (autoRefresh) {
    state.logAutoTimer = setInterval(() => {
      if (!$("#logBackdrop").classList.contains("is-hidden") && state.logLoader) {
        state.logLoader();
      }
    }, 2000);
  }
}

function closeLogModal() {
  clearInterval(state.logAutoTimer);
  state.logAutoTimer = null;
  $("#logBackdrop").classList.add("is-hidden");
  state.logLoader = null;
}

function confirmModal({ eyebrow = "XÁC NHẬN", title, message, confirmText = "Xác nhận", danger = false }) {
  return new Promise((resolve) => {
    $("#modalEyebrow").textContent = eyebrow;
    $("#modalTitle").textContent = title;
    $("#modalBody").innerHTML = `<p>${esc(message)}</p>`;
    $("#modalActions").innerHTML = `<button class="btn subtle" data-modal-cancel>Hủy</button><span class="spacer"></span><button class="btn ${danger ? "danger" : "primary"}" data-modal-confirm>${esc(confirmText)}</button>`;
    $("#modalBackdrop").classList.remove("is-hidden");
    const finish = (value) => {
      closeGenericModal();
      resolve(value);
    };
    $("[data-modal-cancel]").addEventListener("click", () => finish(false));
    $("[data-modal-confirm]").addEventListener("click", () => finish(true));
  });
}

function formModal({ eyebrow = "NHẬP THÔNG TIN", title, fields, confirmText = "Xác nhận" }) {
  return new Promise((resolve) => {
    $("#modalEyebrow").textContent = eyebrow;
    $("#modalTitle").textContent = title;
    $("#modalBody").innerHTML = `<form class="modal-form" id="dynamicModalForm">${fields.map((field) => {
      if (field.type === "select") {
        return `<label>${esc(field.label)}<select name="${attr(field.name)}">${(field.options || []).map((option) => `<option value="${attr(option.value)}">${esc(option.label)}</option>`).join("")}</select></label>`;
      }
      if (field.type === "checkbox") {
        return `<label class="switch"><input type="checkbox" name="${attr(field.name)}"><span></span><b>${esc(field.label)}</b></label>`;
      }
      return `<label>${esc(field.label)}<input name="${attr(field.name)}" value="${attr(field.value || "")}" placeholder="${attr(field.placeholder || "")}" ${field.required ? "required" : ""}></label>`;
    }).join("")}</form>`;
    $("#modalActions").innerHTML = `<button class="btn subtle" data-modal-cancel>Hủy</button><span class="spacer"></span><button class="btn primary" data-modal-confirm>${esc(confirmText)}</button>`;
    $("#modalBackdrop").classList.remove("is-hidden");
    const finish = (value) => {
      closeGenericModal();
      resolve(value);
    };
    $("[data-modal-cancel]").addEventListener("click", () => finish(null));
    $("[data-modal-confirm]").addEventListener("click", () => {
      const form = $("#dynamicModalForm");
      if (!form.reportValidity()) return;
      const data = {};
      fields.forEach((field) => {
        const input = form.elements[field.name];
        data[field.name] = field.type === "checkbox" ? input.checked : input.value.trim();
      });
      finish(data);
    });
    setTimeout(() => $("#dynamicModalForm input, #dynamicModalForm select")?.focus(), 50);
  });
}

function closeGenericModal() {
  $("#modalBackdrop").classList.add("is-hidden");
  $("#modalBody").innerHTML = "";
  $("#modalActions").innerHTML = "";
}

function toast(title, message, type = "success") {
  const item = document.createElement("div");
  item.className = `toast ${type}`;
  item.innerHTML = `<span class="toast-icon"><svg><use href="#${type === "error" ? "i-alert" : "i-check"}"></use></svg></span><div><strong>${esc(title)}</strong><small>${esc(message || "")}</small></div>`;
  $("#toastStack").appendChild(item);
  setTimeout(() => item.remove(), 5000);
}

function drawLineChart(canvas, datasets, options = {}) {
  if (!canvas || !canvas.isConnected) return;
  const rect = canvas.getBoundingClientRect();
  if (!rect.width) return;
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.floor(rect.width * ratio);
  canvas.height = Math.floor((Number(canvas.getAttribute("height")) || 220) * ratio);
  const ctx = canvas.getContext("2d");
  ctx.scale(ratio, ratio);
  const width = rect.width;
  const height = canvas.height / ratio;
  const padding = { top: 14, right: 12, bottom: 24, left: 42 };
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;
  const all = datasets.flatMap((dataset) => dataset.values).filter(Number.isFinite);
  const max = options.max || Math.max(...all, 1) * 1.12;
  const min = options.min || 0;

  ctx.clearRect(0, 0, width, height);
  ctx.font = "9px Inter, sans-serif";
  ctx.fillStyle = css("--subtle");
  ctx.strokeStyle = "rgba(163,181,218,.09)";
  ctx.lineWidth = 1;

  for (let i = 0; i <= 4; i += 1) {
    const y = padding.top + (innerHeight * i) / 4;
    ctx.beginPath();
    ctx.moveTo(padding.left, y);
    ctx.lineTo(width - padding.right, y);
    ctx.stroke();
    const value = max - ((max - min) * i) / 4;
    const label = options.formatter ? options.formatter(value) : `${Math.round(value)}${options.suffix || ""}`;
    ctx.fillText(label, 4, y + 3);
  }

  datasets.forEach((dataset) => {
    const values = dataset.values;
    if (!values.length) return;
    ctx.beginPath();
    values.forEach((value, index) => {
      const x = padding.left + (innerWidth * index) / Math.max(values.length - 1, 1);
      const y = padding.top + innerHeight - ((value - min) / Math.max(max - min, 1)) * innerHeight;
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = dataset.color;
    ctx.lineWidth = 2;
    ctx.stroke();

    const gradient = ctx.createLinearGradient(0, padding.top, 0, height - padding.bottom);
    gradient.addColorStop(0, hexToRgba(dataset.color, 0.16));
    gradient.addColorStop(1, hexToRgba(dataset.color, 0));
    ctx.lineTo(width - padding.right, height - padding.bottom);
    ctx.lineTo(padding.left, height - padding.bottom);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();
  });
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function loadingRow(columns) {
  return `<tr class="loading-row"><td colspan="${columns}">Đang tải dữ liệu…</td></tr>`;
}

function joinPath(base, name) {
  return [base, name].filter(Boolean).join("/").replace(/\/+/g, "/");
}

function filenameFromPath(path) {
  return path.split("/").filter(Boolean).pop() || "download";
}

function formatBytes(value, decimals = 1) {
  const bytes = Number(value) || 0;
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB", "PB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toFixed(index ? decimals : 0)} ${units[index]}`;
}

function formatRate(value) {
  return `${formatBytes(value)}/s`;
}

function formatUptime(seconds) {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days) return `${days} ngày ${hours} giờ`;
  if (hours) return `${hours} giờ ${minutes} phút`;
  return `${minutes} phút`;
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "medium" });
}

function humanAction(value) {
  const map = {
    start: "Khởi động",
    stop: "Dừng",
    restart: "Khởi động lại",
    pause: "Tạm dừng",
    unpause: "Tiếp tục",
    "file.write": "Ghi file",
    "file.mkdir": "Tạo thư mục",
    "file.rename": "Đổi tên file",
    "file.delete": "Xóa file",
    "file.upload": "Upload file",
    "backup.create": "Tạo backup",
    "backup.restore": "Khôi phục backup",
    "backup.delete": "Xóa backup",
    "deploy.project": "Triển khai dự án",
    "service.start": "API‑VPS khởi động",
    "service.stop": "API‑VPS dừng",
  };
  return map[value] || String(value || "unknown").replaceAll(".", " · ");
}

function css(variable) {
  return getComputedStyle(document.documentElement).getPropertyValue(variable).trim();
}

function hexToRgba(color, alpha) {
  if (!color.startsWith("#")) return color;
  const value = color.slice(1);
  const normalized = value.length === 3 ? value.split("").map((c) => c + c).join("") : value;
  const number = Number.parseInt(normalized, 16);
  return `rgba(${(number >> 16) & 255},${(number >> 8) & 255},${number & 255},${alpha})`;
}

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  })[character]);
}

function attr(value) {
  return esc(value).replace(/`/g, "&#096;");
}
