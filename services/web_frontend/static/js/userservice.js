// userservice.js

(function(){
  // 1) 이름/소속대학 렌더링
  function renderUserBasics(name, univ){
    const $name = document.getElementById('userName');
    const $univ = document.getElementById('userUniv');
    if ($name) $name.textContent = name || '-';
    if ($univ) $univ.textContent = univ || '-';
  }

  // 2) 템플릿 주입값 우선, 없으면 API 시도(선택)
  async function initUserBasics(){
    const injected = (window.__USER__ || {});
    if (injected.name || injected.univ) {
      renderUserBasics(injected.name, injected.univ);
      return;
    }

    // 선택: 백엔드에 /api/user/basic 만들어서 {name, univ} 반환하도록 하면 여기서 사용
    try {
      const res = await fetch('/api/user/basic');
      if (res.ok) {
        const data = await res.json();
        renderUserBasics(data.name || '', data.univ || '');
      } else {
        renderUserBasics('', '');
      }
    } catch {
      renderUserBasics('', '');
    }
  }

  // 3) 버튼 액션
  function initActions(){
    const btn = document.getElementById('btnGoProfile');
    if (btn) {
      btn.addEventListener('click', () => {
        // 프로필(내정보) 페이지로 이동 (앞서 만든 /profile 라우트)
        window.location.href = '/profile';
      });
    }
  }

  // init
  window.addEventListener('DOMContentLoaded', () => {
    initUserBasics();
    initActions();
  });
})();
