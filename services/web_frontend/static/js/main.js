// js/main.js - 최종본
// 전역 상태
let currentSectionIndex = 0;
let isScrolling = false;
const scrollCooldown = 800; // 스크롤 쿨다운 시간 (ms)

window.addEventListener('DOMContentLoaded', () => {
  // 헤더 스크롤 로직 초기화 (호환용)
  initHeaderScrollLogic();

  initializeSlider();
  initializeScrollLogic();
  initializeFloatingButton();
  initializeSubCards();   // ✅ 카드 클릭 분기 (2번/3번 카드 동작 포함)
  initializeChatbot();    // 챗봇 초기화
});

// 헤더 스크롤 숨김 로직 (호환용)
function initHeaderScrollLogic() {
  const wrapper = document.querySelector('.sections-wrapper');
  const header = document.getElementById('site-header');
  const heroSlider = document.getElementById('hero-slider');
  if (wrapper && header && heroSlider) {
    // 기존 로직이 있다면 유지, 변경 없음
  }
}

// 슬라이드 자동 전환 주기 (ms)
const SLIDE_INTERVAL = 5000;

function initializeSlider() {
  const slides = Array.from(document.querySelectorAll('#hero-slider .slide'));
  const prevBtn = document.getElementById('prevBtn');
  const nextBtn = document.getElementById('nextBtn');

  if (!slides.length) return;

  let idx = 0;
  let timerId = null;

  function showSlide(i) {
    slides.forEach(s => s.classList.remove('active'));
    slides[i]?.classList.add('active');
  }

  function scheduleNext() {
    clearTimeout(timerId);
    timerId = setTimeout(() => {
      idx = (idx + 1) % slides.length;
      showSlide(idx);
      scheduleNext(); // 다음 타이머 예약
    }, SLIDE_INTERVAL);
  }

  // 초기 표시 + 타이머 시작
  showSlide(idx);
  if (slides.length > 1) scheduleNext();

  // 버튼 클릭 시 즉시 전환하고 자동 타이머 '리셋'
  prevBtn?.addEventListener('click', () => {
    idx = (idx - 1 + slides.length) % slides.length;
    showSlide(idx);
    if (slides.length > 1) scheduleNext(); // 타이머 초기화
  });

  nextBtn?.addEventListener('click', () => {
    idx = (idx + 1) % slides.length;
    showSlide(idx);
    if (slides.length > 1) scheduleNext(); // 타이머 초기화
  });
}


function initializeScrollLogic() {
  const wrapper = document.getElementById('sections-wrapper');
  if (!wrapper) return;

  let lastScrollTime = 0;
  let scrollTimeout;

  wrapper.addEventListener('scroll', () => {
    const now = Date.now();
    if (now - lastScrollTime < 100) return; // 쓰로틀링
    lastScrollTime = now;

    if (scrollTimeout) clearTimeout(scrollTimeout);

    scrollTimeout = setTimeout(() => {
      const scrollTop = wrapper.scrollTop;
      const windowHeight = window.innerHeight;
      const newSectionIndex = Math.round(scrollTop / windowHeight);

      if (newSectionIndex !== currentSectionIndex) {
        currentSectionIndex = newSectionIndex;
        updateUIBasedOnSection(currentSectionIndex);
      }
    }, 150);
  });

  wrapper.addEventListener('wheel', (e) => {
    if (isScrolling) return;
    e.preventDefault();
    isScrolling = true;

    const direction = e.deltaY > 0 ? 1 : -1;
    const newIndex = Math.max(0, Math.min(2, currentSectionIndex + direction));

    if (newIndex !== currentSectionIndex) {
      currentSectionIndex = newIndex;
      const targetScroll = newIndex * window.innerHeight;

      wrapper.scrollTo({ top: targetScroll, behavior: 'smooth' });
      updateUIBasedOnSection(currentSectionIndex);
    }

    setTimeout(() => { isScrolling = false; }, scrollCooldown);
  });
}

function updateUIBasedOnSection(sectionIndex) {
  const header = document.getElementById('site-header');
  const floatingBtn = document.getElementById('floating-header-btn');
  if (!header || !floatingBtn) return;

  header.classList.remove('floating-hover');

  requestAnimationFrame(() => {
    switch (sectionIndex) {
      case 0: // Hero Slider
        header.classList.remove('hidden');
        floatingBtn.style.display = 'none';
        break;
      case 1: // Three Columns
        header.classList.add('hidden');
        setTimeout(() => {
          if (currentSectionIndex === 1) floatingBtn.style.display = 'flex';
        }, 300);
        break;
      case 2: // Footer
        header.classList.remove('hidden');
        floatingBtn.style.display = 'none';
        break;
    }
  });
}

function initializeFloatingButton() {
  const floatingBtn = document.getElementById('floating-header-btn');
  const header = document.getElementById('site-header');
  if (!floatingBtn || !header) return;

  let isHeaderVisible = false;

  floatingBtn.addEventListener('mouseenter', () => {
    if (currentSectionIndex === 1) {
      isHeaderVisible = true;
      floatingBtn.style.display = 'none';
      header.classList.add('floating-hover');
      header.classList.remove('hidden');
    }
  });

  header.addEventListener('mouseleave', () => {
    if (currentSectionIndex === 1 && isHeaderVisible) {
      isHeaderVisible = false;
      header.classList.remove('floating-hover');
      header.classList.add('hidden');
      floatingBtn.style.display = 'flex';
    }
  });

  header.addEventListener('mouseenter', () => {
    if (currentSectionIndex === 1) isHeaderVisible = true;
  });
}

