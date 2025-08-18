// chartpage1.js - Oracle DB 연동 환경점수 분석 페이지 (완전한 버전)
// Oracle ESTIMATIONFUTURE 테이블 연동

// 전역 변수
let tableData = null;
let filteredData = null;
let selectedUniversities = new Set();
let currentChart = null;
let availableYears = [];
let selectionMode = 'all'; // 'all' 또는 'manual'
let selectedDataRange = { start: 1, end: 50 };
let yAxisMode = 'auto'; // 'auto', 'zero', 'manual'
let manualYAxis = { min: 0, max: 100 };

// 차트 색상 팔레트
const CHART_COLORS = {
    primary: '#42a5f5',
    secondary: '#29b6f6',
    positive: '#0068e8',
    negative: '#f44336',
    neutral: '#9e9e9e',
    palette: [
        '#42a5f5', '#29b6f6', '#1e88e5', '#1976d2', '#1565c0',
        '#81c784', '#66bb6a', '#4caf50', '#43a047', '#388e3c',
        '#ffb74d', '#ffa726', '#ff9800', '#fb8c00', '#f57c00',
        '#ff8a65', '#ff7043', '#f44336', '#e91e63', '#9c27b0'
    ]
};

// API를 통해 Oracle 테이블 데이터 로드
async function loadTableData() {
    try {
        console.log('Oracle ESTIMATIONFUTURE 테이블 데이터 로딩 중...');
        showLoading();
        
        const response = await fetch('/api/chart-data');
        if (!response.ok) {
            throw new Error(`API 호출 실패: ${response.status} ${response.statusText}`);
        }
        
        const data = await response.json();
        
        if (data.success) {
            tableData = data.data;
            console.log('테이블 데이터 로드 완료:', tableData.length, '행');
            console.log('사용 가능한 컬럼:', data.columns);
            console.log('점수 컬럼들:', data.score_columns);
            
            // 사용 가능한 연도 추출
            extractAvailableYears();
            
            // 필터 옵션 업데이트
            updateFilterOptions();
            
            // 연도 선택 옵션 업데이트
            updateYearOptions();
            
            // 데이터 범위 슬라이더 초기화
            selectedDataRange = { start: 1, end: Math.min(50, tableData.length) };
            updateDataRangeSliders();
            
            // 초기 필터 적용
            applyFilters();
            
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
            if (year >= 1900 && year <= 2100) {
                availableYears.push(year);
            }
        }
    });
    
    // 연도 정렬 (오름차순)
    availableYears.sort((a, b) => a - b);
    
    console.log('Oracle DB에서 감지된 사용 가능한 연도:', availableYears);
}

