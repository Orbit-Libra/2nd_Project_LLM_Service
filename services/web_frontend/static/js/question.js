// static/js/question.js
//Q&A 작성 페이지(question.html): 폼 검증/제출 로직
//상세 페이지(detail.html): 페이드인 + 조회수 1회 증가 + 좋아요 버튼
//목록 페이지(list.html): 페이드인

document.addEventListener('DOMContentLoaded', () => {
  // -----------------------------
  // 0) 공통: 페이드 인
  // -----------------------------
  (function () {
    const rootScroller = document.getElementById('sections-wrapper') || null;
    const els = document.querySelectorAll('.fade-in');
    if (!('IntersectionObserver' in window)) {
      els.forEach(el => el.classList.add('appear'));
      return;
    }
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) { e.target.classList.add('appear'); io.unobserve(e.target); }
      });
    }, { root: rootScroller, threshold: 0.15 });
    els.forEach(el => io.observe(el));
  })();

  // -----------------------------
  // 1) 공통: 스크롤 탑(있을 때만)
  // -----------------------------
  document.getElementById('scrollTopBtn')?.addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

 // -----------------------------
  // 2) Q&A 작성 폼(question.html) — 폼 검증 + 제출
  // -----------------------------
  (function () {
    const form = document.getElementById('qnaForm');
    if (!form) return; // 이 페이지에 폼이 없으면 skip

    const isEmail = (v) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v || "");

    const showError = (input, msg) => {
      const field = input.closest('.field') || input.parentElement || input;
      let small = field.querySelector('small.error');
      if (!small) {
        small = document.createElement('small');
        small.className = 'error';
        field.appendChild(small);
      }
      small.textContent = msg;
      input.setAttribute('aria-invalid', 'true');
    };

    const clearError = (input) => {
      const field = input.closest('.field') || input.parentElement || input;
      const small = field.querySelector('small.error');
      if (small) small.textContent = '';
      input.removeAttribute('aria-invalid');
    };

  form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const title    = form.title;
      const email    = form.email;
      const content  = form.content;
      const agree    = form.agree;
      const kind     = form.kind;           // 선택
      const filesInp = form.files;          // <input type="file" name="files" multiple>
      const isPublic = form.is_public;      // 공개/비공개

      let ok = true;

      if (!title.value.trim()) { showError(title, '제목은 필수입니다.'); ok = false; } else clearError(title);
      if (!isEmail(email.value.trim())) { showError(email, '유효한 이메일을 입력하세요.'); ok = false; } else clearError(email);
      if ((content.value.trim().length) < 10) { showError(content, '문의 내용은 10자 이상 입력하세요.'); ok = false; } else clearError(content);
      if (!agree.checked) { showError(agree, '개인정보 수집 및 이용에 동의해주세요.'); ok = false; } else clearError(agree);
      if (kind && !kind.value) { showError(kind, '종류를 선택하세요.'); ok = false; } else if (kind) clearError(kind);

      // 파일 검증(있을 때만)
      const maxEach = 10 * 1024 * 1024; // 10MB
      const allowExt = ['jpg','jpeg','png','gif','pdf','txt','doc','docx','xls','xlsx','ppt','pptx'];
      if (filesInp && filesInp.files) {
        if (filesInp.files.length > 5) {
          showError(filesInp, '첨부는 최대 5개까지 가능합니다.'); ok = false;
        } else {
          for (const f of filesInp.files) {
            const ext = (f.name.split('.').pop() || '').toLowerCase();
            if (f.size > maxEach) { showError(filesInp, '파일당 최대 10MB까지 가능합니다.'); ok = false; break; }
            if (!allowExt.includes(ext)) { showError(filesInp, '허용되지 않는 파일 형식입니다.'); ok = false; break; }
          }
          if (ok) clearError(filesInp);
        }
      }
      if (!ok) return;

    // AJAX 제출(부드러운 UX)
    const fd = new FormData(form);
    try {
      const r = await fetch(form.action, {
        method: 'POST',
        body: fd,
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      });
      const data = await r.json();
      if (!r.ok || !data.ok) throw data;
      window.location.href = data.redirect;
    } catch (err) {
      // 서버가 보낸 필드 에러 반영
      if (err && err.errors) {
        if (err.errors.title) showError(title, err.errors.title);
        if (err.errors.email) showError(email, err.errors.email);
        if (err.errors.content) showError(content, err.errors.content);
        if (err.errors.agree) showError(agree, err.errors.agree);
        if (kind && err.errors.kind) showError(kind, err.errors.kind);
      } else {
        alert('제출 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
      }
    }
  });
})();

  // -----------------------------
  // 3) 상세 페이지(detail.html) — 조회수 1회 증가 + 좋아요
  // -----------------------------
  (function () {
    // detail 페이지가 아니면 skip
    const detailRoot = document.getElementById('qnaDetail');
    if (!detailRoot) return;

    // postId 가져오기: data-post-id 우선, 실패 시 URL에서 추정(/qna/123 형태)
    const postId = (detailRoot.dataset && detailRoot.dataset.postId)
      ? detailRoot.dataset.postId
      : (location.pathname.match(/\/qna\/(\d+)/)?.[1] || null);

    if (!postId) return;

    // 조회수: 상세 진입 시 1회 호출 (실패 무시)
    fetch(`/api/qna/posts/${postId}/view`, { method: 'POST' }).catch(() => {});

    // 좋아요
    const likeBtn = document.getElementById('likeBtn');
    const likeCnt = document.getElementById('likeCnt');
    likeBtn?.addEventListener('click', async () => {
      try {
        const r = await fetch(`/api/qna/posts/${postId}/like`, { method: 'POST' });
        const j = await r.json();
        if (j.success) {
          if (likeCnt) likeCnt.textContent = String((parseInt(likeCnt.textContent || '0', 10) + 1));
        } else {
          alert(j.error || '이미 좋아요를 누르셨습니다.');
        }
      } catch (e) { console.log(e); }
    });
  })();
});


