// static/js/common/subheader.js
document.addEventListener('DOMContentLoaded', () => {
  const logoText = document.getElementById('logo-text');
  const sub = document.getElementById('subheader');
  const header = document.getElementById('site-header');
  if (!logoText || !sub || !header) return;
  
  //로고 바로 아래로 정렬(윈도/스크롤/리사이즈 대응)
  function positionUnderLogo() {
    const logo = document.getElementById('logo-area');
    if (!logo) return;
    const r = logo.getBoundingClientRect();
    sub.style.left = `${Math.round(r.left)}px`;  // 뷰포트 기준 좌표
  }
  positionUnderLogo();
  window.addEventListener('resize', positionUnderLogo);
  window.addEventListener('scroll', () => {
    if (sub.classList.contains('is-open')) positionUnderLogo();
  }, { passive:true });

  // (열기/닫기 로직)
  let openTimer = null, closeTimer = null;
  const open = () => {
    clearTimeout(closeTimer);
    sub.hidden = false;
    sub.classList.add('is-open');
    header.querySelector('#logo-link')?.setAttribute('aria-expanded', 'true');
  };
  const close = () => {
    clearTimeout(openTimer);
    sub.classList.remove('is-open');
    header.querySelector('#logo-link')?.setAttribute('aria-expanded', 'false');
    // transition 후 hidden
    setTimeout(() => { if (!sub.classList.contains('is-open')) sub.hidden = true; }, 180);
  };

  // 로고 텍스트 hover/포커스
  logoText.addEventListener('mouseenter', () => { openTimer = setTimeout(open, 80); });
  logoText.addEventListener('focus', () => { openTimer = setTimeout(open, 0); });
  logoText.addEventListener('mouseleave', () => { closeTimer = setTimeout(close, 120); });
  logoText.addEventListener('blur', () => { closeTimer = setTimeout(close, 120); });

  // 서브헤더 영역 위에 있으면 닫지 않음
  sub.addEventListener('mouseenter', () => { clearTimeout(closeTimer); });
  sub.addEventListener('mouseleave', () => { closeTimer = setTimeout(close, 80); });

  // 스크롤/리사이즈 시 안전하게 닫기
  window.addEventListener('scroll', () => { if (sub.classList.contains('is-open')) close(); }, { passive:true });
  window.addEventListener('resize', () => { if (sub.classList.contains('is-open')) close(); });

  // 헤더가 숨겨지면 서브헤더도 닫힘(헤더 JS와 연동)
  const obs = new MutationObserver(() => {
    if (header.classList.contains('hidden')) close();
  });
  obs.observe(header, { attributes:true, attributeFilter:['class'] });
});
