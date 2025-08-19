// static/js/admin.js

// ───────── 공통 유틸 ─────────
function setLoading(btn, loading) {
  if (!btn) return;
  if (loading) { btn.classList.add("is-loading"); btn.disabled = true; }
  else { btn.classList.remove("is-loading"); btn.disabled = false; }
}

function renderBadge(el, isOpen) {
  if (!el) return;
  if (isOpen === true) {
    el.innerHTML = '<span class="badge badge--ok">열림</span>';
  } else if (isOpen === false) {
    el.innerHTML = '<span class="badge badge--danger">닫힘</span>';
  } else {
    el.innerHTML = '<span class="badge badge--muted">알 수 없음</span>';
  }
}

// ───────── 데이터 동기화 ─────────
function initSyncCard() {
  const syncBtn = document.getElementById("sync-btn");
  const syncLog = document.getElementById("sync-log");
  if (!syncBtn) return;

  syncBtn.addEventListener("click", async () => {
    setLoading(syncBtn, true);
    syncLog && (syncLog.textContent = "동기화 요청 중…");
    try {
      const res = await fetch("/sync-estimation", { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      syncLog && (syncLog.textContent = `✅ ${data.message || "동기화가 완료되었습니다."}`);
    } catch (err) {
      syncLog && (syncLog.textContent = `❌ 동기화 실패: ${err.message || err}`);
    } finally {
      setLoading(syncBtn, false);
    }
  });
}

// ───────── 시스템 설정 (포트 상태) ─────────
function renderConn(el, isOpen, onText, offText) {
  if (!el) return;
  if (isOpen === true) {
    el.innerHTML = `<span class="ok">${onText}</span>`;
  } else if (isOpen === false) {
    el.innerHTML = `<span class="danger">${offText}</span>`;
  } else {
    el.innerHTML = `<span class="muted">알 수 없음</span>`;
  }
}

async function refreshPorts() {
  const systemLog = document.getElementById("system-log");
  const el5050 = document.getElementById("port-5050-status");
  const el5100 = document.getElementById("port-5100-status");
  const el5150 = document.getElementById("port-5150-status"); // ✅ 추가
  const conn5050 = document.getElementById("port-5050-conn");
  const conn5100 = document.getElementById("port-5100-conn");
  const conn5150 = document.getElementById("port-5150-conn"); // ✅ 추가

  try {
    const res = await fetch("/admin/ports");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const map = new Map(data.ports.map(p => [p.port, p.open]));

    const open5050 = map.get(5050);
    const open5100 = map.get(5100);
    const open5150 = map.get(5150); // ✅ 추가

    renderBadge(el5050, open5050);
    renderBadge(el5100, open5100);
    renderBadge(el5150, open5150);   // ✅ 추가

    renderConn(conn5050, open5050, "데이터서버 연결 on", "데이터서버 연결 off");
    renderConn(conn5100, open5100, "예측서버 연결 on", "예측서버 연결 off");
    renderConn(conn5150, open5150, "챗봇서버 연결 on", "챗봇서버 연결 off"); // ✅ 추가
  } catch (err) {
    systemLog && (systemLog.textContent = `❌ 포트 조회 실패: ${err.message || err}`);
    renderConn(conn5050, undefined);
    renderConn(conn5100, undefined);
    renderConn(conn5150, undefined); // ✅ 추가
  }
}

function initSystemCard() {
  refreshPorts();
  setInterval(refreshPorts, 8000);
}

// ───────── 사용자 관리 (목록/검색/삭제) ─────────
let usersCache = [];

function renderUsers(rows) {
  const tbody = document.getElementById("user-tbody");
  if (!tbody) return;

  if (!rows?.length) {
    tbody.innerHTML = `<tr><td colspan="7" class="muted">데이터가 없습니다.</td></tr>`;
    return;
  }

  tbody.innerHTML = rows.map(r => `
    <tr data-id="${r.ID ?? ""}">
      <td class="col-id">${r.ID ?? ""}</td>
      <td class="col-cr">${r.USR_CR ?? ""}</td>
      <td class="col-id2">${r.USR_ID ?? ""}</td>
      <td class="col-name">${r.USR_NAME ?? ""}</td>
      <td class="col-email">${r.USR_EMAIL ?? ""}</td>
      <td class="col-snm">${r.USR_SNM ?? ""}</td>
      <td class="col-actions" style="white-space:nowrap;">
        <button class="btn btn--danger btn--sm" data-action="delete" data-id="${r.ID ?? ""}">삭제</button>
      </td>
    </tr>
  `).join("");
}

async function fetchUsers() {
  const tbody = document.getElementById("user-tbody");
  const note = document.getElementById("user-note");
  const refreshBtn = document.getElementById("refresh-users");
  setLoading(refreshBtn, true);
  note && (note.textContent = "");
  tbody && (tbody.innerHTML = `<tr><td colspan="7" class="muted">목록을 불러오는 중…</td></tr>`);

  try {
    const res = await fetch("/admin/users");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (!data.success) throw new Error(data.error || "조회 실패");

    // 🔒 관리자 계정은 프론트에서도 가려줌(백엔드에서도 가드)
    usersCache = (data.rows || []).filter(
      r => String(r.USR_ID || '').toLowerCase() !== 'libra_admin'
    );
    renderUsers(usersCache);
  } catch (err) {
    tbody && (tbody.innerHTML = `<tr><td colspan="7" class="danger">❌ ${err.message || err}</td></tr>`);
  } finally {
    setLoading(refreshBtn, false);
  }
}

function filterUsers() {
  const q = (document.getElementById("user-search")?.value || "").trim().toLowerCase();
  if (!q) { renderUsers(usersCache); return; }
  const filtered = usersCache.filter(r =>
    [r.USR_NAME, r.USR_ID, r.USR_EMAIL].some(v => (v || "").toLowerCase().includes(q))
  );
  renderUsers(filtered);
}

async function deleteUser(id) {
  const note = document.getElementById("user-note");
  if (!id) return;
  if (!confirm(`ID ${id} 사용자를 삭제할까요? 이 작업은 되돌릴 수 없습니다.`)) return;

  try {
    const res = await fetch(`/admin/users/${id}`, { method: "DELETE" });
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.error || `HTTP ${res.status}`);
    // 캐시 갱신 후 렌더
    usersCache = usersCache.filter(r => r.ID !== id);
    renderUsers(usersCache);
    note && (note.textContent = `✅ 삭제 완료 (ID: ${id})`);
  } catch (err) {
    note && (note.textContent = `❌ 삭제 실패: ${err.message || err}`);
  }
}

function initUserCard() {
  const refreshBtn = document.getElementById("refresh-users");
  const searchInput = document.getElementById("user-search");
  const tbody = document.getElementById("user-tbody");

  refreshBtn && refreshBtn.addEventListener("click", fetchUsers);
  searchInput && searchInput.addEventListener("input", filterUsers);
  tbody && tbody.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-action='delete']");
    if (btn) {
      const id = Number(btn.dataset.id);
      deleteUser(id);
    }
  });

  // 최초 로드
  fetchUsers();
}

// ───────── 부트스트랩 ─────────
document.addEventListener("DOMContentLoaded", () => {
  initSyncCard();
  initSystemCard();
  initUserCard();
});
