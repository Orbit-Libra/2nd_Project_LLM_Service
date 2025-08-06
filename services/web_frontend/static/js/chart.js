//차트 페이지 로직 컨트롤러 -메인 진입점
// js/chart.js 

//순수 차트기능만 담당, 다른페이지에서도 사용가능
//DOM요소들과 이벤트 바인딩
//사용자 인터랙션처리
//chart/폴더 컴포넌트들을 조합해서 사용

document.addEventListener('DOMContentLoaded', () => {
  console.log('차트 페이지 로드됨');
  
  // 차트 페이지 관리자 초기화
  setTimeout(() => {
    if (typeof ChartPageManager !== 'undefined') {
      window.chartPageManager = new ChartPageManager();
    } else {
      console.error('ChartPageManager가 정의되지 않았습니다.');
      // 기본 차트 기능만 구현
      initBasicChartFunctionality();
    }
  }, 1000);
});

// 기본 차트 기능 구현
function initBasicChartFunctionality() {
  console.log('기본 차트 기능 초기화');
  
  // 필터링 버튼 이벤트
  const filterBtns = document.querySelectorAll('.filter-btn');
  filterBtns.forEach(btn => {
    btn.addEventListener('click', function() {
      // 활성 버튼 변경
      filterBtns.forEach(b => b.classList.remove('active'));
      this.classList.add('active');
      
      const filterType = this.getAttribute('data-filter');
      console.log('필터 적용:', filterType);
      
      if (filterType === 'all') {
        showMessage('전체 데이터를 표시합니다.');
      } else if (filterType === 'manual') {
        showMessage('수동 선택 모드를 활성화합니다.');
      }
    });
  });
  
  // 출력 범위 슬라이더
  const rangeSliders = document.querySelectorAll('.range-slider');
  rangeSliders.forEach(slider => {
    slider.addEventListener('input', function() {
      const value = this.value;
      const display = this.parentNode.querySelector('.range-display');
      if (display) {
        display.textContent = value;
      }
      console.log('범위 변경:', value);
    });
  });
  
  // 차트 생성 버튼
  const createBtn = document.getElementById('create-chart-btn');
  if (createBtn) {
    createBtn.addEventListener('click', function() {
      console.log('차트 생성 클릭');
      createSampleChart();
    });
  }
  
  // 차트 내보내기 버튼
  const exportBtn = document.getElementById('export-btn');
  if (exportBtn) {
    exportBtn.addEventListener('click', function() {
      console.log('차트 내보내기 클릭');
      exportChart();
    });
  }
  
  // 즐겨찾기 저장 버튼
  const favoriteBtn = document.getElementById('save-favorite-btn');
  if (favoriteBtn) {
    favoriteBtn.addEventListener('click', function() {
      console.log('즐겨찾기 저장 클릭');
      saveFavorite();
    });
  }
  
  // 평균값 분석 버튼 - 중요!
  const analyzeBtn = document.getElementById('analyze-average-btn');
  if (analyzeBtn) {
    analyzeBtn.addEventListener('click', function() {
      console.log('평균값 분석 클릭');
      analyzeAverage();
    });
  } else {
    console.error('평균값 분석 버튼을 찾을 수 없습니다.');
  }
  
  // 차트 타입 변경 버튼들
  const chartTypeBtns = document.querySelectorAll('.chart-control-btn[data-type]');
  chartTypeBtns.forEach(btn => {
    btn.addEventListener('click', function() {
      // 활성 버튼 변경
      chartTypeBtns.forEach(b => b.classList.remove('active'));
      this.classList.add('active');
      
      const chartType = this.getAttribute('data-type');
      console.log('차트 타입 변경:', chartType);
      changeChartType(chartType);
    });
  });
}

