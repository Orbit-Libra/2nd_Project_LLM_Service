# 경로 보정
import os
import sys
sys.path.append("d:/workspace/project/Project_Libra/1st_Project_MachineLearning/model/ml_pipline")

from ExcelToCSVConverter_ver1 import ExcelToCSVConverter_ver1
from ExcelToCSVConverter_ver2 import ExcelToCSVConverter_ver2
from CWURCrawler import CWURCrawler
from EnNameCollector import EnNameCollector
from NameMapper import NameMapper
from RankedScoreExporter import RankedScoreExporter
from HeaderTermCollector import HeaderTermCollector
from HeaderAbbreviationMapper import HeaderAbbreviationMapper
from CSVHeaderRenamer import CSVHeaderRenamer
from CSVToOracleUploader import CSVToOracleUploader

from core_utiles.OracleDBConnection import OracleDBConnection
from core_utiles.config_loader import BASE_RAW_DIR, BASE_CSV_DIR, BASE_OUTPUT_DIR

def ExcelToCSV_ver1():
    print("\nVer1: 엑셀 → CSV 변환 시작")
    targets = [
        ("기본통계_소장및구독자료.xlsx", "Num01_소장및구독자료"),
        ("기본통계_예산및결산.xlsx", "Num03_예산및결산"),
        ("기본통계_이용및이용자.xlsx", "Num04_이용및이용자"),
        ("기본통계_인적자원.xlsx", "Num05_인적자원")
    ]
    for fname, prefix in targets:
        fpath = os.path.join(BASE_RAW_DIR, fname)
        ExcelToCSVConverter_ver1(fpath, prefix, BASE_CSV_DIR).run()
    print("Ver1 CSV 변환 완료\n")

def ExcelToCSV_ver2():
    print("\nVer2: 특이형 엑셀 변환 시작")
    fname, prefix = "기본통계_시설.xlsx", "Num02_시설"
    fpath = os.path.join(BASE_RAW_DIR, fname)
    ExcelToCSVConverter_ver2(fpath, prefix, BASE_CSV_DIR).run()
    print("Ver2 CSV 변환 완료\n")

def Crawling():
    print("\nCWUR 크롤링 시작")
    output_path = os.path.join(BASE_OUTPUT_DIR, "대학평가점수크롤링.csv")
    CWURCrawler(BASE_CSV_DIR, output_path).run()

def EnNameList():
    print("\n대학 영문명 리스트화 시작")
    in_path = os.path.join(BASE_OUTPUT_DIR, "대학평가점수크롤링.csv")
    out_path = os.path.join(BASE_OUTPUT_DIR, "대학영문명리스트.csv")
    EnNameCollector(in_path, out_path).run()

def NameMapping():
    print("\n대학명 매핑 시작")
    in_path = os.path.join(BASE_OUTPUT_DIR, "대학영문명리스트.csv")
    out_path = os.path.join(BASE_OUTPUT_DIR, "대학명매핑표.csv")
    NameMapper(in_path, out_path).run()

def ScoreCSVExporter():
    score_path = os.path.join(BASE_OUTPUT_DIR, "대학평가점수크롤링.csv")
    mapping_path = os.path.join(BASE_OUTPUT_DIR, "대학명매핑표.csv")
    RankedScoreExporter(score_path, mapping_path, BASE_CSV_DIR).run()

def HeaderCollellector():
    print("\n헤더 수집 시작")
    save_path = os.path.join(BASE_OUTPUT_DIR, "모든헤더목록표.csv")
    collector = HeaderTermCollector(BASE_CSV_DIR)
    collector.run()
    collector.save_terms(save_path)

def HeaderMapper():
    print("\n헤더 매핑 시작")
    input_path = os.path.join(BASE_OUTPUT_DIR, "모든헤더목록표.csv")
    output_path = os.path.join(BASE_OUTPUT_DIR, "헤더약어매핑표.csv")
    HeaderAbbreviationMapper(input_path, output_path).run()

def HeaderRenamer():
    print("\nCSV 컬럼명 변경 시작")
    mapping_csv = os.path.join(BASE_OUTPUT_DIR, "헤더약어매핑표.csv")
    CSVHeaderRenamer(BASE_CSV_DIR, mapping_csv).process_all_csvs()

def CreateDB():
    print("\nOracle DB 테이블 생성 시작")
    db = OracleDBConnection()
    db.connect()
    loader = CSVToOracleUploader(db=db, csv_dir=BASE_CSV_DIR)
    loader.run()
    db.close()
    print("DB 생성 완료\n")

if __name__ == "__main__":
    ExcelToCSV_ver1()
    ExcelToCSV_ver2()
    Crawling()
    EnNameList()
    NameMapping()
    ScoreCSVExporter()
    HeaderCollellector()
    HeaderMapper()
    HeaderRenamer()
    CreateDB()

