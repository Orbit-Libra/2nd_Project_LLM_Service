// js/main.js - 개선된 버전
// 전역 변수
let currentSectionIndex = 0;
let isScrolling = false;
const scrollCooldown = 800; // 스크롤 쿨다운 시간 (ms)

window.addEventListener('DOMContentLoaded', () => {
  // 기존 헤더·푸터 인클루드는 Flask 템플릿에서 처리되므로 제거
  // 헤더 로드 후 스크롤 로직 초기화는 즉시 실행
  initHeaderScrollLogic();
  
  initializeSlider();
  initializeScrollLogic();
  initializeFloatingButton();
  initializeSubCards();
  initializeChatbot(); // 챗봇 초기화 추가
});

// 헤더 스크롤 숨김 로직 함수 (기존 유지하되 플로팅 버튼 연동)
function initHeaderScrollLogic() {
  const wrapper = document.querySelector('.sections-wrapper');
  const header = document.getElementById('site-header');
  const heroSlider = document.getElementById('hero-slider');
  
  if (wrapper && header && heroSlider) {
    // 기본 스크롤 이벤트는 새로운 로직으로 대체됨
    // 이 함수는 호환성을 위해 유지
  }
}

function initializeSlider() {
  const slides = Array.from(document.querySelectorAll('#hero-slider .slide'));
  let idx = 0;
  const total = slides.length;

  function showSlide(i) {
    slides.forEach(s => s.classList.remove('active'));
    if (slides[i]) {
      slides[i].classList.add('active');
    }
  }

  // 초기 슬라이드 설정
  if (slides.length > 0) {
    showSlide(0);
  }

  document.getElementById('prevBtn')?.addEventListener('click', () => {
    idx = (idx - 1 + total) % total;
    showSlide(idx);
  });

  document.getElementById('nextBtn')?.addEventListener('click', () => {
    idx = (idx + 1) % total;
    showSlide(idx);
  });

  // 10초(10000ms)마다 자동 전환
  if (slides.length > 1) {
    setInterval(() => {
      idx = (idx + 1) % total;
      showSlide(idx);
    }, 10000);
  }
}

function initializeScrollLogic() {
  const wrapper = document.getElementById('sections-wrapper');
  const header = document.getElementById('site-header');
  const floatingBtn = document.getElementById('floating-header-btn');
  let lastScrollTime = 0;
  let scrollTimeout;

  // 부드러운 스크롤을 위한 스크롤 이벤트 처리
  wrapper.addEventListener('scroll', (e) => {
    const now = Date.now();
    if (now - lastScrollTime < 100) return; // 쓰로틀링 증가 (50ms -> 100ms)
    lastScrollTime = now;

    // 기존 타임아웃이 있으면 취소
    if (scrollTimeout) {
      clearTimeout(scrollTimeout);
    }

    // 스크롤이 완전히 멈춘 후에 UI 업데이트
    scrollTimeout = setTimeout(() => {
      const scrollTop = wrapper.scrollTop;
      const windowHeight = window.innerHeight;
      
      // 현재 섹션 계산 (더 정확하게)
      const newSectionIndex = Math.round(scrollTop / windowHeight);
      
      if (newSectionIndex !== currentSectionIndex) {
        currentSectionIndex = newSectionIndex;
        updateUIBasedOnSection(currentSectionIndex);
      }
    }, 150); // 150ms 후에 UI 업데이트
  });

  // 휠 이벤트로 부드러운 섹션 간 이동
  wrapper.addEventListener('wheel', (e) => {
    if (isScrolling) return;

    e.preventDefault();
    isScrolling = true;

    const direction = e.deltaY > 0 ? 1 : -1;
    const newIndex = Math.max(0, Math.min(2, currentSectionIndex + direction));

    if (newIndex !== currentSectionIndex) {
      currentSectionIndex = newIndex;
      
      const targetScroll = newIndex * window.innerHeight;
      
      // 부드러운 스크롤 애니메이션
      wrapper.scrollTo({
        top: targetScroll,
        behavior: 'smooth'
      });
      
      // UI 업데이트를 즉시 실행 (휠 이벤트는 의도적이므로)
      updateUIBasedOnSection(currentSectionIndex);
    }

    setTimeout(() => {
      isScrolling = false;
    }, scrollCooldown);
  });
}

