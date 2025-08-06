//차트 UI 업데이트와 상태관리 담당
//../static/js/chart/chart-ui.js
//요소캐시-DOM요소들을 미리 캐시해서 성능향상
//상태관리- 선택모드, 선택된 대학들, 업데이트 상태등
//실시간업데이트- 데이터변경시 자동 UI업데이트
//슬라이더 관리- 데이터범위 슬라이더, 범위표시
//대학선택- 개별선택, 전체선택/해제
//폼검증-Y축 값, 선택모드 등 검증
//탭 전환- 차트 탭 상태관리
//알림시스템- 사용자 알림표시


LibraChart.UI = {
    
    // UI 상태
    state: {
        currentSelectionMode: 'all',
        selectedUniversities: new Set(),
        isUpdating: false,
        lastUpdateTime: null
    },
    
    // UI 요소 캐시
    elements: {},
    
    // 초기화
    init: () => {
        LibraChart.Utils.log('UI 모듈 초기화 시작');
        LibraChart.UI.cacheElements();
        LibraChart.UI.setupDataListeners();
        LibraChart.UI.updateAllInfo();
    },
    
    // DOM 요소 캐시
    cacheElements: () => {
        const elementIds = [
            'yearSelect', 'stypFilter', 'fndFilter', 'rgnFilter', 'uscFilter',
            'chartType', 'sortOrder', 'yAxisMode', 'yAxisMin', 'yAxisMax',
            'dataStartSlider', 'dataEndSlider', 'dataCountInfo', 
            'selectedDataRange', 'dataMinLabel', 'dataMaxLabel',
            'universitySelector', 'universityList', 'selectedCount',
            'currentYear', 'currentStyp', 'currentFnd', 'currentRgn', 
            'currentUsc', 'currentChartType', 'currentSortOrder',
            'currentSelectionMode', 'currentYAxisMode', 'dataCount'
        ];
        
        elementIds.forEach(id => {
            LibraChart.UI.elements[id] = LibraChart.Utils.getElementById(id);
        });
        
        const foundElements = Object.values(LibraChart.UI.elements).filter(el => el !== null).length;
        LibraChart.Utils.log(`UI 요소 캐시 완료: ${foundElements}/${elementIds.length}개`);
    },
    
    // 데이터 변경 리스너 설정
    setupDataListeners: () => {
        document.addEventListener('dataChanged', (event) => {
            LibraChart.UI.handleDataChange(event.detail);
        });
        
        document.addEventListener('chartGenerated', (event) => {
            LibraChart.UI.handleChartGenerated(event.detail);
        });
        
        LibraChart.Utils.log('데이터 변경 리스너 설정 완료');
    },
    
    // 데이터 변경 처리
    handleDataChange: (detail) => {
        LibraChart.Utils.log('데이터 변경 감지', detail);
        
        LibraChart.UI.updateDataRangeSlider();
        LibraChart.UI.updateUniversitySelector();
        LibraChart.UI.updateStatisticsInfo();
        LibraChart.UI.state.lastUpdateTime = Date.now();
    },
    
    // 차트 생성 완료 처리
    handleChartGenerated: (detail) => {
        LibraChart.Utils.log('차트 생성 완료 감지', detail);
        LibraChart.UI.updateDataCount(detail.dataCount);
    },
    
    // 현재 정보 전체 업데이트
    updateAllInfo: () => {
        if (LibraChart.UI.state.isUpdating) return;
        
        LibraChart.UI.state.isUpdating = true;
        
        try {
            LibraChart.UI.updateCurrentInfo();
            LibraChart.UI.updateDataRangeSlider();
            LibraChart.UI.updateUniversitySelector();
            LibraChart.UI.updateYAxisCustomFields();
            LibraChart.Utils.log('전체 UI 정보 업데이트 완료');
        } catch (error) {
            LibraChart.Utils.error('UI 업데이트 중 오류', error);
        } finally {
            LibraChart.UI.state.isUpdating = false;
        }
    },
    
    // 현재 설정 정보 업데이트
    updateCurrentInfo: () => {
        const dataState = LibraChart.Data.getState();
        
        // 기본 정보
        const infoMap = {
            currentYear: LibraChart.UI.getSelectValue('yearSelect') + '년',
            currentStyp: LibraChart.UI.getSelectValue('stypFilter'),
            currentFnd: LibraChart.UI.getSelectValue('fndFilter'),
            currentRgn: LibraChart.UI.getSelectValue('rgnFilter'),
            currentUsc: LibraChart.UI.getSelectValue('uscFilter')
        };
        
        // 차트 타입
        const chartTypeMap = {
            'bar': '막대 차트',
            'line': '선 차트',
            'scatter': '산점도',
            'pie': '원형 차트',
            'doughnut': '도넛 차트',
            'radar': '레이더 차트'
        };
        infoMap.currentChartType = chartTypeMap[LibraChart.UI.getSelectValue('chartType')] || '막대 차트';
        
        // 정렬 방식
        const sortOrderMap = {
            'rank_desc': '환경점수 높은 순',
            'rank_asc': '환경점수 낮은 순',
            'university': '대학명 가나다순',
            'student_desc': '학생수 많은 순',
            'budget_desc': '예산 많은 순',
            'employment_desc': '취업률 높은 순'
        };
        infoMap.currentSortOrder = sortOrderMap[LibraChart.UI.getSelectValue('sortOrder')] || '환경점수 높은 순';
        
        // 선택 모드
        const selectionModeMap = {
            'all': '필터링 후 전체',
            'manual': '수동 선택'
        };
        infoMap.currentSelectionMode = selectionModeMap[LibraChart.UI.state.currentSelectionMode] || '필터링 후 전체';
        
        // Y축 모드
        const yAxisModeMap = {
            'enhanced': '향상된 표시',
            'auto': '자동 조절',
            'dataRange': '데이터 범위 기준',
            'custom': '사용자 지정'
        };
        infoMap.currentYAxisMode = yAxisModeMap[LibraChart.UI.getSelectValue('yAxisMode')] || '향상된 표시';
        
        // UI 요소 업데이트
        Object.entries(infoMap).forEach(([key, value]) => {
            LibraChart.UI.setElementText(key, value);
        });
    },
    
    // 데이터 범위 슬라이더 업데이트
    updateDataRangeSlider: () => {
        const data = LibraChart.Data.getFilteredData();
        const dataCount = data.length;
        
        const elements = {
            startSlider: LibraChart.UI.elements.dataStartSlider,
            endSlider: LibraChart.UI.elements.dataEndSlider,
            countInfo: LibraChart.UI.elements.dataCountInfo,
            minLabel: LibraChart.UI.elements.dataMinLabel,
            maxLabel: LibraChart.UI.elements.dataMaxLabel
        };
        
        // 슬라이더 범위 설정
        if (elements.startSlider) {
            elements.startSlider.max = Math.max(1, dataCount);
            if (parseInt(elements.startSlider.value) > dataCount) {
                elements.startSlider.value = 1;
            }
        }
        
        if (elements.endSlider) {
            elements.endSlider.max = Math.max(1, dataCount);
            elements.endSlider.value = Math.max(1, dataCount);
        }
        
        // 라벨 업데이트
        if (elements.countInfo) {
            elements.countInfo.textContent = `필터링된 데이터: ${dataCount}개`;
        }
        
        if (elements.minLabel) elements.minLabel.textContent = '1';
        if (elements.maxLabel) elements.maxLabel.textContent = dataCount.toString();
        
        // 선택 범위 표시 업데이트
        LibraChart.UI.updateSelectedRangeDisplay();
        
        LibraChart.Utils.log(`데이터 범위 슬라이더 업데이트: ${dataCount}개`);
    },
    
    // 선택 범위 표시 업데이트
    updateSelectedRangeDisplay: () => {
        const startSlider = LibraChart.UI.elements.dataStartSlider;
        const endSlider = LibraChart.UI.elements.dataEndSlider;
        const selectedRange = LibraChart.UI.elements.selectedDataRange;
        
        if (!startSlider || !endSlider || !selectedRange) return;
        
        const start = Math.max(1, parseInt(startSlider.value) || 1);
        const end = Math.max(start, parseInt(endSlider.value) || 1);
        const total = Math.max(1, parseInt(startSlider.max) || 1);
        
        let displayText;
        if (start === 1 && end === total) {
            displayText = '전체';
        } else {
            displayText = `${start} ~ ${end} (${end - start + 1}개)`;
        }
        
        selectedRange.textContent = displayText;
    },
    
    // 대학 선택 목록 업데이트
    updateUniversitySelector: () => {
        const universityList = LibraChart.UI.elements.universityList;
        if (!universityList) return;
        
        const data = LibraChart.Data.getFilteredData();
        
        // 기존 목록 제거
        universityList.innerHTML = '';
        
        // 새 목록 생성
        data.forEach((item, index) => {
            const div = LibraChart.Utils.createElement('div', 'university-item');
            
            const checkbox = LibraChart.Utils.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.id = `univ_${index}`;
            checkbox.value = item.university;
            checkbox.checked = LibraChart.UI.state.selectedUniversities.has(item.university);
            
            // 체크박스 이벤트
            LibraChart.Utils.addEvent(checkbox, 'change', (e) => {
                LibraChart.UI.handleUniversitySelection(e);
            });
            
            const label = LibraChart.Utils.createElement('label');
            label.htmlFor = `univ_${index}`;
            label.textContent = `${item.university} (${item.environmentScore}점)`;
            
            div.appendChild(checkbox);
            div.appendChild(label);
            universityList.appendChild(div);
        });
        
        LibraChart.UI.updateSelectedCount();
        LibraChart.Utils.log(`대학 선택 목록 업데이트: ${data.length}개`);
    },
    
    // 대학 선택 처리
    handleUniversitySelection: (event) => {
        const checkbox = event.target;
        const universityName = checkbox.value;
        
        if (checkbox.checked) {
            LibraChart.UI.state.selectedUniversities.add(universityName);
        } else {
            LibraChart.UI.state.selectedUniversities.delete(universityName);
        }
        
        LibraChart.UI.updateSelectedCount();
        LibraChart.Utils.log(`대학 선택 변경: ${universityName} (${checkbox.checked ? '선택' : '해제'})`);
    },
    
    // 선택된 대학 수 업데이트
    updateSelectedCount: () => {
        const selectedCount = LibraChart.UI.elements.selectedCount;
        if (selectedCount) {
            selectedCount.textContent = `${LibraChart.UI.state.selectedUniversities.size}개 선택됨`;
        }
    },
    
    // 전체 대학 선택/해제
    toggleAllUniversities: () => {
        const checkboxes = document.querySelectorAll('#universityList input[type="checkbox"]');
        const allSelected = Array.from(checkboxes).every(cb => cb.checked);
        
        checkboxes.forEach(checkbox => {
            checkbox.checked = !allSelected;
            
            if (!allSelected) {
                LibraChart.UI.state.selectedUniversities.add(checkbox.value);
            } else {
                LibraChart.UI.state.selectedUniversities.delete(checkbox.value);
            }
        });
        
        LibraChart.UI.updateSelectedCount();
        LibraChart.Utils.log(`전체 대학 ${allSelected ? '해제' : '선택'}`);
    },
    
    // 선택 모드 설정
    setSelectionMode: (mode) => {
        LibraChart.UI.state.currentSelectionMode = mode;
        
        // 모드 버튼 상태 업데이트
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.classList.remove('active');
            if (btn.getAttribute('data-mode') === mode) {
                btn.classList.add('active');
            }
        });
        
        // UI 표시/숨김
        const dataRangeSliderGroup = LibraChart.Utils.getElementById('dataRangeSliderGroup');
        const universitySelector = LibraChart.UI.elements.universitySelector;
        
        if (mode === 'all') {
            if (dataRangeSliderGroup) dataRangeSliderGroup.style.display = 'block';
            if (universitySelector) universitySelector.classList.remove('active');
        } else {
            if (dataRangeSliderGroup) dataRangeSliderGroup.style.display = 'none';
            if (universitySelector) {
                universitySelector.classList.add('active');
                LibraChart.UI.updateUniversitySelector();
            }
        }
        
        LibraChart.UI.updateCurrentInfo();
        LibraChart.Utils.log(`선택 모드 변경: ${mode}`);
    },
    
    // Y축 사용자 지정 필드 업데이트
    updateYAxisCustomFields: () => {
        const yAxisMode = LibraChart.UI.getSelectValue('yAxisMode');
        const customRangeGroup = LibraChart.Utils.getElementById('customRangeGroup');
        const customRangeGroupMax = LibraChart.Utils.getElementById('customRangeGroupMax');
        
        const isCustom = yAxisMode === 'custom';
        
        if (customRangeGroup) {
            customRangeGroup.style.display = isCustom ? 'block' : 'none';
        }
        if (customRangeGroupMax) {
            customRangeGroupMax.style.display = isCustom ? 'block' : 'none';
        }
    },
    
    // 탭 전환
    switchTab: (tabName) => {
        document.querySelectorAll('.chart-tab').forEach(tab => {
            tab.classList.remove('active');
            tab.setAttribute('aria-selected', 'false');
            tab.setAttribute('tabindex', '-1');
        });
        
        const activeTab = document.querySelector(`[data-tab="${tabName}"]`);
        if (activeTab) {
            activeTab.classList.add('active');
            activeTab.setAttribute('aria-selected', 'true');
            activeTab.setAttribute('tabindex', '0');
        }
        
        LibraChart.Utils.log(`탭 전환: ${tabName}`);
    },
    
    // 통계 정보 업데이트
    updateStatisticsInfo: () => {
        const stats = LibraChart.Data.getStatistics();
        
        // 통계 정보를 UI에 표시 (향후 확장 가능)
        LibraChart.Utils.log('통계 정보 업데이트', stats);
    },
    
    // 데이터 개수 업데이트
    updateDataCount: (count) => {
        LibraChart.UI.setElementText('dataCount', `${count}개`);
    },
    
    // 슬라이더 값 조정
    adjustDataRange: (type, direction) => {
        const startSlider = LibraChart.UI.elements.dataStartSlider;
        const endSlider = LibraChart.UI.elements.dataEndSlider;
        
        if (!startSlider || !endSlider) return;
        
        const maxValue = parseInt(startSlider.max) || 1;
        
        if (type === 'start') {
            let newValue = parseInt(startSlider.value) + direction;
            newValue = LibraChart.Utils.clamp(newValue, 1, parseInt(endSlider.value));
            startSlider.value = newValue;
        } else if (type === 'end') {
            let newValue = parseInt(endSlider.value) + direction;
            newValue = LibraChart.Utils.clamp(newValue, parseInt(startSlider.value), maxValue);
            endSlider.value = newValue;
        }
        
        LibraChart.UI.updateSelectedRangeDisplay();
        LibraChart.Utils.log(`데이터 범위 조정: ${type} ${direction > 0 ? '+' : ''}${direction}`);
    },
    
    // 폼 검증
    validateForm: () => {
        const errors = [];
        
        // Y축 사용자 지정 값 검증
        const yAxisMode = LibraChart.UI.getSelectValue('yAxisMode');
        if (yAxisMode === 'custom') {
            const minVal = LibraChart.UI.getInputValue('yAxisMin');
            const maxVal = LibraChart.UI.getInputValue('yAxisMax');
            
            if (minVal !== null && maxVal !== null && minVal >= maxVal) {
                errors.push('Y축 최소값은 최대값보다 작아야 합니다.');
            }
        }
        
        // 선택 모드 검증
        if (LibraChart.UI.state.currentSelectionMode === 'manual' && 
            LibraChart.UI.state.selectedUniversities.size === 0) {
            errors.push('수동 선택 모드에서는 최소 1개 이상의 대학을 선택해야 합니다.');
        }
        
        return {
            isValid: errors.length === 0,
            errors: errors
        };
    },
    
    // 알림 표시
    showNotification: (message, type = 'info', duration = 3000) => {
        LibraChart.HeaderFooter.showNotification(message, type, duration);
    },
    
    // 유틸리티 함수들
    getSelectValue: (elementId) => {
        const element = LibraChart.UI.elements[elementId] || LibraChart.Utils.getElementById(elementId);
        return element ? element.value : '';
    },
    
    getInputValue: (elementId) => {
        const element = LibraChart.UI.elements[elementId] || LibraChart.Utils.getElementById(elementId);
        if (!element || element.value === '') return null;
        return LibraChart.Utils.toNumber(element.value);
    },
    
    setElementText: (elementId, text) => {
        const element = LibraChart.UI.elements[elementId] || LibraChart.Utils.getElementById(elementId);
        if (element) {
            element.textContent = text;
        }
    },
    
    setElementValue: (elementId, value) => {
        const element = LibraChart.UI.elements[elementId] || LibraChart.Utils.getElementById(elementId);
        if (element) {
            element.value = value;
        }
    },
    
    // 선택된 대학 목록 가져오기
    getSelectedUniversities: () => {
        return Array.from(LibraChart.UI.state.selectedUniversities);
    },
    
    // 선택된 대학 설정
    setSelectedUniversities: (universities) => {
        LibraChart.UI.state.selectedUniversities.clear();
        universities.forEach(univ => {
            LibraChart.UI.state.selectedUniversities.add(univ);
        });
        LibraChart.UI.updateUniversitySelector();
    },
    
    // 상태 리셋
    reset: () => {
        LibraChart.UI.state = {
            currentSelectionMode: 'all',
            selectedUniversities: new Set(),
            isUpdating: false,
            lastUpdateTime: null
        };
        
        LibraChart.UI.setSelectionMode('all');
        LibraChart.UI.updateAllInfo();
        LibraChart.Utils.log('UI 상태 리셋 완료');
    }
};

LibraChart.Utils.log('UI 모듈 로드 완료');