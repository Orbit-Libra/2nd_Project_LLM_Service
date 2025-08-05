import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from TableMergerUploader import TableMergerUploader
from DataMergerAndExporter import DataMergerAndExporter
from FilteredScoreUploader import FilteredScoreUploader

from core_utiles.OracleDBConnection import OracleDBConnection
from core_utiles.config_loader import (
    CSV_NUM06_PREFIX, CSV_NUM07_PREFIX, CSV_FILTERED_PREFIX
)

def TableMerge(db):
    print("\n테이블 병합 시작")
    common_columns = ['YR', 'ID', 'SNM', 'STYP', 'FND', 'RGN', 'USC']
    years = range(2014, 2025)

    uploader = TableMergerUploader(
        db=db,
        years=years,
        common_cols=common_columns,
        csv_prefix=CSV_NUM06_PREFIX,
        table_prefix="NUM06"
    )
    uploader.process_all_years()

def ScoreTableData(db):
    print("\n평가점수 + 메타데이터 병합 시작")
    years = range(2014, 2025)

    merger = DataMergerAndExporter(
        db=db,
        years=years,
        file_prefix=CSV_NUM07_PREFIX,
        table_prefix="NUM07"
    )
    merger.merge_and_save()

def ScoreFilteredData(db):
    print("\n정규화 대상 인풋 컬럼 필터링 시작")
    years = range(2014, 2025)
    input_abbr = [
        'BCNT_SUM', 'BPS', 'ABI', 'LAS', 'TRS', 'TPC', 'APS',
        'UBGT', 'USTL', 'MCT', 'CPS',
        'LUC', 'LU_SUM', 'LB_SUM', 'EDC', 'EP', 'LPS', 'VPS',
        'SPK', 'LPK', 'EHS'
    ]

    uploader = FilteredScoreUploader(
        db=db,
        years=years,
        input_abbr=input_abbr,
        csv_prefix=CSV_FILTERED_PREFIX,
        table_name="FILTERED"
    )
    uploader.run()

if __name__ == "__main__":

    db = OracleDBConnection()
    db.connect()

    TableMerge(db)
    ScoreTableData(db)
    ScoreFilteredData(db)

    db.close()
