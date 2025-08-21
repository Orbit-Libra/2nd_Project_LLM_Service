// static/js/question.js
document.addEventListener('DOMContentLoaded', () => {
  // 페이드 인
  const io = new IntersectionObserver((es) => {
    es.forEach(e => { if (e.isIntersecting) e.target.classList.add('appear'); });
  }, { threshold: 0.15 });
  document.querySelectorAll('.fade-in').forEach(el => io.observe(el));

  // 스크롤 탑
  document.getElementById('scrollTopBtn')?.addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  // 폼 검증 + 제출
  const form = document.getElementById('qnaForm');
  if (!form) return;

  const isEmail = (v) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v || "");
  const showError = (input, msg) => {
    const field = input.closest('.field');
    let small = field.querySelector('small.error');
    if (!small) {
      small = document.createElement('small');
      small.className = 'error';
      field.appendChild(small);
    }
    small.textContent = msg;
    input.setAttribute('aria-invalid', 'true');
  };
  const clearError = (input) => {
    const field = input.closest('.field');
    const small = field.querySelector('small.error');
    if (small) small.textContent = '';
    input.removeAttribute('aria-invalid');
  };

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const title   = form.title;
    const email   = form.email;
    const content = form.content;
    const agree   = form.agree;

    let ok = true;
    // 클라이언트 검증
    if (!title.value.trim()) { showError(title, '제목은 필수입니다.'); ok = false; } else clearError(title);
    if (!isEmail(email.value.trim())) { showError(email, '유효한 이메일을 입력하세요.'); ok = false; } else clearError(email);
    if ((content.value.trim().length) < 10) { showError(content, '문의 내용은 10자 이상 입력하세요.'); ok = false; } else clearError(content);
    if (!agree.checked) { showError(agree, '개인정보 수집 및 이용에 동의해주세요.'); ok = false; } else clearError(agree);

    if (!ok) return;

    // AJAX 제출(부드러운 UX)
    const fd = new FormData(form);
    try {
      const r = await fetch(form.action, {
        method: 'POST',
        body: fd,
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      });
      const data = await r.json();
      if (!r.ok || !data.ok) throw data;
      window.location.href = data.redirect;
    } catch (err) {
      // 서버가 보낸 필드 에러 반영
      if (err && err.errors) {
        if (err.errors.title) showError(title, err.errors.title);
        if (err.errors.email) showError(email, err.errors.email);
        if (err.errors.content) showError(content, err.errors.content);
        if (err.errors.agree) showError(agree, err.errors.agree);
      } else {
        alert('제출 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
      }
    }
  });
});
