//차트 범례 기능(컴포넌트)
//../static/js/chart/chart-legend.js
//다양한 위치지원(top, bottom, left, right)
//정렬(left, center, right), 호버 효과 및 클릭 감지, 반응형 레이아웃
//아이콘 타입별 렌더링 (line, rect, circle, area), 자동 줄바꿈 (수평 배치 시)
//커스텀 스타일링 및 테마, 시리즈 표시/숨김 토글


class ChartLegend {
    constructor(chart) {
        this.chart = chart;
        this.visible = true;
        this.items = [];
        this.bounds = { x: 0, y: 0, width: 0, height: 0 };
        this.itemBounds = [];
        this.hoveredItem = null;
        
        this.setupDefaultStyles();
    }

    setupDefaultStyles() {
        this.styles = {
            fontSize: 12,
            fontFamily: 'Arial, sans-serif',
            fontColor: '#666666',
            padding: 8,
            itemSpacing: 16,
            iconSize: 12,
            iconMargin: 6,
            lineHeight: 16,
            backgroundColor: 'transparent',
            borderColor: '#e0e0e0',
            borderWidth: 0,
            borderRadius: 4,
            shadowColor: 'rgba(0,0,0,0.1)',
            shadowBlur: 0,
            maxWidth: null,
            itemPadding: 4
        };
    }

    update() {
        if (!this.chart.data || !this.chart.data.series) {
            this.items = [];
            return;
        }

        this.items = this.chart.data.series.map((series, index) => ({
            text: series.label || `Series ${index + 1}`,
            color: series.color,
            borderColor: series.borderColor || series.color,
            visible: series.visible !== false,
            seriesIndex: index,
            icon: this.getIconType(series)
        }));

        this.calculateBounds();
    }

    getIconType(series) {
        const chartType = series.type || this.chart.options.type;
        
        switch (chartType) {
            case 'line':
                return 'line';
            case 'bar':
                return 'rect';
            case 'scatter':
                return 'circle';
            case 'area':
                return 'area';
            default:
                return 'rect';
        }
    }

    calculateBounds() {
        if (!this.visible || !this.items.length) {
            this.bounds = { x: 0, y: 0, width: 0, height: 0 };
            return;
        }

        const ctx = this.chart.ctx;
        const options = this.chart.options.legend;
        const position = options.position || 'top';
        const align = options.align || 'center';
        
        ctx.save();
        ctx.font = `${this.styles.fontSize}px ${this.styles.fontFamily}`;

        // 각 아이템의 크기 계산
        const itemSizes = this.items.map(item => {
            const textWidth = ctx.measureText(item.text).width;
            return {
                width: this.styles.iconSize + this.styles.iconMargin + textWidth + this.styles.itemPadding * 2,
                height: Math.max(this.styles.iconSize, this.styles.lineHeight) + this.styles.itemPadding * 2
            };
        });

        const canvasWidth = this.chart.canvas.width / (window.devicePixelRatio || 1);
        const canvasHeight = this.chart.canvas.height / (window.devicePixelRatio || 1);

        let totalWidth = 0;
        let totalHeight = 0;
        let rows = 1;

        if (position === 'top' || position === 'bottom') {
            // 수평 배치
            const maxWidth = this.styles.maxWidth || (canvasWidth - this.styles.padding * 2);
            let currentRowWidth = 0;
            let currentRowHeight = 0;
            let rowWidths = [];
            let rowHeights = [];

            itemSizes.forEach((size, index) => {
                const itemTotalWidth = size.width + (index > 0 ? this.styles.itemSpacing : 0);
                
                if (currentRowWidth + itemTotalWidth > maxWidth && currentRowWidth > 0) {
                    // 새 행 시작
                    rowWidths.push(currentRowWidth);
                    rowHeights.push(currentRowHeight);
                    currentRowWidth = size.width;
                    currentRowHeight = size.height;
                    rows++;
                } else {
                    currentRowWidth += itemTotalWidth;
                    currentRowHeight = Math.max(currentRowHeight, size.height);
                }
            });

            rowWidths.push(currentRowWidth);
            rowHeights.push(currentRowHeight);

            totalWidth = Math.max(...rowWidths);
            totalHeight = rowHeights.reduce((sum, height) => sum + height, 0) + (rows - 1) * this.styles.itemSpacing;

        } else {
            // 수직 배치 (left, right)
            totalWidth = Math.max(...itemSizes.map(size => size.width));
            totalHeight = itemSizes.reduce((sum, size) => sum + size.height, 0) + (itemSizes.length - 1) * this.styles.itemSpacing;
        }

        // 패딩 추가
        totalWidth += this.styles.padding * 2;
        totalHeight += this.styles.padding * 2;

        // 위치 계산
        let x, y;
        
        switch (position) {
            case 'top':
                x = this.getAlignedX(align, totalWidth, canvasWidth);
                y = this.styles.padding;
                break;
            case 'bottom':
                x = this.getAlignedX(align, totalWidth, canvasWidth);
                y = canvasHeight - totalHeight - this.styles.padding;
                break;
            case 'left':
                x = this.styles.padding;
                y = this.getAlignedY(align, totalHeight, canvasHeight);
                break;
            case 'right':
                x = canvasWidth - totalWidth - this.styles.padding;
                y = this.getAlignedY(align, totalHeight, canvasHeight);
                break;
            default:
                x = this.getAlignedX('center', totalWidth, canvasWidth);
                y = this.styles.padding;
        }

        this.bounds = { x, y, width: totalWidth, height: totalHeight };
        this.calculateItemBounds(itemSizes, position);

        ctx.restore();
    }

