// js/main.js 
window.addEventListener('DOMContentLoaded', () => {
  // 1) 헤더·푸터 인클루드
  fetch('./header.html')
    .then(r => r.text())
    .then(html => {
      document.getElementById('header-area').innerHTML = html;
      
      // 어디서든지 로고 누르면 index인 첫페이지로 이동
      document.getElementById('logo-area')?.addEventListener('click', () => {
        location.href = './index.html';
      });
      
      // 헤더 로드 후 스크롤 로직 초기화 (수정된 부분)
      initHeaderScrollLogic();
    })
    .catch(console.error);

  fetch('./footer.html')
    .then(r => r.text())
    .then(html => {
      document.getElementById('footer-area').innerHTML = html;
    })
    .catch(console.error);

  // 헤더 스크롤 숨김 로직 함수 (수정된 부분)
  function initHeaderScrollLogic() {
    const wrapper = document.querySelector('.sections-wrapper');
    const header = document.getElementById('site-header');
    const heroSlider = document.getElementById('hero-slider'); // 올바른 ID 사용
    
    if (wrapper && header && heroSlider) {
      wrapper.addEventListener('scroll', () => {
        // wrapper.scrollTop이 hero 높이의 50%보다 크면 숨기기
        if (wrapper.scrollTop > heroSlider.offsetHeight * 0.5) {
          header.classList.add('hidden');
        } else {
          header.classList.remove('hidden');
        }
      });
    }
  }

  // 2) Overlap Fade Slider (10s)
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

  // 3) 3컬럼 클릭 페이지1,2,3으로 이동이벤트
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

  // // 4) Chatbot Toggle
  // const chatToggle = document.getElementById('chatToggle');
  // const chatWindow = document.getElementById('chatWindow');
  // const chatCloseBtn = document.getElementById('chatCloseBtn');
  // const chatBody = document.getElementById('chatBody');
  // const chatInput = document.getElementById('chatInput');
  // const chatSendBtn = document.getElementById('chatSendBtn');

  // chatToggle?.addEventListener('click', () => {
  //   if (chatWindow) {
  //     chatWindow.classList.toggle('open');
  //     if (chatWindow.classList.contains('open') && chatInput) {
  //       chatInput.focus();
  //     }
  //   }
  // });

  // chatCloseBtn?.addEventListener('click', () => {
  //   if (chatWindow) {
  //     chatWindow.classList.remove('open');
  //   }
  // });

  // function sendMessage() {
  //   if (!chatInput || !chatBody) return;
    
  //   const txt = chatInput.value.trim();
  //   if (!txt) return;
    
  //   // 사용자 메시지
  //   let userMsg = document.createElement('div');
  //   userMsg.className = 'chat-msg user';
  //   userMsg.textContent = txt;
  //   chatBody.appendChild(userMsg);
    
  //   // 봇 응답
  //   let botMsg = document.createElement('div');
  //   botMsg.className = 'chat-msg bot';
  //   botMsg.textContent = '응답 준비중…';
  //   chatBody.appendChild(botMsg);
    
  //   chatBody.scrollTop = chatBody.scrollHeight;
  //   chatInput.value = '';
  //   chatInput.focus();
  // }

  // chatSendBtn?.addEventListener('click', sendMessage);
  // chatInput?.addEventListener('keydown', e => {
  //   if (e.key === 'Enter') {
  //     e.preventDefault();
  //     sendMessage();
  //   }
  // });
});