// 연도 선택 옵션 업데이트
function updateYearOptions() {
    const yearSelect = document.getElementById('yearSelect');
    if (!yearSelect) return;
    
    // 기존 옵션 제거
    yearSelect.innerHTML = '';
    
    // 기본 옵션 추가
    const defaultOption = document.createElement('option');
    defaultOption.value = '';
    defaultOption.textContent = '연도를 선택하세요';
    yearSelect.appendChild(defaultOption);
    
    // 연도 옵션 추가
    availableYears.forEach(year => {
        const option = document.createElement('option');
        option.value = year;
        option.textContent = `${year}년`;
        yearSelect.appendChild(option);
    });
    
    // 가장 최신 연도로 자동 선택
    if (availableYears.length > 0) {
        yearSelect.value = availableYears[availableYears.length - 1];
        updateCurrentInfo();
    }
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

// 데이터 범위 슬라이더 초기화/업데이트
function updateDataRangeSliders() {
    const filtered = applyFilters();
    const dataCount = filtered.length;
    
    const startSlider = document.getElementById('dataStartSlider');
    const endSlider = document.getElementById('dataEndSlider');
    const minLabel = document.getElementById('dataMinLabel');
    const maxLabel = document.getElementById('dataMaxLabel');
    const countInfo = document.getElementById('dataCountInfo');
    
    if (!startSlider || !endSlider || !minLabel || !maxLabel || !countInfo) return;
    
    // 필터링된 데이터 개수 표시
    countInfo.textContent = `필터링된 데이터: ${dataCount}개`;
    
    if (dataCount === 0) {
        // 데이터가 없을 때
        startSlider.min = 1;
        startSlider.max = 1;
        startSlider.value = 1;
        endSlider.min = 1;
        endSlider.max = 1;
        endSlider.value = 1;
        minLabel.textContent = '1';
        maxLabel.textContent = '1';
        document.getElementById('selectedDataRange').textContent = '데이터 없음';
        return;
    }
    
    // 슬라이더 범위 설정
    startSlider.min = 1;
    startSlider.max = dataCount;
    endSlider.min = 1;
    endSlider.max = dataCount;
    
    // 현재 값이 범위를 벗어나면 조정
    if (selectedDataRange.start > dataCount) {
        selectedDataRange.start = 1;
    }
    if (selectedDataRange.end > dataCount) {
        selectedDataRange.end = dataCount;
    }
    
    startSlider.value = selectedDataRange.start;
    endSlider.value = selectedDataRange.end;
    
    // 레이블 업데이트
    minLabel.textContent = '1';
    maxLabel.textContent = dataCount.toString();
    
    updateSelectedDataRangeDisplay();
}

// 데이터 슬라이더 변경 이벤트
function onDataSliderChange() {
    const startSlider = document.getElementById('dataStartSlider');
    const endSlider = document.getElementById('dataEndSlider');
    
    if (!startSlider || !endSlider) return;
    
    let startIdx = parseInt(startSlider.value);
    let endIdx = parseInt(endSlider.value);
    
    // 시작이 끝보다 크면 조정
    if (startIdx > endIdx) {
        if (event.target.id === 'dataStartSlider') {
            endIdx = startIdx;
            endSlider.value = endIdx;
        } else {
            startIdx = endIdx;
            startSlider.value = startIdx;
        }
    }
    
    selectedDataRange.start = startIdx;
    selectedDataRange.end = endIdx;
    
    updateSelectedDataRangeDisplay();
}

// 화살표 버튼으로 데이터 범위 조절
function adjustDataRange(type, delta) {
    const startSlider = document.getElementById('dataStartSlider');
    const endSlider = document.getElementById('dataEndSlider');
    
    if (!startSlider || !endSlider) return;
    
    const maxValue = parseInt(endSlider.max);
    
    if (type === 'start') {
        let newValue = selectedDataRange.start + delta;
        newValue = Math.max(1, Math.min(newValue, selectedDataRange.end));
        selectedDataRange.start = newValue;
        startSlider.value = newValue;
    } else if (type === 'end') {
        let newValue = selectedDataRange.end + delta;
        newValue = Math.max(selectedDataRange.start, Math.min(newValue, maxValue));
        selectedDataRange.end = newValue;
        endSlider.value = newValue;
    }
    
    updateSelectedDataRangeDisplay();
}

// 선택된 데이터 범위 표시 업데이트
function updateSelectedDataRangeDisplay() {
    const rangeDisplay = document.getElementById('selectedDataRange');
    if (!rangeDisplay) return;
    
    const totalCount = parseInt(document.getElementById('dataMaxLabel').textContent) || 0;
    
    if (totalCount === 0) {
        rangeDisplay.textContent = '데이터 없음';
        return;
    }
    
    const selectedCount = selectedDataRange.end - selectedDataRange.start + 1;
    rangeDisplay.textContent = `${selectedDataRange.start}번째 ~ ${selectedDataRange.end}번째 (${selectedCount}개)`;
}

// 필터링 적용 (이름순 정렬)
function applyFilters() {
    if (!tableData) return [];
    
    const stypFilter = document.getElementById('stypFilter')?.value || '전체';
    const fndFilter = document.getElementById('fndFilter')?.value || '전체';
    const rgnFilter = document.getElementById('rgnFilter')?.value || '전체';
    const uscFilter = document.getElementById('uscFilter')?.value || '전체';
    const selectedYear = document.getElementById('yearSelect')?.value;
    
    filteredData = tableData.filter(row => {
        if (stypFilter !== '전체' && row.STYP !== stypFilter) return false;
        if (fndFilter !== '전체' && row.FND !== fndFilter) return false;
        if (rgnFilter !== '전체' && row.RGN !== rgnFilter) return false;
        if (uscFilter !== '전체' && row.USC !== uscFilter) return false;
        
        // 선택된 연도의 데이터가 있는지 확인
        if (selectedYear) {
            const value = row[`SCR_EST_${selectedYear}`];
            return value !== null && value !== undefined && value !== '' && !isNaN(parseFloat(value));
        }
        
        return true;
    });
    
    // 이름순으로 정렬
    filteredData.sort((a, b) => {
        const nameA = (a.SNM || '').toString();
        const nameB = (b.SNM || '').toString();
        return nameA.localeCompare(nameB, 'ko');
    });
    
    return filteredData;
}

// 대학 목록 업데이트
function updateUniversityList() {
    const listContainer = document.getElementById('universityList');
    if (!listContainer) {
        console.error('universityList 요소를 찾을 수 없습니다.');
        return;
    }
    
    const filtered = applyFilters();
    console.log(`필터링된 대학 수: ${filtered.length}개`);
    
    // 기존 목록 초기화
    listContainer.innerHTML = '';
    
    if (filtered.length === 0) {
        listContainer.innerHTML = '<div style="padding: 20px; text-align: center; color: #666;">필터 조건에 맞는 대학이 없습니다.</div>';
        return;
    }
    
    filtered.forEach((row, index) => {
        const item = document.createElement('div');
        item.className = 'university-item';
        
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.id = `univ_${index}_${row.SNM}`;
        checkbox.value = row.SNM;
        checkbox.checked = selectedUniversities.has(row.SNM);
        checkbox.onchange = () => updateSelectedUniversities();
        
        const label = document.createElement('label');
        label.htmlFor = `univ_${index}_${row.SNM}`;
        label.textContent = row.SNM || 'Unknown';
        
        item.appendChild(checkbox);
        item.appendChild(label);
        listContainer.appendChild(item);
    });
    
    updateSelectedCount();
    console.log('대학 목록 DOM 업데이트 완료');
}

// 선택된 대학 업데이트
function updateSelectedUniversities() {
    selectedUniversities.clear();
    
    const checkboxes = document.querySelectorAll('#universityList input[type="checkbox"]:checked');
    checkboxes.forEach(checkbox => {
        selectedUniversities.add(checkbox.value);
    });
    
    updateSelectedCount();
}

// 선택된 개수 업데이트
function updateSelectedCount() {
    const countElement = document.getElementById('selectedCount');
    if (countElement) {
        countElement.textContent = `${selectedUniversities.size}개 선택됨`;
    }
}

// 전체 선택/해제
function toggleAllUniversities() {
    const checkboxes = document.querySelectorAll('#universityList input[type="checkbox"]');
    const allChecked = Array.from(checkboxes).every(cb => cb.checked);
    
    checkboxes.forEach(checkbox => {
        checkbox.checked = !allChecked;
    });
    
    updateSelectedUniversities();
}

// 선택 모드 설정
function setSelectionMode(mode) {
    selectionMode = mode;
    
    const modeBtns = document.querySelectorAll('.mode-btn');
    modeBtns.forEach(btn => btn.classList.remove('active'));
    
    // 클릭된 버튼을 활성화
    const clickedBtn = Array.from(modeBtns).find(btn => 
        (mode === 'all' && btn.textContent.includes('필터링 후 전체')) ||
        (mode === 'manual' && btn.textContent.includes('수동 선택'))
    );
    if (clickedBtn) {
        clickedBtn.classList.add('active');
    }
    
    const selector = document.getElementById('universitySelector');
    const dataRangeGroup = document.getElementById('dataRangeSliderGroup');
    
    console.log(`선택 모드 변경: ${mode}`);
    
    if (mode === 'manual') {
        // 수동 선택 모드
        if (selector) selector.classList.add('active');
        if (dataRangeGroup) dataRangeGroup.style.display = 'none';
        console.log('대학 목록 업데이트 시작...');
        updateUniversityList();
        console.log('대학 목록 업데이트 완료');
    } else {
        // 전체 모드
        if (selector) selector.classList.remove('active');
        if (dataRangeGroup) dataRangeGroup.style.display = 'block';
        selectedUniversities.clear();
        updateDataRangeSliders();
    }
    
    updateCurrentInfo();
}

// 차트 데이터 준비
function prepareChartData() {
    const selectedYear = document.getElementById('yearSelect')?.value;
    if (!selectedYear) {
        alert('연도를 선택해주세요.');
        return [];
    }
    
    const filtered = applyFilters();
    let dataToUse = filtered;
    
    // 수동 선택 모드이고 선택된 대학이 있으면 필터링
    if (selectionMode === 'manual' && selectedUniversities.size > 0) {
        dataToUse = filtered.filter(row => selectedUniversities.has(row.SNM));
    } else {
        // 전체 모드일 때는 데이터 범위 슬라이더 적용
        const startIdx = selectedDataRange.start - 1; // 1부터 시작하므로 -1
        const endIdx = selectedDataRange.end;
        dataToUse = filtered.slice(startIdx, endIdx);
    }
    
    // 선택된 연도의 점수 데이터만 추출
    const scoreColumn = `SCR_EST_${selectedYear}`;
    
    return dataToUse.map(row => ({
        university: row.SNM,
        score: parseFloat(row[scoreColumn]) || 0,
        styp: row.STYP,
        fnd: row.FND,
        rgn: row.RGN,
        usc: row.USC
    })).filter(item => item.score > 0);
}

// 차트 생성
async function generateChart() {
    if (!tableData) {
        await loadTableData();
        if (!tableData) return;
    }
    
    showLoading();
    
    try {
        const chartData = prepareChartData();
        
        if (chartData.length === 0) {
            showError('선택한 조건에 해당하는 데이터가 없습니다.');
            return;
        }
        
        // 정렬 적용
        const sortOrder = document.getElementById('sortOrder')?.value || 'rank_desc';
        if (sortOrder === 'rank_desc') {
            chartData.sort((a, b) => b.score - a.score);
        } else if (sortOrder === 'rank_asc') {
            chartData.sort((a, b) => a.score - b.score);
        } else if (sortOrder === 'university') {
            chartData.sort((a, b) => a.university.localeCompare(b.university, 'ko'));
        }
        
        createChart(chartData);
        updateDataCount(chartData.length);
        
        // 플레이스홀더 숨기기
        document.getElementById('chartPlaceholder').style.display = 'none';
        document.getElementById('mainChart').style.display = 'block';
        
    } catch (error) {
        console.error('차트 생성 실패:', error);
        showError('차트 생성 중 오류가 발생했습니다.');
    } finally {
        hideLoading();
    }
}

// Y축 스케일 자동 계산 함수
function calculateYAxisScale(scores) {
    if (!scores || scores.length === 0) {
        return { min: 0, max: 100, beginAtZero: true };
    }
    
    const yAxisModeSelect = document.getElementById('yAxisMode')?.value || 'auto';
    
    switch (yAxisModeSelect) {
        case 'zero':
            // 항상 0부터 시작
            return {
                min: 0,
                max: Math.max(100, Math.max(...scores) * 1.1),
                beginAtZero: true
            };
            
        case 'manual':
            // 수동 설정값 사용
            return {
                min: manualYAxis.min,
                max: manualYAxis.max,
                beginAtZero: manualYAxis.min === 0
            };
            
        case 'auto':
        default:
            // 자동 스케일링
            const min = Math.min(...scores);
            const max = Math.max(...scores);
            const range = max - min;
            
            // 데이터 범위가 좁으면 자동 스케일링, 넓으면 0부터 시작
            if (range < 20 && min > 10) {
                // 범위가 좁고 최소값이 10보다 크면 자동 스케일링
                const padding = range * 0.1; // 10% 여백
                return {
                    min: Math.max(0, min - padding),
                    max: max + padding,
                    beginAtZero: false
                };
            } else {
                // 범위가 넓거나 최소값이 작으면 0부터 시작
                return {
                    min: 0,
                    max: Math.max(100, max * 1.1),
                    beginAtZero: true
                };
            }
    }
}

// Y축 모드 변경 이벤트
function onYAxisModeChange() {
    const yAxisModeSelect = document.getElementById('yAxisMode');
    const manualGroup = document.getElementById('manualYAxisGroup');
    
    yAxisMode = yAxisModeSelect?.value || 'auto';
    
    if (yAxisMode === 'manual') {
        manualGroup.style.display = 'block';
        // 현재 데이터 기반으로 기본값 설정
        if (currentChart && currentChart.data.datasets[0].data.length > 0) {
            const scores = currentChart.data.datasets[0].data;
            const min = Math.min(...scores);
            const max = Math.max(...scores);
            const range = max - min;
            const padding = range * 0.1;
            
            document.getElementById('yAxisMin').value = Math.max(0, min - padding).toFixed(1);
            document.getElementById('yAxisMax').value = (max + padding).toFixed(1);
            manualYAxis.min = parseFloat(document.getElementById('yAxisMin').value);
            manualYAxis.max = parseFloat(document.getElementById('yAxisMax').value);
        }
    } else {
        manualGroup.style.display = 'none';
    }
    
    console.log(`Y축 모드 변경: ${yAxisMode}`);
    
    // 차트가 있으면 업데이트
    if (currentChart) {
        generateChart();
    }
}

// 수동 Y축 범위 변경 이벤트
function onManualYAxisChange() {
    const minInput = document.getElementById('yAxisMin');
    const maxInput = document.getElementById('yAxisMax');
    
    let minValue = parseFloat(minInput.value) || 0;
    let maxValue = parseFloat(maxInput.value) || 100;
    
    // 최소값이 최대값보다 크면 조정
    if (minValue >= maxValue) {
        if (event.target.id === 'yAxisMin') {
            maxValue = minValue + 1;
            maxInput.value = maxValue;
        } else {
            minValue = maxValue - 1;
            minInput.value = minValue;
        }
    }
    
    manualYAxis.min = minValue;
    manualYAxis.max = maxValue;
    
    console.log(`수동 Y축 범위 변경: ${minValue} ~ ${maxValue}`);
    
    // 차트가 있으면 업데이트
    if (currentChart) {
        generateChart();
    }
}

// 차트 생성 (차트 타입에 따라)
function createChart(data) {
    const ctx = document.getElementById('mainChart').getContext('2d');
    const chartType = document.getElementById('chartType')?.value || 'bar';
    
    if (currentChart) {
        currentChart.destroy();
    }
    
    const labels = data.map(item => item.university);
    const scores = data.map(item => item.score);
    
    // Y축 스케일 자동 계산
    const yAxisScale = calculateYAxisScale(scores);
    
    let chartConfig = {
        data: {
            labels: labels,
            datasets: [{
                label: '환경점수',
                data: scores,
                backgroundColor: CHART_COLORS.palette.slice(0, data.length),
                borderColor: CHART_COLORS.palette.slice(0, data.length).map(color => color.replace('0.8', '1')),
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: `${document.getElementById('yearSelect')?.value}년 환경점수 분석 (${data.length}개 대학)`
                },
                legend: {
                    display: chartType === 'pie',
                    position: 'bottom'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const item = data[context.dataIndex];
                            return [
                                `${item.university}: ${item.score.toFixed(2)}점`,
                                `유형: ${item.styp || '-'}`,
                                `설립: ${item.fnd || '-'}`,
                                `지역: ${item.rgn || '-'}`,
                                `규모: ${item.usc || '-'}`
                            ];
                        }
                    }
                }
            }
        }
    };
    
    // 차트 타입별 설정
    switch (chartType) {
        case 'bar':
            chartConfig.type = 'bar';
            chartConfig.options.scales = {
                y: {
                    beginAtZero: yAxisScale.beginAtZero,
                    min: yAxisScale.min,
                    max: yAxisScale.max,
                    title: {
                        display: true,
                        text: '환경점수'
                    },
                    ticks: {
                        callback: function(value) {
                            return value.toFixed(1) + '점';
                        }
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: '대학명'
                    },
                    ticks: {
                        maxRotation: 45,
                        minRotation: 45,
                        maxTicksLimit: Math.min(20, data.length) // 너무 많은 라벨 방지
                    }
                }
            };
            break;
            
        case 'line':
            chartConfig.type = 'line';
            chartConfig.data.datasets[0].fill = false;
            chartConfig.data.datasets[0].tension = 0.4;
            chartConfig.data.datasets[0].pointRadius = 4;
            chartConfig.data.datasets[0].pointHoverRadius = 6;
            chartConfig.options.scales = {
                y: {
                    beginAtZero: yAxisScale.beginAtZero,
                    min: yAxisScale.min,
                    max: yAxisScale.max,
                    title: {
                        display: true,
                        text: '환경점수'
                    },
                    ticks: {
                        callback: function(value) {
                            return value.toFixed(1) + '점';
                        }
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: '대학명'
                    },
                    ticks: {
                        maxTicksLimit: Math.min(15, data.length)
                    }
                }
            };
            break;
            
        case 'scatter':
            chartConfig.type = 'scatter';
            chartConfig.data.datasets[0].data = data.map((item, index) => ({
                x: index + 1,
                y: item.score
            }));
            chartConfig.data.datasets[0].pointRadius = 5;
            chartConfig.data.datasets[0].pointHoverRadius = 8;
            chartConfig.options.scales = {
                y: {
                    beginAtZero: yAxisScale.beginAtZero,
                    min: yAxisScale.min,
                    max: yAxisScale.max,
                    title: {
                        display: true,
                        text: '환경점수'
                    },
                    ticks: {
                        callback: function(value) {
                            return value.toFixed(1) + '점';
                        }
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: '순위'
                    },
                    min: 0,
                    max: data.length + 1
                }
            };
            break;
            
        case 'pie':
            chartConfig.type = 'pie';
            // 상위 10개만 표시하고 나머지는 기타로 합치기
            if (data.length > 10) {
                const top10 = data.slice(0, 10);
                const others = data.slice(10);
                const othersSum = others.reduce((sum, item) => sum + item.score, 0);
                
                chartConfig.data.labels = [...top10.map(item => item.university), '기타'];
                chartConfig.data.datasets[0].data = [...top10.map(item => item.score), othersSum];
                chartConfig.data.datasets[0].backgroundColor = [...CHART_COLORS.palette.slice(0, 10), CHART_COLORS.neutral];
            }
            // 원형 차트는 축이 없으므로 scales 제거
            delete chartConfig.options.scales;
            break;
    }
    
    currentChart = new Chart(ctx, chartConfig);
    
    // 차트 생성 후 스케일 정보 로깅
    const scaleInfo = yAxisScale.beginAtZero ? 
        `0부터 시작 (최대: ${yAxisScale.max.toFixed(1)})` : 
        `자동 스케일 (${yAxisScale.min.toFixed(1)} ~ ${yAxisScale.max.toFixed(1)})`;
    
    console.log(`${chartType} 차트 생성 완료 - Y축 스케일: ${scaleInfo}`);
    console.log(`데이터 범위: ${Math.min(...scores).toFixed(2)} ~ ${Math.max(...scores).toFixed(2)}점`);
}


