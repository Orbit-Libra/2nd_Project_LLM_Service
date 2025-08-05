from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
import os

# 다운로드 경로 설정
relative_path = "datafiles/rawfiles"
download_dir = os.path.abspath(relative_path)
os.makedirs(download_dir, exist_ok=True)

# 커스텀 사용자 프로필 정보
chrome_user_data_dir = os.path.abspath("datafiles/chrome_user")  # 자동 경로 변환
chrome_profile_name = "Profile 1"  # 또는 사용자가 생성한 다른 프로필명

# 크롬 옵션 구성
options = Options()
options.add_argument(f"--user-data-dir={chrome_user_data_dir}")
options.add_argument(f"--profile-directory={chrome_profile_name}")
# 필요 없다면 DevTools 포트는 제거 가능:
# options.add_argument("--remote-debugging-port=9222")

# 다운로드 설정
options.add_experimental_option("prefs", {
    "download.default_directory": download_dir,
    "download.prompt_for_download": False,
    "download.directory_upgrade": True
})

# 웹드라이버 실행
driver = webdriver.Chrome(options=options)

# 자료 유형별 다운로드 반복
for su in range(1, 6):
    url = f"http://www.rinfo.kr/stat/search/basic/{su}/result?sm=basic&syf=2014&syt=2024&year=2014%2C2015%2C2016%2C2017%2C2018%2C2019%2C2020%2C2021%2C2022%2C2023%2C2024&st=UNI&ut=&us=&etcheckall=&rgcheckall=&su={su}&oatcheckall=true&oitcheckall=true&oixcheckall=true&cpp=10"
    
    driver.get("about:blank")
    time.sleep(1)
    driver.get(url)
    time.sleep(3)

    # 자바스크립트 함수로 다운로드 트리거
    driver.execute_script("goPage('65535','xls');")
    time.sleep(5)

driver.quit()
