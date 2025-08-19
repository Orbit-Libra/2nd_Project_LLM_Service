// static/js/common/chatbot.js — 모든 페이지 공통
(() => {
  // 중복 초기화 방지
  if (window.__chatbotInitialized) return;
  window.__chatbotInitialized = true;

  const $ = (id) => document.getElementById(id);
  const chatToggle  = $('chatToggle');
  const chatWindow  = $('chatWindow');
  const chatClose   = $('chatCloseBtn');
  const chatBody    = $('chatBody');
  const chatInput   = $('chatInput');
  const chatSend    = $('chatSendBtn');

  // 마크업이 없는 페이지면 조용히 종료
  if (!chatToggle || !chatWindow || !chatBody) return;

  // 🔧 인라인 display:none;이 남아있어도 강제로 보정
  //   (transform으로 슬라이드-숨김, display는 항상 보이도록 유지해야 애니메이션이 동작)
  const ensureVisible = () => {
    const st = window.getComputedStyle(chatWindow);
    if (st.display === 'none' || chatWindow.style.display === 'none') {
      chatWindow.style.display = 'flex';   // flex 레이아웃 유지
    }
  };
  ensureVisible();

  // 열고/닫기는 transform 기반(open 클래스)으로만 제어
  const openChat  = () => {
    ensureVisible();
    chatWindow.classList.add('open');
    chatInput && chatInput.focus();
  };
  const closeChat = () => {
    chatWindow.classList.remove('open');
    // display는 건드리지 않음(애니메이션 유지)
  };

  // 버블 렌더링
  function appendBubble(text, role = 'bot') {
    const wrap = document.createElement('div');
    wrap.className = role === 'user' ? 'msg user' : 'msg bot';
    wrap.style.margin = '8px 12px';
    wrap.style.display = 'flex';
    wrap.style.justifyContent = role === 'user' ? 'flex-end' : 'flex-start';

    const bubble = document.createElement('div');
    bubble.textContent = text;
    bubble.style.maxWidth = '75%';
    bubble.style.padding = '10px 12px';
    bubble.style.borderRadius = '10px';
    bubble.style.lineHeight = '1.4';
    bubble.style.fontSize = '.95rem';
    bubble.style.whiteSpace = 'pre-wrap';
    bubble.style.wordBreak = 'break-word';
    if (role === 'user') {
      bubble.style.background = '#204461';
      bubble.style.color = '#fff';
      bubble.style.borderTopRightRadius = '4px';
    } else {
      bubble.style.background = '#fff';
      bubble.style.color = '#333';
      bubble.style.borderTopLeftRadius = '4px';
      bubble.style.boxShadow = '0 1px 2px rgba(0,0,0,0.06)';
    }

    wrap.appendChild(bubble);
    chatBody.appendChild(wrap);
    chatBody.scrollTop = chatBody.scrollHeight;
  }

  // 서버 호출
  async function callAssistant(message) {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message })
    });
    if (!res.ok) {
      const txt = await res.text().catch(() => '');
      throw new Error(`HTTP ${res.status} ${txt}`);
    }
    return res.json();
  }

  // 전송 처리
  async function sendMessage() {
    const msg = (chatInput?.value || '').trim();
    if (!msg) return;

    appendBubble(msg, 'user');
    if (chatInput) { chatInput.value = ''; chatInput.focus(); }

    // 로딩 표시
    const loader = document.createElement('div');
    loader.textContent = '생각중...';
    loader.style.color = '#888';
    loader.style.margin = '6px 12px';
    chatBody.appendChild(loader);
    chatBody.scrollTop = chatBody.scrollHeight;

    try {
      const data = await callAssistant(msg);
      loader.remove();
      const answer = (data && data.answer) ? String(data.answer).trim() : '';
      appendBubble(answer || '죄송해요, 응답이 비었습니다.', 'bot');
    } catch (err) {
      loader.remove();
      console.error(err);
      appendBubble('에러가 발생했어요. 잠시 후 다시 시도해주세요.', 'bot');
    }
  }

  // 이벤트 바인딩
  chatToggle.addEventListener('click', () => {
    if (chatWindow.classList.contains('open')) closeChat();
    else openChat();
  });
  chatClose?.addEventListener('click', closeChat);
  chatSend?.addEventListener('click', sendMessage);
  chatInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // 혹시 렌더 타이밍에 따라 display가 다시 none이 되면 한 번 더 보정
  document.addEventListener('visibilitychange', ensureVisible);
})();
