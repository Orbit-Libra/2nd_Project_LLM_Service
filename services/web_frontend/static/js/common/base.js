// static/js/common/base.js
// 전역: 네이티브 스크롤바 숨김 + 우측 고정 오버레이 썸/화살표.
// 개선점: 드래그 중 스냅/스무스 OFF(탄성 제거), 드래그 대상 잠금, rAF 기반 업데이트.

(function () {
  const SHOW_DELAY     = 700;   // 스크롤 멈춘 뒤 감춤
  const EDGE_DELAY     = 800;   // 우측 근접 해제 지연
  const EDGE_THRESHOLD = 16;    // 화면 오른쪽 16px 근접
  const MIN_THUMB      = 28;    // 최소 썸 높이
  const PAGE_FACTOR    = 0.9;   // 페이지 이동 비율
  const HOLD_INTERVAL  = 28;    // 화살표 길게 누르기 반복주기

  // 오버레이 UI
  const bar     = document.createElement('div');
  const thumb   = document.createElement('div');
  const arrowUp = document.createElement('button');
  const arrowDn = document.createElement('button');
  bar.className = 'osb-float';
  thumb.className = 'osb-thumb';
  arrowUp.className = 'osb-arrow up';
  arrowDn.className = 'osb-arrow down';
  arrowUp.type = 'button'; arrowDn.type = 'button';
  bar.appendChild(thumb); bar.appendChild(arrowUp); bar.appendChild(arrowDn);

  let activeScroller = null;      // 현재 대상(루트/컨테이너)
  let scrolling = false;
  let edgeActive = false;
  let hideTimer = null, edgeTimer = null, holdTimer = null;

  // 드래그 상태
  const drag = {
    active: false,
    scroller: null,               // 드래그 시작 시 잠금
    offsetY: 0,                   // 포인터와 썸 상단 간 거리
    targetScrollTop: null,        // rAF 타겟 스크롤
    rafId: null,
  };

  // 헬퍼
  const rootScroller = () => document.scrollingElement || document.documentElement;
  const clamp = (v, min, max) => Math.max(min, Math.min(max, v));
  const isScrollable = el => {
    if (!el) return false;
    const sh = el.scrollHeight;
    const ch = (el === rootScroller()) ? window.innerHeight : el.clientHeight;
    return sh > ch + 1;
  };

  // 화면 우측 끝에서 Y위치에 해당하는 스크롤러 찾기
  function findScrollerAtY(clientY) {
    const x = window.innerWidth - 1;
    const stack = document.elementsFromPoint(x, clientY);
    for (const el of stack) {
      if (!(el instanceof Element)) continue;
      const cs = getComputedStyle(el);
      const mayScroll = /(auto|scroll)/.test(cs.overflowY) || /(auto|scroll)/.test(cs.overflow);
      if (mayScroll && isScrollable(el)) return el;
    }
    return isScrollable(rootScroller()) ? rootScroller() : null;
  }

  function getMetrics(scroller) {
    if (!scroller) return null;
    if (scroller === rootScroller()) {
      const sh = scroller.scrollHeight, ch = window.innerHeight, st = scroller.scrollTop;
      const trackTop = 0, trackH = window.innerHeight;
      const thumbH = Math.max(MIN_THUMB, (trackH * ch) / sh);
      const maxTop = Math.max(0, trackH - thumbH);
      return { sh, ch, st, trackTop, trackH, thumbH, maxTop, isRoot: true };
    } else {
      const r = scroller.getBoundingClientRect();
      const sh = scroller.scrollHeight, ch = scroller.clientHeight, st = scroller.scrollTop;
      const trackTop = clamp(r.top, 0, window.innerHeight);
      const trackH = Math.max(0, clamp(r.bottom, 0, window.innerHeight) - trackTop);
      const thumbH = Math.max(MIN_THUMB, (trackH * ch) / sh);
      const maxTop = Math.max(0, trackH - thumbH);
      return { sh, ch, st, trackTop, trackH, thumbH, maxTop, isRoot: false };
    }
  }

  function updateFromScroller(scroller) {
    activeScroller = scroller;
    const m = getMetrics(scroller);
    if (!m || m.sh <= m.ch + 1 || m.trackH <= 0) {
      bar.classList.remove('osb--show');
      return;
    }
    thumb.style.height = `${Math.round(m.thumbH)}px`;
    const top = m.trackTop + (m.st / (m.sh - m.ch)) * m.maxTop;
    thumb.style.transform = `translateY(${Math.round(top)}px)`;
  }

  function showFor(ms) {
    bar.classList.add('osb--show');
    clearTimeout(hideTimer);
    hideTimer = setTimeout(() => {
      scrolling = false;
      if (!edgeActive && !drag.active) bar.classList.remove('osb--show');
    }, ms);
  }

  // 드래그 중 스냅/스무스 OFF
  function setDragScrollMode(on) {
    const sc = drag.scroller || activeScroller || rootScroller();
    const htmlEl = document.documentElement;
    if (sc === rootScroller()) {
      htmlEl.classList.toggle('no-snap', on);
      htmlEl.classList.toggle('no-smooth', on);
    } else if (sc instanceof Element) {
      sc.classList.toggle('no-snap', on);
      sc.classList.toggle('no-smooth', on);
    }
  }

  // rAF 루프: targetScrollTop 반영
  function dragTick() {
    if (!drag.active || drag.targetScrollTop == null) {
      drag.rafId = null;
      return;
    }
    const sc = drag.scroller;
    sc.scrollTop = drag.targetScrollTop;
    updateFromScroller(sc);
    drag.rafId = requestAnimationFrame(dragTick);
  }

  // 페이지 단위 스크롤
  function pageScroll(scroller, dir) {
    if (!scroller) return;
    const step = Math.max(40, (scroller === rootScroller() ? window.innerHeight : scroller.clientHeight) * PAGE_FACTOR);
    if (scroller === rootScroller()) {
      scroller.scrollTop += dir * step; // window.scrollBy 도 OK
    } else {
      scroller.scrollTop += dir * step;
    }
  }

  // ===== 이벤트 바인딩 =====
  document.addEventListener('DOMContentLoaded', () => {
    document.body.appendChild(bar);
    const sc = findScrollerAtY(window.innerHeight / 2) || rootScroller();
    updateFromScroller(sc);
  });

  // 루트 스크롤
  window.addEventListener('scroll', () => {
    const sc = rootScroller();
    if (!isScrollable(sc)) return;
    scrolling = true;
    updateFromScroller(sc);
    showFor(SHOW_DELAY);
  }, { passive: true });

  // 요소 스크롤(캡처 단계)
  document.addEventListener('scroll', (e) => {
    const t = e.target;
    if (!(t instanceof Element)) return;
    if (!isScrollable(t)) return;
    scrolling = true;
    updateFromScroller(t);
    showFor(SHOW_DELAY);
  }, { passive: true, capture: true });

  // 우측 근접 표시
  window.addEventListener('mousemove', (e) => {
    const nearRight = (window.innerWidth - e.clientX) <= EDGE_THRESHOLD;
    if (nearRight) {
      edgeActive = true;
      const sc = findScrollerAtY(e.clientY) || activeScroller || rootScroller();
      updateFromScroller(sc);
      bar.classList.add('osb--show');
      clearTimeout(edgeTimer);
      edgeTimer = setTimeout(() => {
        edgeActive = false;
        if (!scrolling && !drag.active) bar.classList.remove('osb--show');
      }, EDGE_DELAY);
    }
  }, { passive: true });

  window.addEventListener('resize', () => {
    if (activeScroller) updateFromScroller(activeScroller);
  });

  // ==== 썸 드래그 ====
  thumb.addEventListener('mousedown', (e) => {
    e.preventDefault();
    document.documentElement.classList.add('osb-dragging');

    // 드래그 시작: 대상 잠금 + 탄성 방지 모드
    drag.active = true;
    drag.scroller = findScrollerAtY(e.clientY) || activeScroller || rootScroller();
    setDragScrollMode(true);

    // 오프셋 계산
    const rect = thumb.getBoundingClientRect();
    drag.offsetY = e.clientY - rect.top;
    updateFromScroller(drag.scroller);
    bar.classList.add('osb--show');
  });

  window.addEventListener('mousemove', (e) => {
    if (!drag.active) return;
    const m = getMetrics(drag.scroller);
    if (!m || m.maxTop <= 0) return;

    const wantedTop = clamp(e.clientY - drag.offsetY - m.trackTop, 0, m.maxTop);
    const newScroll = (wantedTop / m.maxTop) * (m.sh - m.ch);
    drag.targetScrollTop = newScroll;

    if (!drag.rafId) drag.rafId = requestAnimationFrame(dragTick);
  });

  window.addEventListener('mouseup', () => {
    if (!drag.active) return;
    drag.active = false;
    document.documentElement.classList.remove('osb-dragging');

    // rAF 종료 + 모드 복구
    if (drag.rafId) cancelAnimationFrame(drag.rafId);
    drag.rafId = null;
    setDragScrollMode(false);

    // 상태 초기화
    drag.scroller = null;
    drag.targetScrollTop = null;

    if (!edgeActive && !scrolling) bar.classList.remove('osb--show');
  });

  // ==== 화살표 클릭/홀드 ====
  function startHold(dir) {
    stopHold();
    holdTimer = setInterval(() => {
      const sc = activeScroller || rootScroller();
      pageScroll(sc, dir);
      updateFromScroller(sc);
      bar.classList.add('osb--show');
    }, HOLD_INTERVAL);
  }
  function stopHold() { if (holdTimer) { clearInterval(holdTimer); holdTimer = null; } }

  arrowUp.addEventListener('click', () => {
    const sc = activeScroller || rootScroller();
    pageScroll(sc, -1);
    updateFromScroller(sc);
    showFor(SHOW_DELAY);
  });
  arrowDn.addEventListener('click', () => {
    const sc = activeScroller || rootScroller();
    pageScroll(sc, +1);
    updateFromScroller(sc);
    showFor(SHOW_DELAY);
  });
  arrowUp.addEventListener('mousedown', () => startHold(-1));
  arrowDn.addEventListener('mousedown', () => startHold(+1));
  window.addEventListener('mouseup', stopHold);
  window.addEventListener('blur', stopHold);
})();