// 이벤트 핸들러들
function onYearChange() {
    console.log('연도 변경됨');
    updateCurrentInfo();
    
    // 차트가 있으면 업데이트
    if (currentChart) {
        generateChart();
    }
}

function onFilterChange() {
    console.log('필터 변경됨');
    updateCurrentInfo();
    
    // 데이터 범위 슬라이더 업데이트
    updateDataRangeSliders();
    
    // 수동 선택 모드일 때 대학 목록 업데이트
    if (selectionMode === 'manual') {
        console.log('수동 선택 모드에서 대학 목록 업데이트');
        updateUniversityList();
    }
    
    // 차트가 있으면 업데이트
    if (currentChart) {
        generateChart();
    }
}

function onChartTypeChange() {
    console.log('차트 타입 변경됨');
    updateCurrentInfo();
    
    // 차트가 있으면 새로운 타입으로 재생성
    if (currentChart) {
        generateChart();
    }
}

function onSortOrderChange() {
    console.log('정렬 방식 변경됨');
    
    // 차트가 있으면 새로운 정렬로 재생성
    if (currentChart) {
        generateChart();
    }
}

function updateCurrentInfo() {
    const yearSelect = document.getElementById('yearSelect');
    const stypFilter = document.getElementById('stypFilter');
    const fndFilter = document.getElementById('fndFilter');
    const rgnFilter = document.getElementById('rgnFilter');
    const uscFilter = document.getElementById('uscFilter');
    const chartType = document.getElementById('chartType');
    
    if (yearSelect) document.getElementById('currentYear').textContent = yearSelect.value || '-';
    if (stypFilter) document.getElementById('currentStyp').textContent = stypFilter.value || '전체';
    if (fndFilter) document.getElementById('currentFnd').textContent = fndFilter.value || '전체';
    if (rgnFilter) document.getElementById('currentRgn').textContent = rgnFilter.value || '전체';
    if (uscFilter) document.getElementById('currentUsc').textContent = uscFilter.value || '전체';
    if (chartType) {
        const chartTypeMap = {
            'bar': '막대 차트',
            'line': '선 차트',
            'scatter': '산점도',
            'pie': '원형 차트'
        };
        document.getElementById('currentChartType').textContent = chartTypeMap[chartType.value] || '막대 차트';
    }
    
    document.getElementById('currentSelectionMode').textContent = 
        selectionMode === 'manual' ? '수동 선택' : '필터링 후 전체';
    
    // Y축 모드 정보도 업데이트
    const yAxisModeSelect = document.getElementById('yAxisMode');
    if (yAxisModeSelect) {
        const yAxisModeMap = {
            'auto': '자동 스케일',
            'zero': '0부터 시작',
            'manual': '수동 설정'
        };
        // 현재 분석 정보에 Y축 모드 표시 (선택적)
        console.log('현재 Y축 모드:', yAxisModeMap[yAxisModeSelect.value] || '자동 스케일');
    }
}