// ✅ 카드 클릭 동작: 여기서 한 번에 처리 (2번/3번 카드 요구사항 반영)
function initializeSubCards() {
  const sub1 = document.querySelector('.sub1');
  const sub2 = document.querySelector('.sub2');
  const sub3 = document.querySelector('.sub3');

  // 1번 카드: 학습환경 분석 (차트)
  sub1?.addEventListener('click', () => {
    const url = window.chartUrl || sub1.dataset.link;
    if (url) window.location.href = url;
  });

  // 2번 카드: 발전도 분석 -> chartpage2.html 라우트
  sub2?.addEventListener('click', () => {
    const url = window.predictionUrl || sub2.dataset.link;
    if (url) window.location.href = url;
  });

  // 3번 카드: 마이 서비스 -> 로그인 여부 분기
  sub3?.addEventListener('click', (e) => {
    e.preventDefault();
    const isLoggedIn = window.isLoggedIn === true;
    if (isLoggedIn) {
      window.location.href = window.myServiceUrl;
    } else {
      window.location.href = window.loginUrl;
    }
  });
}

// 키보드 네비게이션
document.addEventListener('keydown', (e) => {
  if (isScrolling) return;

  const wrapper = document.getElementById('sections-wrapper');
  if (!wrapper) return;

  let newIndex = currentSectionIndex;

  switch (e.key) {
    case 'ArrowDown':
    case 'PageDown':
      e.preventDefault();
      newIndex = Math.min(2, currentSectionIndex + 1);
      break;
    case 'ArrowUp':
    case 'PageUp':
      e.preventDefault();
      newIndex = Math.max(0, currentSectionIndex - 1);
      break;
    case 'Home':
      e.preventDefault();
      newIndex = 0;
      break;
    case 'End':
      e.preventDefault();
      newIndex = 2;
      break;
  }

  if (newIndex !== currentSectionIndex) {
    isScrolling = true;
    currentSectionIndex = newIndex;

    const targetScroll = newIndex * window.innerHeight;
    wrapper.scrollTo({ top: targetScroll, behavior: 'smooth' });
    updateUIBasedOnSection(currentSectionIndex);

    setTimeout(() => { isScrolling = false; }, scrollCooldown);
  }
});

// 터치 스와이프 (모바일)
let touchStartY = 0;
let touchEndY = 0;

document.addEventListener('touchstart', e => {
  touchStartY = e.changedTouches[0].screenY;
});

document.addEventListener('touchend', e => {
  if (isScrolling) return;

  touchEndY = e.changedTouches[0].screenY;
  const diff = touchStartY - touchEndY;

  if (Math.abs(diff) > 50) {
    const wrapper = document.getElementById('sections-wrapper');
    if (!wrapper) return;

    let newIndex = currentSectionIndex;

    if (diff > 0) newIndex = Math.min(2, currentSectionIndex + 1);
    else newIndex = Math.max(0, currentSectionIndex - 1);

    if (newIndex !== currentSectionIndex) {
      isScrolling = true;
      currentSectionIndex = newIndex;

      const targetScroll = newIndex * window.innerHeight;
      wrapper.scrollTo({ top: targetScroll, behavior: 'smooth' });
      updateUIBasedOnSection(currentSectionIndex);

      setTimeout(() => { isScrolling = false; }, scrollCooldown);
    }
  }
});

// 리사이즈 처리
window.addEventListener('resize', () => {
  const wrapper = document.getElementById('sections-wrapper');
  if (!wrapper || isScrolling) return;

  const targetScroll = currentSectionIndex * window.innerHeight;
  wrapper.scrollTo({ top: targetScroll, behavior: 'auto' });
});

// 챗봇 초기화
function initializeChatbot() {
  const chatToggle = document.getElementById('chatToggle');
  const chatWindow = document.getElementById('chatWindow');
  const chatCloseBtn = document.getElementById('chatCloseBtn');
  const chatBody = document.getElementById('chatBody');
  const chatInput = document.getElementById('chatInput');
  const chatSendBtn = document.getElementById('chatSendBtn');

  chatToggle?.addEventListener('click', () => {
    if (!chatWindow) return;
    chatWindow.classList.toggle('open');
    if (chatWindow.classList.contains('open') && chatInput) chatInput.focus();
  });

  chatCloseBtn?.addEventListener('click', () => {
    if (chatWindow) chatWindow.classList.remove('open');
  });

  function sendMessage() {
    if (!chatInput || !chatBody) return;

    const txt = chatInput.value.trim();
    if (!txt) return;

    const userMsg = document.createElement('div');
    userMsg.style.cssText = `
      margin: 10px 0; padding: 10px 15px;
      background: #007bff; color: #fff;
      border-radius: 20px 20px 5px 20px;
      max-width: 80%; margin-left: auto;
      word-wrap: break-word;
    `;
    userMsg.textContent = txt;
    chatBody.appendChild(userMsg);

    const botMsg = document.createElement('div');
    botMsg.style.cssText = `
      margin: 10px 0; padding: 10px 15px;
      background: #f1f1f1; color: #333;
      border-radius: 20px 20px 20px 5px;
      max-width: 80%; margin-right: auto;
      word-wrap: break-word;
    `;
    botMsg.textContent = '안녕하세요! Libra 서비스에 대해 궁금한 것이 있으시면 언제든 문의해 주세요. 현재는 데모 모드입니다.';

    setTimeout(() => {
      chatBody.appendChild(botMsg);
      chatBody.scrollTop = chatBody.scrollHeight;
    }, 500);

    chatBody.scrollTop = chatBody.scrollHeight;
    chatInput.value = '';
    chatInput.focus();
  }

  chatSendBtn?.addEventListener('click', sendMessage);
  chatInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      sendMessage();
    }
  });
}
