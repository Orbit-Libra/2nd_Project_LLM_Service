//차트 페이지 로직 컨트롤러 -메인 진입점
// ..static/js/chart.js 
//순수 차트기능만 담당, 다른페이지에서도 사용가능
//DOM요소들과 이벤트 바인딩
//사용자 인터랙션처리
//chart/폴더 컴포넌트들을 조합해서 사용

// 전역 변수들 (기존 script_chartpage_num01.js에서 가져옴)
let csvData = null;
let filteredData = null;
let selectedUniversities = new Set();
let currentChart = null;
let chartData = null;
let currentYear = null;
let availableYears = [];
let selectionMode = 'all'; // 'all' 또는 'manual'
let selectedDataRange = { start: 1, end: 1 };

// 차트 색상 팔레트
const CHART_COLORS = [
    '#42a5f5', '#29b6f6', '#1e88e5', '#1976d2', '#1565c0',
    '#0d47a1', '#81c784', '#66bb6a', '#4caf50', '#43a047',
    '#388e3c', '#2e7d32', '#ffb74d', '#ffa726', '#ff9800',
    '#fb8c00', '#f57c00', '#ef6c00', '#ff8a65', '#ff7043'
];

// 차트 타입별 한글명
const CHART_TYPE_NAMES = {
    'bar': '막대 차트',
    'line': '선 차트',
    'scatter': '산점도',
    'pie': '원형 차트'
};

// 차트 페이지 매니저 클래스
class ChartPageManager {
    constructor() {
        this.initializePage();
        this.setupEventListeners();
    }

    // 페이지 초기화
    async initializePage() {
        console.log('차트 페이지 초기화 시작');
        
        try {
            // CSV 데이터 로드
            await this.loadCSVData();
            
            // UI 초기화
            this.initializeUI();
            
            // 필터 상태 복원
            setTimeout(() => {
                this.restoreFilterState();
                this.updateCurrentInfo();
            }, 500);
            
            console.log('차트 페이지 초기화 완료');
        } catch (error) {
            console.error('페이지 초기화 실패:', error);
        }
    }

    // CSV 데이터 로드
    async loadCSVData() {
        try {
            console.log('예측데이터총합.csv 파일 로딩 중...');
            
            const csvPath = `../../resource/csv_files/예측데이터총합.csv`;
            const response = await fetch(csvPath);
            
            if (!response.ok) {
                throw new Error(`CSV 파일을 찾을 수 없습니다: ${csvPath} (상태: ${response.status})`);
            }
            
            const csvText = await response.text();
            csvData = this.parseCSV(csvText);
            
            console.log('CSV 데이터 로드 완료:', csvData.length, '행');
            
            // 연도 추출 및 UI 업데이트
            this.extractAvailableYears();
            this.updateFilterOptions();
            this.initializeYearSelect();
            
            // 데이터 범위 초기화
            selectedDataRange = { start: 1, end: Math.min(50, csvData.length) };
            this.updateDataRangeSliders();
            
            return csvData;
        } catch (error) {
            console.error('CSV 로드 실패:', error);
            this.showError(`예측데이터총합.csv 파일을 불러올 수 없습니다: ${error.message}`);
            return null;
        }
    }

