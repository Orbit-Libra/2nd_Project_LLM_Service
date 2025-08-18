// main.js — 슬라이더/카드 전용

window.addEventListener('DOMContentLoaded', () => {
  // 안전장치: 스크롤 컨테이너 지정
  const sections = document.getElementById('sections-wrapper');
  if (sections && !sections.classList.contains('scroll-area')) {
    sections.classList.add('scroll-area');
  }

  initializeSlider();
  initializeSubCards();
});

/* 슬라이더 */
const SLIDE_INTERVAL = 5000;
function initializeSlider() {
  const slides = Array.from(document.querySelectorAll('#hero-slider .slide'));
  const prevBtn = document.getElementById('prevBtn');
  const nextBtn = document.getElementById('nextBtn');
  if (!slides.length) return;

  let idx = 0, timerId = null;
  const showSlide = (i) => {
    slides.forEach(s => s.classList.remove('active'));
    slides[i]?.classList.add('active');
  };
  const scheduleNext = () => {
    clearTimeout(timerId);
    if (slides.length > 1) {
      timerId = setTimeout(() => {
        idx = (idx + 1) % slides.length;
        showSlide(idx);
        scheduleNext();
      }, SLIDE_INTERVAL);
    }
  };

  showSlide(idx);
  scheduleNext();

  prevBtn?.addEventListener('click', () => {
    idx = (idx - 1 + slides.length) % slides.length;
    showSlide(idx);
    scheduleNext();
  });
  nextBtn?.addEventListener('click', () => {
    idx = (idx + 1) % slides.length;
    showSlide(idx);
    scheduleNext();
  });
}

/* 카드 이동 */
function initializeSubCards() {
  const sub1 = document.querySelector('.sub1');
  const sub2 = document.querySelector('.sub2');
  const sub3 = document.querySelector('.sub3');

  sub1?.addEventListener('click', () => {
    const url = window.chartUrl || sub1.dataset.link;
    if (url) window.location.href = url;
  });

  sub2?.addEventListener('click', () => {
    const url = window.predictionUrl || sub2.dataset.link;
    if (url) window.location.href = url;
  });

  sub3?.addEventListener('click', (e) => {
    e.preventDefault();
    const isLoggedIn = window.isLoggedIn === true || window.isLoggedIn === 'true';
    window.location.href = isLoggedIn ? window.myServiceUrl : window.loginUrl;
  });
}
