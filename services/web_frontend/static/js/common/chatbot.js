// chatbot.js — 모든 페이지 공통

function initializeChatbot() {
  const chatToggle  = document.getElementById('chatToggle');
  const chatWindow  = document.getElementById('chatWindow');
  const chatClose   = document.getElementById('chatCloseBtn');
  const chatBody    = document.getElementById('chatBody');
  const chatInput   = document.getElementById('chatInput');
  const chatSend    = document.getElementById('chatSendBtn');

  // 마크업이 없는 페이지면 조용히 종료
  if (!chatToggle || !chatWindow) return;

  const appendBubble = (text, role = 'user') => {
    if (!chatBody) return;
    const wrap = document.createElement('div');
    wrap.style.margin = '6px 0';
    wrap.style.display = 'flex';
    wrap.style.justifyContent = role === 'user' ? 'flex-end' : 'flex-start';

    const bubble = document.createElement('div');
    bubble.textContent = text;
    bubble.style.maxWidth = '75%';
    bubble.style.padding = '8px 10px';
    bubble.style.borderRadius = '10px';
    bubble.style.lineHeight = '1.3';
    bubble.style.fontSize = '.9rem';
    bubble.style.whiteSpace = 'pre-wrap';
    bubble.style.wordBreak = 'break-word';
    if (role === 'user') {
      bubble.style.background = '#204461';
      bubble.style.color = '#fff';
      bubble.style.borderTopRightRadius = '3px';
    } else {
      bubble.style.background = '#fff';
      bubble.style.color = '#333';
      bubble.style.borderTopLeftRadius = '3px';
      bubble.style.boxShadow = '0 1px 2px rgba(0,0,0,0.06)';
    }

    wrap.appendChild(bubble);
    chatBody.appendChild(wrap);
    chatBody.scrollTop = chatBody.scrollHeight;
  };

  const sendMessage = () => {
    if (!chatInput || !chatBody) return;
    const txt = chatInput.value.trim();
    if (!txt) return;

    appendBubble(txt, 'user');
    chatInput.value = '';
    chatInput.focus();

    // TODO: 서버 연동 위치
    setTimeout(() => {
      appendBubble('요청을 접수했어요! (데모 응답)', 'assistant');
    }, 250);
  };

  const openChat = () => {
    chatWindow.classList.add('open');
    chatInput?.focus();
  };
  const closeChat = () => chatWindow.classList.remove('open');

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
}

/* ✅ 모든 페이지에서 자동 초기화 */
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeChatbot);
} else {
  initializeChatbot();
}
