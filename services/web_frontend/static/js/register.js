// /static/js/register.js
(async function () {
  const idInput = document.getElementById('usr_id');
  const checkBtn = document.getElementById('check_id_btn');
  const idMsg = document.getElementById('usr_id_msg');

  const pw = document.getElementById('usr_pw');
  const pw2 = document.getElementById('usr_pw2');
  const pwMsg = document.getElementById('pw_msg');

  const snmInput = document.getElementById('usr_snm');
  const snmList = document.getElementById('snm-list');
  const snmMsg = document.getElementById('snm_msg');

  const form = document.getElementById('register-form');

  let snmCache = [];
  let idChecked = false;
  let lastCheckedId = '';

  // 1) 소속대학 목록 로딩
  async function loadSNM() {
    try {
      const res = await fetch('/api/snm');
      const data = await res.json();
      if (data.success) {
        snmCache = data.items || [];
        snmList.innerHTML = '';
        snmCache.forEach(name => {
          const opt = document.createElement('option');
          opt.value = name;
          snmList.appendChild(opt);
        });
      } else {
        snmMsg.textContent = '소속대학 목록을 불러오지 못했습니다.';
      }
    } catch (e) {
      snmMsg.textContent = '소속대학 목록 로딩 오류';
    }
  }

  // 2) 아이디 중복확인
  async function checkIdDuplicate() {
    const val = idInput.value.trim();
    if (!val) {
      idMsg.textContent = '아이디를 입력하세요.';
      idMsg.style.color = 'red';
      idChecked = false;
      return;
    }
    try {
      const res = await fetch(`/api/check_id?usr_id=${encodeURIComponent(val)}`);
      const data = await res.json();
      if (data.exists) {
        idMsg.textContent = '이미 사용 중인 아이디입니다.';
        idMsg.style.color = 'red';
        idChecked = false;
      } else {
        idMsg.textContent = '사용 가능한 아이디입니다.';
        idMsg.style.color = 'green';
        idChecked = true;
        lastCheckedId = val;
      }
    } catch (e) {
      idMsg.textContent = '중복 확인 중 오류가 발생했습니다.';
      idMsg.style.color = 'red';
      idChecked = false;
    }
  }

  // 3) 비밀번호 확인 실시간 체크
  function validatePw() {
    if (!pw.value || !pw2.value) {
      pwMsg.textContent = '';
      return;
    }
    if (pw.value !== pw2.value) {
      pwMsg.textContent = '비밀번호가 일치하지 않습니다.';
      pwMsg.style.color = 'red';
    } else {
      pwMsg.textContent = '비밀번호가 일치합니다.';
      pwMsg.style.color = 'green';
    }
  }

  // 4) 소속대학 검증 (입력값이 목록에 존재하는지)
  function validateSNM() {
    const val = snmInput.value.trim();
    if (!val) {
      snmMsg.textContent = '';
      return true;
    }
    const ok = snmCache.includes(val);
    if (!ok) {
      snmMsg.textContent = '소속대학명이 목록과 일치하지 않습니다.';
      snmMsg.style.color = 'red';
      return false;
    } else {
      snmMsg.textContent = '';
      return true;
    }
  }

  // 이벤트 바인딩
  checkBtn.addEventListener('click', checkIdDuplicate);
  idInput.addEventListener('input', () => {
    idChecked = false;
    idMsg.textContent = '';
  });
  pw.addEventListener('input', validatePw);
  pw2.addEventListener('input', validatePw);
  snmInput.addEventListener('input', validateSNM);

  // 제출
  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    // 기본 검증
    if (!idChecked || lastCheckedId !== idInput.value.trim()) {
      idMsg.textContent = '아이디 중복 확인을 해주세요.';
      idMsg.style.color = 'red';
      return;
    }
    if (pw.value !== pw2.value) {
      pwMsg.textContent = '비밀번호가 일치하지 않습니다.';
      pwMsg.style.color = 'red';
      return;
    }
    if (!validateSNM()) {
      return;
    }

    // 서버 전송
    const payload = {
      usr_id: idInput.value.trim(),
      usr_pw: pw.value,
      usr_name: document.getElementById('usr_name').value.trim(),
      usr_email: document.getElementById('usr_email').value.trim(),
      usr_snm: snmInput.value.trim()
    };

    try {
      const res = await fetch('/api/register', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) {
        alert('가입이 완료되었습니다.');
        window.location.href = '/login';
      } else {
        alert(data.error || '가입 중 오류가 발생했습니다.');
      }
    } catch (e) {
      alert('네트워크 오류가 발생했습니다.');
    }
  });

  // 초기화
  await loadSNM();
})();
