//차트 축(X,Y축) 기능(컴포넌트)
//../static/js/chart/chart-axes.js
//X축/Y축 지원: 독립적인 축 관리, 범위 설정: 자동/수동 범위 조정
//자동 틱 생성: Nice number 알고리즘으로 깔끔한 간격
//다양한 스케일: 선형(Linear), 로그(Log), 시간(Time) 스케일
//그리드 시스템: 주/부 그리드 라인
//커스텀 포맷팅: 값, 시간, 단위 표시 포맷터
//라벨 회전: X축 라벨 회전 지원
//반응형: 자동 간격 조정으로 겹침 방지
//ChartAxes: 전체 축 시스템 관리, Axis: 개별 축(X/Y) 구현체


class ChartAxes {
    constructor(chart) {
        this.chart = chart;
        this.xAxis = new Axis(chart, 'x');
        this.yAxis = new Axis(chart, 'y');
        
        this.setupDefaultStyles();
    }

    setupDefaultStyles() {
        this.styles = {
            lineColor: '#e0e0e0',
            lineWidth: 1,
            tickColor: '#cccccc',
            tickSize: 6,
            labelColor: '#666666',
            labelFont: '11px Arial, sans-serif',
            titleColor: '#333333',
            titleFont: 'bold 14px Arial, sans-serif',
            gridColor: '#f0f0f0',
            gridWidth: 1,
            padding: 40
        };
    }

    draw() {
        if (this.chart.options.axes.x.display) {
            this.xAxis.draw();
        }
        
        if (this.chart.options.axes.y.display) {
            this.yAxis.draw();
        }
    }

    drawGrid() {
        if (this.chart.options.axes.x.grid) {
            this.xAxis.drawGrid();
        }
        
        if (this.chart.options.axes.y.grid) {
            this.yAxis.drawGrid();
        }
    }

    updateBounds() {
        this.xAxis.calculateBounds();
        this.yAxis.calculateBounds();
    }

    getDrawingArea() {
        const canvas = this.chart.canvas;
        const dpr = window.devicePixelRatio || 1;
        const width = canvas.width / dpr;
        const height = canvas.height / dpr;
        
        const legendHeight = this.chart.legend.getHeight();
        const padding = this.styles.padding;
        
        return {
            x: padding,
            y: padding + legendHeight,
            width: width - padding * 2,
            height: height - padding * 2 - legendHeight
        };
    }
}

class Axis {
    constructor(chart, type) {
        this.chart = chart;
        this.type = type; // 'x' or 'y'
        this.isHorizontal = type === 'x';
        
        this.min = null;
        this.max = null;
        this.ticks = [];
        this.labels = [];
        this.bounds = { x: 0, y: 0, width: 0, height: 0 };
        
        this.setupDefaultOptions();
    }

    setupDefaultOptions() {
        this.options = {
            display: true,
            position: this.isHorizontal ? 'bottom' : 'left',
            title: '',
            min: null,
            max: null,
            grid: true,
            ticks: {
                display: true,
                count: this.isHorizontal ? 8 : 6,
                precision: 2,
                formatter: null,
                rotation: 0,
                padding: 8
            },
            labels: {
                display: true,
                padding: 12,
                formatter: null
            }
        };
    }

    calculateBounds() {
        if (!this.chart.bounds) return;

        const chartBounds = this.chart.bounds;
        const area = this.chart.axes.getDrawingArea();
        
        // 축의 범위 설정
        if (this.isHorizontal) {
            this.min = this.options.min !== null ? this.options.min : chartBounds.minX;
            this.max = this.options.max !== null ? this.options.max : chartBounds.maxX;
            
            this.bounds = {
                x: area.x,
                y: area.y + area.height,
                width: area.width,
                height: 0
            };
        } else {
            this.min = this.options.min !== null ? this.options.min : chartBounds.minY;
            this.max = this.options.max !== null ? this.options.max : chartBounds.maxY;
            
            this.bounds = {
                x: area.x,
                y: area.y,
                width: 0,
                height: area.height
            };
        }

        this.generateTicks();
        this.generateLabels();
    }

    generateTicks() {
        this.ticks = [];
        
        const range = this.max - this.min;
        if (range === 0) return;

        const tickCount = this.options.ticks.count;
        const step = this.calculateNiceStep(range, tickCount);
        
        // 시작점을 nice number로 조정
        const start = Math.floor(this.min / step) * step;
        
        for (let value = start; value <= this.max + step * 0.001; value += step) {
            if (value >= this.min && value <= this.max) {
                this.ticks.push({
                    value: this.roundToPrecision(value, this.options.ticks.precision),
                    position: this.valueToPosition(value),
                    label: this.formatTickValue(value)
                });
            }
        }
    }

