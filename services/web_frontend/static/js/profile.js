// static/js/profile.js
document.addEventListener('DOMContentLoaded', () => {
  /* =========================
   * 공통 유틸
   * ========================= */
  function setBusy(btn, busy, textWhenBusy = '저장 중…', textNormal = '저장') {
    if (!btn) return;
    btn.disabled = !!busy;
    btn.textContent = busy ? textWhenBusy : textNormal;
  }

  async function jsonFetch(url, options = {}) {
    const res = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      ...options,
    });
    const data = await res.json().catch(() => ({}));
    return { res, data };
  }

  // (선택) CSRF 토큰 사용 시 주석 해제해서 headers에 포함
  // const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
  // const csrfHeader = csrfToken ? { 'X-CSRFToken': csrfToken } : {};

  /* =========================
   * 학년별 입력 폼 저장
   * ========================= */
  (function initAcademicForm() {
    const academicForm = document.getElementById('academic-form');
    if (!academicForm) return;

    const valOrNull = (id) => {
      const el = document.getElementById(id);
      if (!el) return null;
      const v = el.value.trim();
      return v === '' ? null : Number(v);
    };

    academicForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!confirm('입력한 내용을 저장하겠습니까?')) return;

      const payload = {
        '1ST_YR':      valOrNull('first_yr'),
        '1ST_USR_CPS': valOrNull('first_cps'),
        '1ST_USR_LPS': valOrNull('first_lps'),
        '1ST_USR_VPS': valOrNull('first_vps'),
        '2ND_YR':      valOrNull('second_yr'),
        '2ND_USR_CPS': valOrNull('second_cps'),
        '2ND_USR_LPS': valOrNull('second_lps'),
        '2ND_USR_VPS': valOrNull('second_vps'),
        '3RD_YR':      valOrNull('third_yr'),
        '3RD_USR_CPS': valOrNull('third_cps'),
        '3RD_USR_LPS': valOrNull('third_lps'),
        '3RD_USR_VPS': valOrNull('third_vps'),
        '4TH_YR':      valOrNull('fourth_yr'),
        '4TH_USR_CPS': valOrNull('fourth_cps'),
        '4TH_USR_LPS': valOrNull('fourth_lps'),
        '4TH_USR_VPS': valOrNull('fourth_vps'),
      };

      try {
        const { res, data } = await jsonFetch('/api/user/academic', {
          method: 'POST',
          body: JSON.stringify(payload),
          // headers: csrfHeader,
        });
        if (res.ok && data?.success) {
          alert('저장이 완료되었습니다.');
          location.reload();
        } else {
          alert(data?.error || `저장 중 오류가 발생했습니다. (HTTP ${res.status})`);
        }
      } catch {
        alert('네트워크 오류가 발생했습니다.');
      }
    });
  })();

  /* =========================
   * 회원정보 수정 모달
   * ========================= */
  (function initProfileEditModal() {
    const openBtn   = document.getElementById('open-edit-profile');
    const dlg       = document.getElementById('edit-profile-dialog');
    const editForm  = document.getElementById('edit-profile-form');
    const cancelBtn = document.getElementById('cancel-edit');
    const saveBtn   = document.getElementById('save-edit');

    const nameInput  = document.getElementById('edit_name');
    const emailInput = document.getElementById('edit_email');
    const snmInput   = document.getElementById('edit_snm');
    const snmList    = document.getElementById('snm-list-edit');
    const snmMsg     = document.getElementById('snm_edit_msg');

    const curPw      = document.getElementById('cur_pw');
    const newPw      = document.getElementById('new_pw');
    const newPw2     = document.getElementById('new_pw2');
    const newPwMsg   = document.getElementById('new_pw_msg');

    if (!openBtn || !dlg || !editForm) return;

    let snmCache = [];

    async function loadSNM() {
      try {
        const { res, data } = await jsonFetch('/api/snm');
        if (res.ok && data?.success) {
          snmCache = data.items || [];
          snmList.innerHTML = '';
          snmCache.forEach((name) => {
            const opt = document.createElement('option');
            opt.value = name;
            snmList.appendChild(opt);
          });
        } else {
          snmMsg.textContent = '소속대학 목록을 불러오지 못했습니다.';
          snmMsg.style.color = 'red';
        }
      } catch {
        snmMsg.textContent = '소속대학 목록 로딩 오류';
        snmMsg.style.color = 'red';
      }
    }

    function validateSNM() {
      const val = snmInput.value.trim();
      if (!val) { snmMsg.textContent = ''; return false; }
      const ok = snmCache.includes(val);
      snmMsg.textContent = ok ? '' : '소속대학명이 목록과 일치하지 않습니다.';
      snmMsg.style.color = ok ? '' : 'red';
      return ok;
    }

    function validateNewPw() {
      const a = newPw.value;
      const b = newPw2.value;
      if (!a && !b) { newPwMsg.textContent = ''; return true; }
      if (a !== b) {
        newPwMsg.textContent = '새 비밀번호가 일치하지 않습니다.';
        newPwMsg.style.color = 'red';
        return false;
      }
      newPwMsg.textContent = '새 비밀번호가 일치합니다.';
      newPwMsg.style.color = 'green';
      return true;
    }

    openBtn.addEventListener('click', async () => {
      await loadSNM();
      dlg.showModal();
    });

    cancelBtn?.addEventListener('click', () => dlg.close());
    snmInput?.addEventListener('input', validateSNM);
    newPw?.addEventListener('input', validateNewPw);
    newPw2?.addEventListener('input', validateNewPw);

    editForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!validateSNM()) return;
      if (!validateNewPw()) return;

      const payload = {
        usr_name: nameInput.value.trim(),
        usr_email: emailInput.value.trim(),
        usr_snm: snmInput.value.trim(),
        current_password: curPw.value,
        new_password: newPw.value || null,
      };

      if (!payload.usr_name || !payload.usr_email || !payload.usr_snm || !payload.current_password) {
        alert('필수 항목을 확인해주세요.');
        return;
      }

      setBusy(saveBtn, true);
      try {
        const { res, data } = await jsonFetch('/api/user/profile', {
          method: 'PUT',
          body: JSON.stringify(payload),
          // headers: csrfHeader,
        });
        if (res.ok && data?.success) {
          alert('회원정보가 수정되었습니다.');
          dlg.close();
          location.reload();
        } else {
          alert(data?.error || `수정 실패 (HTTP ${res.status})`);
        }
      } catch {
        alert('네트워크 오류가 발생했습니다.');
      } finally {
        setBusy(saveBtn, false);
      }
    });
  })();
});
