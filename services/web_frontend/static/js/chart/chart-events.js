//차트 이벤트 핸들러
//../static/js/chart/chart-events.js
//이벤트- 마우스,키보드,리사잊,터치후버
//이벤트 리스너



class ChartEvents {
    constructor(chartInstance) {
        this.chart = chartInstance;
        this.bindEvents();
    }

    bindEvents() {
        // 마우스 이벤트
        this.bindMouseEvents();
        // 키보드 이벤트
        this.bindKeyboardEvents();
        // 리사이즈 이벤트
        this.bindResizeEvents();
        // 터치 이벤트 (모바일)
        this.bindTouchEvents();
    }

    bindMouseEvents() {
        const canvas = this.chart.canvas;
        
        canvas.addEventListener('mousemove', (e) => {
            this.handleMouseMove(e);
        });

        canvas.addEventListener('click', (e) => {
            this.handleClick(e);
        });

        canvas.addEventListener('mouseenter', (e) => {
            this.handleMouseEnter(e);
        });

        canvas.addEventListener('mouseleave', (e) => {
            this.handleMouseLeave(e);
        });

        canvas.addEventListener('wheel', (e) => {
            this.handleWheel(e);
        });
    }

    bindKeyboardEvents() {
        document.addEventListener('keydown', (e) => {
            if (this.chart.isFocused) {
                this.handleKeyDown(e);
            }
        });
    }

    bindResizeEvents() {
        window.addEventListener('resize', () => {
            this.handleResize();
        });
    }

    bindTouchEvents() {
        const canvas = this.chart.canvas;
        
        canvas.addEventListener('touchstart', (e) => {
            this.handleTouchStart(e);
        });

        canvas.addEventListener('touchmove', (e) => {
            this.handleTouchMove(e);
        });

        canvas.addEventListener('touchend', (e) => {
            this.handleTouchEnd(e);
        });
    }

    handleMouseMove(event) {
        const rect = this.chart.canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;

        // 데이터 포인트 하이라이트
        this.highlightDataPoint(x, y);
        
        // 툴팁 업데이트
        this.updateTooltip(x, y);
        
        // 커서 스타일 업데이트
        this.updateCursor(x, y);
    }

    handleClick(event) {
        const rect = this.chart.canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;

        // 데이터 포인트 선택
        const selectedPoint = this.getDataPointAt(x, y);
        if (selectedPoint) {
            this.selectDataPoint(selectedPoint);
            this.triggerCustomEvent('dataPointClick', selectedPoint);
        }

        // 범례 클릭 처리
        const legendItem = this.getLegendItemAt(x, y);
        if (legendItem) {
            this.toggleSeries(legendItem.seriesIndex);
            this.triggerCustomEvent('legendClick', legendItem);
        }
    }

    handleMouseEnter(event) {
        this.chart.isHovered = true;
        this.chart.canvas.style.cursor = 'crosshair';
    }

    handleMouseLeave(event) {
        this.chart.isHovered = false;
        this.chart.canvas.style.cursor = 'default';
        this.hideTooltip();
        this.clearHighlights();
    }

    handleWheel(event) {
        event.preventDefault();
        
        if (this.chart.options.zoom.enabled) {
            const delta = event.deltaY;
            const rect = this.chart.canvas.getBoundingClientRect();
            const x = event.clientX - rect.left;
            const y = event.clientY - rect.top;
            
            this.handleZoom(delta, x, y);
        }
    }

    handleKeyDown(event) {
        switch(event.key) {
            case 'ArrowLeft':
                this.navigateDataPoint(-1);
                break;
            case 'ArrowRight':
                this.navigateDataPoint(1);
                break;
            case 'Escape':
                this.clearSelection();
                break;
            case '+':
            case '=':
                this.zoomIn();
                break;
            case '-':
                this.zoomOut();
                break;
            case '0':
                this.resetZoom();
                break;
        }
    }

    handleResize() {
        clearTimeout(this.resizeTimer);
        this.resizeTimer = setTimeout(() => {
            this.chart.resize();
        }, 250);
    }

    handleTouchStart(event) {
        event.preventDefault();
        const touches = event.touches;
        
        if (touches.length === 1) {
            // 단일 터치 - 팬 시작
            this.lastTouchX = touches[0].clientX;
            this.lastTouchY = touches[0].clientY;
            this.isPanning = true;
        } else if (touches.length === 2) {
            // 더블 터치 - 줌 시작
            this.lastTouchDistance = this.getTouchDistance(touches[0], touches[1]);
            this.isZooming = true;
            this.isPanning = false;
        }
    }

    handleTouchMove(event) {
        event.preventDefault();
        const touches = event.touches;

        if (this.isPanning && touches.length === 1) {
            const deltaX = touches[0].clientX - this.lastTouchX;
            const deltaY = touches[0].clientY - this.lastTouchY;
            
            this.handlePan(deltaX, deltaY);
            
            this.lastTouchX = touches[0].clientX;
            this.lastTouchY = touches[0].clientY;
        } else if (this.isZooming && touches.length === 2) {
            const currentDistance = this.getTouchDistance(touches[0], touches[1]);
            const scale = currentDistance / this.lastTouchDistance;
            
            this.handleTouchZoom(scale);
            
            this.lastTouchDistance = currentDistance;
        }
    }

    handleTouchEnd(event) {
        this.isPanning = false;
        this.isZooming = false;
    }