    calculateNiceStep(range, targetTicks) {
        const roughStep = range / (targetTicks - 1);
        const magnitude = Math.pow(10, Math.floor(Math.log10(roughStep)));
        const normalizedStep = roughStep / magnitude;
        
        let niceStep;
        if (normalizedStep <= 1) {
            niceStep = 1;
        } else if (normalizedStep <= 2) {
            niceStep = 2;
        } else if (normalizedStep <= 5) {
            niceStep = 5;
        } else {
            niceStep = 10;
        }
        
        return niceStep * magnitude;
    }

    roundToPrecision(value, precision) {
        const factor = Math.pow(10, precision);
        return Math.round(value * factor) / factor;
    }

    valueToPosition(value) {
        const ratio = (value - this.min) / (this.max - this.min);
        
        if (this.isHorizontal) {
            return this.bounds.x + ratio * this.bounds.width;
        } else {
            return this.bounds.y + this.bounds.height - ratio * this.bounds.height;
        }
    }

    positionToValue(position) {
        let ratio;
        
        if (this.isHorizontal) {
            ratio = (position - this.bounds.x) / this.bounds.width;
        } else {
            ratio = (this.bounds.y + this.bounds.height - position) / this.bounds.height;
        }
        
        return this.min + ratio * (this.max - this.min);
    }

    generateLabels() {
        this.labels = [];
        
        if (this.chart.data && this.chart.data.labels && this.isHorizontal) {
            // X축에 대해 데이터 라벨 사용
            this.chart.data.labels.forEach((label, index) => {
                const position = this.valueToPosition(index);
                this.labels.push({
                    text: label,
                    position: position,
                    index: index
                });
            });
        }
    }

    formatTickValue(value) {
        if (this.options.ticks.formatter) {
            return this.options.ticks.formatter(value);
        }
        
        // 기본 포맷팅
        if (Math.abs(value) >= 1000000) {
            return (value / 1000000).toFixed(1) + 'M';
        } else if (Math.abs(value) >= 1000) {
            return (value / 1000).toFixed(1) + 'K';
        } else if (value % 1 === 0) {
            return value.toString();
        } else {
            return value.toFixed(this.options.ticks.precision);
        }
    }

    draw() {
        if (!this.options.display) return;

        const ctx = this.chart.ctx;
        ctx.save();

        // 축 선 그리기
        this.drawAxisLine();
        
        // 틱 그리기
        if (this.options.ticks.display) {
            this.drawTicks();
        }
        
        // 라벨 그리기
        if (this.options.labels.display) {
            this.drawLabels();
        }
        
        // 제목 그리기
        if (this.options.title) {
            this.drawTitle();
        }

        ctx.restore();
    }

    drawAxisLine() {
        const ctx = this.chart.ctx;
        const styles = this.chart.axes.styles;
        
        ctx.strokeStyle = styles.lineColor;
        ctx.lineWidth = styles.lineWidth;
        ctx.beginPath();
        
        if (this.isHorizontal) {
            ctx.moveTo(this.bounds.x, this.bounds.y);
            ctx.lineTo(this.bounds.x + this.bounds.width, this.bounds.y);
        } else {
            ctx.moveTo(this.bounds.x, this.bounds.y);
            ctx.lineTo(this.bounds.x, this.bounds.y + this.bounds.height);
        }
        
        ctx.stroke();
    }

    drawTicks() {
        const ctx = this.chart.ctx;
        const styles = this.chart.axes.styles;
        
        ctx.strokeStyle = styles.tickColor;
        ctx.lineWidth = styles.lineWidth;
        
        this.ticks.forEach(tick => {
            ctx.beginPath();
            
            if (this.isHorizontal) {
                ctx.moveTo(tick.position, this.bounds.y);
                ctx.lineTo(tick.position, this.bounds.y + styles.tickSize);
            } else {
                ctx.moveTo(this.bounds.x, tick.position);
                ctx.lineTo(this.bounds.x - styles.tickSize, tick.position);
            }
            
            ctx.stroke();
            
            // 틱 라벨 그리기
            this.drawTickLabel(tick);
        });
    }

    drawTickLabel(tick) {
        const ctx = this.chart.ctx;
        const styles = this.chart.axes.styles;
        const padding = this.options.ticks.padding;
        
        ctx.fillStyle = styles.labelColor;
        ctx.font = styles.labelFont;
        ctx.textAlign = this.isHorizontal ? 'center' : 'right';
        ctx.textBaseline = this.isHorizontal ? 'top' : 'middle';
        
        const x = this.isHorizontal ? tick.position : this.bounds.x - styles.tickSize - padding;
        const y = this.isHorizontal ? this.bounds.y + styles.tickSize + padding : tick.position;
        
        // 회전 적용
        if (this.options.ticks.rotation !== 0 && this.isHorizontal) {
            ctx.save();
            ctx.translate(x, y);
            ctx.rotate(this.options.ticks.rotation * Math.PI / 180);
            ctx.fillText(tick.label, 0, 0);
            ctx.restore();
        } else {
            ctx.fillText(tick.label, x, y);
        }
    }

