// chartpage1.js - 환경점수 분석 페이지
// Oracle ESTIMATIONFUTURE 테이블 연동

// 전역 변수
let tableData = null;
let filteredData = null;
let currentChart = null;
let chartData = null;
let currentYear = null;
let availableYears = [];

// 차트 색상 팔레트
const CHART_COLORS = [
    '#42a5f5', '#29b6f6', '#1e88e5', '#1976d2', '#1565c0',
    '#81c784', '#66bb6a', '#4caf50', '#43a047', '#388e3c',
    '#ffb74d', '#ffa726', '#ff9800', '#fb8c00', '#f57c00',
    '#ff8a65', '#ff7043', '#f44336', '#e91e63', '#9c27b0'
];

// 차트 타입별 한글명
const CHART_TYPE_NAMES = {
    'bar': '막대 차트',
    'line': '선 차트', 
    'scatter': '산점도',
    'pie': '원형 차트'
};

// API를 통해 Oracle 테이블 데이터 로드
async function loadTableData() {
    try {
        console.log('ESTIMATIONFUTURE 테이블 데이터 로딩 중...');
        showLoading();
        
        const response = await fetch('/api/chart-data');
        if (!response.ok) {
            throw new Error(`API 호출 실패: ${response.status} ${response.statusText}`);
        }
        
        const data = await response.json();
        
        if (data.success) {
            tableData = data.data;
            console.log('테이블 데이터 로드 완료:', tableData.length, '행');
            
            // 사용 가능한 연도 추출
            extractAvailableYears();
            
            // 필터 옵션 업데이트
            updateFilterOptions();
            
            // 연도 셀렉트 박스 초기화
            initializeYearSelect();
            
            return tableData;
        } else {
            throw new Error(data.message || '데이터 로드 실패');
        }
        
    } catch (error) {
        console.error('테이블 데이터 로드 실패:', error);
        showError(`데이터를 불러올 수 없습니다: ${error.message}`);
        return null;
    } finally {
        hideLoading();
    }
}

// 사용 가능한 연도 추출
function extractAvailableYears() {
    if (!tableData || tableData.length === 0) return;
    
    const firstRow = tableData[0];
    availableYears = [];
    
    // SCR_EST_YYYY 형태의 컬럼명에서 연도 추출
    Object.keys(firstRow).forEach(key => {
        const match = key.match(/^SCR_EST_(\d{4})$/);
        if (match) {
            const year = parseInt(match[1]);
            if (year >= 2000 && year <= 2050) {
                availableYears.push(year);
            }
        }
    });
    
    // 연도 정렬 (내림차순 - 최신 연도부터)
    availableYears.sort((a, b) => b - a);
    
    console.log('사용 가능한 연도:', availableYears);
}

// 필터 옵션 업데이트
function updateFilterOptions() {
    if (!tableData || tableData.length === 0) return;
    
    // 각 필터별 고유값 추출
    const stypValues = new Set();
    const fndValues = new Set();
    const rgnValues = new Set();
    const uscValues = new Set();
    
    tableData.forEach(row => {
        if (row.STYP) stypValues.add(row.STYP);
        if (row.FND) fndValues.add(row.FND);
        if (row.RGN) rgnValues.add(row.RGN);
        if (row.USC) uscValues.add(row.USC);
    });
    
    // 필터 옵션 업데이트
    updateSelectOptions('stypFilter', Array.from(stypValues).sort());
    updateSelectOptions('fndFilter', Array.from(fndValues).sort());
    updateSelectOptions('rgnFilter', Array.from(rgnValues).sort());
    updateSelectOptions('uscFilter', Array.from(uscValues).sort());
}

// Select 옵션 업데이트
function updateSelectOptions(selectId, values) {
    const select = document.getElementById(selectId);
    if (!select) return;
    
    // 기존 옵션 제거 (전체 옵션 제외)
    while (select.options.length > 1) {
        select.remove(1);
    }
    
    // 새 옵션 추가
    values.forEach(value => {
        const option = document.createElement('option');
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
    });
}

// 연도 셀렉트 박스 초기화
function initializeYearSelect() {
    const yearSelect = document.getElementById('yearSelect');
    if (!yearSelect) return;
    
    // 기존 옵션 제거
    yearSelect.innerHTML = '';
    
    // 사용 가능한 연도로 옵션 추가
    availableYears.forEach(year => {
        const option = document.createElement('option');
        option.value = year;
        option.textContent = `${year}년`;
        yearSelect.appendChild(option);
    });
    
    // 기본값을 가장 최신 연도로 설정
    if (availableYears.length > 0) {
        currentYear = availableYears[0];
        yearSelect.value = currentYear;
        updateCurrentInfo();
    }
}

