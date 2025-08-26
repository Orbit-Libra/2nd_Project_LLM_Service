// services/web_frontend/static/js/agent.js

(function () {
  const $ = (s, d=document) => d.querySelector(s);

  // --- 차트 자리 표시 (데이터 없이 빈 차트) ---
  let chart;
  function initEmptyChart() {
    const ctx = $("#agentChart").getContext("2d");
    chart = new Chart(ctx, {
      type: "line",
      data: {
        labels: ["Y1","Y2","Y3"],
        datasets: [{ label: "예시 시리즈", data: [null, null, null] }]
      },
      options: { responsive: true, interaction: { mode: 'index', intersect: false } }
    });
  }

  // --- 채팅 UI만 동작 (아직 백엔드 연동 X) ---
  function appendMsg(text, role="user") {
    const box = $("#chatWindow");
    const div = document.createElement("div");
    div.className = `msg ${role}`;
    div.textContent = text;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
  }

  function wireChat() {
    const input = $("#chatInput");
    const send  = $("#chatSendBtn");

    const sendNow = () => {
      const t = input.value.trim();
      if (!t) return;
      appendMsg(t, "user");
      input.value = "";

      // TODO: 나중에 /api/agent/analyze 로 POST하고 응답 차트/메시지 바인딩
      setTimeout(() => {
        appendMsg("아직 분석 API와 연결 전입니다. 곧 연결 예정!", "bot");
      }, 200);
    };

    send.addEventListener("click", sendNow);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); sendNow(); }
    });
  }

  // init
  document.addEventListener("DOMContentLoaded", () => {
    initEmptyChart();
    wireChat();
  });
})();