    drawLabels() {
        if (!this.labels.length) return;
        
        const ctx = this.chart.ctx;
        const styles = this.chart.axes.styles;
        const padding = this.options.labels.padding;
        
        ctx.fillStyle = styles.labelColor;
        ctx.font = styles.labelFont;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        
        this.labels.forEach(label => {
            const x = label.position;
            const y = this.bounds.y + styles.tickSize + this.options.ticks.padding + padding;
            
            ctx.fillText(label.text, x, y);
        });
    }

    drawTitle() {
        const ctx = this.chart.ctx;
        const styles = this.chart.axes.styles;
        const area = this.chart.axes.getDrawingArea();
        
        ctx.fillStyle = styles.titleColor;
        ctx.font = styles.titleFont;
        
        if (this.isHorizontal) {
            ctx.textAlign = 'center';
            ctx.textBaseline = 'bottom';
            const x = area.x + area.width / 2;
            const y = area.y + area.height + styles.padding - 10;
            ctx.fillText(this.options.title, x, y);
        } else {
            ctx.save();
            ctx.textAlign = 'center';
            ctx.textBaseline = 'bottom';
            const x = 20;
            const y = area.y + area.height / 2;
            ctx.translate(x, y);
            ctx.rotate(-Math.PI / 2);
            ctx.fillText(this.options.title, 0, 0);
            ctx.restore();
        }
    }

    drawGrid() {
        if (!this.options.grid) return;
        
        const ctx = this.chart.ctx;
        const styles = this.chart.axes.styles;
        const area = this.chart.axes.getDrawingArea();
        
        ctx.strokeStyle = styles.gridColor;
        ctx.lineWidth = styles.gridWidth;
        ctx.setLineDash([]);
        
        this.ticks.forEach(tick => {
            // 0축은 더 진하게
            if (tick.value === 0) {
                ctx.strokeStyle = styles.lineColor;
                ctx.lineWidth = styles.lineWidth;
            } else {
                ctx.strokeStyle = styles.gridColor;
                ctx.lineWidth = styles.gridWidth;
            }
            
            ctx.beginPath();
            
            if (this.isHorizontal) {
                ctx.moveTo(tick.position, area.y);
                ctx.lineTo(tick.position, area.y + area.height);
            } else {
                ctx.moveTo(area.x, tick.position);
                ctx.lineTo(area.x + area.width, tick.position);
            }
            
            ctx.stroke();
        });
    }

    // 축 범위 설정
    setRange(min, max) {
        this.options.min = min;
        this.options.max = max;
        this.calculateBounds();
    }

    // 자동 범위 계산
    autoRange() {
        this.options.min = null;
        this.options.max = null;
        this.calculateBounds();
    }

    // 틱 개수 설정
    setTickCount(count) {
        this.options.ticks.count = count;
        this.calculateBounds();
    }

    // 틱 포맷터 설정
    setTickFormatter(formatter) {
        this.options.ticks.formatter = formatter;
        this.calculateBounds();
    }

    // 제목 설정
    setTitle(title) {
        this.options.title = title;
    }

    // 로그 스케일 지원
    setLogScale(enabled) {
        this.logScale = enabled;
        if (enabled) {
            this.valueToPosition = this.logValueToPosition;
            this.positionToValue = this.logPositionToValue;
            this.generateTicks = this.generateLogTicks;
        } else {
            this.valueToPosition = this.linearValueToPosition;
            this.positionToValue = this.linearPositionToValue;
            this.generateTicks = this.generateLinearTicks;
        }
        this.calculateBounds();
    }

    linearValueToPosition(value) {
        const ratio = (value - this.min) / (this.max - this.min);
        
        if (this.isHorizontal) {
            return this.bounds.x + ratio * this.bounds.width;
        } else {
            return this.bounds.y + this.bounds.height - ratio * this.bounds.height;
        }
    }

    linearPositionToValue(position) {
        let ratio;
        
        if (this.isHorizontal) {
            ratio = (position - this.bounds.x) / this.bounds.width;
        } else {
            ratio = (this.bounds.y + this.bounds.height - position) / this.bounds.height;
        }
        
        return this.min + ratio * (this.max - this.min);
    }

    logValueToPosition(value) {
        if (value <= 0) return this.bounds.x; // 로그는 양수만
        
        const logMin = Math.log10(this.min);
        const logMax = Math.log10(this.max);
        const logValue = Math.log10(value);
        const ratio = (logValue - logMin) / (logMax - logMin);
        
        if (this.isHorizontal) {
            return this.bounds.x + ratio * this.bounds.width;
        } else {
            return this.bounds.y + this.bounds.height - ratio * this.bounds.height;
        }
    }

