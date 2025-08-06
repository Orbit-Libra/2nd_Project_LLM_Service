//차트 메인 초기화
//../static/js/chart/chart-main.js
//캔버스기반 차트 라이브러리의 메인클래스
//다양한 차트 타입 지원 (line, bar, scatter, area)
//애니메이션: 다양한 이징함수지원
//인터랙션: 마우스/터치 이벤트영역채우기, 하이라이트 포인트그리기
//반응형:리사이즈처리
//커스터마이징: 색상, 스타일,옵션설정
//데이터처리: 다양한 데이터 포맷지원


class Chart {
    constructor(canvas, options = {}) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.options = this.mergeOptions(this.getDefaultOptions(), options);
        
        // 상태 변수들
        this.data = null;
        this.isHovered = false;
        this.isFocused = false;
        this.animationId = null;
        this.zoomLevel = 1;
        this.panX = 0;
        this.panY = 0;
        
        // 컴포넌트 초기화
        this.tooltip = new ChartTooltip(this);
        this.legend = new ChartLegend(this);
        this.axes = new ChartAxes(this);
        this.events = new ChartEvents(this);
        
        // 초기 설정
        this.setupCanvas();
        this.setupAnimation();
    }

    getDefaultOptions() {
        return {
            type: 'line',
            responsive: true,
            maintainAspectRatio: true,
            animation: {
                enabled: true,
                duration: 1000,
                easing: 'easeOutQuart'
            },
            colors: {
                primary: '#3498db',
                secondary: '#e74c3c',
                success: '#2ecc71',
                warning: '#f39c12',
                info: '#9b59b6',
                light: '#ecf0f1',
                dark: '#34495e'
            },
            grid: {
                display: true,
                color: '#e0e0e0',
                lineWidth: 1
            },
            axes: {
                x: {
                    display: true,
                    title: '',
                    min: null,
                    max: null,
                    grid: true
                },
                y: {
                    display: true,
                    title: '',
                    min: null,
                    max: null,
                    grid: true
                }
            },
            legend: {
                display: true,
                position: 'top',
                align: 'center'
            },
            tooltip: {
                enabled: true,
                backgroundColor: 'rgba(0,0,0,0.8)',
                textColor: '#fff',
                borderRadius: 4,
                padding: 8
            },
            zoom: {
                enabled: false,
                sensitivity: 0.1,
                min: 0.1,
                max: 10
            },
            pan: {
                enabled: false,
                sensitivity: 1
            },
            interaction: {
                intersect: true,
                mode: 'nearest'
            }
        };
    }

    mergeOptions(defaults, options) {
        const merged = JSON.parse(JSON.stringify(defaults));
        
        function deepMerge(target, source) {
            for (const key in source) {
                if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
                    target[key] = target[key] || {};
                    deepMerge(target[key], source[key]);
                } else {
                    target[key] = source[key];
                }
            }
        }
        
        deepMerge(merged, options);
        return merged;
    }

    setupCanvas() {
        // 고해상도 디스플레이 지원
        const dpr = window.devicePixelRatio || 1;
        const rect = this.canvas.getBoundingClientRect();
        
        this.canvas.width = rect.width * dpr;
        this.canvas.height = rect.height * dpr;
        this.canvas.style.width = rect.width + 'px';
        this.canvas.style.height = rect.height + 'px';
        
        this.ctx.scale(dpr, dpr);
        
        // 포커스 가능하도록 설정
        this.canvas.tabIndex = 0;
        
        this.canvas.addEventListener('focus', () => {
            this.isFocused = true;
        });
        
        this.canvas.addEventListener('blur', () => {
            this.isFocused = false;
        });
    }

    setupAnimation() {
        this.animationFrame = 0;
        this.animationProgress = 0;
        this.isAnimating = false;
    }

    setData(data) {
        this.data = this.processData(data);
        this.calculateBounds();
        
        if (this.options.animation.enabled) {
            this.startAnimation();
        } else {
            this.render();
        }
    }

    processData(data) {
        // 데이터 구조 정규화
        const processed = {
            labels: data.labels || [],
            series: []
        };

        if (Array.isArray(data.datasets)) {
            processed.series = data.datasets.map((dataset, index) => ({
                label: dataset.label || `Series ${index + 1}`,
                data: dataset.data || [],
                color: dataset.color || this.getSeriesColor(index),
                borderColor: dataset.borderColor || dataset.color || this.getSeriesColor(index),
                backgroundColor: dataset.backgroundColor || this.addAlpha(dataset.color || this.getSeriesColor(index), 0.2),
                borderWidth: dataset.borderWidth || 2,
                pointRadius: dataset.pointRadius || 4,
                pointHoverRadius: dataset.pointHoverRadius || 6,
                fill: dataset.fill !== undefined ? dataset.fill : false,
                visible: dataset.visible !== undefined ? dataset.visible : true,
                type: dataset.type || this.options.type
            }));
        } else if (data.series) {
            processed.series = data.series.map((series, index) => ({
                ...series,
                color: series.color || this.getSeriesColor(index),
                visible: series.visible !== undefined ? series.visible : true
            }));
        }

        return processed;
    }

    getSeriesColor(index) {
        const colors = Object.values(this.options.colors);
        return colors[index % colors.length];
    }

    addAlpha(color, alpha) {
        if (color.startsWith('#')) {
            const r = parseInt(color.slice(1, 3), 16);
            const g = parseInt(color.slice(3, 5), 16);
            const b = parseInt(color.slice(5, 7), 16);
            return `rgba(${r}, ${g}, ${b}, ${alpha})`;
        }
        return color;
    }

    calculateBounds() {
        if (!this.data || !this.data.series.length) return;

        let minX = Infinity, maxX = -Infinity;
        let minY = Infinity, maxY = -Infinity;

        this.data.series.forEach(series => {
            if (!series.visible) return;
            
            series.data.forEach((point, index) => {
                const x = typeof point === 'object' ? point.x : index;
                const y = typeof point === 'object' ? point.y : point;
                
                minX = Math.min(minX, x);
                maxX = Math.max(maxX, x);
                minY = Math.min(minY, y);
                maxY = Math.max(maxY, y);
            });
        });

        // 여백 추가
        const paddingX = (maxX - minX) * 0.05;
        const paddingY = (maxY - minY) * 0.1;

        this.bounds = {
            minX: this.options.axes.x.min || (minX - paddingX),
            maxX: this.options.axes.x.max || (maxX + paddingX),
            minY: this.options.axes.y.min || (minY - paddingY),
            maxY: this.options.axes.y.max || (maxY + paddingY)
        };
    }

    getDrawingArea() {
        const padding = 40;
        const legendHeight = this.legend.visible ? this.legend.getHeight() : 0;
        
        return {
            x: padding,
            y: padding + legendHeight,
            width: this.canvas.width / (window.devicePixelRatio || 1) - padding * 2,
            height: this.canvas.height / (window.devicePixelRatio || 1) - padding * 2 - legendHeight
        };
    }

    getPointPosition(seriesIndex, pointIndex) {
        const series = this.data.series[seriesIndex];
        if (!series || !series.data[pointIndex]) return null;

        const point = series.data[pointIndex];
        const x = typeof point === 'object' ? point.x : pointIndex;
        const y = typeof point === 'object' ? point.y : point;

        return this.transformPoint(x, y);
    }

    transformPoint(x, y) {
        const area = this.getDrawingArea();
        
        const transformedX = area.x + ((x - this.bounds.minX) / (this.bounds.maxX - this.bounds.minX)) * area.width;
        const transformedY = area.y + area.height - ((y - this.bounds.minY) / (this.bounds.maxY - this.bounds.minY)) * area.height;
        
        // 줌/팬 적용
        return {
            x: (transformedX - area.x - area.width/2) * this.zoomLevel + area.x + area.width/2 + this.panX,
            y: (transformedY - area.y - area.height/2) * this.zoomLevel + area.y + area.height/2 + this.panY
        };
    }

    startAnimation() {
        this.isAnimating = true;
        this.animationFrame = 0;
        this.animationProgress = 0;
        this.animate();
    }

    animate() {
        if (!this.isAnimating) return;

        this.animationFrame++;
        this.animationProgress = Math.min(1, this.animationFrame / (this.options.animation.duration / 16));
        
        // 이징 함수 적용
        const easedProgress = this.applyEasing(this.animationProgress);
        
        this.render(easedProgress);
        
        if (this.animationProgress < 1) {
            this.animationId = requestAnimationFrame(() => this.animate());
        } else {
            this.isAnimating = false;
        }
    }

    applyEasing(progress) {
        switch (this.options.animation.easing) {
            case 'linear':
                return progress;
            case 'easeInQuart':
                return progress * progress * progress * progress;
            case 'easeOutQuart':
                return 1 - Math.pow(1 - progress, 4);
            case 'easeInOutQuart':
                return progress < 0.5 
                    ? 8 * progress * progress * progress * progress
                    : 1 - Math.pow(-2 * progress + 2, 4) / 2;
            default:
                return progress;
        }
    }

    render(animationProgress = 1) {
        // 캔버스 초기화
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        if (!this.data || !this.data.series.length) return;

        // 배경 그리기
        this.drawBackground();
        
        // 그리드 그리기
        if (this.options.grid.display) {
            this.axes.drawGrid();
        }
        
        // 축 그리기
        this.axes.draw();
        
        // 시리즈 그리기
        this.drawSeries(animationProgress);
        
        // 범례 그리기
        if (this.options.legend.display) {
            this.legend.draw();
        }
        
        // 하이라이트 그리기
        this.drawHighlights();
    }

    drawBackground() {
        this.ctx.fillStyle = '#ffffff';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    }

    drawSeries(animationProgress = 1) {
        this.data.series.forEach((series, index) => {
            if (!series.visible) return;
            
            this.ctx.save();
            
            switch (series.type || this.options.type) {
                case 'line':
                    this.drawLineSeries(series, animationProgress);
                    break;
                case 'bar':
                    this.drawBarSeries(series, index, animationProgress);
                    break;
                case 'scatter':
                    this.drawScatterSeries(series, animationProgress);
                    break;
                case 'area':
                    this.drawAreaSeries(series, animationProgress);
                    break;
            }
            
            this.ctx.restore();
        });
    }

    drawLineSeries(series, animationProgress) {
        const points = [];
        
        series.data.forEach((point, index) => {
            const x = typeof point === 'object' ? point.x : index;
            const y = typeof point === 'object' ? point.y : point;
            const pos = this.transformPoint(x, y);
            
            if (!isNaN(pos.x) && !isNaN(pos.y)) {
                points.push(pos);
            }
        });

        if (points.length < 2) return;

        // 애니메이션을 위한 점 개수 조절
        const visiblePoints = Math.ceil(points.length * animationProgress);
        const drawPoints = points.slice(0, visiblePoints);

        // 선 그리기
        this.ctx.strokeStyle = series.borderColor;
        this.ctx.lineWidth = series.borderWidth;
        this.ctx.beginPath();
        
        drawPoints.forEach((point, index) => {
            if (index === 0) {
                this.ctx.moveTo(point.x, point.y);
            } else {
                this.ctx.lineTo(point.x, point.y);
            }
        });
        
        this.ctx.stroke();

        // 포인트 그리기
        drawPoints.forEach(point => {
            this.ctx.fillStyle = series.backgroundColor;
            this.ctx.strokeStyle = series.borderColor;
            this.ctx.lineWidth = 2;
            
            this.ctx.beginPath();
            this.ctx.arc(point.x, point.y, series.pointRadius, 0, Math.PI * 2);
            this.ctx.fill();
            this.ctx.stroke();
        });
    }

    drawBarSeries(series, seriesIndex, animationProgress) {
        const area = this.getDrawingArea();
        const barWidth = area.width / series.data.length * 0.8;
        const barSpacing = area.width / series.data.length * 0.2;

        series.data.forEach((point, index) => {
            const y = typeof point === 'object' ? point.y : point;
            const pos = this.transformPoint(index, y);
            const zeroPos = this.transformPoint(index, 0);
            
            const barHeight = (zeroPos.y - pos.y) * animationProgress;
            const x = area.x + index * (barWidth + barSpacing) + barSpacing / 2;
            
            this.ctx.fillStyle = series.backgroundColor;
            this.ctx.fillRect(x, zeroPos.y - barHeight, barWidth, barHeight);
            
            // 테두리
            this.ctx.strokeStyle = series.borderColor;
            this.ctx.lineWidth = series.borderWidth;
            this.ctx.strokeRect(x, zeroPos.y - barHeight, barWidth, barHeight);
        });
    }

    drawScatterSeries(series, animationProgress) {
        const visiblePoints = Math.ceil(series.data.length * animationProgress);
        
        series.data.slice(0, visiblePoints).forEach((point, index) => {
            const x = typeof point === 'object' ? point.x : index;
            const y = typeof point === 'object' ? point.y : point;
            const pos = this.transformPoint(x, y);
            
            this.ctx.fillStyle = series.backgroundColor;
            this.ctx.strokeStyle = series.borderColor;
            this.ctx.lineWidth = 2;
            
            this.ctx.beginPath();
            this.ctx.arc(pos.x, pos.y, series.pointRadius, 0, Math.PI * 2);
            this.ctx.fill();
            this.ctx.stroke();
        });
    }

    drawAreaSeries(series, animationProgress) {
        const points = [];
        
        series.data.forEach((point, index) => {
            const x = typeof point === 'object' ? point.x : index;
            const y = typeof point === 'object' ? point.y : point;
            const pos = this.transformPoint(x, y);
            
            if (!isNaN(pos.x) && !isNaN(pos.y)) {
                points.push(pos);
            }
        });

        if (points.length < 2) return;

        const visiblePoints = Math.ceil(points.length * animationProgress);
        const drawPoints = points.slice(0, visiblePoints);
        const area = this.getDrawingArea();

        // 영역 채우기
        this.ctx.fillStyle = series.backgroundColor;
        this.ctx.beginPath();
        
        // 시작점
        this.ctx.moveTo(drawPoints[0].x, area.y + area.height);
        
        // 데이터 포인트들
        drawPoints.forEach(point => {
            this.ctx.lineTo(point.x, point.y);
        });
        
        // 끝점에서 바닥으로
        this.ctx.lineTo(drawPoints[drawPoints.length - 1].x, area.y + area.height);
        this.ctx.closePath();
        this.ctx.fill();

        // 경계선 그리기
        this.ctx.strokeStyle = series.borderColor;
        this.ctx.lineWidth = series.borderWidth;
        this.ctx.beginPath();
        
        drawPoints.forEach((point, index) => {
            if (index === 0) {
                this.ctx.moveTo(point.x, point.y);
            } else {
                this.ctx.lineTo(point.x, point.y);
            }
        });
        
        this.ctx.stroke();
    }

    drawHighlights() {
        // 하이라이트된 포인트 그리기
        if (this.events.highlightedPoint) {
            const point = this.events.highlightedPoint;
            const pos = this.getPointPosition(point.seriesIndex, point.pointIndex);
            
            if (pos) {
                this.ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
                this.ctx.strokeStyle = point.series.borderColor;
                this.ctx.lineWidth = 3;
                
                this.ctx.beginPath();
                this.ctx.arc(pos.x, pos.y, point.series.pointHoverRadius, 0, Math.PI * 2);
                this.ctx.fill();
                this.ctx.stroke();
            }
        }

        // 선택된 포인트 그리기
        if (this.events.selectedPoint) {
            const point = this.events.selectedPoint;
            const pos = this.getPointPosition(point.seriesIndex, point.pointIndex);
            
            if (pos) {
                this.ctx.strokeStyle = '#ff6b6b';
                this.ctx.lineWidth = 3;
                this.ctx.setLineDash([5, 5]);
                
                this.ctx.beginPath();
                this.ctx.arc(pos.x, pos.y, point.series.pointHoverRadius + 2, 0, Math.PI * 2);
                this.ctx.stroke();
                
                this.ctx.setLineDash([]);
            }
        }
    }

    // 줌 관련 메서드들
    zoom(factor, centerX, centerY) {
        if (!this.options.zoom.enabled) return;

        const newZoomLevel = this.zoomLevel * factor;
        
        if (newZoomLevel < this.options.zoom.min || newZoomLevel > this.options.zoom.max) {
            return;
        }

        if (centerX !== undefined && centerY !== undefined) {
            const area = this.getDrawingArea();
            this.panX = (this.panX - (centerX - area.x - area.width/2)) * factor + (centerX - area.x - area.width/2);
            this.panY = (this.panY - (centerY - area.y - area.height/2)) * factor + (centerY - area.y - area.height/2);
        }

        this.zoomLevel = newZoomLevel;
        this.render();
    }

    pan(deltaX, deltaY) {
        if (!this.options.pan.enabled) return;

        this.panX += deltaX * this.options.pan.sensitivity;
        this.panY += deltaY * this.options.pan.sensitivity;
        this.render();
    }

    resetZoom() {
        this.zoomLevel = 1;
        this.panX = 0;
        this.panY = 0;
        this.render();
    }

    // 리사이즈 처리
    resize() {
        this.setupCanvas();
        this.render();
    }

    // 데이터 업데이트
    updateData(data) {
        this.setData(data);
    }

    // 옵션 업데이트
    updateOptions(options) {
        this.options = this.mergeOptions(this.options, options);
        this.render();
    }

    // 시리즈 토글
    toggleSeries(seriesIndex) {
        if (this.data && this.data.series[seriesIndex]) {
            this.data.series[seriesIndex].visible = !this.data.series[seriesIndex].visible;
            this.calculateBounds();
            this.render();
        }
    }

    // 차트 정리
    destroy() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
        
        this.events.destroy();
        this.tooltip.destroy();
        
        // 캔버스 정리
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    }

    // 이미지로 내보내기
    toDataURL(type = 'image/png', quality = 1.0) {
        return this.canvas.toDataURL(type, quality);
    }

    // 차트 데이터 가져오기
    getData() {
        return this.data;
    }

    // 차트 옵션 가져오기
    getOptions() {
        return this.options;
    }
}

// 차트 팩토리 함수
function createChart(canvas, options = {}) {
    return new Chart(canvas, options);
}

// 글로벌로 사용할 수 있도록 export
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { Chart, createChart };
} else {
    window.Chart = Chart;
    window.createChart = createChart;
}