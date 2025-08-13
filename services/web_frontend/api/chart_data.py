"""
차트 페이지용 데이터 제공 API
"""

from flask import Blueprint, jsonify
from . import oracle_utils

# Blueprint 생성
chart_data_bp = Blueprint('chart_data', __name__)

@chart_data_bp.route('/api/chart-data')
def get_chart_data():
    """ESTIMATIONFUTURE 테이블 데이터를 JSON으로 반환"""
    try:
        print("=== 차트 데이터 조회 시작 ===")
        
        result = oracle_utils.get_table_data('ESTIMATIONFUTURE', limit=1000)
        
        if not result['success']:
            return jsonify({
                'success': False,
                'message': result['error'],
                'data': []
            }), 500
        
        data = result['data']
        columns = result['columns']
        
        print(f"조회된 데이터: {len(data)}개")
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'ESTIMATIONFUTURE 테이블에 데이터가 없습니다.',
                'data': []
            }), 404
        
        score_columns = [col for col in columns if col.startswith('SCR_EST_')]
        print(f"점수 컬럼들: {score_columns}")
        
        if not score_columns:
            return jsonify({
                'success': False,
                'message': 'SCR_EST_ 형태의 점수 컬럼을 찾을 수 없습니다.',
                'data': [],
                'available_columns': columns
            }), 404
        
        print(f"첫 번째 행 샘플: {data[0]}")
        for score_col in score_columns:
            valid_scores = [
                row[score_col] for row in data[:5] 
                if score_col in row and row[score_col] is not None 
                and str(row[score_col]).strip() != ''
            ]
            print(f"{score_col} 샘플 값들: {valid_scores}")
        
        print(f"=== 데이터 조회 완료: {len(data)}개 ===")
        
        return jsonify({
            'success': True,
            'data': data,
            'count': len(data),
            'columns': columns,
            'score_columns': score_columns,
            'message': f'{len(data)}개의 데이터를 성공적으로 조회했습니다.'
        })
        
    except Exception as e:
        error_message = str(e)
        print(f"차트 데이터 조회 실패: {error_message}")
        
        return jsonify({
            'success': False,
            'message': f'데이터 조회 중 오류가 발생했습니다: {error_message}',
            'data': []
        }), 500

@chart_data_bp.route('/api/chart-test')
def test_connection():
    """Oracle 연결 테스트 및 테이블 확인"""
    try:
        print("=== Oracle 연결 테스트 시작 ===")
        
        success, message = oracle_utils.test_connection()
        
        if success:
            result = oracle_utils.get_table_data('ESTIMATIONFUTURE', limit=1)
            
            if result['success']:
                return jsonify({
                    'success': True,
                    'message': 'Oracle 연결 성공! ESTIMATIONFUTURE 테이블에 데이터가 있습니다.',
                    'sample_data': result['data'][:1],
                    'columns': result['columns']
                })
            else:
                return jsonify({
                    'success': False,
                    'message': f'연결은 성공했지만 테이블 조회 실패: {result["error"]}'
                }), 500
        else:
            return jsonify({
                'success': False,
                'message': f'Oracle 연결 실패: {message}'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'연결 테스트 중 오류: {str(e)}'
        }), 500

@chart_data_bp.route('/api/table-info')
def get_table_info():
    """ESTIMATIONFUTURE 테이블 구조 정보 조회"""
    try:
        connection = oracle_utils.get_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, NULLABLE
            FROM USER_TAB_COLUMNS 
            WHERE TABLE_NAME = 'ESTIMATIONFUTURE'
            ORDER BY COLUMN_ID
        """
        
        cursor.execute(query)
        columns_info = [
            {
                'column_name': row[0],
                'data_type': row[1],
                'data_length': row[2],
                'nullable': row[3]
            }
            for row in cursor.fetchall()
        ]
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'table_name': 'ESTIMATIONFUTURE',
            'columns': columns_info,
            'column_count': len(columns_info)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'테이블 정보 조회 실패: {str(e)}'
        }), 500
