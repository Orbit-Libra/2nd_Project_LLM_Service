//헤더 푸터 기능 전담
//../static/js/common/header-footer.js
//모든 페이지에서 공용으로 헤더푸터가 사용됨
//헤더/푸터/챗봇 자동로드
//로그인 상태별 네비게이션 변경
//스크롤 기반 헤더 숨김/표시


class HeaderFooterManager {
  constructor() {
    this.headerLoaded = false;
    this.footerLoaded = false;
    this.chatbotLoaded = false;
    this.init();
  }

  async init() {
    try {
      await Promise.all([
        this.loadHeader(),
        this.loadFooter(),
        this.loadChatbot()
      ]);
      
      this.setupHeaderEvents();
      this.initHeaderScrollLogic();
      
      console.log('Header/Footer/Chatbot 로드 완료');
    } catch (error) {
      console.error('Header/Footer/Chatbot 로드 실패:', error);
      this.showFallback();
    }
  }

  async loadHeader() {
    try {
      const response = await fetch('./header.html');
      if (!response.ok) {
        throw new Error(`Header 로드 실패: ${response.status}`);
      }
      
      const html = await response.text();
      const headerArea = document.getElementById('header-area');
      
      if (headerArea) {
        headerArea.innerHTML = html;
        this.headerLoaded = true;
        
        // 헤더 로드 완료 이벤트 발생
        this.dispatchEvent('headerLoaded');
      }
    } catch (error) {
      console.error('Header 로드 에러:', error);
      this.createFallbackHeader();
    }
  }

  async loadFooter() {
    try {
      const response = await fetch('./footer.html');
      if (!response.ok) {
        throw new Error(`Footer 로드 실패: ${response.status}`);
      }
      
      const html = await response.text();
      const footerArea = document.getElementById('footer-area');
      
      if (footerArea) {
        footerArea.innerHTML = html;
        this.footerLoaded = true;
        
        // 푸터 로드 완료 이벤트 발생
        this.dispatchEvent('footerLoaded');
      }
    } catch (error) {
      console.error('Footer 로드 에러:', error);
      this.createFallbackFooter();
    }
  }

  async loadChatbot() {
    try {
      const response = await fetch('./chatbot.html');
      if (!response.ok) {
        throw new Error(`Chatbot 로드 실패: ${response.status}`);
      }
      
      const html = await response.text();
      
      // body 끝에 챗봇 HTML 추가
      document.body.insertAdjacentHTML('beforeend', html);
      this.chatbotLoaded = true;
      
      // 챗봇 로드 완료 이벤트 발생
      this.dispatchEvent('chatbotLoaded');
    } catch (error) {
      console.error('Chatbot 로드 에러:', error);
      this.createFallbackChatbot();
    }
  }

  setupHeaderEvents() {
    // 로고 클릭 이벤트
    const logoArea = document.getElementById('logo-area');
    if (logoArea) {
      logoArea.addEventListener('click', () => {
        // 현재 페이지 위치에 따라 다른 링크
        const currentPath = window.location.pathname;
        
        if (currentPath.includes('html/')) {
          // html 폴더 내의 페이지들 - 같은 폴더의 main.html로
          window.location.href = './main.html';
        } else {
          // 다른 폴더에서는 html 폴더의 main.html로
          window.location.href = './html/main.html';
        }
      });
      
      // 로고 호버 효과
      logoArea.addEventListener('mouseenter', () => {
        logoArea.style.transform = 'scale(1.05)';
      });
      
      logoArea.addEventListener('mouseleave', () => {
        logoArea.style.transform = 'scale(1)';
      });
    }

    // 로그인 상태에 따른 네비게이션 업데이트
    this.updateNavigationForLoginStatus();
    
    // 네비게이션 링크 활성화 상태 설정
    this.setActiveNavLink();
    
    // 네비게이션 호버 효과
    this.setupNavHoverEffects();
  }

  updateNavigationForLoginStatus() {
    const nav = document.getElementById('main-nav');
    if (!nav) return;

    // 로그인 상태 확인 (여러 방법으로 체크)
    const isLoggedIn = this.checkLoginStatus();
    
    if (isLoggedIn) {
      // 로그인된 상태 - Login을 마이페이지로 변경
      const loginLink = nav.querySelector('a[href*="devpage"]');
      if (loginLink) {
        loginLink.href = 'page_userpage_num01.html';
        loginLink.textContent = '마이페이지';
        loginLink.classList.add('logged-in');
      }
    } else {
      // 로그아웃 상태 - 마이페이지를 Login으로 변경
      const mypageLink = nav.querySelector('a[href*="userpage"]');
      if (mypageLink) {
        mypageLink.href = 'page_devpage_num01.html';
        mypageLink.textContent = 'Login';
        mypageLink.classList.remove('logged-in');
      }
    }
  }

