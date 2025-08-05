import os
import re
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class CWURCrawler:
    def __init__(self, folder_path, output_path):
        self.folder_path = folder_path
        self.output_path = output_path

    def extract_years(self):
        years = []
        for fname in os.listdir(self.folder_path):
            match = re.search(r'_(\d{4})\.csv$', fname)
            if match:
                years.append(int(match.group(1)))
        return sorted(set(years))

    def get_cwur_url(self, year):
        if 2018 <= year <= 2022:
            return f"https://cwur.org/{year}-{str(year+1)[-2:]}.php"
        else:
            return f"https://cwur.org/{year}.php"

    def find_column_index(self, candidates, headers):
        for col in candidates:
            if col in headers:
                return headers.index(col)
        return None

    def crawl_year(self, year):
        url = self.get_cwur_url(year)

        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--no-sandbox")

        driver = webdriver.Chrome(options=options)
        driver.get(url)

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "table"))
            )
        except:
            print(f"연도 {year}: 테이블 로딩 실패")
            driver.quit()
            return []

        html = driver.page_source
        driver.quit()
        soup = BeautifulSoup(html, "html.parser")

        table = soup.find("table")
        if not table:
            print(f"연도 {year}: 테이블 없음")
            return []

        headers = [th.text.strip() for th in table.find("tr").find_all("th")]
        loc_idx = self.find_column_index(["Location", "Country"], headers)
        inst_idx = self.find_column_index(["Institution"], headers)
        score_idx = self.find_column_index(["Score", "Overall Score"], headers)

        missing = []
        if loc_idx is None: missing.append("Location/Country")
        if inst_idx is None: missing.append("Institution")
        if score_idx is None: missing.append("Score")

        if missing:
            print(f"연도 {year}: 누락된 컬럼 - {', '.join(missing)}")
            return []

        data = []
        for row in table.find_all("tr")[1:]:
            cols = row.find_all("td")
            if len(cols) > max(loc_idx, inst_idx, score_idx):
                if cols[loc_idx].text.strip() == "South Korea":
                    institution = cols[inst_idx].text.strip()
                    score = cols[score_idx].text.strip()
                    data.append({
                        "Institution": institution,
                        "Score": score,
                        "Year": year
                    })
        return data

    def run(self):
        years = self.extract_years()
        print(f"추출된 연도들: {years}")
        all_data = []
        for year in years:
            print(f"\n크롤링 중: {year}")
            result = self.crawl_year(year)
            if result:
                print(f"평가점수({year}) 크롤링 완료")
            else:
                print(f"평가점수({year}) 크롤링 실패 or 데이터 없음")
            all_data.extend(result)


        df = pd.DataFrame(all_data)
        df.to_csv(self.output_path, index=False, encoding="utf-8-sig")
        print(f"저장 완료: {self.output_path}")