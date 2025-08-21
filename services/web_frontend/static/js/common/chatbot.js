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
  const SIZE_KEY    = `libraChat.size.${USER}`;
  const POSITION_KEY = `libraChat.position.${USER}`;
  const MAX_MESSAGES = 200; // 너무 길어지지 않게 컷

  let history = []; // {role:'user'|'bot', text:string, ts:number}[]

  // --- 리사이즈 관련 변수들 (원본 방식 유지) ---
  let isResizing = false;
  let resizeDirection = null;
  let startX, startY, startWidth, startHeight, startBottom, startRight;

  // --- 드래그 관련 변수들 ---
  let isDragging = false;
  let dragStartX, dragStartY, dragStartLeft, dragStartTop;

  // --- 스크롤 관련 변수들 ---
  let scrollContainer, customScrollbar, scrollThumb, scrollTrack;
  let isScrollDragging = false;
  let scrollDragStart = 0;

  // 페이지 로드 완료 여부 체크
  let isPageLoaded = false;

  const openChat = () => { 
    chatWindow.style.display = 'flex';
    
    // 페이지 로드 시에는 애니메이션 없이, 사용자 클릭 시에는 애니메이션과 함께
    if (isPageLoaded) {
      chatWindow.classList.remove('no-animation');
      setTimeout(() => chatWindow.classList.add('open'), 10); // 약간의 지연으로 애니메이션 트리거
    } else {
      chatWindow.classList.add('no-animation', 'open');
    }
    
    chatInput?.focus(); 
  };
  
  const closeChat = () => { 
    chatWindow.classList.remove('open', 'no-animation');
    setTimeout(() => {
      if (!chatWindow.classList.contains('open')) {
        chatWindow.style.display = 'none';
      }
    }, 300); // 애니메이션 시간과 맞춤
  };

  // --- 크기 저장/복원 (sessionStorage 사용) ---
  function persistSize() {
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

  // --- 위치 저장/복원 ---
  function persistPosition() {
    const position = {
      bottom: parseFloat(chatWindow.style.bottom) || 16,
      right: parseFloat(chatWindow.style.right) || 16
    };
    try { 
      sessionStorage.setItem(POSITION_KEY, JSON.stringify(position)); 
    } catch(_) {}
  }

  function restorePosition() {
    try {
      const positionRaw = sessionStorage.getItem(POSITION_KEY);
      if (positionRaw) {
        const position = JSON.parse(positionRaw);
        if (position.bottom !== undefined) {
          chatWindow.style.bottom = position.bottom + 'px';
        }
        if (position.right !== undefined) {
          chatWindow.style.right = position.right + 'px';
        }
      } else {
        // 기본 위치 설정 (우측 하단)
        chatWindow.style.bottom = '16px';
        chatWindow.style.right = '16px';
      }
    } catch(_) {
      // 에러 시 기본 위치
      chatWindow.style.bottom = '16px';
      chatWindow.style.right = '16px';
    }
  }

  // --- 저장/복원 (sessionStorage 사용) ---
  function persistHistory() {
    try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(history)); } catch(_) {}
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
    
    // scrollContainer가 있으면 사용, 없으면 chatBody 사용 (초기화 순서 문제 해결)
    const container = scrollContainer || chatBody;
    container.appendChild(wrap);
    container.scrollTop = container.scrollHeight;
    
    // 스크롤바가 초기화되어 있으면 업데이트
    if (scrollContainer && updateScrollbar) {
      updateScrollbar();
    }

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
    
    // scrollContainer가 있으면 사용, 없으면 chatBody 사용
    const container = scrollContainer || chatBody;
    container.appendChild(loader);
    container.scrollTop = container.scrollHeight;
    
    if (scrollContainer && updateScrollbar) {
      updateScrollbar();
    }

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

  // --- 커스텀 스크롤바 기능 ---
  function initCustomScrollbar() {
    // 기존 chatBody 내용을 스크롤 컨테이너로 감싸기
    const existingContent = chatBody.innerHTML;
    chatBody.innerHTML = `
      <div class="chat-scroll-container">
        ${existingContent}
      </div>
      <div class="custom-scrollbar">
        <div class="scroll-arrow up">▲</div>
        <div class="scrollbar-track">
          <div class="scrollbar-thumb"></div>
        </div>
        <div class="scroll-arrow down">▼</div>
      </div>
    `;
    
    scrollContainer = chatBody.querySelector('.chat-scroll-container');
    customScrollbar = chatBody.querySelector('.custom-scrollbar');
    scrollThumb = chatBody.querySelector('.scrollbar-thumb');
    scrollTrack = chatBody.querySelector('.scrollbar-track');
    
    const upArrow = chatBody.querySelector('.scroll-arrow.up');
    const downArrow = chatBody.querySelector('.scroll-arrow.down');
    
    // 스크롤 컨테이너에 휠 이벤트 추가 (기본 스크롤 기능 복원)
    scrollContainer.addEventListener('wheel', (e) => {
      e.stopPropagation(); // 페이지 스크롤 방지
      scrollContainer.scrollTop += e.deltaY;
    });
    
    // 스크롤 이벤트
    scrollContainer.addEventListener('scroll', updateScrollbar);
    
    // 화살표 클릭
    upArrow.addEventListener('click', () => {
      scrollContainer.scrollTop -= 50;
    });
    
    downArrow.addEventListener('click', () => {
      scrollContainer.scrollTop += 50;
    });
    
    // 스크롤바 드래그
    scrollThumb.addEventListener('mousedown', startScrollDrag);
    
    // 트랙 클릭
    scrollTrack.addEventListener('click', (e) => {
      if (e.target === scrollTrack) {
        const rect = scrollTrack.getBoundingClientRect();
        const clickY = e.clientY - rect.top;
        const trackHeight = scrollTrack.offsetHeight;
        const scrollRatio = clickY / trackHeight;
        const maxScroll = scrollContainer.scrollHeight - scrollContainer.offsetHeight;
        scrollContainer.scrollTop = maxScroll * scrollRatio;
      }
    });
    
    updateScrollbar();
  }

  function updateScrollbar() {
    if (!scrollContainer || !scrollThumb || !scrollTrack) return;
    
    const containerHeight = scrollContainer.offsetHeight;
    const contentHeight = scrollContainer.scrollHeight;
    const scrollTop = scrollContainer.scrollTop;
    
    if (contentHeight <= containerHeight) {
      customScrollbar.style.display = 'none';
      return;
    }
    
    customScrollbar.style.display = 'block';
    
    const trackHeight = scrollTrack.offsetHeight;
    const thumbHeight = Math.max(20, (containerHeight / contentHeight) * trackHeight);
    const maxThumbTop = trackHeight - thumbHeight;
    const thumbTop = (scrollTop / (contentHeight - containerHeight)) * maxThumbTop;
    
    scrollThumb.style.height = thumbHeight + 'px';
    scrollThumb.style.top = thumbTop + 'px';
  }

  function startScrollDrag(e) {
    isScrollDragging = true;
    scrollDragStart = e.clientY;
    scrollThumb.classList.add('dragging');
    e.preventDefault();
  }

  function doScrollDrag(e) {
    if (!isScrollDragging) return;
    
    const deltaY = e.clientY - scrollDragStart;
    const trackHeight = scrollTrack.offsetHeight;
    const thumbHeight = scrollThumb.offsetHeight;
    const maxThumbTop = trackHeight - thumbHeight;
    
    const currentThumbTop = parseFloat(scrollThumb.style.top) || 0;
    const newThumbTop = Math.max(0, Math.min(maxThumbTop, currentThumbTop + deltaY));
    
    const scrollRatio = newThumbTop / maxThumbTop;
    const maxScroll = scrollContainer.scrollHeight - scrollContainer.offsetHeight;
    
    scrollContainer.scrollTop = maxScroll * scrollRatio;
    scrollDragStart = e.clientY;
  }

  function stopScrollDrag() {
    if (isScrollDragging) {
      isScrollDragging = false;
      scrollThumb.classList.remove('dragging');
    }
  }

  // --- 드래그 기능 ---
  function startDrag(e) {
    // 닫기 버튼을 클릭한 경우 드래그 시작하지 않음
    if (e.target.id === 'chatCloseBtn') return;
    if (!chatWindow.classList.contains('open')) return;
    
    isDragging = true;
    
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    
    const rect = chatWindow.getBoundingClientRect();
    dragStartLeft = rect.left;
    dragStartTop = rect.top;
    
    document.body.style.cursor = 'move';
    document.body.style.userSelect = 'none';
    
    e.preventDefault();
  }

  function doDrag(e) {
    if (!isDragging) return;
    
    const dx = e.clientX - dragStartX;
    const dy = e.clientY - dragStartY;
    
    let newLeft = dragStartLeft + dx;
    let newTop = dragStartTop + dy;
    
    // 화면 경계 체크
    const windowWidth = window.innerWidth;
    const windowHeight = window.innerHeight;
    const chatWidth = chatWindow.offsetWidth;
    const chatHeight = chatWindow.offsetHeight;
    
    // 최소 10px 여백 유지
    newLeft = Math.max(10, Math.min(windowWidth - chatWidth - 10, newLeft));
    newTop = Math.max(10, Math.min(windowHeight - chatHeight - 10, newTop));
    
    // right, bottom 기준으로 변환
    const newRight = windowWidth - newLeft - chatWidth;
    const newBottom = windowHeight - newTop - chatHeight;
    
    chatWindow.style.right = newRight + 'px';
    chatWindow.style.bottom = newBottom + 'px';
  }

  function stopDrag() {
    if (isDragging) {
      isDragging = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      
      // 위치 변경 저장
      persistPosition();
    }
  }

  // --- 리사이즈 기능 (원본 방식 그대로 유지) ---
  function startResize(e) {
    if (!chatWindow.classList.contains('open')) return;
    
    isResizing = true;
    resizeDirection = e.target.dataset.direction;
    
    startX = e.clientX;
    startY = e.clientY;
    startWidth = parseInt(document.defaultView.getComputedStyle(chatWindow).width, 10);
    startHeight = parseInt(document.defaultView.getComputedStyle(chatWindow).height, 10);
    
    // 현재 위치 저장 (bottom, right 기준) - 원본 방식
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
    
    // 방향에 따른 크기 계산 (방향 수정)
    if (resizeDirection.includes('e')) {
      newWidth = startWidth + dx;
    }
    if (resizeDirection.includes('w')) {
      newWidth = startWidth - dx;
      newRight = startRight - dx; // 수정: + 대신 -
    }
    if (resizeDirection.includes('s')) {
      newHeight = startHeight + dy;
    }
    if (resizeDirection.includes('n')) {
      newHeight = startHeight - dy;
      newBottom = startBottom - dy; // 수정: + 대신 -
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
    
    updateScrollbar();
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

  // 리사이즈 핸들 이벤트
  const resizeHandles = chatWindow.querySelectorAll('.resize-handle');
  resizeHandles.forEach(handle => {
    handle.addEventListener('mousedown', startResize);
  });

  // 헤더 드래그 이벤트
  const chatHeader = chatWindow.querySelector('.chat-header');
  chatHeader.addEventListener('mousedown', startDrag);

  // 전역 마우스 이벤트 (원본 방식)
  document.addEventListener('mousemove', (e) => {
    doResize(e);
    doDrag(e);
    doScrollDrag(e);
  });

  document.addEventListener('mouseup', () => {
    stopResize();
    stopDrag();
    stopScrollDrag();
  });

  // 채팅창 전체에 휠 이벤트 추가 (스크롤 기능 복원)
  chatWindow.addEventListener('wheel', (e) => {
    // 채팅창이 열려있을 때만 스크롤 처리
    if (chatWindow.classList.contains('open')) {
      e.stopPropagation(); // 페이지 스크롤 방지
      if (scrollContainer) {
        scrollContainer.scrollTop += e.deltaY;
      }
    }
  });

  // 윈도우 리사이즈 시 챗봇 위치 조정
  window.addEventListener('resize', () => {
    if (!chatWindow.classList.contains('open')) return;
    
    const rect = chatWindow.getBoundingClientRect();
    const newRight = Math.max(10, Math.min(window.innerWidth - chatWindow.offsetWidth - 10, 
                                           window.innerWidth - rect.right));
    const newBottom = Math.max(10, Math.min(window.innerHeight - chatWindow.offsetHeight - 10, 
                                            window.innerHeight - rect.bottom));
    
    chatWindow.style.right = newRight + 'px';
    chatWindow.style.bottom = newBottom + 'px';
    
    updateScrollbar();
  });

  // 페이지 언로드 시 정리
  window.addEventListener('beforeunload', () => {
    console.log('챗봇 세션이 종료됩니다.');
  });

  // 페이지 로드 완료 체크
  if (document.readyState === 'complete') {
    isPageLoaded = true;
  } else {
    window.addEventListener('load', () => {
      setTimeout(() => {
        isPageLoaded = true;
      }, 100);
    });
  }

  // 최초 복원 및 초기화 (순서 중요)
  initCustomScrollbar(); // 먼저 스크롤바 초기화
  restore(); // 그 다음 대화내역 복원
  restoreSize();
  restorePosition();
})();