    getAlignedX(align, width, canvasWidth) {
        switch (align) {
            case 'left':
                return this.styles.padding;
            case 'right':
                return canvasWidth - width - this.styles.padding;
            case 'center':
            default:
                return (canvasWidth - width) / 2;
        }
    }

    getAlignedY(align, height, canvasHeight) {
        switch (align) {
            case 'top':
                return this.styles.padding;
            case 'bottom':
                return canvasHeight - height - this.styles.padding;
            case 'center':
            default:
                return (canvasHeight - height) / 2;
        }
    }

    calculateItemBounds(itemSizes, position) {
        this.itemBounds = [];
        
        let currentX = this.bounds.x + this.styles.padding;
        let currentY = this.bounds.y + this.styles.padding;
        const maxWidth = this.styles.maxWidth || (this.chart.canvas.width / (window.devicePixelRatio || 1) - this.styles.padding * 2);

        if (position === 'top' || position === 'bottom') {
            // 수평 배치
            itemSizes.forEach((size, index) => {
                const itemTotalWidth = size.width + (index > 0 ? this.styles.itemSpacing : 0);
                
                if (currentX + itemTotalWidth > this.bounds.x + maxWidth && index > 0) {
                    // 새 행으로 이동
                    currentX = this.bounds.x + this.styles.padding;
                    currentY += size.height + this.styles.itemSpacing;
                }

                this.itemBounds.push({
                    x: currentX,
                    y: currentY,
                    width: size.width,
                    height: size.height
                });

                currentX += size.width + this.styles.itemSpacing;
            });
        } else {
            // 수직 배치
            itemSizes.forEach((size, index) => {
                this.itemBounds.push({
                    x: currentX,
                    y: currentY,
                    width: size.width,
                    height: size.height
                });

                currentY += size.height + this.styles.itemSpacing;
            });
        }
    }

    draw() {
        if (!this.visible || !this.items.length) return;

        const ctx = this.chart.ctx;
        
        ctx.save();
        
        // 배경 그리기
        this.drawBackground();
        
        // 각 범례 아이템 그리기
        this.items.forEach((item, index) => {
            this.drawItem(item, index);
        });
        
        ctx.restore();
    }