function updateDataCount(count) {
    document.getElementById('dataCount').textContent = `${count}개`;
}

function showLoading() {
    const loading = document.getElementById('chartLoading');
    const placeholder = document.getElementById('chartPlaceholder');
    const mainChart = document.getElementById('mainChart');
    
    if (loading) loading.style.display = 'flex';
    if (placeholder) placeholder.style.display = 'none';
    if (mainChart) mainChart.style.display = 'none';
}

function hideLoading() {
    const loading = document.getElementById('chartLoading');
    if (loading) loading.style.display = 'none';
}

function showError(message) {
    const placeholder = document.getElementById('chartPlaceholder');
    const mainChart = document.getElementById('mainChart');
    
    if (placeholder) {
        placeholder.innerHTML = `
            <div class="placeholder-content">
                <div class="placeholder-icon">⚠️</div>
                <h3>오류 발생</h3>
                <p>${message}</p>
                <p style="font-size: 12px; color: #666; margin-top: 10px;">
                    Oracle DB 연결 상태를 확인하세요.
                </p>
            </div>
        `;
        placeholder.style.display = 'flex';
    }
    
    if (mainChart) mainChart.style.display = 'none';
    hideLoading();
}

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
        const year = document.getElementById('yearSelect')?.value || 'unknown';
        const chartType = document.getElementById('chartType')?.value || 'chart';
        a.download = `libra_environmental_score_${year}_${chartType}_${timestamp}.png`;
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
    console.log('환경점수 분석 페이지 초기화');
    updateCurrentInfo();
    
    // Oracle DB 데이터 로드
    loadTableData();
    
    // 이벤트 리스너 등록
    setupEventListeners();
}