// 차트 생성 함수
async function generateChart() {
    console.log('차트 생성 시작');
    
    // 테이블 데이터가 없으면 먼저 로드
    if (!tableData) {
        await loadTableData();
        if (!tableData) {
            return;
        }
    }
    
    const year = document.getElementById('yearSelect').value;
    currentYear = year;
    
    const chartType = document.getElementById('chartType').value;
    
    console.log('차트 생성 요청:', { year, chartType });
    
    showLoading();
    
    try {
        // 데이터 처리
        const processedData = processTableDataForChart(tableData, year);
        
        if (processedData && processedData.length > 0) {
            // 차트 생성
            createChart(processedData, chartType);
            updateDataCount(processedData.length);
            
            // 플레이스홀더 숨기기
            document.getElementById('chartPlaceholder').style.display = 'none';
        } else {
            showError('선택한 조건에 해당하는 데이터가 없습니다.');
        }
    } catch (error) {
        console.error('차트 생성 실패:', error);
        showError('차트 생성 중 오류가 발생했습니다: ' + error.message);
    } finally {
        hideLoading();
    }
}

// 테이블 데이터 처리
function processTableDataForChart(data, selectedYear) {
    const scoreColumn = `SCR_EST_${selectedYear}`;
    console.log(`선택된 연도: ${selectedYear}, 점수 컬럼: ${scoreColumn}`);
    
    // 필터 적용
    filteredData = applyFilters(data, scoreColumn);
    console.log('필터 적용 후 데이터 수:', filteredData.length);
    
    // 정렬 적용
    const sortOrder = document.getElementById('sortOrder').value;
    applySorting(filteredData, sortOrder, scoreColumn);
    
    // 출력 개수 제한
    const dataLimit = document.getElementById('dataLimit').value;
    let limitedData = filteredData;
    
    if (dataLimit !== 'all') {
        const limit = parseInt(dataLimit);
        limitedData = filteredData.slice(0, limit);
    }
    
    console.log('최종 선택된 데이터 수:', limitedData.length);
    
    // 차트용 데이터 변환
    return limitedData.map((row, index) => {
        const score = parseFloat(row[scoreColumn]) || 0;
        return {
            university: row.SNM || 'Unknown',
            value: score,
            styp: row.STYP || '',
            fnd: row.FND || '',
            rgn: row.RGN || '',
            usc: row.USC || '',
            rank: index + 1,
            label: `${row.SNM} (${score}점)`
        };
    });
}

// 필터 적용
function applyFilters(data, scoreColumn) {
    const stypFilter = document.getElementById('stypFilter').value;
    const fndFilter = document.getElementById('fndFilter').value;
    const rgnFilter = document.getElementById('rgnFilter').value;
    const uscFilter = document.getElementById('uscFilter').value;
    
    return data.filter(row => {
        // 필터 조건 확인
        if (stypFilter !== '전체' && row.STYP !== stypFilter) return false;
        if (fndFilter !== '전체' && row.FND !== fndFilter) return false;
        if (rgnFilter !== '전체' && row.RGN !== rgnFilter) return false;
        if (uscFilter !== '전체' && row.USC !== uscFilter) return false;
        
        // 점수 유효성 확인
        const scoreValue = row[scoreColumn];
        return scoreValue !== null && 
               scoreValue !== undefined && 
               scoreValue !== '' &&
               !isNaN(parseFloat(scoreValue)) &&
               row.SNM; // 학교명이 있어야 함
    });
}

// 정렬 적용
function applySorting(data, sortOrder, scoreColumn) {
    switch(sortOrder) {
        case 'rank_asc':
            data.sort((a, b) => {
                const scoreA = parseFloat(a[scoreColumn]) || 0;
                const scoreB = parseFloat(b[scoreColumn]) || 0;
                return scoreA - scoreB;
            });
            break;
            
        case 'rank_desc':
            data.sort((a, b) => {
                const scoreA = parseFloat(a[scoreColumn]) || 0;
                const scoreB = parseFloat(b[scoreColumn]) || 0;
                return scoreB - scoreA;
            });
            break;
            
        case 'university':
            data.sort((a, b) => {
                const nameA = (a.SNM || '').toString();
                const nameB = (b.SNM || '').toString();
                return nameA.localeCompare(nameB, 'ko');
            });
            break;
    }
}

// Chart.js를 사용한 차트 생성
function createChart(data, chartType) {
    const ctx = document.getElementById('mainChart').getContext('2d');
    
    // 기존 차트 제거
    if (currentChart) {
        currentChart.destroy();
    }
    
    chartData = data;
    
    const labels = data.map(item => item.university);
    const values = data.map(item => item.value);
    
    const chartConfig = {
        type: chartType === 'scatter' ? 'scatter' : chartType,
        data: {
            labels: labels,
            datasets: [{
                label: '환경점수',
                data: chartType === 'scatter' ? 
                    data.map((item, index) => ({x: index, y: item.value})) : 
                    values,
                backgroundColor: chartType === 'pie' ? 
                    CHART_COLORS.slice(0, data.length) : 
                    CHART_COLORS[0] + '80',
                borderColor: CHART_COLORS[0],
                borderWidth: 2,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: `환경점수 분석 (${currentYear}년)`,
                    font: {
                        size: 16,
                        weight: 'bold'
                    },
                    color: '#42a5f5'
                },
                legend: {
                    display: chartType === 'pie',
                    position: 'bottom'
                }
            },
            scales: getScaleConfig(chartType)
        }
    };
    
    currentChart = new Chart(ctx, chartConfig);
    console.log('차트 생성 완료');
}

