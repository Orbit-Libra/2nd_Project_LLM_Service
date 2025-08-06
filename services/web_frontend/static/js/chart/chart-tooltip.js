//차트 툴팁 컴포넌트
//../static/js/chart/chart-tooltip.js
//동적 툴팁생성 및 위치조정
//페이드 인/아웃 애니메이션
//멀티 시리즈 데이터 표시
//커스텀 포맷터 지원
//다양한 테마(dark, light, minimal)
//스마트 위치 조정(화면 경계 처리)
//HTML/텍스트 콘텐츠 지원


class ChartTooltip {
    constructor(chart) {
        this.chart = chart;
        this.visible = false;
        this.content = '';
        this.x = 0;
        this.y = 0;
        this.element = null;
        this.fadeTimeout = null;
        
        this.createTooltipElement();
        this.setupStyles();
    }

    createTooltipElement() {
        this.element = document.createElement('div');
        this.element.className = 'chart-tooltip';
        this.element.style.position = 'absolute';
        this.element.style.pointerEvents = 'none';
        this.element.style.zIndex = '1000';
        this.element.style.opacity = '0';
        this.element.style.transition = 'opacity 0.2s ease-in-out';
        
        // 차트 컨테이너에 추가
        const container = this.chart.canvas.parentNode;
        if (container) {
            container.style.position = 'relative';
            container.appendChild(this.element);
        } else {
            document.body.appendChild(this.element);
        }
    }

    setupStyles() {
        const options = this.chart.options.tooltip;
        
        this.element.style.backgroundColor = options.backgroundColor;
        this.element.style.color = options.textColor;
        this.element.style.borderRadius = options.borderRadius + 'px';
        this.element.style.padding = options.padding + 'px';
        this.element.style.fontSize = '12px';
        this.element.style.fontFamily = 'Arial, sans-serif';
        this.element.style.boxShadow = '0 2px 8px rgba(0,0,0,0.2)';
        this.element.style.whiteSpace = 'nowrap';
        this.element.style.minWidth = '80px';
        this.element.style.textAlign = 'center';
    }

    show(dataPoint, x, y) {
        if (!this.chart.options.tooltip.enabled) return;

        this.content = this.generateContent(dataPoint);
        this.element.innerHTML = this.content;
        
        this.updatePosition(x, y);
        this.visible = true;
        
        // 페이드 인 효과
        clearTimeout(this.fadeTimeout);
        this.element.style.opacity = '1';
        this.element.style.display = 'block';
    }

    hide() {
        if (!this.visible) return;
        
        this.visible = false;
        
        // 페이드 아웃 효과
        this.element.style.opacity = '0';
        
        this.fadeTimeout = setTimeout(() => {
            if (!this.visible) {
                this.element.style.display = 'none';
            }
        }, 200);
    }

    updatePosition(x, y) {
        const tooltipRect = this.element.getBoundingClientRect();
        const canvasRect = this.chart.canvas.getBoundingClientRect();
        const containerRect = this.chart.canvas.parentNode?.getBoundingClientRect() || canvasRect;
        
        // 기본 위치 (마우스 우측 하단)
        let tooltipX = x + 10;
        let tooltipY = y + 10;
        
        // 우측 경계 체크
        if (tooltipX + tooltipRect.width > containerRect.width) {
            tooltipX = x - tooltipRect.width - 10;
        }
        
        // 하단 경계 체크
        if (tooltipY + tooltipRect.height > containerRect.height) {
            tooltipY = y - tooltipRect.height - 10;
        }
        
        // 좌측 경계 체크
        if (tooltipX < 0) {
            tooltipX = 10;
        }
        
        // 상단 경계 체크
        if (tooltipY < 0) {
            tooltipY = 10;
        }
        
        this.element.style.left = tooltipX + 'px';
        this.element.style.top = tooltipY + 'px';
        
        this.x = tooltipX;
        this.y = tooltipY;
    }