    // CSV 파싱
    parseCSV(csvText) {
        const lines = csvText.trim().split('\n');
        if (lines.length < 2) {
            throw new Error('CSV 파일이 비어있거나 형식이 올바르지 않습니다.');
        }
        
        const headers = lines[0].split(',').map(h => h.trim().replace(/"/g, ''));
        const data = [];
        
        for (let i = 1; i < lines.length; i++) {
            const values = this.parseCSVLine(lines[i]);
            if (values.length === headers.length) {
                const row = {};
                headers.forEach((header, index) => {
                    const value = values[index];
                    const numValue = parseFloat(value);
                    row[header] = isNaN(numValue) ? value : numValue;
                });
                data.push(row);
            }
        }
        
        return data;
    }

    // CSV 라인 파싱
    parseCSVLine(line) {
        const result = [];
        let current = '';
        let inQuotes = false;
        
        for (let i = 0; i < line.length; i++) {
            const char = line[i];
            
            if (char === '"') {
                inQuotes = !inQuotes;
            } else if (char === ',' && !inQuotes) {
                result.push(current.trim());
                current = '';
            } else {
                current += char;
            }
        }
        
        result.push(current.trim());
        return result.map(val => val.replace(/"/g, ''));
    }

    // 사용 가능한 연도 추출
    extractAvailableYears() {
        if (!csvData || csvData.length === 0) return;
        
        const firstRow = csvData[0];
        availableYears = [];
        
        Object.keys(firstRow).forEach(key => {
            const match = key.match(/^SCR_EST_(\d{4})$/);
            if (match) {
                const year = parseInt(match[1]);
                if (year >= 1900 && year <= 2100) {
                    availableYears.push(year);
                }
            }
        });
        
        availableYears.sort((a, b) => b - a);
        console.log('사용 가능한 연도:', availableYears);
    }

    // UI 초기화
    initializeUI() {
        // 선택 모드 버튼 초기화
        this.setSelectionMode('all');
        
        // 현재 정보 업데이트
        this.updateCurrentInfo();
    }

    // 이벤트 리스너 설정
    setupEventListeners() {
        // 차트 생성 버튼
        const generateBtn = document.getElementById('generateChart');
        if (generateBtn) {
            generateBtn.addEventListener('click', () => this.generateChart());
        }

        // 평균값 분석 버튼
        const avgBtn = document.getElementById('averageAnalysis');
        if (avgBtn) {
            avgBtn.addEventListener('click', () => this.updateChartWithAverageData());
        }

        // 모드 버튼들
        const modeBtns = document.querySelectorAll('.mode-btn');
        modeBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const mode = e.target.textContent.includes('필터링 후 전체') ? 'all' : 'manual';
                this.setSelectionMode(mode);
            });
        });

        // 필터 변경 이벤트들
        const filterIds = ['stypFilter', 'fndFilter', 'rgnFilter', 'uscFilter', 'sortOrder'];
        filterIds.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.addEventListener('change', () => this.onFilterChange());
            }
        });

        // 연도 선택 이벤트
        const yearSelect = document.getElementById('yearSelect');
        if (yearSelect) {
            yearSelect.addEventListener('change', () => this.onYearChange());
        }

        // 차트 타입 변경 이벤트
        const chartType = document.getElementById('chartType');
        if (chartType) {
            chartType.addEventListener('change', () => this.onChartTypeChange());
        }

        // 데이터 범위 슬라이더 이벤트
        const startSlider = document.getElementById('dataStartSlider');
        const endSlider = document.getElementById('dataEndSlider');
        if (startSlider) {
            startSlider.addEventListener('input', () => this.onDataSliderChange());
        }
        if (endSlider) {
            endSlider.addEventListener('input', () => this.onDataSliderChange());
        }

        // Y축 모드 변경 이벤트
        const yAxisMode = document.getElementById('yAxisMode');
        if (yAxisMode) {
            yAxisMode.addEventListener('change', () => this.onYAxisModeChange());
        }

        // 내보내기 버튼
        const exportBtn = document.getElementById('exportChart');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportChart());
        }

        // 즐겨찾기 저장 버튼
        const saveBtn = document.getElementById('saveFavorite');
        if (saveBtn) {
            saveBtn.addEventListener('click', () => this.saveAnalysis());
        }

        // 전체 선택/해제 버튼
        const toggleAllBtn = document.getElementById('toggleAll');
        if (toggleAllBtn) {
            toggleAllBtn.addEventListener('click', () => this.toggleAllUniversities());
        }
    }

    // 차트 생성 메인 함수
    async generateChart() {
        console.log('차트 생성 시작');
        
        if (!csvData) {
            this.showLoading();
            await this.loadCSVData();
            if (!csvData) {
                this.hideLoading();
                return;
            }
            this.hideLoading();
        }

        const year = document.getElementById('yearSelect')?.value;
        if (!year) {
            this.showError('연도를 선택해주세요.');
            return;
        }

        currentYear = year;
        const chartType = document.getElementById('chartType')?.value || 'bar';
        
        this.showLoading();
        
        try {
            const processedData = this.processCSVDataForChart(csvData, year);
            
            if (processedData && processedData.length > 0) {
                this.createChart(processedData, chartType);
                this.updateDataCount(processedData.length);
                
                // 플레이스홀더 숨기기
                const placeholder = document.getElementById('chartPlaceholder');
                if (placeholder) {
                    placeholder.style.display = 'none';
                }
            } else {
                this.showError('대학의 정보가 없습니다. 다른 곳을 선택해주세요.');
            }
        } catch (error) {
            console.error('차트 생성 실패:', error);
            this.showError('차트 생성 중 오류가 발생했습니다: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }

    // 선택 모드 설정
    setSelectionMode(mode) {
        selectionMode = mode;
        
        const modeBtns = document.querySelectorAll('.mode-btn');
        modeBtns.forEach(btn => btn.classList.remove('active'));
        
        const clickedBtn = Array.from(modeBtns).find(btn => 
            (mode === 'all' && btn.textContent.includes('필터링 후 전체')) ||
            (mode === 'manual' && btn.textContent.includes('수동 선택'))
        );
        if (clickedBtn) {
            clickedBtn.classList.add('active');
        }
        
        const selector = document.getElementById('universitySelector');
        const dataRangeGroup = document.getElementById('dataRangeSliderGroup');
        
        if (mode === 'manual') {
            if (selector) selector.classList.add('active');
            if (dataRangeGroup) dataRangeGroup.style.display = 'none';
            this.updateUniversityList();
        } else {
            if (selector) selector.classList.remove('active');
            if (dataRangeGroup) dataRangeGroup.style.display = 'block';
            selectedUniversities.clear();
            this.updateDataRangeSliders();
        }
        
        this.updateCurrentInfo();
    }

    // 나머지 메서드들은 기존 코드에서 그대로 가져오되, this. 붙여서 사용
    showLoading() {
        const loading = document.getElementById('chartLoading');
        const placeholder = document.getElementById('chartPlaceholder');
        if (loading) loading.style.display = 'flex';
        if (placeholder) placeholder.style.display = 'none';
    }

    hideLoading() {
        const loading = document.getElementById('chartLoading');
        if (loading) loading.style.display = 'none';
    }

    showError(message) {
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
        this.hideLoading();
    }

    // 추가 메서드들... (기존 코드에서 필요한 것들 추가)
    updateCurrentInfo() {
        // 현재 상태 정보 업데이트
        const elements = {
            'currentYear': currentYear ? `${currentYear}년` : '-',
            'currentStyp': document.getElementById('stypFilter')?.value || '전체',
            'currentFnd': document.getElementById('fndFilter')?.value || '전체',
            'currentRgn': document.getElementById('rgnFilter')?.value || '전체',
            'currentUsc': document.getElementById('uscFilter')?.value || '전체',
            'currentChartType': CHART_TYPE_NAMES[document.getElementById('chartType')?.value] || '막대 차트',
            'currentSelectionMode': selectionMode === 'manual' ? '수동 선택' : '필터링 후 전체'
        };

        Object.entries(elements).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) element.textContent = value;
        });
    }

    updateDataCount(count) {
        const element = document.getElementById('dataCount');
        if (element) element.textContent = `${count}개`;
    }

    // ... 나머지 필요한 메서드들도 추가
}

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', function() {
    console.log('차트 페이지 DOM 로드 완료');
    
    // ChartPageManager 인스턴스 생성
    window.chartPageManager = new ChartPageManager();
});

// 전역 함수들 (HTML에서 직접 호출하는 경우를 위해)
function generateChart() {
    if (window.chartPageManager) {
        window.chartPageManager.generateChart();
    }
}

function setSelectionMode(mode) {
    if (window.chartPageManager) {
        window.chartPageManager.setSelectionMode(mode);
    }
}

// 디버깅용
window.debugChart = function() {
    console.log('=== 차트 페이지 디버깅 정보 ===');
    console.log('csvData:', csvData);
    console.log('currentYear:', currentYear);
    console.log('selectionMode:', selectionMode);
    console.log('chartPageManager:', window.chartPageManager);
};