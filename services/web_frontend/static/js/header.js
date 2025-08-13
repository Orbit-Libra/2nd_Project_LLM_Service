// static/js/header.js
document.addEventListener("DOMContentLoaded", function () {
  // href가 /logout으로 끝나는 a 태그 선택
  const logoutLink = document.querySelector('a[href$="/logout"]');
  if (logoutLink) {
    logoutLink.addEventListener("click", function (e) {
      if (!confirm("로그아웃 하시겠습니까?")) {
        e.preventDefault(); // 이동 취소
      }
    });
  }
});