function updateUIBasedOnSection(sectionIndex) {
  const header = document.getElementById('site-header');
  const floatingBtn = document.getElementById('floating-header-btn');

  // 모든 상태 초기화
  header.classList.remove('floating-hover');

  // 부드러운 전환을 위한 약간의 지연
  requestAnimationFrame(() => {
    switch(sectionIndex) {
      case 0: // Hero Slider
        header.classList.remove('hidden');
        floatingBtn.style.display = 'none';
        break;
      case 1: // Three Columns
        header.classList.add('hidden');
        // 약간의 지연 후 플로팅 버튼 표시 (헤더가 완전히 사라진 후)
        setTimeout(() => {
          if (currentSectionIndex === 1) { // 여전히 같은 섹션에 있을 때만
            floatingBtn.style.display = 'flex';
          }
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
  let isHeaderVisible = false;

  // 플로팅 버튼에 마우스 올릴 때
  floatingBtn.addEventListener('mouseenter', () => {
    if (currentSectionIndex === 1) { // Three Columns 섹션에서만
      isHeaderVisible = true;
      floatingBtn.style.display = 'none'; // 버튼 숨기기
      header.classList.add('floating-hover');
      header.classList.remove('hidden');
    }
  });

  // 헤더에서 마우스가 벗어날 때
  header.addEventListener('mouseleave', () => {
    if (currentSectionIndex === 1 && isHeaderVisible) { // Three Columns 섹션에서만
      isHeaderVisible = false;
      header.classList.remove('floating-hover');
      header.classList.add('hidden');
      floatingBtn.style.display = 'flex'; // 버튼 다시 보이기
    }
  });

  // 헤더에 마우스가 올라가 있을 때는 계속 보이게
  header.addEventListener('mouseenter', () => {
    if (currentSectionIndex === 1) {
      isHeaderVisible = true;
    }
  });
}

function initializeSubCards() {
  // 3컬럼 클릭 페이지1,2,3으로 이동이벤트
  document.querySelectorAll('.sub').forEach(el => {
    // 3번카드 >> 임시 오버레이 스타일 추가 >> 추후 로그인가능자 페이지연동
    if (el.classList.contains('sub3')) {
      // 3번 카드만 별도 처리
      el.addEventListener('click', e => {
        e.preventDefault();
        const today = new Date().toISOString().slice(0, 10); // YYYY-MM-DD
        const visited = localStorage.getItem('sub3AccessDate');

        if (visited === today) {
          // 이미 오늘 본 적 있으면 바로 이동
          const url = el.dataset.link;
          if (url) window.location.href = url;
        } else {
          // 처음 보는 날이면 오버레이 보여주고 10초 후 진입
          const overlay = document.getElementById('temp-overlay');
          if (overlay) {
            overlay.classList.add('show');

            // 오늘 날짜 저장
            localStorage.setItem('sub3AccessDate', today);

            // 10초 후 페이지 이동
            setTimeout(() => {
              overlay.classList.remove('show');
              const url = el.dataset.link;
              if (url) window.location.href = url;
            }, 10000);
          }
        }
      });
    } else {
      // sub1, sub2: 원래 이동
      el.addEventListener('click', () => {
        const url = el.dataset.link;
        if (url) window.location.href = url;
      });
    }
  });
}

// 키보드 네비게이션 지원
document.addEventListener('keydown', (e) => {
  if (isScrolling) return;

  const wrapper = document.getElementById('sections-wrapper');
  let newIndex = currentSectionIndex;

  switch(e.key) {
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
    wrapper.scrollTo({
      top: targetScroll,
      behavior: 'smooth'
    });
    
    updateUIBasedOnSection(currentSectionIndex);
    
    setTimeout(() => {
      isScrolling = false;
    }, scrollCooldown);
  }
});

// 터치 스와이프 지원 (모바일)
let touchStartY = 0;
let touchEndY = 0;

document.addEventListener('touchstart', e => {
  touchStartY = e.changedTouches[0].screenY;
});

document.addEventListener('touchend', e => {
  if (isScrolling) return;

  touchEndY = e.changedTouches[0].screenY;
  const diff = touchStartY - touchEndY;
  
  if (Math.abs(diff) > 50) { // 최소 스와이프 거리
    const wrapper = document.getElementById('sections-wrapper');
    let newIndex = currentSectionIndex;

    if (diff > 0) { // 위로 스와이프 (다음 섹션)
      newIndex = Math.min(2, currentSectionIndex + 1);
    } else { // 아래로 스와이프 (이전 섹션)
      newIndex = Math.max(0, currentSectionIndex - 1);
    }

    if (newIndex !== currentSectionIndex) {
      isScrolling = true;
      currentSectionIndex = newIndex;
      
      const targetScroll = newIndex * window.innerHeight;
      wrapper.scrollTo({
        top: targetScroll,
        behavior: 'smooth'
      });
      
      updateUIBasedOnSection(currentSectionIndex);
      
      setTimeout(() => {
        isScrolling = false;
      }, scrollCooldown);
    }
  }
});

// 리사이즈 처리
window.addEventListener('resize', () => {
  if (!isScrolling) {
    const wrapper = document.getElementById('sections-wrapper');
    const targetScroll = currentSectionIndex * window.innerHeight;
    wrapper.scrollTo({
      top: targetScroll,
      behavior: 'auto'
    });
  }
});

// 챗봇 초기화 함수
function initializeChatbot() {
  const chatToggle = document.getElementById('chatToggle');
  const chatWindow = document.getElementById('chatWindow');
  const chatCloseBtn = document.getElementById('chatCloseBtn');
  const chatBody = document.getElementById('chatBody');
  const chatInput = document.getElementById('chatInput');
  const chatSendBtn = document.getElementById('chatSendBtn');

  chatToggle?.addEventListener('click', () => {
    if (chatWindow) {
      chatWindow.classList.toggle('open');
      if (chatWindow.classList.contains('open') && chatInput) {
        chatInput.focus();
      }
    }
  });

  chatCloseBtn?.addEventListener('click', () => {
    if (chatWindow) {
      chatWindow.classList.remove('open');
    }
  });

  function sendMessage() {
    if (!chatInput || !chatBody) return;
    
    const txt = chatInput.value.trim();
    if (!txt) return;
    
    // 사용자 메시지
    let userMsg = document.createElement('div');
    userMsg.style.cssText = `
      margin: 10px 0;
      padding: 10px 15px;
      background: #007bff;
      color: white;
      border-radius: 20px 20px 5px 20px;
      max-width: 80%;
      margin-left: auto;
      word-wrap: break-word;
    `;
    userMsg.textContent = txt;
    chatBody.appendChild(userMsg);
    
    // 봇 응답
    let botMsg = document.createElement('div');
    botMsg.style.cssText = `
      margin: 10px 0;
      padding: 10px 15px;
      background: #f1f1f1;
      color: #333;
      border-radius: 20px 20px 20px 5px;
      max-width: 80%;
      margin-right: auto;
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
  chatInput?.addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      e.preventDefault();
      sendMessage();
    }
  });
}