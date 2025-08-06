//챗봇 기능 전담
//../static/js/common/chatbot.js
//창관리- 열기/닫기, 토글, 자동포커스
//메시지시스템-사용자/봇메시지추가,타이핑표시
//키워드응답-간단한 키워드 기반 자동응답(예,차트,오류,안녕)
//히스토리 관리- 채팅기록 저장/로드/삭제
//이벤트처리-엔터키,클릭,포커스등
//애니메이션-메시지등장효과,타이핑...

// js/common/chatbot.js - 챗봇 기능 관리
class ChatBot {
  constructor() {
    this.isOpen = false;
    this.messages = [];
    this.isTyping = false;
    this.responses = this.initializeResponses();
    
    this.elements = {
      toggle: null,
      window: null,
      closeBtn: null,
      body: null,
      input: null,
      sendBtn: null
    };
    
    this.init();
  }

  init() {
    this.bindElements();
    this.setupEventListeners();
    this.addWelcomeMessage();
    
    console.log('ChatBot 초기화 완료');
  }

  bindElements() {
    this.elements.toggle = document.getElementById('chatToggle');
    this.elements.window = document.getElementById('chatWindow');
    this.elements.closeBtn = document.getElementById('chatCloseBtn');
    this.elements.body = document.getElementById('chatBody');
    this.elements.input = document.getElementById('chatInput');
    this.elements.sendBtn = document.getElementById('chatSendBtn');
    
    // 요소가 없는 경우 에러 로그
    if (!this.elements.toggle) console.error('챗봇 토글 버튼을 찾을 수 없습니다.');
    if (!this.elements.window) console.error('챗봇 윈도우를 찾을 수 없습니다.');
  }

