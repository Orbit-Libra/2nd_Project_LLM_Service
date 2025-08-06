window.addEventListener('DOMContentLoaded', () => {
  // 1) 헤더 로고 클릭 → 루트 페이지로 이동
  document.getElementById('logo-area')?.addEventListener('click', () => {
    location.href = '/';
  });

  // 2) 헤더 스크롤 숨김 로직
  const wrapper = document.querySelector('.sections-wrapper');
  const header = document.getElementById('site-header');
  const heroSlider = document.getElementById('hero-slider');

  if (wrapper && header && heroSlider) {
    wrapper.addEventListener('scroll', () => {
      if (wrapper.scrollTop > heroSlider.offsetHeight * 0.5) {
        header.classList.add('hidden');
      } else {
        header.classList.remove('hidden');
      }
    });
  }

  // 3) Overlap Fade Slider (10s)
  const slides = Array.from(document.querySelectorAll('#hero-slider .slide'));
  let idx = 0;
  const total = slides.length;

  function showSlide(i) {
    slides.forEach(s => s.classList.remove('active'));
    if (slides[i]) {
      slides[i].classList.add('active');
    }
  }

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

  if (slides.length > 1) {
    setInterval(() => {
      idx = (idx + 1) % total;
      showSlide(idx);
    }, 10000);
  }

  // 4) 3컬럼 클릭 이벤트
  document.querySelectorAll('.sub').forEach(el => {
    if (el.classList.contains('sub3')) {
      el.addEventListener('click', e => {
        e.preventDefault();
        const today = new Date().toISOString().slice(0, 10);
        const visited = localStorage.getItem('sub3AccessDate');

        if (visited === today) {
          const url = el.dataset.link;
          if (url) window.location.href = url;
        } else {
          const overlay = document.getElementById('temp-overlay');
          if (overlay) {
            overlay.classList.add('show');
            localStorage.setItem('sub3AccessDate', today);
            setTimeout(() => {
              overlay.classList.remove('show');
              const url = el.dataset.link;
              if (url) window.location.href = url;
            }, 10000);
          }
        }
      });
    } else {
      el.addEventListener('click', () => {
        const url = el.dataset.link;
        if (url) window.location.href = url;
      });
    }
  });

  // 5) Chatbot Toggle
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

    let userMsg = document.createElement('div');
    userMsg.className = 'chat-msg user';
    userMsg.textContent = txt;
    chatBody.appendChild(userMsg);

    let botMsg = document.createElement('div');
    botMsg.className = 'chat-msg bot';
    botMsg.textContent = '응답 준비중…';
    chatBody.appendChild(botMsg);

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
});
