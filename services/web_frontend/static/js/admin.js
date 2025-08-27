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

// ───────── LLM 데이터베이스 관리 ─────────
function initLLMDBCard() {
  const clearBtn = document.getElementById("clear-llm-data-btn");
  const llmDbLog = document.getElementById("llm-db-log");
  if (!clearBtn) return;

  clearBtn.addEventListener("click", async () => {
    if (!confirm("정말로 LLM_DATA 테이블의 모든 데이터를 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.")) {
      return;
    }

    setLoading(clearBtn, true);
    llmDbLog && (llmDbLog.textContent = "LLM 데이터 삭제 중…");
    
    try {
      const res = await fetch("/admin/clear-llm-data", { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      
      if (data.success) {
        llmDbLog && (llmDbLog.textContent = `✅ ${data.message || "LLM 데이터가 성공적으로 삭제되었습니다."}`);
      } else {
        throw new Error(data.error || "삭제 실패");
      }
    } catch (err) {
      llmDbLog && (llmDbLog.textContent = `❌ 삭제 실패: ${err.message || err}`);
    } finally {
      setLoading(clearBtn, false);
    }
  });
}
function initLLMCard() {
  const llmBtn = document.getElementById("llm-reload-btn");
  const llmLog = document.getElementById("llm-log");
  if (!llmBtn) return;

  llmBtn.addEventListener("click", async () => {
    setLoading(llmBtn, true);
    llmLog && (llmLog.textContent = "LLM 함수 초기화 중…");
    try {
      const res = await fetch("/admin/llm/reload", { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      
      if (data.status === "success") {
        llmLog && (llmLog.textContent = `✅ ${data.message || "LLM 함수 초기화가 완료되었습니다."}`);
      } else {
        throw new Error(data.message || "초기화 실패");
      }
    } catch (err) {
      llmLog && (llmLog.textContent = `❌ LLM 초기화 실패: ${err.message || err}`);
    } finally {
      setLoading(llmBtn, false);
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
  const el5150 = document.getElementById("port-5150-status");
  const el5200 = document.getElementById("port-5200-status");
  const conn5050 = document.getElementById("port-5050-conn");
  const conn5100 = document.getElementById("port-5100-conn");
  const conn5150 = document.getElementById("port-5150-conn");
  const conn5200 = document.getElementById("port-5200-conn");

  try {
    const res = await fetch("/admin/ports");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const map = new Map(data.ports.map(p => [p.port, p.open]));

    const open5050 = map.get(5050);
    const open5100 = map.get(5100);
    const open5150 = map.get(5150);
    const open5200 = map.get(5200);

    renderBadge(el5050, open5050);
    renderBadge(el5100, open5100);
    renderBadge(el5150, open5150);
    renderBadge(el5200, open5200);

    renderConn(conn5050, open5050, "데이터서버 연결 on", "데이터서버 연결 off");
    renderConn(conn5100, open5100, "예측서버 연결 on", "예측서버 연결 off");
    renderConn(conn5150, open5150, "챗봇서버 연결 on", "챗봇서버 연결 off");
    renderConn(conn5200, open5200, "에이전트서버 연결 on", "에이전트서버 연결 off");
  } catch (err) {
    systemLog && (systemLog.textContent = `❌ 포트 조회 실패: ${err.message || err}`);
    renderConn(conn5050, undefined);
    renderConn(conn5100, undefined);
    renderConn(conn5150, undefined);
    renderConn(conn5200, undefined);
  }
}

function initSystemCard() {
  refreshPorts();
  setInterval(refreshPorts, 8000);
}

// ───────── 래그 디비 관리 ─────────

function initRagCard() {
  const syncBtn = document.getElementById("rag-sync-btn");
  const resetBtn = document.getElementById("rag-reset-btn");
  const note = document.getElementById("rag-log");
  if (!syncBtn || !resetBtn) return;

  // 동기화: 기존 컬렉션 삭제 후 재업로드(reset=true)
  syncBtn.addEventListener("click", async () => {
    setLoading(syncBtn, true);
    note && (note.textContent = "Vector DB 동기화 중…");
    try {
      const res = await fetch("/admin/rag/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reset: true })
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      note && (note.textContent = `✅ 동기화 완료 (files=${data?.stats?.indexed_files ?? 0}, chunks=${data?.stats?.indexed_chunks ?? 0})`);
    } catch (err) {
      note && (note.textContent = `❌ 동기화 실패: ${err.message || err}`);
    } finally {
      setLoading(syncBtn, false);
    }
  });

  // 초기화: 모든 컬렉션 삭제
  resetBtn.addEventListener("click", async () => {
    if (!confirm("Vector DB를 초기화(모든 컬렉션 삭제)하시겠습니까?")) return;
    setLoading(resetBtn, true);
    note && (note.textContent = "Vector DB 초기화 중…");
    try {
      const res = await fetch("/admin/rag/reset", { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      note && (note.textContent = `✅ 초기화 완료 (deleted=${(data.reset?.deleted_groups || []).length})`);
    } catch (err) {
      note && (note.textContent = `❌ 초기화 실패: ${err.message || err}`);
    } finally {
      setLoading(resetBtn, false);
    }
  });
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

    // 관리자 계정은 프론트에서도 가려줌
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
  initLLMCard();
  initLLMDBCard(); // 새로 추가
  initSystemCard();
  initUserCard();
  initRagCard();
});