    drawBackground() {
        if (this.styles.backgroundColor === 'transparent' && this.styles.borderWidth === 0) return;

        const ctx = this.chart.ctx;
        
        // 그림자
        if (this.styles.shadowBlur > 0) {
            ctx.shadowColor = this.styles.shadowColor;
            ctx.shadowBlur = this.styles.shadowBlur;
            ctx.shadowOffsetX = 2;
            ctx.shadowOffsetY = 2;
        }

        // 배경
        if (this.styles.backgroundColor !== 'transparent') {
            ctx.fillStyle = this.styles.backgroundColor;
            this.roundRect(ctx, this.bounds.x, this.bounds.y, this.bounds.width, this.bounds.height, this.styles.borderRadius);
            ctx.fill();
        }

        // 테두리
        if (this.styles.borderWidth > 0) {
            ctx.strokeStyle = this.styles.borderColor;
            ctx.lineWidth = this.styles.borderWidth;
            this.roundRect(ctx, this.bounds.x, this.bounds.y, this.bounds.width, this.bounds.height, this.styles.borderRadius);
            ctx.stroke();
        }

        // 그림자 리셋
        ctx.shadowColor = 'transparent';
        ctx.shadowBlur = 0;
        ctx.shadowOffsetX = 0;
        ctx.shadowOffsetY = 0;
    }

    drawItem(item, index) {
        const ctx = this.chart.ctx;
        const bounds = this.itemBounds[index];
        
        if (!bounds) return;

        const isHovered = this.hoveredItem === index;
        const alpha = item.visible ? 1.0 : 0.3;
        
        ctx.save();
        ctx.globalAlpha = alpha;

        // 아이템 배경 (호버 효과)
        if (isHovered) {
            ctx.fillStyle = 'rgba(0, 0, 0, 0.05)';
            this.roundRect(ctx, bounds.x - 2, bounds.y - 2, bounds.width + 4, bounds.height + 4, 2);
            ctx.fill();
        }

        // 아이콘 그리기
        const iconX = bounds.x + this.styles.itemPadding;
        const iconY = bounds.y + this.styles.itemPadding + (bounds.height - this.styles.itemPadding * 2 - this.styles.iconSize) / 2;
        
        this.drawIcon(item, iconX, iconY);

        // 텍스트 그리기
        const textX = iconX + this.styles.iconSize + this.styles.iconMargin;
        const textY = bounds.y + bounds.height / 2;
        
        ctx.fillStyle = item.visible ? this.styles.fontColor : this.adjustColorOpacity(this.styles.fontColor, 0.5);
        ctx.font = `${this.styles.fontSize}px ${this.styles.fontFamily}`;
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';
        
        ctx.fillText(item.text, textX, textY);

        ctx.restore();
    }

    drawIcon(item, x, y) {
        const ctx = this.chart.ctx;
        const size = this.styles.iconSize;
        
        switch (item.icon) {
            case 'line':
                this.drawLineIcon(item, x, y, size);
                break;
            case 'rect':
                this.drawRectIcon(item, x, y, size);
                break;
            case 'circle':
                this.drawCircleIcon(item, x, y, size);
                break;
            case 'area':
                this.drawAreaIcon(item, x, y, size);
                break;
            default:
                this.drawRectIcon(item, x, y, size);
        }
    }

