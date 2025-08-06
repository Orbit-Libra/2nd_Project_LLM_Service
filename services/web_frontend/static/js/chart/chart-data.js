//차트 데이터 관리
//../static/js/chart/chart-data.js
//데이터생성-더미대학데이터 25개생성
//필터링-대학유형,설립,지역,규모별 필터
//정렬-환경점수, 대학명, 학생수, 예산, 취업률 등
//검색- 대학명/지역/유형으로 검색
//통계-평균,최대/최소값, 분포 계산
//내보내기-JSON/CSV 형식지원
//범위 선택- 특정범위나 선택된 대학만
//이벤트- 데이터 변경시 자동알림


LibraChart.Data = {
    
    // 데이터 상태
    state: {
        allData: [],
        filteredData: [],
        currentYear: null,
        filters: {
            styp: '전체',
            fnd: '전체',
            rgn: '전체',
            usc: '전체'
        },
        sortOrder: 'rank_desc',
        isLoading: false
    },
    
    // 초기화
    init: () => {
        LibraChart.Utils.log('데이터 모듈 초기화 시작');
        LibraChart.Data.state.currentYear = LibraChart.Utils.getCurrentYear();
        LibraChart.Data.loadInitialData();
        LibraChart.Data.setupYearOptions();
    },
    
    // 연도 옵션 설정
    setupYearOptions: () => {
        const yearSelect = LibraChart.Utils.getElementById('yearSelect');
        if (!yearSelect) {
            LibraChart.Utils.error('yearSelect 요소를 찾을 수 없습니다');
            return;
        }
        
        const currentYear = LibraChart.Data.state.currentYear;
        
        // 기존 옵션이 있는지 확인
        if (yearSelect.options.length === 0) {
            // 2020년부터 현재 연도까지 옵션 추가
            for (let year = currentYear; year >= 2020; year--) {
                const option = LibraChart.Utils.createElement('option');
                option.value = year;
                option.textContent = year + '년';
                yearSelect.appendChild(option);
            }
        }
        
        // 기본값 설정
        yearSelect.value = currentYear;
        LibraChart.Utils.log(`연도 옵션 설정 완료: ${currentYear}`);
    },
    
    // 초기 데이터 로드
    loadInitialData: () => {
        LibraChart.Utils.log('초기 데이터 로드 시작');
        LibraChart.Data.state.isLoading = true;
        
        try {
            // 더미 데이터 생성
            LibraChart.Data.state.allData = LibraChart.Data.generateDummyData();
            LibraChart.Data.state.filteredData = [...LibraChart.Data.state.allData];
            
            LibraChart.Utils.log(`초기 데이터 로드 완료: ${LibraChart.Data.state.allData.length}개`);
            
            // 필터 적용
            LibraChart.Data.applyFilters();
            
        } catch (error) {
            LibraChart.Utils.error('초기 데이터 로드 실패', error);
        } finally {
            LibraChart.Data.state.isLoading = false;
        }
    },
    
    // 더미 데이터 생성
    generateDummyData: () => {
        const universities = [
            '서울대학교', '연세대학교', 'KAIST', '고려대학교', 'POSTECH',
            '성균관대학교', '한양대학교', '중앙대학교', '경희대학교', '이화여자대학교',
            '부산대학교', '전남대학교', '경북대학교', '충남대학교', '전북대학교',
            '인하대학교', '아주대학교', '국민대학교', '동국대학교', '홍익대학교',
            '건국대학교', '서강대학교', '단국대학교', '숙명여자대학교', '덕성여자대학교'
        ];
        
        const regions = [
            '서울', '부산', '대구', '인천', '광주', '대전', '울산', '세종',
            '경기', '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주'
        ];
        
        const types = ['대학', '전문대학', '대학원대학'];
        const foundations = ['국립', '공립', '사립'];
        const scales = ['A그룹', 'B그룹', 'C그룹'];
        
        return universities.map((univ, index) => ({
            id: index + 1,
            university: univ,
            environmentScore: LibraChart.Utils.round(Math.random() * 40 + 60, 1), // 60-100 사이
            region: regions[Math.floor(Math.random() * regions.length)],
            type: types[Math.floor(Math.random() * types.length)],
            foundation: foundations[Math.floor(Math.random() * foundations.length)],
            scale: scales[Math.floor(Math.random() * scales.length)],
            year: LibraChart.Data.state.currentYear,
            rank: index + 1,
            // 추가 데이터
            studentCount: Math.floor(Math.random() * 20000) + 5000,
            facultyCount: Math.floor(Math.random() * 1000) + 200,
            establishedYear: Math.floor(Math.random() * 100) + 1920,
            budget: Math.floor(Math.random() * 50000) + 10000, // 백만원 단위
            researchScore: LibraChart.Utils.round(Math.random() * 40 + 50, 1),
            employmentRate: LibraChart.Utils.round(Math.random() * 30 + 65, 1)
        }));
    },
    
    // 특정 연도 데이터 로드
    loadDataForYear: (year) => {
        LibraChart.Utils.log(`${year}년 데이터 로드`);
        
        LibraChart.Data.state.currentYear = parseInt(year);
        
        // 연도에 따른 데이터 조정
        LibraChart.Data.state.allData = LibraChart.Data.state.allData.map(item => ({
            ...item,
            year: LibraChart.Data.state.currentYear,
            // 연도별 점수 변화 시뮬레이션
            environmentScore: LibraChart.Utils.round(
                item.environmentScore + (Math.random() - 0.5) * 5, 1
            ),
            employmentRate: LibraChart.Utils.round(
                item.employmentRate + (Math.random() - 0.5) * 3, 1
            )
        }));
        
        LibraChart.Data.applyFilters();
        LibraChart.Utils.log(`${year}년 데이터 로드 완료`);
    },
    
    // 필터 적용
    applyFilters: () => {
        const { allData, filters } = LibraChart.Data.state;
        
        LibraChart.Utils.log('필터 적용 시작', filters);
        
        // 필터링
        LibraChart.Data.state.filteredData = allData.filter(item => {
            return (filters.styp === '전체' || item.type === filters.styp) &&
                   (filters.fnd === '전체' || item.foundation === filters.fnd) &&
                   (filters.rgn === '전체' || item.region === filters.rgn) &&
                   (filters.usc === '전체' || item.scale === filters.usc);
        });
        
        // 정렬 적용
        LibraChart.Data.applySorting();
        
        LibraChart.Utils.log(`필터 적용 완료: ${LibraChart.Data.state.filteredData.length}개 데이터`);
        
        // 이벤트 발생
        LibraChart.Data.triggerDataChangeEvent();
    },
    
    // 정렬 적용
    applySorting: () => {
        const { filteredData, sortOrder } = LibraChart.Data.state;
        
        switch (sortOrder) {
            case 'rank_desc':
                filteredData.sort((a, b) => b.environmentScore - a.environmentScore);
                break;
            case 'rank_asc':
                filteredData.sort((a, b) => a.environmentScore - b.environmentScore);
                break;
            case 'university':
                filteredData.sort((a, b) => a.university.localeCompare(b.university, 'ko'));
                break;
            case 'student_desc':
                filteredData.sort((a, b) => b.studentCount - a.studentCount);
                break;
            case 'budget_desc':
                filteredData.sort((a, b) => b.budget - a.budget);
                break;
            case 'employment_desc':
                filteredData.sort((a, b) => b.employmentRate - a.employmentRate);
                break;
            default:
                LibraChart.Utils.warn(`알 수 없는 정렬 방식: ${sortOrder}`);
        }
        
        // 정렬 후 순위 재계산
        filteredData.forEach((item, index) => {
            item.currentRank = index + 1;
        });
        
        LibraChart.Utils.log(`정렬 적용 완료: ${sortOrder}`);
    },
    
    // 필터 값 설정
    setFilter: (filterType, value) => {
        if (LibraChart.Data.state.filters.hasOwnProperty(filterType)) {
            LibraChart.Data.state.filters[filterType] = value;
            LibraChart.Utils.log(`필터 설정: ${filterType} = ${value}`);
            LibraChart.Data.applyFilters();
            return true;
        } else {
            LibraChart.Utils.error(`잘못된 필터 타입: ${filterType}`);
            return false;
        }
    },
    
    // 정렬 방식 설정
    setSortOrder: (sortOrder) => {
        LibraChart.Data.state.sortOrder = sortOrder;
        LibraChart.Utils.log(`정렬 방식 설정: ${sortOrder}`);
        LibraChart.Data.applySorting();
        LibraChart.Data.triggerDataChangeEvent();
    },
    
    // 데이터 가져오기
    getFilteredData: () => {
        return [...LibraChart.Data.state.filteredData];
    },
    
    getAllData: () => {
        return [...LibraChart.Data.state.allData];
    },
    
    // 범위별 데이터 가져오기
    getDataInRange: (startIndex, endIndex) => {
        const data = LibraChart.Data.getFilteredData();
        const start = Math.max(0, startIndex - 1); // 1-based to 0-based
        const end = Math.min(data.length, endIndex);
        return data.slice(start, end);
    },
    
    // 선택된 대학들의 데이터 가져오기
    getSelectedUniversitiesData: (universityNames) => {
        const data = LibraChart.Data.getFilteredData();
        return data.filter(item => universityNames.includes(item.university));
    },
    
    // 통계 정보 계산
    getStatistics: () => {
        const data = LibraChart.Data.getFilteredData();
        
        if (data.length === 0) {
            return {
                count: 0,
                avgEnvironmentScore: 0,
                minEnvironmentScore: 0,
                maxEnvironmentScore: 0,
                avgEmploymentRate: 0,
                totalStudents: 0
            };
        }
        
        const scores = data.map(item => item.environmentScore);
        const employmentRates = data.map(item => item.employmentRate);
        const studentCounts = data.map(item => item.studentCount);
        
        return {
            count: data.length,
            avgEnvironmentScore: LibraChart.Utils.round(
                scores.reduce((sum, score) => sum + score, 0) / scores.length, 1
            ),
            minEnvironmentScore: Math.min(...scores),
            maxEnvironmentScore: Math.max(...scores),
            avgEmploymentRate: LibraChart.Utils.round(
                employmentRates.reduce((sum, rate) => sum + rate, 0) / employmentRates.length, 1
            ),
            totalStudents: studentCounts.reduce((sum, count) => sum + count, 0),
            // 지역별 분포
            regionDistribution: LibraChart.Data.getRegionDistribution(data),
            // 유형별 분포
            typeDistribution: LibraChart.Data.getTypeDistribution(data)
        };
    },
    
    // 지역별 분포 계산
    getRegionDistribution: (data = null) => {
        const targetData = data || LibraChart.Data.getFilteredData();
        const distribution = {};
        
        targetData.forEach(item => {
            distribution[item.region] = (distribution[item.region] || 0) + 1;
        });
        
        return distribution;
    },
    
    // 유형별 분포 계산
    getTypeDistribution: (data = null) => {
        const targetData = data || LibraChart.Data.getFilteredData();
        const distribution = {};
        
        targetData.forEach(item => {
            distribution[item.type] = (distribution[item.type] || 0) + 1;
        });
        
        return distribution;
    },
    
    // 검색 기능
    searchUniversities: (query) => {
        if (!query || query.trim() === '') {
            return LibraChart.Data.getFilteredData();
        }
        
        const searchTerm = query.toLowerCase().trim();
        const data = LibraChart.Data.getFilteredData();
        
        return data.filter(item => 
            item.university.toLowerCase().includes(searchTerm) ||
            item.region.toLowerCase().includes(searchTerm) ||
            item.type.toLowerCase().includes(searchTerm) ||
            item.foundation.toLowerCase().includes(searchTerm)
        );
    },
    
    // 데이터 내보내기
    exportData: (format = 'json') => {
        const data = LibraChart.Data.getFilteredData();
        const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
        
        switch (format.toLowerCase()) {
            case 'json':
                return {
                    filename: `libra-data-${timestamp}.json`,
                    content: JSON.stringify(data, null, 2),
                    mimeType: 'application/json'
                };
            
            case 'csv':
                const csvContent = LibraChart.Data.convertToCSV(data);
                return {
                    filename: `libra-data-${timestamp}.csv`,
                    content: csvContent,
                    mimeType: 'text/csv'
                };
            
            default:
                LibraChart.Utils.error(`지원하지 않는 형식: ${format}`);
                return null;
        }
    },
    
    // CSV 변환
    convertToCSV: (data) => {
        if (data.length === 0) return '';
        
        const headers = Object.keys(data[0]);
        const csvHeaders = headers.join(',');
        
        const csvRows = data.map(row => 
            headers.map(header => {
                const value = row[header];
                // 문자열에 쉼표가 있으면 따옴표로 감싸기
                return typeof value === 'string' && value.includes(',') 
                    ? `"${value}"` 
                    : value;
            }).join(',')
        );
        
        return [csvHeaders, ...csvRows].join('\n');
    },
    
    // 데이터 변경 이벤트 발생
    triggerDataChangeEvent: () => {
        const event = new CustomEvent('dataChanged', {
            detail: {
                filteredData: LibraChart.Data.getFilteredData(),
                statistics: LibraChart.Data.getStatistics(),
                filters: { ...LibraChart.Data.state.filters },
                sortOrder: LibraChart.Data.state.sortOrder
            }
        });
        
        document.dispatchEvent(event);
        LibraChart.Utils.log('데이터 변경 이벤트 발생');
    },
    
    // 데이터 리셋
    reset: () => {
        LibraChart.Data.state = {
            allData: [],
            filteredData: [],
            currentYear: LibraChart.Utils.getCurrentYear(),
            filters: {
                styp: '전체',
                fnd: '전체',
                rgn: '전체',
                usc: '전체'
            },
            sortOrder: 'rank_desc',
            isLoading: false
        };
        
        LibraChart.Data.loadInitialData();
        LibraChart.Utils.log('데이터 상태 리셋 완료');
    },
    
    // 상태 정보 가져오기
    getState: () => {
        return {
            ...LibraChart.Data.state,
            statistics: LibraChart.Data.getStatistics()
        };
    }
};

LibraChart.Utils.log('Data 모듈 로드 완료');