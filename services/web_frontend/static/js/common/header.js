// static/js/header.js - 헤더 전용 스크립트

document.addEventListener("DOMContentLoaded", () => {
  console.log('=== Header script loading ===');
  confirmLogout();
  // 메인 페이지 스크립트가 로드된 후 헤더 설정
  setTimeout(() => {
    console.log('=== Starting header setup ===');
    setupFloatingHeaderGlobal();
  }, 300);
});

function confirmLogout() {
  const logoutLink = document.querySelector('#site-header a[href$="/logout"]');
  if (!logoutLink) return;
  logoutLink.addEventListener("click", (e) => {
    if (!confirm("로그아웃 하시겠습니까?")) e.preventDefault();
  });
}

function setupFloatingHeaderGlobal() {
  console.log('=== setupFloatingHeaderGlobal START ===');
  
  const header = document.getElementById('site-header');
  if (!header) {
    console.error('❌ Header element not found!');
    return;
  }
  console.log('✅ Header found:', header);

  // 플로팅 버튼 없으면 동적 생성
  let btn = document.getElementById('floating-header-btn');
  if (!btn) {
    console.log('Creating floating button...');
    btn = document.createElement('div');
    btn.id = 'floating-header-btn';
    btn.setAttribute('aria-label', 'Show header');
    document.body.appendChild(btn);
    console.log('✅ Button created and added to body');
  } else {
    console.log('✅ Button already exists');
  }

  // 스크롤 기준 결정
  const wrapper = document.getElementById('sections-wrapper');
  console.log('Wrapper element:', wrapper);
  
  const scroller = wrapper || window;
  console.log('Using scroller:', scroller === window ? 'window' : 'wrapper element');

  const getScrollTop = () => {
    let scrollTop;
    if (scroller === window) {
      scrollTop = window.scrollY || window.pageYOffset || document.documentElement.scrollTop || 0;
    } else {
      scrollTop = wrapper.scrollTop || 0;
    }
    return scrollTop;
  };

  const THRESHOLD = 120;
  let pinned = false;
  let hideTimer = null;
  let ticking = false;

  const updateByScroll = () => {
    const scrollTop = getScrollTop();
    const scrolled = scrollTop > THRESHOLD;
    
    console.log('📊 Scroll Update:', { 
      scrollTop, 
      threshold: THRESHOLD, 
      scrolled, 
      pinned,
      headerClasses: header.className,
      buttonClasses: btn.className
    });
    
    if (scrolled && !pinned) {
      console.log('🔽 Hiding header');
      header.classList.add('hidden');
      header.classList.remove('floating-hover');
      showBtn();
    } else if (!scrolled) {
      console.log('🔼 Showing header');
      header.classList.remove('hidden', 'floating-hover');
      hideBtn();
    }
  };

  const onScroll = () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => {
      updateByScroll();
      ticking = false;
    });
  };

  // 초기 상태 확인
  console.log('Initial scroll position:', getScrollTop());
  updateByScroll();
  
  // 스크롤 이벤트 리스너 등록
  if (scroller === window) {
    console.log('Adding window scroll listener');
    window.addEventListener('scroll', onScroll, { passive: true });
  } else {
    console.log('Adding wrapper scroll listener');
    scroller.addEventListener('scroll', onScroll, { passive: true });
  }
  
  window.addEventListener('resize', onScroll);

  // 수동 테스트를 위한 전역 함수
  window.testHeaderHide = () => {
    console.log('Manual test: hiding header');
    header.classList.add('hidden');
    showBtn();
  };
  
  window.testHeaderShow = () => {
    console.log('Manual test: showing header');
    header.classList.remove('hidden');
    hideBtn();
  };

  // 버튼/헤더 인터랙션
  const showTemporarily = () => {
    console.log('🎯 Show temporarily triggered');
    pinned = true;
    header.classList.remove('hidden');
    header.classList.add('floating-hover');
    hideBtn();
    if (hideTimer) { 
      clearTimeout(hideTimer); 
      hideTimer = null; 
    }
  };

  const maybeHide = () => {
    console.log('🎯 Maybe hide triggered');
    pinned = false;
    header.classList.remove('floating-hover');
    if (getScrollTop() > THRESHOLD) {
      header.classList.add('hidden');
      showBtn();
    } else {
      header.classList.remove('hidden');
      hideBtn();
    }
  };

  // 버튼 이벤트
  btn.addEventListener('mouseenter', () => {
    console.log('🖱️ Button mouseenter');
    showTemporarily();
  });
  
  btn.addEventListener('click', () => {
    console.log('🖱️ Button click');
    if (header.classList.contains('hidden')) {
      showTemporarily();
    } else {
      maybeHide();
    }
  });

  // 헤더 이벤트
  header.addEventListener('mouseenter', () => {
    console.log('🖱️ Header mouseenter');
    showTemporarily();
  });
  
  header.addEventListener('mouseleave', () => { 
    console.log('🖱️ Header mouseleave');
    hideTimer = setTimeout(maybeHide, 140); 
  });

  function showBtn() { 
    console.log('🔘 Show button');
    btn.classList.remove('hiddenBtn'); 
    btn.classList.add('visible'); 
  }
  
  function hideBtn() { 
    console.log('🔘 Hide button');
    btn.classList.remove('visible'); 
    btn.classList.add('hiddenBtn'); 
  }

  console.log('=== Header setup complete ===');
  console.log('💡 Test commands available:');
  console.log('   testHeaderHide() - manually hide header');
  console.log('   testHeaderShow() - manually show header');
}