function setupEventListeners() {
    // 애니메이션 효과
    const panelSections = document.querySelectorAll('.panel-section');
    panelSections.forEach((section, index) => {
        section.style.animationDelay = `${index * 0.1}s`;
        section.style.animation = 'fadeInUp 0.6s ease-out both';
    });
    
    // 초기 선택 모드 설정
    setSelectionMode('all');
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
    console.log('환경점수 분석 페이지 DOM 로드 완료');
    initializePage();
});

// 페이지 떠날 때 차트 정리
window.addEventListener('beforeunload', function() {
    if (currentChart) {
        currentChart.destroy();
    }
    console.log('환경점수 분석 페이지를 떠납니다.');
});

// API 연결 테스트 함수
async function testOracleConnection() {
    try {
        console.log('Oracle 연결 테스트 중...');
        const response = await fetch('/api/chart-test');
        const data = await response.json();
        
        if (data.success) {
            console.log('Oracle 연결 성공:', data.message);
            console.log('샘플 데이터:', data.sample_data);
            console.log('사용 가능한 컬럼:', data.columns);
            return true;
        } else {
            console.error('Oracle 연결 실패:', data.message);
            return false;
        }
    } catch (error) {
        console.error('연결 테스트 중 오류:', error);
        return false;
    }
}

