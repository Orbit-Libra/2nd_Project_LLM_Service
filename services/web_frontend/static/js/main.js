// main.js — 슬라이더/카드/챗봇 전용

window.addEventListener('DOMContentLoaded', () => {
  // 안전장치: 스크롤 컨테이너 지정
  const sections = document.getElementById('sections-wrapper');
  if (sections && !sections.classList.contains('scroll-area')) {
    sections.classList.add('scroll-area');
  }

  initializeSlider();
  initializeSubCards();
  initializeChatbot();
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

/* 챗봇 */
function initializeChatbot() {
  const chatToggle  = document.getElementById('chatToggle');
  const chatWindow  = document.getElementById('chatWindow');
  const chatClose   = document.getElementById('chatCloseBtn');
  const chatBody    = document.getElementById('chatBody');
  const chatInput   = document.getElementById('chatInput');
  const chatSend    = document.getElementById('chatSendBtn');

  const sendMessage = () => {
    if (!chatInput || !chatBody) return;
    const txt = chatInput.value.trim();
    if (!txt) return;

    const userMsg = document.createElement('div');
    userMsg.style.cssText = `
      margin:10px 0; padding:10px 15px;
      background:#007bff; color:#fff;
      border-radius:20px 20px 5px 20px;
      max-width:80%; margin-left:auto; word-wrap:break-word;`;
    userMsg.textContent = txt;
    chatBody.appendChild(userMsg);

    const botMsg = document.createElement('div');
    botMsg.style.cssText = `
      margin:10px 0; padding:10px 15px;
      background:#f1f1f1; color:#333;
      border-radius:20px 20px 20px 5px;
      max-width:80%; margin-right:auto; word-wrap:break-word;`;
    botMsg.textContent = '안녕하세요! Libra 서비스에 대해 궁금한 것이 있으시면 언제든 문의해 주세요. 현재는 데모 모드입니다.';

    setTimeout(() => {
      chatBody.appendChild(botMsg);
      chatBody.scrollTop = chatBody.scrollHeight;
    }, 400);

    chatBody.scrollTop = chatBody.scrollHeight;
    chatInput.value = '';
    chatInput.focus();
  };

  chatToggle?.addEventListener('click', () => {
    if (!chatWindow) return;
    chatWindow.classList.toggle('open');
    if (chatWindow.classList.contains('open') && chatInput) chatInput.focus();
  });

  chatClose?.addEventListener('click', () => chatWindow?.classList.remove('open'));
  chatSend?.addEventListener('click', sendMessage);
  chatInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      sendMessage();
    }
  });
}
