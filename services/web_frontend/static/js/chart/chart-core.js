//차트 생성 핵심로직담당
//../static/js/chart/chart-core.js
//chart.js통합- 라이브러리 검증, 캔버스 설정
//차트생성- 모든타입지원(bar,line,pie,scatter,radar등)
//데이터셋 생성- 타입별 최적화된 데이터 구조
//동적색상- 데이터수에따른 HSL 색상 자동생성
//Y축 설정- 향상된/자동/데이터범위/사용자 지정모드
//차트 업데이트- 기존 차트 데이터만 변경
//내보내기- PNG/JPG/WebP 형식지원
//이벤트 시스템- 차트생성/업데이트 이벤트
//에러 처리- 검증, 로딩,에러메시지


LibraChart.Core = {
    
    // 차트 상태
    state: {
        currentChart: null,
        canvas: null,
        ctx: null,
        isGenerating: false,
        lastConfig: null
    },
    
    // Chart.js 기본 설정
    defaultConfig: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
            intersect: false,
            mode: 'index'
        },
        plugins: {
            tooltip: {
                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                titleColor: '#fff',
                bodyColor: '#fff',
                borderColor: '#42a5f5',
                borderWidth: 1,
                cornerRadius: 6,
                displayColors: true,
                callbacks: {
                    title: function(tooltipItems) {
                        return tooltipItems[0].label;
                    },
                    label: function(context) {
                        const value = context.parsed.y || context.parsed;
                        return `환경점수: ${value}점`;
                    }
                }
            },
            legend: {
                display: true,
                position: 'top',
                labels: {
                    usePointStyle: true,
                    padding: 20,
                    font: {
                        size: 12
                    }
                }
            }
        },
        animation: {
            duration: 800,
            easing: 'easeInOutQuart'
        }
    },
    
    // 초기화
    init: () => {
        LibraChart.Utils.log('차트 코어 모듈 초기화');
        LibraChart.Core.setupCanvas();
        LibraChart.Core.validateChartJS();
    },
    
    // 캔버스 설정
    setupCanvas: () => {
        LibraChart.Core.state.canvas = LibraChart.Utils.getElementById('mainChart');
        
        if (!LibraChart.Core.state.canvas) {
            LibraChart.Utils.error('차트 캔버스를 찾을 수 없습니다');
            return false;
        }
        
        LibraChart.Core.state.ctx = LibraChart.Core.state.canvas.getContext('2d');
        LibraChart.Utils.log('캔버스 설정 완료');
        return true;
    },
    
    // Chart.js 라이브러리 확인
    validateChartJS: () => {
        if (typeof Chart === 'undefined') {
            LibraChart.Utils.error('Chart.js 라이브러리가 로드되지 않았습니다');
            return false;
        }
        
        LibraChart.Utils.log(`Chart.js 버전: ${Chart.version}`);
        return true;
    },
    
    // 차트 생성 메인 함수
    generateChart: (data, options = {}) => {
        LibraChart.Utils.log('차트 생성 시작', { dataCount: data.length, options });
        
        if (LibraChart.Core.state.isGenerating) {
            LibraChart.Utils.warn('이미 차트 생성 중입니다');
            return false;
        }
        
        try {
            LibraChart.Core.state.isGenerating = true;
            LibraChart.Core.showLoading(true);
            
            // 데이터 검증
            if (!LibraChart.Core.validateData(data)) {
                throw new Error('유효하지 않은 데이터입니다');
            }
            
            // 기존 차트 제거
            LibraChart.Core.destroyChart();
            
            // 차트 설정 생성
            const config = LibraChart.Core.createChartConfig(data, options);
            
            // Chart.js 인스턴스 생성
            LibraChart.Core.state.currentChart = new Chart(
                LibraChart.Core.state.ctx,
                config
            );
            
            // 설정 저장
            LibraChart.Core.state.lastConfig = config;
            
            // 플레이스홀더 숨기기
            LibraChart.Core.hidePlaceholder();
            
            LibraChart.Utils.log('차트 생성 완료');
            
            // 성공 이벤트 발생
            LibraChart.Core.triggerChartEvent('chartGenerated', {
                chart: LibraChart.Core.state.currentChart,
                config: config,
                dataCount: data.length
            });
            
            return LibraChart.Core.state.currentChart;
            
        } catch (error) {
            LibraChart.Utils.error('차트 생성 실패', error);
            LibraChart.Core.showError(error.message);
            return null;
        } finally {
            LibraChart.Core.state.isGenerating = false;
            LibraChart.Core.showLoading(false);
        }
    },
    
    // 데이터 검증
    validateData: (data) => {
        if (!Array.isArray(data)) {
            LibraChart.Utils.error('데이터가 배열이 아닙니다');
            return false;
        }
        
        if (data.length === 0) {
            LibraChart.Utils.error('데이터가 비어있습니다');
            return false;
        }
        
        // 필수 필드 확인
        const requiredFields = ['university', 'environmentScore'];
        const hasRequiredFields = data.every(item => 
            requiredFields.every(field => item.hasOwnProperty(field))
        );
        
        if (!hasRequiredFields) {
            LibraChart.Utils.error('필수 필드가 누락된 데이터가 있습니다', requiredFields);
            return false;
        }
        
        return true;
    },
    
    // 차트 설정 생성
    createChartConfig: (data, options) => {
        const chartType = options.type || 'bar';
        const dataset = LibraChart.Core.createDataset(data, chartType);
        const chartOptions = LibraChart.Core.createOptions(chartType, options);
        
        return {
            type: chartType,
            data: dataset,
            options: chartOptions
        };
    },
    
    // 데이터셋 생성
    createDataset: (data, chartType) => {
        const labels = data.map(item => 
            LibraChart.Utils.truncate(item.university, 15)
        );
        const values = data.map(item => item.environmentScore);
        
        let datasets = [];
        
        switch (chartType) {
            case 'pie':
            case 'doughnut':
                datasets = [{
                    data: values,
                    backgroundColor: LibraChart.Core.generateColors(data.length),
                    borderWidth: 2,
                    borderColor: '#fff',
                    hoverBorderWidth: 3,
                    hoverBorderColor: '#42a5f5'
                }];
                break;
                
            case 'radar':
                datasets = [{
                    label: '환경점수',
                    data: values,
                    backgroundColor: 'rgba(66, 165, 245, 0.2)',
                    borderColor: '#42a5f5',
                    borderWidth: 2,
                    pointBackgroundColor: '#42a5f5',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 4
                }];
                break;
                
            case 'scatter':
                datasets = [{
                    label: '환경점수',
                    data: data.map((item, index) => ({
                        x: index + 1,
                        y: item.environmentScore,
                        r: Math.max(5, item.studentCount / 2000) // 학생수에 따른 점 크기
                    })),
                    backgroundColor: 'rgba(66, 165, 245, 0.6)',
                    borderColor: '#42a5f5',
                    borderWidth: 1
                }];
                break;
                
            case 'line':
                datasets = [{
                    label: '환경점수',
                    data: values,
                    borderColor: '#42a5f5',
                    backgroundColor: 'rgba(66, 165, 245, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#42a5f5',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 5,
                    pointHoverRadius: 7
                }];
                break;
                
            case 'bar':
            default:
                datasets = [{
                    label: '환경점수',
                    data: values,
                    backgroundColor: data.map((item, index) => {
                        const opacity = 0.6 + (item.environmentScore / 100) * 0.4;
                        return `rgba(66, 165, 245, ${opacity})`;
                    }),
                    borderColor: '#42a5f5',
                    borderWidth: 1,
                    borderRadius: 4,
                    borderSkipped: false
                }];
        }
        
        return {
            labels: labels,
            datasets: datasets
        };
    },
    
    // 차트 옵션 생성
    createOptions: (chartType, userOptions) => {
        let options = LibraChart.Utils.deepClone(LibraChart.Core.defaultConfig);
        
        // 차트 타입별 특별 설정
        switch (chartType) {
            case 'pie':
            case 'doughnut':
                options.plugins.legend.display = true;
                options.plugins.legend.position = 'right';
                delete options.scales;
                break;
                
            case 'radar':
                options.scales = {
                    r: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            stepSize: 20
                        },
                        grid: {
                            color: 'rgba(66, 165, 245, 0.2)'
                        }
                    }
                };
                break;
                
            case 'scatter':
                options.scales = {
                    x: {
                        type: 'linear',
                        position: 'bottom',
                        title: {
                            display: true,
                            text: '순위'
                        }
                    },
                    y: {
                        ...LibraChart.Core.getYAxisConfig(userOptions),
                        title: {
                            display: true,
                            text: '환경점수'
                        }
                    }
                };
                break;
                
            default:
                options.scales = {
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            maxRotation: 45,
                            font: {
                                size: 10
                            }
                        }
                    },
                    y: {
                        ...LibraChart.Core.getYAxisConfig(userOptions),
                        grid: {
                            color: 'rgba(0, 0, 0, 0.1)'
                        },
                        title: {
                            display: true,
                            text: '환경점수'
                        }
                    }
                };
        }
        
        // 사용자 옵션 병합
        if (userOptions.yAxis) {
            Object.assign(options.scales?.y || {}, userOptions.yAxis);
        }
        
        return options;
    },
    
    // Y축 설정 생성
    getYAxisConfig: (options = {}) => {
        const mode = options.yAxisMode || 'enhanced';
        const data = LibraChart.Data.getFilteredData();
        
        if (data.length === 0) return { beginAtZero: false };
        
        const values = data.map(item => item.environmentScore);
        const minValue = Math.min(...values);
        const maxValue = Math.max(...values);
        
        switch (mode) {
            case 'enhanced':
                const range = maxValue - minValue;
                const padding = Math.max(range * 0.1, 5);
                return {
                    min: Math.max(0, minValue - padding),
                    max: Math.min(100, maxValue + padding),
                    beginAtZero: false
                };
                
            case 'dataRange':
                return {
                    min: Math.max(0, minValue - 1),
                    max: Math.min(100, maxValue + 1),
                    beginAtZero: false
                };
                
            case 'custom':
                return {
                    min: LibraChart.Utils.toNumber(options.yAxisMin, 0),
                    max: LibraChart.Utils.toNumber(options.yAxisMax, 100),
                    beginAtZero: false
                };
                
            case 'auto':
            default:
                return {
                    beginAtZero: false
                };
        }
    },
    
    // 색상 생성
    generateColors: (count) => {
        const colors = [];
        const hueStep = 360 / count;
        
        for (let i = 0; i < count; i++) {
            const hue = (i * hueStep) % 360;
            const saturation = 70 + (i % 3) * 10; // 70%, 80%, 90% 순환
            const lightness = 60 + (i % 2) * 10;  // 60%, 70% 순환
            colors.push(`hsla(${hue}, ${saturation}%, ${lightness}%, 0.8)`);
        }
        
        return colors;
    },
    
    // 차트 업데이트
    updateChart: (newData, options = {}) => {
        if (!LibraChart.Core.state.currentChart) {
            LibraChart.Utils.warn('업데이트할 차트가 없습니다. 새로 생성합니다.');
            return LibraChart.Core.generateChart(newData, options);
        }
        
        try {
            LibraChart.Utils.log('차트 업데이트 시작');
            
            const chart = LibraChart.Core.state.currentChart;
            const newDataset = LibraChart.Core.createDataset(newData, chart.config.type);
            
            // 데이터 업데이트
            chart.data.labels = newDataset.labels;
            chart.data.datasets = newDataset.datasets;
            
            // 옵션 업데이트 (필요시)
            if (options.yAxis) {
                Object.assign(chart.options.scales.y, LibraChart.Core.getYAxisConfig(options));
            }
            
            chart.update('active');
            
            LibraChart.Utils.log('차트 업데이트 완료');
            
            // 업데이트 이벤트 발생
            LibraChart.Core.triggerChartEvent('chartUpdated', {
                chart: chart,
                dataCount: newData.length
            });
            
            return chart;
            
        } catch (error) {
            LibraChart.Utils.error('차트 업데이트 실패', error);
            return LibraChart.Core.generateChart(newData, options);
        }
    },
    
    // 차트 제거
    destroyChart: () => {
        if (LibraChart.Core.state.currentChart) {
            LibraChart.Core.state.currentChart.destroy();
            LibraChart.Core.state.currentChart = null;
            LibraChart.Utils.log('기존 차트 제거됨');
        }
    },
    
    // 차트 내보내기
    exportChart: (format = 'png', filename = null) => {
        if (!LibraChart.Core.state.currentChart) {
            LibraChart.Utils.error('내보낼 차트가 없습니다');
            return false;
        }
        
        try {
            const canvas = LibraChart.Core.state.canvas;
            const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
            const defaultFilename = filename || `libra-chart-${timestamp}`;
            
            let url, mimeType;
            
            switch (format.toLowerCase()) {
                case 'png':
                    url = canvas.toDataURL('image/png');
                    mimeType = 'image/png';
                    break;
                case 'jpg':
                case 'jpeg':
                    url = canvas.toDataURL('image/jpeg', 0.9);
                    mimeType = 'image/jpeg';
                    break;
                case 'webp':
                    url = canvas.toDataURL('image/webp', 0.9);
                    mimeType = 'image/webp';
                    break;
                default:
                    throw new Error(`지원하지 않는 형식: ${format}`);
            }
            
            // 다운로드 링크 생성
            const link = document.createElement('a');
            link.download = `${defaultFilename}.${format}`;
            link.href = url;
            link.click();
            
            LibraChart.Utils.log(`차트 내보내기 완료: ${format}`);
            return true;
            
        } catch (error) {
            LibraChart.Utils.error('차트 내보내기 실패', error);
            return false;
        }
    },
    
    // 로딩 표시
    showLoading: (show = true) => {
        const loading = LibraChart.Utils.getElementById('chartLoading');
        if (loading) {
            loading.style.display = show ? 'flex' : 'none';
        }
    },
    
    // 에러 표시
    showError: (message) => {
        const errorDiv = LibraChart.Utils.getElementById('errorMessage');
        if (errorDiv) {
            errorDiv.textContent = message;
            errorDiv.style.display = 'block';
            
            setTimeout(() => {
                errorDiv.style.display = 'none';
            }, 5000);
        }
    },
    
    // 플레이스홀더 숨기기
    hidePlaceholder: () => {
        const placeholder = LibraChart.Utils.getElementById('chartPlaceholder');
        if (placeholder) {
            placeholder.style.display = 'none';
        }
    },
    
    // 플레이스홀더 표시
    showPlaceholder: () => {
        const placeholder = LibraChart.Utils.getElementById('chartPlaceholder');
        if (placeholder) {
            placeholder.style.display = 'flex';
        }
    },
    
    // 차트 이벤트 발생
    triggerChartEvent: (eventType, detail) => {
        const event = new CustomEvent(eventType, { detail });
        document.dispatchEvent(event);
    },
    
    // 현재 차트 정보 가져오기
    getChartInfo: () => {
        if (!LibraChart.Core.state.currentChart) {
            return null;
        }
        
        const chart = LibraChart.Core.state.currentChart;
        
        return {
            type: chart.config.type,
            dataCount: chart.data.labels.length,
            config: LibraChart.Core.state.lastConfig,
            canvas: {
                width: chart.canvas.width,
                height: chart.canvas.height
            }
        };
    },
    
    // 유틸리티 함수들
    deepClone: (obj) => {
        return JSON.parse(JSON.stringify(obj));
    },
    
    // 차트 리사이즈
    resize: () => {
        if (LibraChart.Core.state.currentChart) {
            LibraChart.Core.state.currentChart.resize();
            LibraChart.Utils.log('차트 리사이즈 완료');
        }
    },
    
    // 상태 리셋
    reset: () => {
        LibraChart.Core.destroyChart();
        LibraChart.Core.showPlaceholder();
        LibraChart.Core.state.lastConfig = null;
        LibraChart.Utils.log('차트 상태 리셋 완료');
    }
};

// 윈도우 리사이즈 이벤트 리스너
LibraChart.Utils.addEvent(window, 'resize', 
    LibraChart.Utils.throttle(LibraChart.Core.resize, 250)
);

LibraChart.Utils.log('Core 모듈 로드 완료');