// 테이블 정보 조회 함수
async function getTableInfo() {
    try {
        console.log('테이블 정보 조회 중...');
        const response = await fetch('/api/table-info');
        const data = await response.json();
        
        if (data.success) {
            console.log('테이블 정보:', data);
            console.log('컬럼 수:', data.column_count);
            console.log('컬럼 목록:', data.columns);
            return data;
        } else {
            console.error('테이블 정보 조회 실패:', data.message);
            return null;
        }
    } catch (error) {
        console.error('테이블 정보 조회 중 오류:', error);
        return null;
    }
}

// 디버깅용 함수
function debugInfo() {
    console.log('=== 환경점수 분석 디버깅 정보 ===');
    console.log('Oracle DB 연결 상태:', tableData ? '연결됨' : '연결 안됨');
    console.log('사용 가능한 연도:', availableYears);
    console.log('테이블 데이터:', tableData ? tableData.length + '행' : '없음');
    console.log('선택된 데이터 범위:', selectedDataRange);
    console.log('선택 모드:', selectionMode);
    console.log('선택된 대학 수:', selectedUniversities.size);
    console.log('현재 차트:', currentChart ? '있음' : '없음');
    
    if (tableData && tableData.length > 0) {
        console.log('컬럼명:', Object.keys(tableData[0]));
        
        // 점수 컬럼들 확인
        const scoreColumns = Object.keys(tableData[0]).filter(key => key.match(/^SCR_EST_\d{4}$/));
        console.log('점수 컬럼들:', scoreColumns);
        
        // 각 연도별 유효 데이터 수
        availableYears.forEach(year => {
            const validCount = tableData.filter(row => {
                const value = row[`SCR_EST_${year}`];
                return value !== null && value !== undefined && value !== '' && !isNaN(parseFloat(value));
            }).length;
            console.log(`${year}년: ${validCount}개 유효 데이터`);
        });
        
        // 샘플 데이터 출력
        console.log('첫 번째 행 샘플:', tableData[0]);
    }
    
    // 필터 상태
    const filters = {
        year: document.getElementById('yearSelect')?.value,
        styp: document.getElementById('stypFilter')?.value,
        fnd: document.getElementById('fndFilter')?.value,
        rgn: document.getElementById('rgnFilter')?.value,
        usc: document.getElementById('uscFilter')?.value,
        chartType: document.getElementById('chartType')?.value,
        sortOrder: document.getElementById('sortOrder')?.value
    };
    console.log('현재 필터 설정:', filters);
    
    // 필터링된 데이터 수
    if (tableData) {
        const filtered = applyFilters();
        console.log('필터링된 데이터 수:', filtered.length);
    }
}