    generateContent(dataPoint) {
        const { series, data, pointIndex } = dataPoint;
        const label = this.chart.data.labels ? this.chart.data.labels[pointIndex] : `Point ${pointIndex + 1}`;
        
        let html = '<div class="tooltip-content">';
        
        // 제목 (라벨)
        if (label) {
            html += `<div class="tooltip-title" style="font-weight: bold; margin-bottom: 4px; border-bottom: 1px solid rgba(255,255,255,0.3); padding-bottom: 2px;">${this.escapeHtml(label)}</div>`;
        }
        
        // 시리즈 정보
        html += '<div class="tooltip-items">';
        
        // 색상 인디케이터와 시리즈 정보
        const colorIndicator = `<span style="display: inline-block; width: 10px; height: 10px; background-color: ${series.color}; border-radius: 50%; margin-right: 6px; vertical-align: middle;"></span>`;
        
        const value = typeof data === 'object' ? data.y : data;
        const formattedValue = this.formatValue(value);
        
        html += `<div style="margin: 2px 0;">`;
        html += colorIndicator;
        html += `<span style="color: ${this.chart.options.tooltip.textColor};">${this.escapeHtml(series.label)}: </span>`;
        html += `<span style="font-weight: bold;">${formattedValue}</span>`;
        html += `</div>`;
        
        // 추가 정보가 있는 경우
        if (typeof data === 'object' && data.x !== undefined) {
            html += `<div style="margin: 2px 0; font-size: 11px; opacity: 0.8;">`;
            html += `X: ${this.formatValue(data.x)}`;
            html += `</div>`;
        }
        
        html += '</div>';
        html += '</div>';
        
        return html;
    }

    generateMultiSeriesContent(dataPoints) {
        const pointIndex = dataPoints[0].pointIndex;
        const label = this.chart.data.labels ? this.chart.data.labels[pointIndex] : `Point ${pointIndex + 1}`;
        
        let html = '<div class="tooltip-content">';
        
        // 제목
        if (label) {
            html += `<div class="tooltip-title" style="font-weight: bold; margin-bottom: 6px; border-bottom: 1px solid rgba(255,255,255,0.3); padding-bottom: 4px;">${this.escapeHtml(label)}</div>`;
        }
        
        // 각 시리즈 정보
        html += '<div class="tooltip-items">';
        
        dataPoints.forEach(dataPoint => {
            const { series, data } = dataPoint;
            const colorIndicator = `<span style="display: inline-block; width: 10px; height: 10px; background-color: ${series.color}; border-radius: 50%; margin-right: 6px; vertical-align: middle;"></span>`;
            
            const value = typeof data === 'object' ? data.y : data;
            const formattedValue = this.formatValue(value);
            
            html += `<div style="margin: 3px 0; display: flex; align-items: center;">`;
            html += colorIndicator;
            html += `<span style="flex: 1;">${this.escapeHtml(series.label)}: </span>`;
            html += `<span style="font-weight: bold; margin-left: 8px;">${formattedValue}</span>`;
            html += `</div>`;
        });
        
        html += '</div>';
        html += '</div>';
        
        return html;
    }