// 차트 타입별 스케일 설정
function getScaleConfig(chartType) {
    if (chartType === 'pie') {
        return {};
    }
    
    return {
        x: {
            display: true,
            title: {
                display: true,
                text: '대학교',
                color: '#666'
            },
            ticks: {
                maxRotation: 90,
                minRotation: 45,
                font: {
                    size: 10
                }
            }
        },
        y: {
            display: true,
            title: {
                display: true,
                text: '환경점수',
                color: '#666'
            },
            beginAtZero: false
        }
    };
}

// 이벤트 핸들러 함수들
function onYearChange() {
    const year = document.getElementById('yearSelect').value;
    console.log('연도 변경:', year);
    currentYear = year;
    updateCurrentInfo();
}

function onFilterChange() {
    console.log('필터 변경');
    updateCurrentInfo();
}

function onChartTypeChange() {
    console.log('차트 타입 변경');
    updateCurrentInfo();
    
    if (currentChart && chartData) {
        const chartType = document.getElementById('chartType').value;
        createChart(chartData, chartType);
    }
}

function onSortOrderChange() {
    console.log('정렬 방식 변경');
    updateCurrentInfo();
}

function onDataLimitChange() {
    console.log('데이터 제한 변경');
    updateCurrentInfo();
}

// 현재 정보 업데이트
function updateCurrentInfo() {
    const elements = {
        currentYear: currentYear ? `${currentYear}년` : '-',
        currentStyp: document.getElementById('stypFilter')?.value || '전체',
        currentFnd: document.getElementById('fndFilter')?.value || '전체',
        currentRgn: document.getElementById('rgnFilter')?.value || '전체',
        currentUsc: document.getElementById('uscFilter')?.value || '전체',
        currentChartType: CHART_TYPE_NAMES[document.getElementById('chartType')?.value] || '막대 차트'
    };
    
    Object.entries(elements).forEach(([id, value]) => {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
    });
}

function updateDataCount(count) {
    const element = document.getElementById('dataCount');
    if (element) {
        element.textContent = `${count}개`;
    }
}

// UI 상태 관리
function showLoading() {
    const loading = document.getElementById('chartLoading');
    const placeholder = document.getElementById('chartPlaceholder');
    
    if (loading) loading.style.display = 'flex';
    if (placeholder) placeholder.style.display = 'none';
}

function hideLoading() {
    const loading = document.getElementById('chartLoading');
    if (loading) loading.style.display = 'none';
}

function showError(message) {
    const placeholder = document.getElementById('chartPlaceholder');
    if (placeholder) {
        placeholder.innerHTML = `
            <div class="placeholder-content">
                <div class="placeholder-icon">⚠️</div>
                <h3>오류 발생</h3>
                <p>${message}</p>
            </div>
        `;
        placeholder.style.display = 'flex';
    }
    hideLoading();
}

// 차트 내보내기
function exportChart() {
    if (!currentChart) {
        alert('내보낼 차트가 없습니다. 먼저 차트를 생성해주세요.');
        return;
    }
    
    try {
        const canvas = document.getElementById('mainChart');
        const url = canvas.toDataURL('image/png');
        
        const a = document.createElement('a');
        a.href = url;
        const timestamp = new Date().toISOString().slice(0, 10);
        a.download = `libra_chart_${currentYear}_${timestamp}.png`;
        
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        
        console.log('차트 내보내기 완료');
    } catch (error) {
        console.error('차트 내보내기 실패:', error);
        alert('차트 내보내기에 실패했습니다.');
    }
}

// 페이지 초기화
function initializePage() {
    console.log('차트 페이지 초기화');
    
    // 테이블 데이터 로드
    loadTableData();
    
    // 기본 정보 업데이트
    updateCurrentInfo();
}

// 키보드 단축키
document.addEventListener('keydown', function(event) {
    if (event.ctrlKey && event.key === 'Enter') {
        event.preventDefault();
        generateChart();
    }
    
    if (event.ctrlKey && event.key === 'e') {
        event.preventDefault();
        exportChart();
    }
});

// 페이지 로드 완료 시 초기화
document.addEventListener('DOMContentLoaded', function() {
    console.log('차트 페이지 DOM 로드 완료');
    initializePage();
});

// 페이지 떠날 때 차트 정리
window.addEventListener('beforeunload', function() {
    if (currentChart) {
        currentChart.destroy();
    }
});