// 개발자 도구용 전역 함수 등록
window.debugChart = debugInfo;
window.testConnection = testOracleConnection;
window.getTableInfo = getTableInfo;
window.chartPage1 = {
    tableData,
    availableYears,
    selectedDataRange,
    selectionMode,
    selectedUniversities,
    generateChart,
    loadData: loadTableData,
    debugInfo,
    testConnection: testOracleConnection,
    getTableInfo,
    
    // 테스트 함수들
    testManualMode: function() {
        console.log('수동 선택 모드 테스트');
        console.log('현재 모드:', selectionMode);
        console.log('선택된 대학 수:', selectedUniversities.size);
        console.log('선택된 대학들:', Array.from(selectedUniversities));
        
        const selector = document.getElementById('universitySelector');
        const listContainer = document.getElementById('universityList');
        console.log('selector 표시 상태:', selector ? selector.classList.contains('active') : 'selector 없음');
        console.log('listContainer 내용:', listContainer ? listContainer.children.length + '개 항목' : 'listContainer 없음');
        
        if (listContainer && listContainer.children.length === 0) {
            console.log('대학 목록이 비어있음 - updateUniversityList() 실행');
            updateUniversityList();
        }
    },
    
    setManualMode: function() {
        setSelectionMode('manual');
    },
    setAllMode: function() {
        setSelectionMode('all');
    },
    
    // 데이터 범위 테스트
    testDataRange: function() {
        console.log('데이터 범위 테스트');
        console.log('현재 데이터 범위:', selectedDataRange);
        
        console.log('데이터 끝 +10 테스트');
        adjustDataRange('end', 10);
        console.log('변경 후 데이터 범위:', selectedDataRange);
        
        console.log('데이터 끝 -10 테스트 (원복)');
        adjustDataRange('end', -10);
        console.log('원복 후 데이터 범위:', selectedDataRange);
    },
    
    // 연도별 데이터 테스트
    testYearData: function(year) {
        if (!tableData || !availableYears.includes(year)) {
            console.log(`${year}년 데이터가 없습니다.`);
            return;
        }
        
        const scoreColumn = `SCR_EST_${year}`;
        const validData = tableData.filter(row => {
            const value = row[scoreColumn];
            return value !== null && value !== undefined && value !== '' && !isNaN(parseFloat(value));
        });
        
        console.log(`${year}년 데이터 현황:`);
        console.log(`- 전체 데이터: ${tableData.length}개`);
        console.log(`- 유효 데이터: ${validData.length}개`);
        
        if (validData.length > 0) {
            const scores = validData.map(row => parseFloat(row[scoreColumn]));
            console.log(`- 점수 범위: ${Math.min(...scores)} ~ ${Math.max(...scores)}`);
            console.log(`- 평균 점수: ${(scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(2)}`);
        }
    },
    
    // 화살표 기능 테스트
    testArrowFunctions: function() {
        console.log('화살표 기능 테스트');
        console.log('현재 데이터 범위:', selectedDataRange);
        
        // 데이터 범위 화살표 테스트
        console.log('데이터 끝 +1 테스트');
        adjustDataRange('end', 1);
        console.log('변경 후 데이터 범위:', selectedDataRange);
        
        // 원복
        console.log('데이터 끝 -1 테스트 (원복)');
        adjustDataRange('end', -1);
        console.log('원복 후 데이터 범위:', selectedDataRange);
    },
    
    // Oracle DB 재로드
    reloadData: async function() {
        console.log('Oracle DB 데이터 재로드');
        tableData = null;
        availableYears = [];
        await loadTableData();
    },
    
    // 차트 강제 재생성
    forceRegenerateChart: function() {
        console.log('차트 강제 재생성');
        if (currentChart) {
            currentChart.destroy();
            currentChart = null;
        }
        generateChart();
    },
    
    // 필터 리셋
    resetFilters: function() {
        console.log('필터 리셋');
        const selects = ['yearSelect', 'stypFilter', 'fndFilter', 'rgnFilter', 'uscFilter', 'chartType', 'sortOrder'];
        selects.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                if (id === 'yearSelect') {
                    element.value = availableYears.length > 0 ? availableYears[availableYears.length - 1] : '';
                } else if (id === 'chartType') {
                    element.value = 'bar';
                } else if (id === 'sortOrder') {
                    element.value = 'rank_desc';
                } else {
                    element.value = '전체';
                }
            }
        });
        selectedUniversities.clear();
        onFilterChange();
    },
    
    // 차트 타입 변경 테스트
    testChartTypes: function() {
        const types = ['bar', 'line', 'scatter', 'pie'];
        let currentIndex = 0;
        
        const changeType = () => {
            const chartTypeSelect = document.getElementById('chartType');
            if (chartTypeSelect) {
                chartTypeSelect.value = types[currentIndex];
                onChartTypeChange();
                console.log(`차트 타입 변경: ${types[currentIndex]}`);
                currentIndex = (currentIndex + 1) % types.length;
            }
        };
        
        console.log('차트 타입 테스트 시작 (3초마다 변경)');
        const interval = setInterval(() => {
            changeType();
            if (currentIndex === 0) {
                clearInterval(interval);
                console.log('차트 타입 테스트 완료');
            }
        }, 3000);
    }
};