    // 유틸리티 메서드들
    highlightDataPoint(x, y) {
        const point = this.getDataPointAt(x, y);
        if (point !== this.highlightedPoint) {
            this.clearHighlights();
            this.highlightedPoint = point;
            if (point) {
                this.chart.render();
            }
        }
    }

    updateTooltip(x, y) {
        const point = this.getDataPointAt(x, y);
        if (point) {
            this.showTooltip(point, x, y);
        } else {
            this.hideTooltip();
        }
    }

    showTooltip(dataPoint, x, y) {
        const tooltip = this.chart.tooltip;
        tooltip.show(dataPoint, x, y);
    }

    hideTooltip() {
        const tooltip = this.chart.tooltip;
        tooltip.hide();
    }

    updateCursor(x, y) {
        const point = this.getDataPointAt(x, y);
        const legendItem = this.getLegendItemAt(x, y);
        
        if (point || legendItem) {
            this.chart.canvas.style.cursor = 'pointer';
        } else {
            this.chart.canvas.style.cursor = 'crosshair';
        }
    }

    getDataPointAt(x, y) {
        const tolerance = 10;
        
        for (let seriesIndex = 0; seriesIndex < this.chart.data.series.length; seriesIndex++) {
            const series = this.chart.data.series[seriesIndex];
            if (!series.visible) continue;
            
            for (let pointIndex = 0; pointIndex < series.data.length; pointIndex++) {
                const point = this.chart.getPointPosition(seriesIndex, pointIndex);
                if (point && this.isPointNear(x, y, point.x, point.y, tolerance)) {
                    return {
                        seriesIndex,
                        pointIndex,
                        data: series.data[pointIndex],
                        series: series
                    };
                }
            }
        }
        return null;
    }

    getLegendItemAt(x, y) {
        if (!this.chart.legend || !this.chart.legend.visible) return null;
        
        const legendBounds = this.chart.legend.getBounds();
        if (!this.isPointInRect(x, y, legendBounds)) return null;
        
        return this.chart.legend.getItemAt(x, y);
    }

    isPointNear(x1, y1, x2, y2, tolerance) {
        const dx = x1 - x2;
        const dy = y1 - y2;
        return Math.sqrt(dx * dx + dy * dy) <= tolerance;
    }

    isPointInRect(x, y, rect) {
        return x >= rect.x && x <= rect.x + rect.width &&
               y >= rect.y && y <= rect.y + rect.height;
    }

    selectDataPoint(point) {
        this.selectedPoint = point;
        this.chart.render();
    }

    clearSelection() {
        this.selectedPoint = null;
        this.chart.render();
    }

    clearHighlights() {
        if (this.highlightedPoint) {
            this.highlightedPoint = null;
            this.chart.render();
        }
    }

    toggleSeries(seriesIndex) {
        const series = this.chart.data.series[seriesIndex];
        series.visible = !series.visible;
        this.chart.render();
    }

    handleZoom(delta, centerX, centerY) {
        const zoomFactor = delta > 0 ? 0.9 : 1.1;
        this.chart.zoom(zoomFactor, centerX, centerY);
    }

    handleTouchZoom(scale) {
        this.chart.zoom(scale);
    }

    handlePan(deltaX, deltaY) {
        this.chart.pan(deltaX, deltaY);
    }

    zoomIn() {
        this.chart.zoom(1.2);
    }

    zoomOut() {
        this.chart.zoom(0.8);
    }

    resetZoom() {
        this.chart.resetZoom();
    }

    navigateDataPoint(direction) {
        // 키보드 네비게이션 구현
        if (!this.selectedPoint) {
            // 첫 번째 데이터 포인트 선택
            this.selectFirstDataPoint();
            return;
        }

        const currentSeries = this.selectedPoint.seriesIndex;
        const currentPoint = this.selectedPoint.pointIndex;
        const series = this.chart.data.series[currentSeries];

        let newPointIndex = currentPoint + direction;
        
        if (newPointIndex >= 0 && newPointIndex < series.data.length) {
            this.selectDataPoint({
                seriesIndex: currentSeries,
                pointIndex: newPointIndex,
                data: series.data[newPointIndex],
                series: series
            });
        }
    }

    selectFirstDataPoint() {
        for (let i = 0; i < this.chart.data.series.length; i++) {
            const series = this.chart.data.series[i];
            if (series.visible && series.data.length > 0) {
                this.selectDataPoint({
                    seriesIndex: i,
                    pointIndex: 0,
                    data: series.data[0],
                    series: series
                });
                break;
            }
        }
    }

    getTouchDistance(touch1, touch2) {
        const dx = touch1.clientX - touch2.clientX;
        const dy = touch1.clientY - touch2.clientY;
        return Math.sqrt(dx * dx + dy * dy);
    }

    triggerCustomEvent(eventName, data) {
        const event = new CustomEvent(eventName, {
            detail: data
        });
        this.chart.canvas.dispatchEvent(event);
    }

    destroy() {
        // 이벤트 리스너 정리
        const canvas = this.chart.canvas;
        canvas.removeEventListener('mousemove', this.handleMouseMove);
        canvas.removeEventListener('click', this.handleClick);
        canvas.removeEventListener('mouseenter', this.handleMouseEnter);
        canvas.removeEventListener('mouseleave', this.handleMouseLeave);
        canvas.removeEventListener('wheel', this.handleWheel);
        
        window.removeEventListener('resize', this.handleResize);
        
        if (this.resizeTimer) {
            clearTimeout(this.resizeTimer);
        }
    }
}

// 글로벌로 사용할 수 있도록 export
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ChartEvents;
} else {
    window.ChartEvents = ChartEvents;
}