// 샘플 차트 생성
function createSampleChart() {
  const chartWrapper = document.getElementById('chart-wrapper');
  const chartCanvas = document.getElementById('main-chart');
  const placeholder = document.getElementById('chart-placeholder');
  
  if (chartWrapper && chartCanvas && placeholder) {
    // 플레이스홀더 숨기고 차트 표시
    placeholder.style.display = 'none';
    chartCanvas.style.display = 'block';
    chartWrapper.classList.add('has-data');
    
    // 간단한 캔버스 차트 그리기
    const ctx = chartCanvas.getContext('2d');
    
    // 캔버스 크기 설정
    chartCanvas.width = chartWrapper.offsetWidth;
    chartCanvas.height = chartWrapper.offsetHeight;
    
    // 배경 그리기
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, chartCanvas.width, chartCanvas.height);
    
    // 샘플 바 차트 그리기
    const data = [85, 92, 78, 88, 95];
    const labels = ['도서관', '강의실', '연구시설', '체육시설', '기숙사'];
    const colors = ['#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6'];
    
    const barWidth = chartCanvas.width / (data.length * 2);
    const maxHeight = chartCanvas.height - 100;
    const maxValue = Math.max(...data);
    
    data.forEach((value, index) => {
      const x = (index * 2 + 1) * barWidth;
      const height = (value / maxValue) * maxHeight;
      const y = chartCanvas.height - height - 50;
      
      // 바 그리기
      ctx.fillStyle = colors[index];
      ctx.fillRect(x, y, barWidth * 0.8, height);
      
      // 라벨 그리기
      ctx.fillStyle = '#333';
      ctx.font = '12px Arial';
      ctx.textAlign = 'center';
      ctx.fillText(labels[index], x + barWidth * 0.4, chartCanvas.height - 20);
      
      // 값 표시
      ctx.fillText(value, x + barWidth * 0.4, y - 10);
    });
    
    showMessage('샘플 차트가 생성되었습니다!');
  } else {
    console.error('차트 요소들을 찾을 수 없습니다.');
  }
}

// 평균값 분석
function analyzeAverage() {
  const data = [85, 92, 78, 88, 95]; // 샘플 데이터
  const average = data.reduce((sum, value) => sum + value, 0) / data.length;
  const max = Math.max(...data);
  const min = Math.min(...data);
  
  const analysisText = `
📊 분석 결과

🔹 평균 점수: ${average.toFixed(1)}점
🔹 최고 점수: ${max}점  
🔹 최저 점수: ${min}점
🔹 점수 편차: ${(max - min).toFixed(1)}점

📈 종합 평가: ${getGradeByScore(average)}
  `;
  
  alert(analysisText);
  console.log('평균값 분석 완료');
}

// 점수별 등급
function getGradeByScore(score) {
  if (score >= 90) return 'A+ (매우 우수)';
  if (score >= 80) return 'A (우수)';
  if (score >= 70) return 'B (양호)';
  if (score >= 60) return 'C (보통)';
  return 'D (개선 필요)';
}

// 차트 타입 변경
function changeChartType(type) {
  showMessage(`차트 타입을 ${type}로 변경했습니다.`);
  // 실제 차트 타입 변경 로직 구현
}

// 차트 내보내기
function exportChart() {
  const canvas = document.getElementById('main-chart');
  if (canvas) {
    const dataURL = canvas.toDataURL('image/png');
    const link = document.createElement('a');
    link.download = 'chart.png';
    link.href = dataURL;
    link.click();
    showMessage('차트를 내보냈습니다!');
  }
}

// 즐겨찾기 저장
function saveFavorite() {
  try {
    const favorites = JSON.parse(localStorage.getItem('chartFavorites') || '[]');
    const newFavorite = {
      id: Date.now(),
      name: '샘플 차트',
      createdAt: new Date().toISOString()
    };
    
    favorites.push(newFavorite);
    localStorage.setItem('chartFavorites', JSON.stringify(favorites));
    
    showMessage('즐겨찾기에 저장되었습니다!');
  } catch (error) {
    console.error('즐겨찾기 저장 실패:', error);
  }
}

// 메시지 표시 함수
function showMessage(message) {
  // 간단한 토스트 메시지
  const toast = document.createElement('div');
  toast.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    background: #333;
    color: white;
    padding: 12px 20px;
    border-radius: 4px;
    z-index: 10000;
    font-size: 14px;
  `;
  toast.textContent = message;
  
  document.body.appendChild(toast);
  
  setTimeout(() => {
    toast.remove();
  }, 3000);
}