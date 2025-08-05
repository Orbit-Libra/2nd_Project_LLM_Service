import os
import subprocess

def create_chrome_profile():
    chrome_user_dir = os.path.abspath("datafiles/chrome_user")
    profile_name = "Profile 1"
    profile_path = os.path.join(chrome_user_dir, profile_name)

    # 이미 생성된 경우 스킵
    if os.path.exists(profile_path):
        print(f"이미 프로필이 존재합니다: {profile_path}")
        print("WIN + R 키를 누른 후 다음 명령어를 실행해주세요.")
        print('chrome.exe --user-data-dir="D:\workspace\project\Project_Libra\2nd_Project_LLM_Service\services\data_service\datafiles\chrome_user" --profile-directory="Profile 1"')
        print('설정 - 개인 정보 보호 및 보안 - 사이트 설정 - 추가 콘텐츠 설정 - ')
        print('안전하지 않은 콘텐츠 - 안전하지 않은 콘텐츠 표시가 허용됨 설정에')
        print('http://www.rinfo.kr 를 추가 후 다운로드 경로를 datafiles/rawfiles로 지정해주세요.')
        return

    os.makedirs(profile_path, exist_ok=True)
    print(f"프로필 디렉토리 생성: {profile_path}")

    # 크롬 실행하여 해당 프로필 초기화
    chrome_path = "C:/Program Files/Google/Chrome/Application/chrome.exe"
    launch_cmd = [
        chrome_path,
        f'--user-data-dir="{chrome_user_dir}"',
        f'--profile-directory="{profile_name}"'
    ]
    subprocess.Popen(" ".join(launch_cmd), shell=True)
    print("크롬이 새 프로필로 실행되었습니다.")
    print("WIN + R 키를 누른 후 다음 명령어를 실행해주세요.")
    print('chrome.exe --user-data-dir="D:\workspace\project\Project_Libra\2nd_Project_LLM_Service\services\data_service\datafiles\chrome_user" --profile-directory="Profile 1"')
    print('설정 - 개인 정보 보호 및 보안 - 사이트 설정 - 추가 콘텐츠 설정 - ')
    print('안전하지 않은 콘텐츠 - 안전하지 않은 콘텐츠 표시가 허용됨 설정에')
    print('http://www.rinfo.kr 를 추가 후 다운로드 경로를 datafiles/rawfiles로 지정해주세요.')
    

if __name__ == "__main__":
    create_chrome_profile()