    drawLineIcon(item, x, y, size) {
        const ctx = this.chart.ctx;
        
        // 선 그리기
        ctx.strokeStyle = item.borderColor;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(x, y + size / 2);
        ctx.lineTo(x + size, y + size / 2);
        ctx.stroke();

        // 포인트 그리기
        ctx.fillStyle = item.color;
        ctx.strokeStyle = item.borderColor;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(x + size / 2, y + size / 2, 3, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
    }

    drawRectIcon(item, x, y, size) {
        const ctx = this.chart.ctx;
        
        ctx.fillStyle = item.color;
        ctx.strokeStyle = item.borderColor;
        ctx.lineWidth = 1;
        
        ctx.fillRect(x, y + 2, size, size - 4);
        ctx.strokeRect(x, y + 2, size, size - 4);
    }

    drawCircleIcon(item, x, y, size) {
        const ctx = this.chart.ctx;
        
        ctx.fillStyle = item.color;
        ctx.strokeStyle = item.borderColor;
        ctx.lineWidth = 1;
        
        ctx.beginPath();
        ctx.arc(x + size / 2, y + size / 2, (size - 2) / 2, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
    }

    drawAreaIcon(item, x, y, size) {
        const ctx = this.chart.ctx;
        
        // 영역 그리기
        ctx.fillStyle = item.color;
        ctx.beginPath();
        ctx.moveTo(x, y + size);
        ctx.lineTo(x, y + size / 3);
        ctx.lineTo(x + size / 3, y + size / 4);
        ctx.lineTo(x + size * 2/3, y + size / 2);
        ctx.lineTo(x + size, y + size / 3);
        ctx.lineTo(x + size, y + size);
        ctx.closePath();
        ctx.fill();

        // 경계선 그리기
        ctx.strokeStyle = item.borderColor;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x, y + size / 3);
        ctx.lineTo(x + size / 3, y + size / 4);
        ctx.lineTo(x + size * 2/3, y + size / 2);
        ctx.lineTo(x + size, y + size / 3);
        ctx.stroke();
    }

    roundRect(ctx, x, y, width, height, radius) {
        if (radius === 0) {
            ctx.rect(x, y, width, height);
            return;
        }

        ctx.beginPath();
        ctx.moveTo(x + radius, y);
        ctx.lineTo(x + width - radius, y);
        ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
        ctx.lineTo(x + width, y + height - radius);
        ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
        ctx.lineTo(x + radius, y + height);
        ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
        ctx.lineTo(x, y + radius);
        ctx.quadraticCurveTo(x, y, x + radius, y);
        ctx.closePath();
    }

    adjustColorOpacity(color, opacity) {
        if (color.startsWith('#')) {
            const r = parseInt(color.slice(1, 3), 16);
            const g = parseInt(color.slice(3, 5), 16);
            const b = parseInt(color.slice(5, 7), 16);
            return `rgba(${r}, ${g}, ${b}, ${opacity})`;
        } else if (color.startsWith('rgb')) {
            return color.replace('rgb', 'rgba').replace(')', `, ${opacity})`);
        }
        return color;
    }

    // 마우스 위치에서 범례 아이템 찾기
    getItemAt(x, y) {
        for (let i = 0; i < this.itemBounds.length; i++) {
            const bounds = this.itemBounds[i];
            if (x >= bounds.x && x <= bounds.x + bounds.width &&
                y >= bounds.y && y <= bounds.y + bounds.height) {
                return {
                    index: i,
                    item: this.items[i],
                    seriesIndex: this.items[i].seriesIndex
                };
            }
        }
        return null;
    }

    // 호버 상태 설정
    setHoveredItem(index) {
        if (this.hoveredItem !== index) {
            this.hoveredItem = index;
            this.chart.render();
        }
    }

    // 호버 해제
    clearHover() {
        if (this.hoveredItem !== null) {
            this.hoveredItem = null;
            this.chart.render();
        }
    }

    // 범례 높이 가져오기
    getHeight() {
        return this.visible ? this.bounds.height : 0;
    }

    // 범례 너비 가져오기
    getWidth() {
        return this.visible ? this.bounds.width : 0;
    }

    // 범례 경계 가져오기
    getBounds() {
        return this.bounds;
    }

    // 스타일 업데이트
    updateStyle(styles) {
        Object.assign(this.styles, styles);
        this.calculateBounds();
    }

    // 위치 설정
    setPosition(position, align) {
        this.chart.options.legend.position = position;
        this.chart.options.legend.align = align;
        this.calculateBounds();
    }

    // 표시/숨김 토글
    toggle() {
        this.visible = !this.visible;
        this.calculateBounds();
    }

    // 표시 설정
    show() {
        if (!this.visible) {
            this.visible = true;
            this.calculateBounds();
        }
    }

    // 숨김 설정
    hide() {
        if (this.visible) {
            this.visible = false;
            this.calculateBounds();
        }
    }

    // 커스텀 아이템 추가
    addCustomItem(item) {
        this.items.push({
            text: item.text,
            color: item.color,
            borderColor: item.borderColor || item.color,
            visible: item.visible !== false,
            seriesIndex: -1, // 커스텀 아이템 표시
            icon: item.icon || 'rect',
            custom: true
        });
        this.calculateBounds();
    }

    // 커스텀 아이템 제거
    removeCustomItems() {
        this.items = this.items.filter(item => !item.custom);
        this.calculateBounds();
    }

    // 디버깅 정보
    getDebugInfo() {
        return {
            visible: this.visible,
            bounds: this.bounds,
            itemCount: this.items.length,
            itemBounds: this.itemBounds,
            hoveredItem: this.hoveredItem
        };
    }
}

// 글로벌로 사용할 수 있도록 export
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ChartLegend;
} else {
    window.ChartLegend = ChartLegend;
}