  setupEventListeners() {
    // 챗봇 토글 버튼
    this.elements.toggle?.addEventListener('click', () => {
      this.toggle();
    });

    // 닫기 버튼
    this.elements.closeBtn?.addEventListener('click', () => {
      this.close();
    });

    // 전송 버튼
    this.elements.sendBtn?.addEventListener('click', () => {
      this.sendMessage();
    });

    // Enter 키로 메시지 전송
    this.elements.input?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.sendMessage();
      }
    });

    // 입력 중 상태 표시
    this.elements.input?.addEventListener('input', () => {
      this.handleTyping();
    });

    // 창 외부 클릭 시 닫기
    document.addEventListener('click', (e) => {
      if (this.isOpen && 
          !this.elements.window?.contains(e.target) && 
          !this.elements.toggle?.contains(e.target)) {
        this.close();
      }
    });

    // ESC 키로 닫기
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.isOpen) {
        this.close();
      }
    });
  }

  toggle() {
    if (this.isOpen) {
      this.close();
    } else {
      this.open();
    }
  }

  open() {
    if (!this.elements.window) return;
    
    this.elements.window.classList.add('open');
    this.isOpen = true;
    
    // 입력창에 포커스
    setTimeout(() => {
      this.elements.input?.focus();
    }, 300);
    
    // 스크롤을 맨 아래로
    this.scrollToBottom();
    
    // 열림 효과
    this.elements.toggle?.classList.add('active');
  }

  close() {
    if (!this.elements.window) return;
    
    this.elements.window.classList.remove('open');
    this.isOpen = false;
    this.elements.toggle?.classList.remove('active');
  }

  async sendMessage() {
    const input = this.elements.input;
    if (!input || !this.elements.body) return;
    
    const message = input.value.trim();
    if (!message) return;
    
    // 사용자 메시지 추가
    this.addMessage(message, 'user');
    input.value = '';
    
    // 전송 버튼 비활성화
    this.setSendButtonState(false);
    
    // 타이핑 표시
    this.showTyping();
    
    // 응답 생성 (딜레이 시뮬레이션)
    setTimeout(() => {
      this.hideTyping();
      const response = this.generateResponse(message);
      this.addMessage(response, 'bot');
      this.setSendButtonState(true);
    }, this.getRandomDelay(800, 2000));
  }

  addMessage(text, type) {
    if (!this.elements.body) return;
    
    const messageElement = this.createMessageElement(text, type);
    this.elements.body.appendChild(messageElement);
    
    // 메시지 히스토리에 추가
    this.messages.push({ text, type, timestamp: new Date() });
    
    // 스크롤을 맨 아래로
    this.scrollToBottom();
    
    // 메시지 애니메이션
    this.animateMessage(messageElement);
  }

  createMessageElement(text, type) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-msg ${type}`;
    
    // 봇 메시지인 경우 아바타 추가 가능
    if (type === 'bot') {
      messageDiv.innerHTML = `
        <div class="message-content">${this.parseMessage(text)}</div>
        <div class="message-time">${this.getCurrentTime()}</div>
      `;
    } else {
      messageDiv.innerHTML = `
        <div class="message-content">${this.parseMessage(text)}</div>
        <div class="message-time">${this.getCurrentTime()}</div>
      `;
    }
    
    return messageDiv;
  }

  parseMessage(text) {
    // URL 링크 자동 변환
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    text = text.replace(urlRegex, '<a href="$1" target="_blank" rel="noopener">$1</a>');
    
    // 이메일 링크 변환
    const emailRegex = /([a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+\.[a-zA-Z0-9_-]+)/g;
    text = text.replace(emailRegex, '<a href="mailto:$1">$1</a>');
    
    // 줄바꿈 처리
    text = text.replace(/\n/g, '<br>');
    
    return text;
  }

  showTyping() {
    if (!this.elements.body) return;
    
    const typingElement = document.createElement('div');
    typingElement.className = 'chat-msg bot typing';
    typingElement.innerHTML = `
      <div class="typing-indicator">
        <span></span>
        <span></span>
        <span></span>
      </div>
    `;
    typingElement.id = 'typing-indicator';
    
    this.elements.body.appendChild(typingElement);
    this.scrollToBottom();
    this.isTyping = true;
  }

  hideTyping() {
    const typingElement = document.getElementById('typing-indicator');
    if (typingElement) {
      typingElement.remove();
    }
    this.isTyping = false;
  }

  generateResponse(message) {
    const lowerMessage = message.toLowerCase();
    
    // 키워드 기반 응답
    for (const [category, data] of Object.entries(this.responses)) {
      if (category === 'default') continue;
      
      if (data.keywords && data.keywords.some(keyword => lowerMessage.includes(keyword))) {
        return this.getRandomResponse(data.responses);
      }
    }
    
    // 기본 응답
    return this.getRandomResponse(this.responses.default);
  }

  initializeResponses() {
    return {
      // 인사
      greetings: {
        keywords: ['안녕', '하이', '헬로', '안녕하세요', 'hi', 'hello'],
        responses: [
          '안녕하세요! Libra 서비스에 오신 것을 환영합니다! 😊',
          '안녕하세요! 무엇을 도와드릴까요?',
          '반갑습니다! Libra에 대해 궁금한 것이 있으시면 언제든 물어보세요!'
        ]
      },
      
      // 서비스 관련
      service: {
        keywords: ['libra', '리브라', '서비스', '기능'],
        responses: [
          'Libra는 교육 인프라 분석 및 예측 서비스입니다! 📊\n\n• 학습환경 분석\n• 발전도 예측\n• 개인 맞춤 서비스',
          'Libra를 통해 대학의 인프라 점수를 확인하고 발전 가능성을 예측할 수 있습니다!',
          '저희 서비스는 교육 데이터 분석을 통해 더 나은 학습 환경을 제공합니다! 🎓'
        ]
      },
      
      // 차트/분석 관련
      chart: {
        keywords: ['차트', '분석', '데이터', '통계', '그래프'],
        responses: [
          '차트 페이지에서 다양한 데이터 시각화를 확인하실 수 있습니다! 📈',
          '학습환경 분석 페이지에서 상세한 통계를 제공합니다!',
          '데이터 기반의 정확한 분석 결과를 확인해보세요!'
        ]
      },
      
      // 예측 관련
      prediction: {
        keywords: ['예측', '발전', '미래', '전망'],
        responses: [
          '발전도 분석 페이지에서 미래 전망을 확인하실 수 있습니다! 🔮',
          '연도별 점수 추이를 통해 발전 가능성을 예측합니다!',
          'AI 기반 예측 모델을 활용하여 정확한 전망을 제공합니다!'
        ]
      },
      
      // 로그인/회원 관련
      login: {
        keywords: ['로그인', '회원', '가입', '계정'],
        responses: [
          '마이 서비스를 이용하려면 로그인이 필요합니다! 🔐',
          '회원가입 후 개인 맞춤 서비스를 이용해보세요!',
          '로그인하시면 더 많은 기능을 사용하실 수 있습니다!'
        ]
      },
      
      // 도움말/사용법
      help: {
        keywords: ['도움', '사용법', '방법', '어떻게'],
        responses: [
          '상단 메뉴를 통해 원하는 서비스를 선택하실 수 있습니다! 🧭',
          '메인 페이지의 카드를 클릭하여 각 기능에 접근해보세요!',
          '궁금한 점이 있으시면 언제든 물어보세요! 저는 24시간 대기 중입니다! 🤖'
        ]
      },
      
      // 감사 인사
      thanks: {
        keywords: ['감사', '고마워', '고맙', 'thanks', 'thank you'],
        responses: [
          '천만에요! 더 궁금한 것이 있으시면 언제든 말씀해주세요! 😊',
          '도움이 되었다니 기쁩니다! 🎉',
          '별말씀을요! Libra를 이용해주셔서 감사합니다!'
        ]
      },
      
      // 작별 인사
      goodbye: {
        keywords: ['안녕', '잘가', '빠이', 'bye', 'goodbye'],
        responses: [
          '안녕히 가세요! 언제든 다시 찾아와주세요! 👋',
          'Libra를 이용해주셔서 감사합니다! 좋은 하루 되세요! ☀️',
          '또 만나요! 언제든 도움이 필요하면 저를 찾아주세요! 🤗'
        ]
      },
      
      // 기본 응답
      default: [
        '죄송합니다. 잘 이해하지 못했어요. 다시 한 번 말씀해주시겠어요? 🤔',
        'Libra 서비스에 대해 더 자세히 알고 싶으시다면 구체적으로 물어보세요!',
        '무엇을 도와드릴까요? 서비스 기능이나 사용법에 대해 궁금한 점이 있으시면 말씀해주세요! 💡',
        '잘 모르겠네요. 하지만 Libra의 학습환경 분석, 발전도 예측, 마이 서비스에 대해서는 자세히 알려드릴 수 있어요!'
      ]
    };
  }

  getRandomResponse(responses) {
    return responses[Math.floor(Math.random() * responses.length)];
  }

  addWelcomeMessage() {
    if (this.messages.length === 0) {
      setTimeout(() => {
        this.addMessage('안녕하세요! Libra 챗봇입니다! 🤖\n\n교육 인프라 분석 서비스에 대해 궁금한 점이 있으시면 언제든 물어보세요!', 'bot');
      }, 500);
    }
  }

  scrollToBottom() {
    if (this.elements.body) {
      setTimeout(() => {
        this.elements.body.scrollTop = this.elements.body.scrollHeight;
      }, 100);
    }
  }

  animateMessage(element) {
    element.style.opacity = '0';
    element.style.transform = 'translateY(1rem)';
    
    setTimeout(() => {
      element.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
      element.style.opacity = '1';
      element.style.transform = 'translateY(0)';
    }, 50);
  }

  setSendButtonState(enabled) {
    if (this.elements.sendBtn) {
      this.elements.sendBtn.disabled = !enabled;
      this.elements.sendBtn.style.opacity = enabled ? '1' : '0.6';
    }
  }

  handleTyping() {
    // 입력 중일 때의 추가 로직 (예: 전송 버튼 활성화)
    const hasText = this.elements.input?.value.trim().length > 0;
    this.setSendButtonState(hasText && !this.isTyping);
  }

  getCurrentTime() {
    return new Date().toLocaleTimeString('ko-KR', {
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  getRandomDelay(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
  }

  // 메시지 히스토리 관리
  clearHistory() {
    this.messages = [];
    if (this.elements.body) {
      this.elements.body.innerHTML = '';
    }
    this.addWelcomeMessage();
  }

  exportHistory() {
    return JSON.stringify(this.messages, null, 2);
  }

  // 설정 관리
  setAutoResponse(enabled) {
    this.autoResponse = enabled;
  }

  setResponseDelay(min, max) {
    this.responseDelay = { min, max };
  }

  // 디버그 정보
  getDebugInfo() {
    return {
      isOpen: this.isOpen,
      messageCount: this.messages.length,
      isTyping: this.isTyping,
      elements: Object.keys(this.elements).reduce((acc, key) => {
        acc[key] = !!this.elements[key];
        return acc;
      }, {})
    };
  }
}

// CSS 동적 추가 (타이핑 인디케이터 애니메이션)
function addChatbotStyles() {
  if (document.getElementById('chatbot-dynamic-styles')) return;
  
  const style = document.createElement('style');
  style.id = 'chatbot-dynamic-styles';
  style.textContent = `
    .typing-indicator {
      display: flex;
      align-items: center;
      padding: 0.5rem;
    }
    
    .typing-indicator span {
      width: 0.5rem;
      height: 0.5rem;
      border-radius: 50%;
      background-color: #999;
      margin: 0 0.1rem;
      animation: typing 1.5s infinite;
    }
    
    .typing-indicator span:nth-child(2) {
      animation-delay: 0.2s;
    }
    
    .typing-indicator span:nth-child(3) {
      animation-delay: 0.4s;
    }
    
    @keyframes typing {
      0%, 60%, 100% {
        transform: translateY(0);
        opacity: 0.4;
      }
      30% {
        transform: translateY(-0.5rem);
        opacity: 1;
      }
    }
    
    .message-time {
      font-size: 0.7rem;
      opacity: 0.6;
      margin-top: 0.25rem;
      text-align: right;
    }
    
    .chat-msg.user .message-time {
      text-align: left;
    }
    
    .message-content a {
      color: inherit;
      text-decoration: underline;
    }
    
    .chat-msg.bot .message-content a {
      color: #007bff;
    }
  `;
  
  document.head.appendChild(style);
}

// DOM 로드 완료 후 초기화
document.addEventListener('DOMContentLoaded', () => {
  addChatbotStyles();
  
  // 약간의 딜레이 후 챗봇 초기화 (다른 컴포넌트들이 먼저 로드되도록)
  setTimeout(() => {
    window.chatBot = new ChatBot();
  }, 100);
});

// 전역에서 사용할 수 있도록 노출
window.ChatBot = ChatBot;