  checkLoginStatus() {
    // 방법 1: 로컬스토리지에서 확인
    const authToken = localStorage.getItem('authToken');
    if (authToken) {
      // 토큰 유효성 검사 (선택사항)
      try {
        const tokenData = JSON.parse(atob(authToken.split('.')[1]));
        const currentTime = Date.now() / 1000;
        return tokenData.exp > currentTime;
      } catch {
        localStorage.removeItem('authToken');
        return false;
      }
    }

    // 방법 2: 세션스토리지에서 확인
    const sessionUser = sessionStorage.getItem('user');
    if (sessionUser) {
      return true;
    }

    // 방법 3: 쿠키에서 확인
    const userCookie = this.getCookie('user_session');
    if (userCookie) {
      return true;
    }

    // 방법 4: 서버에 API 요청으로 확인 (비동기)
    this.checkServerLoginStatus();

    return false;
  }

  async checkServerLoginStatus() {
    try {
      const response = await fetch('/api/check-login', {
        method: 'GET',
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        if (data.logged_in) {
          this.updateNavigationForLoginStatus();
        }
      }
    } catch (error) {
      console.log('서버 로그인 상태 확인 실패:', error);
    }
  }

  getCookie(name) {
    const nameEQ = name + "=";
    const ca = document.cookie.split(';');
    for (let i = 0; i < ca.length; i++) {
      let c = ca[i];
      while (c.charAt(0) === ' ') c = c.substring(1, c.length);
      if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
    }
    return null;
  }

  setActiveNavLink() {
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.nav-link');
    
    navLinks.forEach(link => {
      const href = link.getAttribute('href');
      
      // 현재 페이지와 링크가 일치하는지 확인
      if (currentPath.includes(href.replace('.html', ''))) {
        link.classList.add('active');
        link.style.color = 'var(--color-logo-text)';
      }
    });
  }

  setupNavHoverEffects() {
    const navLinks = document.querySelectorAll('.nav-link');
    
    navLinks.forEach(link => {
      link.addEventListener('mouseenter', () => {
        if (!link.classList.contains('active')) {
          link.style.transform = 'translateY(-0.2rem)';
        }
      });
      
      link.addEventListener('mouseleave', () => {
        if (!link.classList.contains('active')) {
          link.style.transform = 'translateY(0)';
        }
      });
    });
  }

  initHeaderScrollLogic() {
    const wrapper = document.querySelector('.sections-wrapper');
    const header = document.getElementById('site-header');
    const heroSlider = document.getElementById('hero-slider');
    
    if (!wrapper || !header) return;
    
    let lastScrollTop = 0;
    let scrollTimeout;
    
    const handleScroll = () => {
      const currentScroll = wrapper.scrollTop;
      
      // 스크롤 방향 감지
      if (currentScroll > lastScrollTop && currentScroll > 100) {
        // 아래로 스크롤 - 헤더 숨김
        header.classList.add('hidden');
      } else {
        // 위로 스크롤 - 헤더 표시
        header.classList.remove('hidden');
      }
      
      // Hero 섹션을 지나면 헤더 배경 변경
      if (heroSlider) {
        if (currentScroll > heroSlider.offsetHeight * 0.3) {
          header.style.background = 'rgba(13, 31, 45, 0.95)';
          header.style.backdropFilter = 'blur(0.5rem)';
        } else {
          header.style.background = '#0d1f2d';
          header.style.backdropFilter = 'none';
        }
      }
      
      lastScrollTop = currentScroll;
      
      // 스크롤 정지 감지
      clearTimeout(scrollTimeout);
      scrollTimeout = setTimeout(() => {
        header.classList.remove('hidden');
      }, 1000);
    };
    
    // 스크롤 이벤트 등록 (throttle 적용)
    let ticking = false;
    wrapper.addEventListener('scroll', () => {
      if (!ticking) {
        requestAnimationFrame(() => {
          handleScroll();
          ticking = false;
        });
        ticking = true;
      }
    });
  }

  createFallbackHeader() {
    const headerArea = document.getElementById('header-area');
    if (!headerArea) return;
    
    headerArea.innerHTML = `
      <header id="site-header">
        <div class="logo" id="logo-area">
          <img src="../static/images/logo.jpeg" alt="Libra Logo" id="logo-img">
          <span id="logo-text">Libra</span>
        </div>
        <nav id="main-nav">
          <a href="page_chartpage_num01.html" class="nav-link">학습환경 분석</a>
          <a href="page_prediction_num01.html" class="nav-link">발전도 분석</a>
          <a href="page_devpage_num01.html" class="nav-link">Login</a>
        </nav>
      </header>
    `;
    
    console.log('Fallback 헤더 생성됨');
    this.setupHeaderEvents();
  }

  createFallbackFooter() {
    const footerArea = document.getElementById('footer-area');
    if (!footerArea) return;
    
    footerArea.innerHTML = `
      <footer id="site-footer">
        &copy; 2025 Libra. All rights reserved.
      </footer>
    `;
    
    console.log('Fallback 푸터 생성됨');
  }

  createFallbackChatbot() {
    const chatbotHTML = `
      <!-- Chatbot Toggle -->
      <div class="chatbot" id="chatToggle">
          <div class="chat-icon">
              <img src="../static/images/chatbot.png" alt="Chatbot" id="chatbot-img">
          </div>
      </div>

      <!-- Chatbot Window -->
      <div class="chat-window" id="chatWindow">
          <div class="chat-header">
              <span>AI Chat</span>
              <button id="chatCloseBtn" aria-label="Close">&times;</button>
          </div>
          <div class="chat-body" id="chatBody"></div>
          <div class="chat-input">
              <input type="text" id="chatInput" placeholder="메시지를 입력하세요...">
              <button id="chatSendBtn">전송</button>
          </div>
      </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', chatbotHTML);
    console.log('Fallback 챗봇 생성됨');
  }

  showFallback() {
    if (!this.headerLoaded) {
      this.createFallbackHeader();
    }
    if (!this.footerLoaded) {
      this.createFallbackFooter();
    }
    if (!this.chatbotLoaded) {
      this.createFallbackChatbot();
    }
  }

  // 커스텀 이벤트 발생
  dispatchEvent(eventName, data = {}) {
    const event = new CustomEvent(eventName, {
      detail: data
    });
    document.dispatchEvent(event);
  }

  // 헤더 표시/숨김 제어
  showHeader() {
    const header = document.getElementById('site-header');
    if (header) {
      header.classList.remove('hidden');
    }
  }

  hideHeader() {
    const header = document.getElementById('site-header');
    if (header) {
      header.classList.add('hidden');
    }
  }

  // 헤더 배경 변경
  setHeaderBackground(background) {
    const header = document.getElementById('site-header');
    if (header) {
      header.style.background = background;
    }
  }

  // 현재 페이지 감지
  getCurrentPage() {
    const path = window.location.pathname;
    
    if (path.includes('main')) return 'main';
    if (path.includes('chartpage')) return 'chart';
    if (path.includes('prediction')) return 'prediction';
    if (path.includes('userpage')) return 'user';
    if (path.includes('devpage')) return 'dev';
    
    return 'unknown';
  }

  // 네비게이션 업데이트
  updateNavigation(activePage) {
    const navLinks = document.querySelectorAll('.nav-link');
    
    navLinks.forEach(link => {
      link.classList.remove('active');
      link.style.color = '#fff';
    });
    
    // 활성 페이지 표시
    const activeLink = document.querySelector(`[href*="${activePage}"]`);
    if (activeLink) {
      activeLink.classList.add('active');
      activeLink.style.color = 'var(--color-logo-text)';
    }
  }

  // 디버그 정보
  getDebugInfo() {
    return {
      headerLoaded: this.headerLoaded,
      footerLoaded: this.footerLoaded,
      chatbotLoaded: this.chatbotLoaded,
      currentPage: this.getCurrentPage(),
      headerVisible: !document.getElementById('site-header')?.classList.contains('hidden')
    };
  }
}

// DOM 로드 완료 후 초기화
document.addEventListener('DOMContentLoaded', () => {
  window.headerFooterManager = new HeaderFooterManager();
});

// 전역에서 사용할 수 있도록 노출
window.HeaderFooterManager = HeaderFooterManager;