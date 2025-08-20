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

  // --- 퍼시스턴스 키(사용자별 저장) - sessionStorage 사용 ---
  const USER = (window.LIBRA_USER && String(window.LIBRA_USER)) || 'guest';
  const STORAGE_KEY = `libraChat.history.${USER}`;
  const UI_KEY      = `libraChat.ui.${USER}`;
  const SIZE_KEY    = `libraChat.size.${USER}`;
  const MAX_MESSAGES = 200; // 너무 길어지지 않게 컷

  let history = []; // {role:'user'|'bot', text:string, ts:number}[]

  // --- 리사이즈 관련 변수들 ---
  let isResizing = false;
  let resizeDirection = null;
  let startX, startY, startWidth, startHeight, startBottom, startRight;

  const ensureVisible = () => {
    const st = window.getComputedStyle(chatWindow);
    if (st.display === 'none' || chatWindow.style.display === 'none') {
      chatWindow.style.display = 'flex'; // transform 기반 애니메이션 위해 항상 보이게
    }
  };

  const openChat  = () => { ensureVisible(); chatWindow.classList.add('open'); persistUI(); chatInput?.focus(); };
  const closeChat = () => { chatWindow.classList.remove('open'); persistUI(); };

  // --- 크기 저장/복원 (sessionStorage 사용) ---
  function persistSize() {
    const rect = chatWindow.getBoundingClientRect();
    const size = {
      width: chatWindow.offsetWidth,
      height: chatWindow.offsetHeight,
      bottom: parseFloat(chatWindow.style.bottom) || 16, // 1rem = 16px
      right: parseFloat(chatWindow.style.right) || 16
    };
    try { 
      sessionStorage.setItem(SIZE_KEY, JSON.stringify(size)); 
    } catch(_) {}
  }

  function restoreSize() {
    try {
      const sizeRaw = sessionStorage.getItem(SIZE_KEY);
      if (sizeRaw) {
        const size = JSON.parse(sizeRaw);
        if (size.width && size.height) {
          chatWindow.style.width = size.width + 'px';
          chatWindow.style.height = size.height + 'px';
          if (size.bottom !== undefined) {
            chatWindow.style.bottom = size.bottom + 'px';
          }
          if (size.right !== undefined) {
            chatWindow.style.right = size.right + 'px';
          }
        }
      }
    } catch(_) {}
  }

  // --- 저장/복원 (sessionStorage 사용) ---
  function persistHistory() {
    try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(history)); } catch(_) {}
  }
  function persistUI() {
    const ui = { open: chatWindow.classList.contains('open') };
    try { sessionStorage.setItem(UI_KEY, JSON.stringify(ui)); } catch(_) {}
  }
  function restore() {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
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
      const uiRaw = sessionStorage.getItem(UI_KEY);
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

  // --- 리사이즈 기능 ---
  function initResize() {
    const resizeHandles = chatWindow.querySelectorAll('.resize-handle');
    
    resizeHandles.forEach(handle => {
      handle.addEventListener('mousedown', startResize);
    });

    document.addEventListener('mousemove', doResize);
    document.addEventListener('mouseup', stopResize);
  }

  function startResize(e) {
    if (!chatWindow.classList.contains('open')) return;
    
    isResizing = true;
    resizeDirection = e.target.dataset.direction;
    
    startX = e.clientX;
    startY = e.clientY;
    startWidth = parseInt(document.defaultView.getComputedStyle(chatWindow).width, 10);
    startHeight = parseInt(document.defaultView.getComputedStyle(chatWindow).height, 10);
    
    // 현재 위치 저장 (bottom, right 기준)
    const rect = chatWindow.getBoundingClientRect();
    startBottom = window.innerHeight - rect.bottom;
    startRight = window.innerWidth - rect.right;
    
    document.body.style.cursor = e.target.style.cursor;
    document.body.style.userSelect = 'none';
    
    e.preventDefault();
  }

  function doResize(e) {
    if (!isResizing) return;
    
    const dx = e.clientX - startX;
    const dy = e.clientY - startY;
    
    let newWidth = startWidth;
    let newHeight = startHeight;
    let newBottom = startBottom;
    let newRight = startRight;
    
    // 방향에 따른 크기 계산
    if (resizeDirection.includes('e')) {
      newWidth = startWidth + dx;
    }
    if (resizeDirection.includes('w')) {
      newWidth = startWidth - dx;
      newRight = startRight + dx;
    }
    if (resizeDirection.includes('s')) {
      newHeight = startHeight + dy;
    }
    if (resizeDirection.includes('n')) {
      newHeight = startHeight - dy;
      newBottom = startBottom + dy;
    }
    
    // 최소/최대 크기 제한
    const minWidth = 250;
    const minHeight = 300;
    const maxWidth = window.innerWidth * 0.9;
    const maxHeight = window.innerHeight * 0.9;
    
    newWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));
    newHeight = Math.max(minHeight, Math.min(maxHeight, newHeight));
    
    // 화면 경계 체크
    newRight = Math.max(10, Math.min(window.innerWidth - newWidth - 10, newRight));
    newBottom = Math.max(10, Math.min(window.innerHeight - newHeight - 10, newBottom));
    
    // 적용
    chatWindow.style.width = newWidth + 'px';
    chatWindow.style.height = newHeight + 'px';
    chatWindow.style.right = newRight + 'px';
    chatWindow.style.bottom = newBottom + 'px';
  }

  function stopResize() {
    if (isResizing) {
      isResizing = false;
      resizeDirection = null;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      
      // 크기 변경 저장
      persistSize();
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

  // 탭간 동기화(다른 탭에서 갱신되면 반영) - sessionStorage 이벤트
  window.addEventListener('storage', (e) => {
    // sessionStorage는 같은 탭에서만 유효하므로 이 이벤트는 발생하지 않음
    // 필요시 다른 동기화 방법 사용
  });

  // 윈도우 리사이즈 시 챗봇 위치 조정
  window.addEventListener('resize', () => {
    const rect = chatWindow.getBoundingClientRect();
    const newRight = Math.max(10, Math.min(window.innerWidth - chatWindow.offsetWidth - 10, 
                                           window.innerWidth - rect.right));
    const newBottom = Math.max(10, Math.min(window.innerHeight - chatWindow.offsetHeight - 10, 
                                            window.innerHeight - rect.bottom));
    
    chatWindow.style.right = newRight + 'px';
    chatWindow.style.bottom = newBottom + 'px';
  });

  // 페이지 언로드 시 정리 (선택사항)
  window.addEventListener('beforeunload', () => {
    // sessionStorage는 자동으로 삭제되므로 별도 처리 불필요
    console.log('챗봇 세션이 종료됩니다.');
  });

  // 최초 복원 및 초기화
  ensureVisible();
  restore();
  restoreSize();
  initResize();
})();