    logPositionToValue(position) {
        let ratio;
        
        if (this.isHorizontal) {
            ratio = (position - this.bounds.x) / this.bounds.width;
        } else {
            ratio = (this.bounds.y + this.bounds.height - position) / this.bounds.height;
        }
        
        const logMin = Math.log10(this.min);
        const logMax = Math.log10(this.max);
        const logValue = logMin + ratio * (logMax - logMin);
        
        return Math.pow(10, logValue);
    }

    generateLinearTicks() {
        // 기본 선형 틱 생성 (위에서 구현됨)
        this.ticks = [];
        
        const range = this.max - this.min;
        if (range === 0) return;

        const tickCount = this.options.ticks.count;
        const step = this.calculateNiceStep(range, tickCount);
        const start = Math.floor(this.min / step) * step;
        
        for (let value = start; value <= this.max + step * 0.001; value += step) {
            if (value >= this.min && value <= this.max) {
                this.ticks.push({
                    value: this.roundToPrecision(value, this.options.ticks.precision),
                    position: this.valueToPosition(value),
                    label: this.formatTickValue(value)
                });
            }
        }
    }

    generateLogTicks() {
        this.ticks = [];
        
        if (this.min <= 0 || this.max <= 0) return;
        
        const logMin = Math.floor(Math.log10(this.min));
        const logMax = Math.ceil(Math.log10(this.max));
        
        for (let power = logMin; power <= logMax; power++) {
            const baseValue = Math.pow(10, power);
            
            // 주 틱 (10^n)
            if (baseValue >= this.min && baseValue <= this.max) {
                this.ticks.push({
                    value: baseValue,
                    position: this.valueToPosition(baseValue),
                    label: this.formatTickValue(baseValue),
                    major: true
                });
            }
            
            // 부 틱 (2×10^n, 5×10^n)
            for (let multiplier of [2, 5]) {
                const value = multiplier * baseValue;
                if (value >= this.min && value <= this.max) {
                    this.ticks.push({
                        value: value,
                        position: this.valueToPosition(value),
                        label: this.formatTickValue(value),
                        major: false
                    });
                }
            }
        }
        
        // 값으로 정렬
        this.ticks.sort((a, b) => a.value - b.value);
    }

    // 시간 축 지원
    setTimeScale(enabled, timeFormat) {
        this.timeScale = enabled;
        this.timeFormat = timeFormat || 'YYYY-MM-DD';
        
        if (enabled) {
            this.formatTickValue = this.formatTimeValue;
        } else {
            this.formatTickValue = this.formatNumericValue;
        }
        
        this.calculateBounds();
    }

    formatTimeValue(timestamp) {
        const date = new Date(timestamp);
        // 간단한 날짜 포맷팅 (실제로는 moment.js 등 사용 권장)
        return date.toLocaleDateString();
    }

    formatNumericValue(value) {
        if (this.options.ticks.formatter) {
            return this.options.ticks.formatter(value);
        }
        
        if (Math.abs(value) >= 1000000) {
            return (value / 1000000).toFixed(1) + 'M';
        } else if (Math.abs(value) >= 1000) {
            return (value / 1000).toFixed(1) + 'K';
        } else if (value % 1 === 0) {
            return value.toString();
        } else {
            return value.toFixed(this.options.ticks.precision);
        }
    }

    // 축 반전
    setReversed(reversed) {
        this.reversed = reversed;
        this.calculateBounds();
    }

    // 틱과 라벨 간격 자동 조정
    autoAdjustSpacing() {
        const ctx = this.chart.ctx;
        ctx.save();
        ctx.font = this.chart.axes.styles.labelFont;
        
        // 라벨 길이 측정하여 겹침 방지
        const maxLabelWidth = Math.max(...this.ticks.map(tick => 
            ctx.measureText(tick.label).width
        ));
        
        const availableSpace = this.isHorizontal ? this.bounds.width : this.bounds.height;
        const minSpacing = maxLabelWidth + 10; // 10px 여백
        const maxTicks = Math.floor(availableSpace / minSpacing);
        
        if (this.ticks.length > maxTicks) {
            // 틱 개수 줄이기
            const step = Math.ceil(this.ticks.length / maxTicks);
            this.ticks = this.ticks.filter((tick, index) => index % step === 0);
        }
        
        ctx.restore();
    }

    // 디버깅 정보
    getDebugInfo() {
        return {
            type: this.type,
            min: this.min,
            max: this.max,
            tickCount: this.ticks.length,
            bounds: this.bounds,
            options: this.options
        };
    }
}

// 글로벌로 사용할 수 있도록 export
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ChartAxes, Axis };
} else {
    window.ChartAxes = ChartAxes;
    window.Axis = Axis;
}