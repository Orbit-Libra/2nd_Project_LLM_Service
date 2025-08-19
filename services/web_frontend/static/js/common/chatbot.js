// static/js/common/chatbot.js
(() => {
  if (window.__chatbotInitialized) return;
  window.__chatbotInitialized = true;

  const $ = (id) => document.getElementById(id);
  const chatToggle  = $('chatToggle');
  const chatWindow  = $('chatWindow');
  const chatClose   = $('chatCloseBtn');
  const chatBody    = $('chatBody');
  const chatInput   = $('chatInput');
  const chatSend    = $('chatSendBtn');

  if (!chatToggle || !chatWindow || !chatBody) return;

  // --- 퍼시스턴스 키(사용자별 저장) ---
  const USER = (window.LIBRA_USER && String(window.LIBRA_USER)) || 'guest';
  const STORAGE_KEY = `libraChat.history.${USER}`;
  const UI_KEY      = `libraChat.ui.${USER}`;
  const MAX_MESSAGES = 200; // 너무 길어지지 않게 컷

  let history = []; // {role:'user'|'bot', text:string, ts:number}[]

  const ensureVisible = () => {
    const st = window.getComputedStyle(chatWindow);
    if (st.display === 'none' || chatWindow.style.display === 'none') {
      chatWindow.style.display = 'flex'; // transform 기반 애니메이션 위해 항상 보이게
    }
  };

  const openChat  = () => { ensureVisible(); chatWindow.classList.add('open'); persistUI(); chatInput?.focus(); };
  const closeChat = () => { chatWindow.classList.remove('open'); persistUI(); };

  // --- 저장/복원 ---
  function persistHistory() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(history)); } catch(_) {}
  }
  function persistUI() {
    const ui = { open: chatWindow.classList.contains('open') };
    try { localStorage.setItem(UI_KEY, JSON.stringify(ui)); } catch(_) {}
  }
  function restore() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const arr = JSON.parse(raw);
        if (Array.isArray(arr)) {
          history = arr;
          // 복원 렌더 (저장은 중복 방지 위해 off)
          for (const m of history) appendBubble(m.text, m.role, /*persist=*/false);
        }
      }
    } catch(_) {}
    try {
      const uiRaw = localStorage.getItem(UI_KEY);
      if (uiRaw) {
        const ui = JSON.parse(uiRaw);
        if (ui && ui.open) openChat();
      }
    } catch(_) {}
  }
  function pushMessage(role, text) {
    history.push({ role, text, ts: Date.now() });
    if (history.length > MAX_MESSAGES) history = history.slice(-MAX_MESSAGES);
    persistHistory();
  }

  // --- 버블 렌더 ---
  function appendBubble(text, role = 'bot', persist = true) {
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

    if (persist) {
      pushMessage(role, text);
    }
  }

  // --- 서버 호출 ---
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

  // --- 전송 ---
  async function sendMessage() {
    const msg = (chatInput?.value || '').trim();
    if (!msg) return;

    appendBubble(msg, 'user'); // 저장됨
    if (chatInput) { chatInput.value = ''; chatInput.focus(); }

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
      appendBubble(answer || '죄송해요, 응답이 비었습니다.', 'bot'); // 저장됨
    } catch (err) {
      loader.remove();
      console.error(err);
      appendBubble('에러가 발생했어요. 잠시 후 다시 시도해주세요.', 'bot'); // 저장됨
    }
  }

  // --- 이벤트 바인딩 ---
  chatToggle.addEventListener('click', () => {
    if (chatWindow.classList.contains('open')) closeChat(); else openChat();
  });
  chatClose?.addEventListener('click', closeChat);
  chatSend?.addEventListener('click', sendMessage);
  chatInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // 탭간 동기화(다른 탭에서 갱신되면 반영)
  window.addEventListener('storage', (e) => {
    if (e.key === STORAGE_KEY || e.key === UI_KEY) {
      // 간단히 전체 리프레시
      chatBody.innerHTML = '';
      history = [];
      restore();
    }
  });

  // 최초 복원
  ensureVisible();
  restore();
})();
