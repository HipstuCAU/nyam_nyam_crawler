from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import math
import json
from google.cloud import firestore
import os

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./firebaseServiceAccountKey.json"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 시작 시간
start = time.time()

def jsonParser(data):
    with open(os.path.join(BASE_DIR, './Doc/CAUMealData.json'), 'w+', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent='\t')

# 식당 메뉴 정보 가져오는 함수
def getMealInfo(mealSchedule):
    menuInfoDict = {}
    try:
        # 모든 식당(dl) 요소 찾기
        cafeterias = dr.find_elements(By.CSS_SELECTOR, '#carteP005 > li.on > dl.nb-p-04-list-02')
        
        for cafeteria in cafeterias:
            try:
                # 식당명 가져오기
                cafeteriaName = cafeteria.find_element(By.CSS_SELECTOR, 'dt > a > span').text
                cafeteriaName = cafeteriaName.replace('다빈치', '안성')
                menuInfoDict[cafeteriaName] = {}
                
                # 식당 클릭 (메뉴 표시)
                cafeteriaButton = cafeteria.find_element(By.CSS_SELECTOR, 'dt')
                cafeteriaButton.click()
                time.sleep(0.5)
                
                # 해당 식당의 모든 메뉴 항목 가져오기
                menuItems = cafeteria.find_elements(By.CSS_SELECTOR, 'dd')
                
                for menuItem in menuItems:
                    try:
                        # 시간과 코스명 가져오기
                        timeText = menuItem.find_element(By.CSS_SELECTOR, 'ul.meals-detail > li > p > span:nth-child(1)').text
                        courseText = menuItem.find_element(By.CSS_SELECTOR, 'ul.meals-detail > li > p > span:nth-child(2)').text
                        
                        # 가격 가져오기
                        priceText = menuItem.find_element(By.CSS_SELECTOR, 'ul.meals-detail > li > div > span').text
                        
                        # 메뉴 상세 정보 가져오기
                        menuDetailElements = menuItem.find_elements(By.CSS_SELECTOR, 'ul.meals-detail > li > div > div.nb-p-04-03 > p')
                        menuDetailList = [elem.text for elem in menuDetailElements]
                        menuDetail = '|'.join(menuDetailList)
                        
                        # 메뉴 타입을 키로 사용
                        menuInfoDict[cafeteriaName][courseText] = {
                            'time': timeText,
                            'price': priceText,
                            'menu': menuDetail
                        }
                        
                    except Exception as e:
                        print(f"메뉴 항목 처리 중 오류: {e}")
                        continue
                        
            except Exception as e:
                print(f"식당 처리 중 오류: {e}")
                continue
                
    except Exception as e:
        print(f"getMealInfo 오류: {e}")
    
    return menuInfoDict

# 데일리 메뉴 정보 가져오는 함수
def getDayOfMeal():
    dailyMenuInfoDict = {}
    try:
        # 조식, 중식, 석식 탭 찾기
        mealTabs = dr.find_elements(By.CSS_SELECTOR, 'header.nb-p-headers > ol.nb-p-04-list > li')
        
        for idx, tab in enumerate(mealTabs):
            try:
                tab.click()
                time.sleep(0.8)
                dailyMenuInfoDict[idx] = getMealInfo(idx)
            except Exception as e:
                print(f"식사 시간대 {idx} 처리 중 오류: {e}")
                continue
                
    except Exception as e:
        print(f"getDayOfMeal 오류: {e}")
    
    return dailyMenuInfoDict

# 위클리 메뉴 정보 가져오는 함수
def getWeekOfMeal():
    weeklyMenuDict = {}
    weeklyIndex = 7
    
    try:
        # 서울, 다빈치 캠퍼스 탭 찾기
        campusTabs = dr.find_elements(By.CSS_SELECTOR, 'header.nb-p-headers > div.nb-right > ol.nb-p-tab > li')
        
        for campusIdx, campusTab in enumerate(campusTabs):
            weeklyMenuDict[campusIdx] = {}
            
            try:
                # 캠퍼스 선택
                campusTab.click()
                time.sleep(1)
                
                # 7일치 데이터 수집
                for day in range(weeklyIndex):
                    try:
                        # 현재 날짜 가져오기
                        dateElement = dr.find_element(By.CSS_SELECTOR, 'div.nb-p-time-select > p.nb-p-time-select-current')
                        currentDate = dateElement.text
                        
                        print(f"캠퍼스 {campusIdx}, 날짜: {currentDate} 크롤링 중...")
                        
                        # 해당 날짜의 메뉴 정보 수집
                        weeklyMenuDict[campusIdx][currentDate] = getDayOfMeal()
                        
                        # 다음 날로 이동 (마지막 날이 아닐 때만)
                        if day < weeklyIndex - 1:
                            nextButton = dr.find_element(By.CSS_SELECTOR, 'div.nb-p-time-select > a.nb-p-time-select-next')
                            nextButton.click()
                            time.sleep(1)
                            
                    except Exception as e:
                        print(f"날짜 {day} 처리 중 오류: {e}")
                        continue
                
                # 원래 날짜로 되돌리기 (7일 전으로)
                for day in range(weeklyIndex):
                    try:
                        prevButton = dr.find_element(By.CSS_SELECTOR, 'div.nb-p-time-select > a.nb-p-time-select-prev')
                        prevButton.click()
                        time.sleep(0.5)
                    except:
                        pass
                        
            except Exception as e:
                print(f"캠퍼스 {campusIdx} 처리 중 오류: {e}")
                continue
                
    except Exception as e:
        print(f"getWeekOfMeal 오류: {e}")
    
    return weeklyMenuDict

def runCrawler():
    try:
        weeklyData = getWeekOfMeal()
        jsonParser(weeklyData)
        print("크롤링 완료")
        return True
    except Exception as e:
        print(f"크롤링 실행 중 오류: {e}")
        return False

try:
    # Chrome 옵션 설정
    options = webdriver.ChromeOptions()
    options.add_argument("start-maximized")
    options.add_argument("lang=ko_KR")
    options.add_argument('headless')
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Chrome driver 초기화
    dr = webdriver.Chrome(options=options)
    dr.implicitly_wait(5)
    
    # 변경된 URL로 접속
    print("사이트 접속 중...")
    dr.get('https://mportal2.cau.ac.kr/main.do')
    
    # 페이지 로딩 대기
    time.sleep(3)
    
    # Run Crawler
    if runCrawler():
        # Set FireStore
        try:
            db = firestore.Client()
            doc_ref = db.collection(u'CAU_Haksik').document('CAU_Cafeteria_Menu')
            
            with open(os.path.join(BASE_DIR, './Doc/CAUMealData.json'), 'r', encoding='utf-8') as f:
                cafeteria_data_dic = json.load(f)
            
            doc_ref.set(cafeteria_data_dic)
            print("Firestore 업데이트 완료")
            
        except Exception as e:
            print("Firestore 업데이트 예외 발생:", e)
            import traceback
            traceback.print_exc()
    else:
        print("크롤링 실패")

except Exception as e:
    print("프로그램 실행 중 예외 발생:", e)
    import traceback
    traceback.print_exc()

finally:
    try:
        dr.quit()
    except:
        pass
    
    print("최신화 완료")
    processTime = time.time() - start
    minute = processTime / 60
    second = processTime % 60
    print("실행 시간:", math.trunc(minute), "분", round(second), "초")