    formatValue(value) {
        if (typeof value === 'number') {
            // 소수점 처리
            if (value % 1 === 0) {
                return value.toLocaleString();
            } else {
                return parseFloat(value.toFixed(2)).toLocaleString();
            }
        }
        return String(value);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // 커스텀 툴팁 포맷터 설정
    setCustomFormatter(formatter) {
        this.customFormatter = formatter;
    }

    // 커스텀 포맷터가 있는 경우 사용
    generateCustomContent(dataPoint) {
        if (this.customFormatter) {
            return this.customFormatter(dataPoint);
        }
        return this.generateContent(dataPoint);
    }

    // 툴팁 스타일 업데이트
    updateStyle(styles) {
        Object.assign(this.element.style, styles);
    }

    // 툴팁 클래스 추가/제거
    addClass(className) {
        this.element.classList.add(className);
    }

    removeClass(className) {
        this.element.classList.remove(className);
    }

    // 애니메이션 효과 설정
    setAnimation(options) {
        const { duration = 200, easing = 'ease-in-out' } = options;
        this.element.style.transition = `opacity ${duration}ms ${easing}`;
    }

    // 위치 고정 모드 (마우스 따라다니지 않음)
    setFixedPosition(x, y) {
        this.element.style.left = x + 'px';
        this.element.style.top = y + 'px';
        this.fixedPosition = true;
    }

    // 위치 고정 해제
    unsetFixedPosition() {
        this.fixedPosition = false;
    }

    // 툴팁 내용 직접 설정
    setContent(content) {
        this.element.innerHTML = content;
    }

    // 툴팁 크기 가져오기
    getBounds() {
        return this.element.getBoundingClientRect();
    }

    // 툴팁 표시 여부 확인
    isVisible() {
        return this.visible;
    }

    // 고급 위치 조정 옵션
    setPositionMode(mode) {
        this.positionMode = mode; // 'follow', 'fixed', 'smart'
    }

    // 스마트 위치 조정 (차트 영역 내에서만)
    smartPosition(x, y) {
        const canvasRect = this.chart.canvas.getBoundingClientRect();
        const tooltipRect = this.element.getBoundingClientRect();
        
        // 차트 영역 내에서만 위치 조정
        let tooltipX = Math.max(0, Math.min(x, canvasRect.width - tooltipRect.width));
        let tooltipY = Math.max(0, Math.min(y, canvasRect.height - tooltipRect.height));
        
        this.element.style.left = tooltipX + 'px';
        this.element.style.top = tooltipY + 'px';
    }

    // 툴팁 테마 설정
    setTheme(theme) {
        const themes = {
            dark: {
                backgroundColor: 'rgba(0, 0, 0, 0.9)',
                color: '#ffffff',
                borderRadius: '6px',
                boxShadow: '0 4px 12px rgba(0,0,0,0.3)'
            },
            light: {
                backgroundColor: 'rgba(255, 255, 255, 0.95)',
                color: '#333333',
                borderRadius: '6px',
                boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
                border: '1px solid #e0e0e0'
            },
            minimal: {
                backgroundColor: 'rgba(255, 255, 255, 0.9)',
                color: '#666666',
                borderRadius: '2px',
                boxShadow: 'none',
                border: '1px solid #cccccc',
                fontSize: '11px'
            }
        };
        
        if (themes[theme]) {
            Object.assign(this.element.style, themes[theme]);
        }
    }

    // 멀티라인 툴팁 지원
    setMultiline(enabled) {
        if (enabled) {
            this.element.style.whiteSpace = 'pre-line';
            this.element.style.textAlign = 'left';
        } else {
            this.element.style.whiteSpace = 'nowrap';
            this.element.style.textAlign = 'center';
        }
    }

    // 툴팁에 HTML 콘텐츠 허용/비허용
    setAllowHTML(allowed) {
        this.allowHTML = allowed;
    }

    // 안전한 HTML 렌더링
    safeSetContent(content) {
        if (this.allowHTML) {
            this.element.innerHTML = content;
        } else {
            this.element.textContent = content;
        }
    }

    // 툴팁 정리
    destroy() {
        if (this.fadeTimeout) {
            clearTimeout(this.fadeTimeout);
        }
        
        if (this.element && this.element.parentNode) {
            this.element.parentNode.removeChild(this.element);
        }
        
        this.element = null;
        this.chart = null;
    }

    // 디버깅용 정보 출력
    getDebugInfo() {
        return {
            visible: this.visible,
            position: { x: this.x, y: this.y },
            content: this.content,
            bounds: this.getBounds()
        };
    }
}

// 글로벌로 사용할 수 있도록 export
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ChartTooltip;
} else {
    window.ChartTooltip = ChartTooltip;
}