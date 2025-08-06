//공통 유틸리티 함수들
//../static/js/common/utils.js
//로깅,DOM조작,배열/숫자/문자열처리
//이벤트 관리,색상 생성,로컬 스토리지
//Ajax요청, 검증 함수들
//전역 에러 핸들링

// js/common/utils.js - 공통 유틸리티 함수들
const Utils = {
  
  // DOM 관련 유틸리티
  DOM: {
    // 요소 선택
    $(selector) {
      return document.querySelector(selector);
    },
    
    $$(selector) {
      return document.querySelectorAll(selector);
    },
    
    // 요소 생성
    create(tag, options = {}) {
      const element = document.createElement(tag);
      
      if (options.className) {
        element.className = options.className;
      }
      
      if (options.id) {
        element.id = options.id;
      }
      
      if (options.innerHTML) {
        element.innerHTML = options.innerHTML;
      }
      
      if (options.textContent) {
        element.textContent = options.textContent;
      }
      
      if (options.attributes) {
        Object.entries(options.attributes).forEach(([key, value]) => {
          element.setAttribute(key, value);
        });
      }
      
      if (options.styles) {
        Object.assign(element.style, options.styles);
      }
      
      return element;
    },
    
    // 이벤트 리스너 등록 (한 번만 실행)
    once(element, event, callback) {
      element.addEventListener(event, callback, { once: true });
    },
    
    // 요소가 뷰포트에 있는지 확인
    isInViewport(element) {
      const rect = element.getBoundingClientRect();
      return (
        rect.top >= 0 &&
        rect.left >= 0 &&
        rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
        rect.right <= (window.innerWidth || document.documentElement.clientWidth)
      );
    },
    
    // 부드러운 스크롤
    smoothScroll(target, duration = 500) {
      const targetElement = typeof target === 'string' ? this.$(target) : target;
      if (!targetElement) return;
      
      targetElement.scrollIntoView({
        behavior: 'smooth',
        block: 'start'
      });
    }
  },

  // 디바이스 감지
  Device: {
    // 모바일 감지
    isMobile() {
      return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
             window.innerWidth <= 768;
    },
    
    // 태블릿 감지
    isTablet() {
      return /iPad|Android/i.test(navigator.userAgent) && 
             window.innerWidth > 768 && window.innerWidth <= 1024;
    },
    
    // 데스크톱 감지
    isDesktop() {
      return !this.isMobile() && !this.isTablet();
    },
    
    // 터치 디바이스 감지
    isTouchDevice() {
      return 'ontouchstart' in window || navigator.maxTouchPoints > 0;
    },
    
    // 뷰포트 크기
    getViewportSize() {
      return {
        width: window.innerWidth,
        height: window.innerHeight
      };
    },
    
    // 디바이스 타입 반환
    getDeviceType() {
      if (this.isMobile()) return 'mobile';
      if (this.isTablet()) return 'tablet';
      return 'desktop';
    }
  },

  // 데이터 검증
  Validation: {
    // 이메일 형식 검증
    isEmail(email) {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      return emailRegex.test(email);
    },
    
    // 전화번호 형식 검증 (한국)
    isPhoneNumber(phone) {
      const phoneRegex = /^01[016789]-?\d{3,4}-?\d{4}$/;
      return phoneRegex.test(phone);
    },
    
    // 빈 값 검증
    isEmpty(value) {
      return value === null || value === undefined || value === '' || 
             (Array.isArray(value) && value.length === 0) ||
             (typeof value === 'object' && Object.keys(value).length === 0);
    },
    
    // 숫자 검증
    isNumber(value) {
      return !isNaN(value) && !isNaN(parseFloat(value));
    },
    
    // URL 검증
    isURL(url) {
      try {
        new URL(url);
        return true;
      } catch {
        return false;
      }
    }
  },

  // 포맷팅 유틸리티
  Format: {
    // 숫자 천단위 콤마
    numberWithCommas(num) {
      return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    },
    
    // 파일 크기 포맷
    fileSize(bytes) {
      if (bytes === 0) return '0 Bytes';
      const k = 1024;
      const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },
    
    // 날짜 포맷
    date(date, format = 'YYYY-MM-DD') {
      const d = new Date(date);
      const year = d.getFullYear();
      const month = String(d.getMonth() + 1).padStart(2, '0');
      const day = String(d.getDate()).padStart(2, '0');
      const hours = String(d.getHours()).padStart(2, '0');
      const minutes = String(d.getMinutes()).padStart(2, '0');
      const seconds = String(d.getSeconds()).padStart(2, '0');
      
      return format
        .replace('YYYY', year)
        .replace('MM', month)
        .replace('DD', day)
        .replace('HH', hours)
        .replace('mm', minutes)
        .replace('ss', seconds);
    },
    
    // 상대 시간 (몇 분 전, 몇 시간 전 등)
    timeAgo(date) {
      const now = new Date();
      const diffInSeconds = Math.floor((now - new Date(date)) / 1000);
      
      if (diffInSeconds < 60) return '방금 전';
      if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}분 전`;
      if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}시간 전`;
      if (diffInSeconds < 2592000) return `${Math.floor(diffInSeconds / 86400)}일 전`;
      if (diffInSeconds < 31536000) return `${Math.floor(diffInSeconds / 2592000)}달 전`;
      return `${Math.floor(diffInSeconds / 31536000)}년 전`;
    },
    
    // 텍스트 자르기
    truncate(text, length = 100, suffix = '...') {
      if (text.length <= length) return text;
      return text.slice(0, length) + suffix;
    }
  },

  // 성능 유틸리티
  Performance: {
    // 쓰로틀링
    throttle(func, delay) {
      let timeoutId;
      let lastExecTime = 0;
      
      return function (...args) {
        const currentTime = Date.now();
        
        if (currentTime - lastExecTime > delay) {
          func.apply(this, args);
          lastExecTime = currentTime;
        } else {
          clearTimeout(timeoutId);
          timeoutId = setTimeout(() => {
            func.apply(this, args);
            lastExecTime = Date.now();
          }, delay - (currentTime - lastExecTime));
        }
      };
    },
    
    // 디바운싱
    debounce(func, delay) {
      let timeoutId;
      return function (...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => func.apply(this, args), delay);
      };
    },
    
    // RAF 기반 쓰로틀링
    rafThrottle(func) {
      let ticking = false;
      return function (...args) {
        if (!ticking) {
          requestAnimationFrame(() => {
            func.apply(this, args);
            ticking = false;
          });
          ticking = true;
        }
      };
    }
  },

  // 스토리지 유틸리티
  Storage: {
    // 로컬 스토리지
    set(key, value) {
      try {
        localStorage.setItem(key, JSON.stringify(value));
        return true;
      } catch (error) {
        console.error('Storage set error:', error);
        return false;
      }
    },
    
    get(key, defaultValue = null) {
      try {
        const item = localStorage.getItem(key);
        return item ? JSON.parse(item) : defaultValue;
      } catch (error) {
        console.error('Storage get error:', error);
        return defaultValue;
      }
    },
    
    remove(key) {
      try {
        localStorage.removeItem(key);
        return true;
      } catch (error) {
        console.error('Storage remove error:', error);
        return false;
      }
    },
    
    clear() {
      try {
        localStorage.clear();
        return true;
      } catch (error) {
        console.error('Storage clear error:', error);
        return false;
      }
    },
    
    // 세션 스토리지
    session: {
      set(key, value) {
        try {
          sessionStorage.setItem(key, JSON.stringify(value));
          return true;
        } catch (error) {
          console.error('Session storage set error:', error);
          return false;
        }
      },
      
      get(key, defaultValue = null) {
        try {
          const item = sessionStorage.getItem(key);
          return item ? JSON.parse(item) : defaultValue;
        } catch (error) {
          console.error('Session storage get error:', error);
          return defaultValue;
        }
      },
      
      remove(key) {
        try {
          sessionStorage.removeItem(key);
          return true;
        } catch (error) {
          console.error('Session storage remove error:', error);
          return false;
        }
      }
    }
  },

  // HTTP 요청 유틸리티
  HTTP: {
    // GET 요청
    async get(url, options = {}) {
      try {
        const response = await fetch(url, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            ...options.headers
          },
          ...options
        });
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
      } catch (error) {
        console.error('GET request error:', error);
        throw error;
      }
    },
    
    // POST 요청
    async post(url, data, options = {}) {
      try {
        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...options.headers
          },
          body: JSON.stringify(data),
          ...options
        });
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
      } catch (error) {
        console.error('POST request error:', error);
        throw error;
      }
    },
    
    // 파일 다운로드
    downloadFile(url, filename) {
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  },

  // 애니메이션 유틸리티
  Animation: {
    // 페이드 인
    fadeIn(element, duration = 300) {
      element.style.opacity = '0';
      element.style.display = 'block';
      
      const start = performance.now();
      
      const animate = (currentTime) => {
        const elapsed = currentTime - start;
        const progress = Math.min(elapsed / duration, 1);
        
        element.style.opacity = progress;
        
        if (progress < 1) {
          requestAnimationFrame(animate);
        }
      };
      
      requestAnimationFrame(animate);
    },
    
    // 페이드 아웃
    fadeOut(element, duration = 300) {
      const start = performance.now();
      const startOpacity = parseFloat(getComputedStyle(element).opacity);
      
      const animate = (currentTime) => {
        const elapsed = currentTime - start;
        const progress = Math.min(elapsed / duration, 1);
        
        element.style.opacity = startOpacity * (1 - progress);
        
        if (progress < 1) {
          requestAnimationFrame(animate);
        } else {
          element.style.display = 'none';
        }
      };
      
      requestAnimationFrame(animate);
    },
    
    // 슬라이드 업
    slideUp(element, duration = 300) {
      const height = element.offsetHeight;
      element.style.transition = `height ${duration}ms ease`;
      element.style.height = height + 'px';
      element.offsetHeight; // 리플로우 강제
      element.style.height = '0px';
      
      setTimeout(() => {
        element.style.display = 'none';
        element.style.transition = '';
        element.style.height = '';
      }, duration);
    }
  },

  // 기타 유틸리티
  Misc: {
    // 랜덤 ID 생성
    generateId(length = 8) {
      return Math.random().toString(36).substr(2, length);
    },
    
    // 배열 섞기
    shuffleArray(array) {
      const shuffled = [...array];
      for (let i = shuffled.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
      }
      return shuffled;
    },
    
    // 딥 클론
    deepClone(obj) {
      return JSON.parse(JSON.stringify(obj));
    },
    
    // 객체 병합
    mergeObjects(target, ...sources) {
      return Object.assign({}, target, ...sources);
    },
    
    // 쿼리 파라미터 파싱
    parseQueryParams() {
      const params = new URLSearchParams(window.location.search);
      const result = {};
      for (const [key, value] of params) {
        result[key] = value;
      }
      return result;
    },
    
    // 쿠키 설정/가져오기
    setCookie(name, value, days = 7) {
      const expires = new Date();
      expires.setTime(expires.getTime() + (days * 24 * 60 * 60 * 1000));
      document.cookie = `${name}=${value};expires=${expires.toUTCString()};path=/`;
    },
    
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
  }
};

// 전역에서 사용할 수 있도록 노출
window.Utils = Utils;