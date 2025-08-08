// static/js/userservice.js (로더 통합본)
(function () {
  'use strict';

  const USER_COLOR = '#42a5f5';
  const UNIVERSITY_COLOR = '#29b6f6';
  let charts = [];

  // === 글로벌 로더 유틸 (레퍼런스 카운트 방식) ===
  let __loaderCount = 0;
  function showGlobalLoader() {
    __loaderCount++;
    const el = document.getElementById('global-loader');
    if (el) el.style.display = 'block';
  }
  function hideGlobalLoader() {
    __loaderCount = Math.max(0, __loaderCount - 1);
    if (__loaderCount === 0) {
      const el = document.getElementById('global-loader');
      if (el) el.style.display = 'none';
    }
  }

  function renderUserBasics(name, univ) {
    const $name = document.getElementById('userName');
    const $univ = document.getElementById('userUniv');
    if ($name) $name.textContent = name || '-';
    if ($univ) $univ.textContent = univ || '-';
  }

  async function syncPrediction() {
    const btn = document.getElementById('btnSyncPredict');
    try {
      if (!confirm('현재 저장된 학년별 데이터로 예측 점수를 계산하고 저장할까요?')) return;
      if (btn) { btn.disabled = true; btn.textContent = '동기화 중...'; }
      showGlobalLoader();

      const res = await fetch('/api/user/predict-sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: '{}' // 서버가 세션기반으로 DB 조회
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.success) {
        alert('예측 동기화 실패: ' + (data && data.error ? data.error : res.statusText));
        return;
      }

      const p = data.predictions || {};
      alert(
        '예측 저장 완료!\n' +
        `1학년: ${p.SCR_EST_1ST != null ? p.SCR_EST_1ST : '-'}\n` +
        `2학년: ${p.SCR_EST_2ND != null ? p.SCR_EST_2ND : '-'}\n` +
        `3학년: ${p.SCR_EST_3RD != null ? p.SCR_EST_3RD : '-'}\n` +
        `4학년: ${p.SCR_EST_4TH != null ? p.SCR_EST_4TH : '-'}`
      );

      // 새 점수 반영해서 다시 그림
      await loadAndRender();
    } catch (e) {
      console.error(e);
      alert('네트워크 오류로 실패했습니다.');
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = '예측 점수 동기화'; }
      hideGlobalLoader();
    }
  }

  function destroyCharts() {
    charts.forEach(c => { try { c.destroy(); } catch (e) {} });
    charts = [];
  }

  function showPlaceholder(msg) {
    const grid = document.getElementById('chartGrid');
    if (!grid) return;
    grid.innerHTML = `
      <div class="chart-placeholder" id="chartPlaceholder">
        <div class="placeholder-content">
          <div class="placeholder-icon">👤</div>
          <h3>${msg || '내 정보 기반 개인화 영역'}</h3>
        </div>
      </div>`;
  }

  function yRange(a, b) {
    const A = Number(a) || 0;
    const B = Number(b) || 0;
    const max = Math.max(A, B);
    const min = Math.min(A, B);
    const range = max - min;
    if (max === 0) return { min: 0, max: 10 };
    if (range === 0) return { min: Math.max(0, max * 0.7), max: max * 1.3 };
    if (min === 0) return { min: 0, max: max * 1.2 };
    const pad = range * 0.3;
    return { min: Math.max(0, min - pad), max: max + pad };
  }

  function findSimilar(byYearScores, userScore) {
    if (!Array.isArray(byYearScores) || byYearScores.length === 0 || userScore == null) return [];
    const arr = byYearScores
      .filter(x => x && typeof x.score === 'number')
      .sort((a, b) => b.score - a.score);

    const us = Number(userScore);
    let userRank = arr.length;
    for (let i = 0; i < arr.length; i++) {
      if (arr[i].score <= us) { userRank = i; break; }
    }
    const get = i => (i >= 0 && i < arr.length) ? arr[i] : null;
    const minus2 = get(userRank + 2);
    const minus1 = get(userRank + 1);
    const plus1  = get(userRank - 1);
    const plus2  = get(userRank - 2);

    const out = [];
    if (minus2) out.push({ name: minus2.SNM, score: minus2.score, position: 'minus2' });
    if (minus1) out.push({ name: minus1.SNM, score: minus1.score, position: 'minus1' });
    out.push({ name: '유저', score: us, isUser: true });
    if (plus1)  out.push({ name: plus1.SNM, score: plus1.score, position: 'plus1' });
    if (plus2)  out.push({ name: plus2.SNM, score: plus2.score, position: 'plus2' });
    return out;
  }

  function addGradeBlock(container, grade, g) {
    const block = document.createElement('div');
    block.className = 'chart-block';
    block.innerHTML = `
      <div class="chart-block-header">
        ${grade}학년 (${g.year}년) - 학습활동 데이터 비교
      </div>
      <div class="chart-block-content">
        <div class="bar-charts-container">
          <div class="individual-bar-chart">
            <div class="chart-title">자료구입비</div>
            <canvas id="gradeCPSChart${grade}"></canvas>
          </div>
          <div class="individual-bar-chart">
            <div class="chart-title">대출책수</div>
            <canvas id="gradeLPSChart${grade}"></canvas>
          </div>
          <div class="individual-bar-chart">
            <div class="chart-title">도서관방문수</div>
            <canvas id="gradeVPSChart${grade}"></canvas>
          </div>
        </div>
        <div class="donut-charts-container">
          <div class="donut-chart-item">
            <div class="chart-title">자료구입비 비율</div>
            <canvas id="donutCPS${grade}" class="donut-chart"></canvas>
            <div class="donut-label" id="labelCPS${grade}">-</div>
          </div>
          <div class="donut-chart-item">
            <div class="chart-title">대출책수 비율</div>
            <canvas id="donutLPS${grade}" class="donut-chart"></canvas>
            <div class="donut-label" id="labelLPS${grade}">-</div>
          </div>
          <div class="donut-chart-item">
            <div class="chart-title">도서관방문수 비율</div>
            <canvas id="donutVPS${grade}" class="donut-chart"></canvas>
            <div class="donut-label" id="labelVPS${grade}">-</div>
          </div>
        </div>
      </div>`;
    container.appendChild(block);

    // 개별 막대
    [
      { key: 'CPS', canvas: `gradeCPSChart${grade}` },
      { key: 'LPS', canvas: `gradeLPSChart${grade}` },
      { key: 'VPS', canvas: `gradeVPSChart${grade}` }
    ].forEach(({ key, canvas }) => {
      const ctx = document.getElementById(canvas);
      if (!ctx || typeof Chart === 'undefined') return;
      const userV = Number(g.userData[key]) || 0;
      const univV = Number(g.universityData[key]) || 0;
      const yr = yRange(userV, univV);
      const ch = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: [''],
          datasets: [
            { label: '유저', data: [userV], backgroundColor: USER_COLOR + '80', borderColor: USER_COLOR, borderWidth: 1, maxBarThickness: 40 },
            { label: '대학평균', data: [univV], backgroundColor: UNIVERSITY_COLOR + '80', borderColor: UNIVERSITY_COLOR, borderWidth: 1, maxBarThickness: 40 }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: 'bottom', labels: { font: { size: 8 }, boxWidth: 8, padding: 8 } } },
          scales: { y: { min: yr.min, max: yr.max, ticks: { font: { size: 7 }, maxTicksLimit: 5 } }, x: { display: false } }
        }
      });
      charts.push(ch);
    });

    // 도넛
    ['CPS', 'LPS', 'VPS'].forEach((key) => {
      const ctx = document.getElementById(`donut${key}${grade}`);
      const label = document.getElementById(`label${key}${grade}`);
      if (!ctx || !label || typeof Chart === 'undefined') return;
      const userV = Number(g.userData[key]) || 0;
      const univV = Number(g.universityData[key]) || 0;
      const maxV = Math.max(userV, univV);
      const minV = Math.min(userV, univV);
      const pct = maxV > 0 ? Math.round((minV / maxV) * 100) : 0;
      const isUserHigher = userV >= univV;
      const ch = new Chart(ctx, {
        type: 'doughnut',
        data: { datasets: [{ data: [pct, 100 - pct], backgroundColor: [isUserHigher ? USER_COLOR : UNIVERSITY_COLOR, '#e0e0e0'], borderWidth: 0 }] },
        options: { responsive: true, maintainAspectRatio: true, cutout: '60%', plugins: { legend: { display: false } } }
      });
      label.innerHTML = `${isUserHigher ? '대학' : '유저'}<br>${pct}%`;
      charts.push(ch);
    });
  }

  function addScoreBlock(container, grade, g) {
    const block = document.createElement('div');
    block.className = 'chart-block';
    block.innerHTML = `
      <div class="chart-block-header">
        ${grade}학년 (${g.year}년) - 환경점수 비교 분석
      </div>
      <div class="chart-block-content">
        <div class="score-comparison-block">
          <div class="user-score-chart">
            <div class="chart-title">유저 vs 소속대학</div>
            <canvas id="userScoreChart${grade}"></canvas>
          </div>
          <div class="similar-scores-chart">
            <div class="chart-title">유사 점수 대학 비교</div>
            <canvas id="similarScoresChart${grade}"></canvas>
          </div>
        </div>
      </div>`;
    container.appendChild(block);

    // 유저 vs 대학
    const ctx1 = document.getElementById(`userScoreChart${grade}`);
    if (ctx1 && typeof Chart !== 'undefined') {
      const u = Number(g.userScore) || 0;
      const v = Number(g.universityScore) || 0;
      const r = yRange(u, v);
      const ch1 = new Chart(ctx1, {
        type: 'bar',
        data: {
          labels: ['환경점수'],
          datasets: [
            { label: '유저', data: [u], backgroundColor: USER_COLOR + '80', borderColor: USER_COLOR, borderWidth: 2, maxBarThickness: 100 },
            { label: '소속대학', data: [v], backgroundColor: UNIVERSITY_COLOR + '80', borderColor: UNIVERSITY_COLOR, borderWidth: 2, maxBarThickness: 100 }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: 'top' } },
          scales: {
            y: {
              min: r.min, max: r.max,
              ticks: { font: { size: 10 }, callback: function (val) { return Number(val).toFixed(1); } }
            }
          }
        }
      });
      charts.push(ch1);
    }

    // 유사대학 5개
    const ctx2 = document.getElementById(`similarScoresChart${grade}`);
    if (ctx2 && typeof Chart !== 'undefined') {
      const sims = findSimilar(g.byYearScores, g.userScore);
      const labels = sims.map(x => x.isUser ? '유저' : (x.name && x.name.length > 6 ? (x.name.slice(0, 6) + '…') : x.name || '-'));
      const scores = sims.map(x => x.score != null ? Number(x.score) : 0);
      const colors = sims.map(x => x.isUser ? USER_COLOR : '#81c784');
      const max = Math.max(...scores);
      const nz = scores.filter(s => s > 0);
      const min = nz.length ? Math.min(...nz) : 0;
      const pad = Math.max((max - min) * 0.15, 0.5);
      const yMin = min ? Math.max(0, min - pad) : 0;
      const yMax = max + pad;

      const ch2 = new Chart(ctx2, {
        type: 'bar',
        data: { labels: labels, datasets: [{ label: '환경점수', data: scores, backgroundColor: colors.map(c => c + '80'), borderColor: colors, borderWidth: 2, maxBarThickness: 50 }] },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: { min: yMin, max: yMax, ticks: { font: { size: 10 }, callback: function (v) { return Number(v).toFixed(1); } } },
            x: { ticks: { maxRotation: 45, font: { size: 9 } } }
          }
        }
      });
      charts.push(ch2);
    }
  }

  async function loadAndRender() {
    showGlobalLoader();
    try {
      const res = await fetch('/api/user/analysis');
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.success) {
        showPlaceholder((data && data.error) ? data.error : '데이터 로드 실패');
        return;
      }

      // 상단 기본정보
      renderUserBasics(data.user && data.user.name, data.user && data.user.snm);

      const grid = document.getElementById('chartGrid');
      if (!grid) return;
      grid.innerHTML = '';
      destroyCharts();

      // 1~4학년 블록 순서대로
      [1, 2, 3, 4].forEach(grade => {
        const g = data.grades && data.grades[grade];
        if (g) addGradeBlock(grid, grade, g);
      });
      [1, 2, 3, 4].forEach(grade => {
        const g = data.grades && data.grades[grade];
        if (g) addScoreBlock(grid, grade, g);
      });
    } catch (e) {
      console.error(e);
      showPlaceholder('초기화 중 오류가 발생했습니다.');
    } finally {
      hideGlobalLoader();
    }
  }

  function initActions() {
    const btnProfile = document.getElementById('btnGoProfile');
    if (btnProfile) {
      btnProfile.addEventListener('click', function () {
        window.location.href = '/profile';
      });
    }

    const btnSync = document.getElementById('btnSyncPredict');
    if (btnSync) {
      btnSync.addEventListener('click', syncPrediction);
    }
  }

  window.addEventListener('DOMContentLoaded', function () {
    (async function () {
      try {
        await loadAndRender();
      } catch (e) {
        console.error(e);
        showPlaceholder('초기화 중 오류가 발생했습니다.');
      }
      initActions();
    })();
  });
})();
