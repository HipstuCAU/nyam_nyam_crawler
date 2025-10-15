from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
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
def getMealInfo():
    menuInfoDict = {}
    wait = WebDriverWait(dr, 10)
    
    try:
        # 현재 활성화된 li 안의 모든 식당(dl) 찾기
        cafeterias = dr.find_elements(By.CSS_SELECTOR, '#carteP005 > li.on > dl.nb-p-04-list-02')
        print(f"  찾은 식당 수: {len(cafeterias)}")
        
        for idx, cafeteria in enumerate(cafeterias):
            try:
                # 식당명 가져오기
                cafeteriaName = None
                try:
                    cafeteriaName = cafeteria.find_element(By.CSS_SELECTOR, 'dt span').text.strip()
                except:
                    try:
                        cafeteriaName = cafeteria.find_element(By.CSS_SELECTOR, 'dt a').text.strip()
                    except:
                        try:
                            cafeteriaName = cafeteria.find_element(By.CSS_SELECTOR, 'dt').text.strip()
                        except:
                            continue
                
                if not cafeteriaName:
                    continue
                
                cafeteriaName = cafeteriaName.replace('다빈치', '안성')
                print(f"  처리 중: {cafeteriaName}")
                menuInfoDict[cafeteriaName] = {}
                
                # 식당 클릭하여 메뉴 펼치기
                try:
                    dt_element = cafeteria.find_element(By.CSS_SELECTOR, 'dt')
                    dr.execute_script("arguments[0].click();", dt_element)
                    time.sleep(0.7)
                except Exception as e:
                    print(f"    클릭 실패: {e}")
                
                # 메뉴 항목들 다시 찾기 (클릭 후 DOM이 변경되므로)
                menuItems = cafeteria.find_elements(By.CSS_SELECTOR, 'dd')
                print(f"    메뉴 항목 수: {len(menuItems)}")
                
                for menuItem in menuItems:
                    try:
                        # ng-hide 클래스가 있으면 건너뛰기
                        if 'ng-hide' in menuItem.get_attribute('class'):
                            continue
                        
                        # 시간 가져오기
                        timeText = ""
                        try:
                            timeText = menuItem.find_element(By.CSS_SELECTOR, 'span[ng-bind="row.time"]').text.strip()
                        except:
                            pass
                        
                        # 코스명 가져오기
                        courseText = ""
                        try:
                            courseText = menuItem.find_element(By.CSS_SELECTOR, 'span[ng-bind="row.course"]').text.strip()
                        except:
                            pass
                        
                        # 가격 가져오기
                        priceText = ""
                        try:
                            priceText = menuItem.find_element(By.CSS_SELECTOR, 'span[ng-bind="row.price"]').text.strip()
                        except:
                            pass
                        
                        # 메뉴 상세 가져오기
                        menuDetail = ""
                        try:
                            # ng-bind-html로 된 div 찾기
                            menuDiv = menuItem.find_element(By.CSS_SELECTOR, 'div[ng-bind-html]')
                            
                            # p 태그들이 있으면 그것으로
                            menuPs = menuDiv.find_elements(By.TAG_NAME, 'p')
                            if menuPs:
                                menuDetailList = [p.text.strip() for p in menuPs if p.text.strip()]
                                menuDetail = '|'.join(menuDetailList)
                            else:
                                # p 태그가 없으면 전체 텍스트
                                menuDetail = menuDiv.text.strip()
                        except Exception as e:
                            pass
                        
                        # 메뉴 정보 정리
                        menuDetail = menuDetail.replace('<일품>', '').replace('특)', '').replace('(중식만가능)', '')
                        
                        # 빈 코스명 처리
                        if not courseText:
                            courseText = "기타"
                        
                        # 저장
                        if timeText or priceText or menuDetail:  # 최소한 하나라도 있어야 저장
                            menuInfoDict[cafeteriaName][courseText] = {
                                'time': timeText,
                                'price': priceText,
                                'menu': menuDetail
                            }
                        
                    except Exception as e:
                        print(f"    메뉴 항목 오류: {e}")
                        continue
                
            except Exception as e:
                print(f"  식당 처리 오류 ({idx}): {e}")
                continue
        
    except Exception as e:
        print(f"  getMealInfo 전체 오류: {e}")
    
    return menuInfoDict

# 데일리 메뉴 정보 가져오는 함수
def getDayOfMeal():
    dailyMenuInfoDict = {}
    
    try:
        # 조식, 중식, 석식 탭 찾기
        mealTabs = dr.find_elements(By.CSS_SELECTOR, 'ol.nb-p-04-list > li')
        print(f"  식사 시간대 수: {len(mealTabs)}")
        
        for idx in range(len(mealTabs)):
            try:
                # 탭을 다시 찾아서 클릭 (stale element 방지)
                mealTabs = dr.find_elements(By.CSS_SELECTOR, 'ol.nb-p-04-list > li')
                tab = mealTabs[idx]
                
                mealType = tab.text.strip()
                print(f"  {mealType} 수집 중...")
                
                dr.execute_script("arguments[0].click();", tab)
                time.sleep(1)
                
                dailyMenuInfoDict[idx] = getMealInfo()
                
            except Exception as e:
                print(f"  식사 시간대 {idx} 오류: {e}")
                continue
    
    except Exception as e:
        print(f"  getDayOfMeal 오류: {e}")
    
    return dailyMenuInfoDict

# 위클리 메뉴 정보 가져오는 함수
def getWeekOfMeal():
    weeklyMenuDict = {}
    weeklyIndex = 2
    
    try:
        # 서울, 다빈치 캠퍼스 탭 찾기
        campusTabs = dr.find_elements(By.CSS_SELECTOR, 'ol.nb-p-tab > li')
        print(f"캠퍼스 수: {len(campusTabs)}")
        
        for campusIdx in range(len(campusTabs)):
            weeklyMenuDict[campusIdx] = {}
            
            try:
                # 캠퍼스 탭 다시 찾아서 클릭
                campusTabs = dr.find_elements(By.CSS_SELECTOR, 'ol.nb-p-tab > li')
                campusTab = campusTabs[campusIdx]
                campusName = campusTab.text.strip()
                
                print(f"\n=== {campusName} 캠퍼스 크롤링 시작 ===")
                dr.execute_script("arguments[0].click();", campusTab)
                time.sleep(1.5)
                
                # 7일치 데이터 수집
                for day in range(weeklyIndex):
                    try:
                        # 현재 날짜 가져오기
                        dateElement = dr.find_element(By.CSS_SELECTOR, 'p.nb-p-time-select-current')
                        currentDate = dateElement.text.strip()
                        
                        print(f"\n날짜: {currentDate}")
                        
                        # 해당 날짜의 메뉴 정보 수집
                        weeklyMenuDict[campusIdx][currentDate] = getDayOfMeal()
                        
                        # 다음 날로 이동 (마지막 날이 아닐 때만)
                        if day < weeklyIndex - 1:
                            nextButton = dr.find_element(By.CSS_SELECTOR, 'a.nb-p-time-select-next')
                            dr.execute_script("arguments[0].click();", nextButton)
                            time.sleep(1)
                        
                    except Exception as e:
                        print(f"날짜 {day} 처리 오류: {e}")
                        continue
                
                # 원래 날짜로 되돌리기
                print(f"\n{campusName} 날짜 되돌리는 중...")
                for day in range(weeklyIndex):
                    try:
                        prevButton = dr.find_element(By.CSS_SELECTOR, 'a.nb-p-time-select-prev')
                        dr.execute_script("arguments[0].click();", prevButton)
                        time.sleep(0.3)
                    except:
                        pass
                
            except Exception as e:
                print(f"캠퍼스 {campusIdx} 처리 오류: {e}")
                import traceback
                traceback.print_exc()
                continue
        
    except Exception as e:
        print(f"getWeekOfMeal 오류: {e}")
        import traceback
        traceback.print_exc()
    
    return weeklyMenuDict

def runCrawler():
    try:
        weeklyData = getWeekOfMeal()
        jsonParser(weeklyData)
        print("\n크롤링 완료!")
        return True
    except Exception as e:
        print(f"크롤링 실행 오류: {e}")
        import traceback
        traceback.print_exc()
        return False

try:
    # Chrome 옵션 설정
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--lang=ko_KR")
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Chrome driver 초기화
    dr = webdriver.Chrome(options=options)
    dr.implicitly_wait(5)
    
    # 사이트 접속
    print("사이트 접속 중...")
    dr.get('https://mportal2.cau.ac.kr/main.do')
    time.sleep(3)
    
    # 크롤링 실행
    if runCrawler():
        # Firestore 업데이트
        try:
            print("\nFirestore 업데이트 중...")
            db = firestore.Client()
            doc_ref = db.collection(u'CAU_Haksik').document('CAU_Cafeteria_Menu')
            
            with open(os.path.join(BASE_DIR, './Doc/CAUMealData.json'), 'r', encoding='utf-8') as f:
                cafeteria_data_dic = json.load(f)
            
            doc_ref.set(cafeteria_data_dic)
            print("Firestore 업데이트 완료!")
            
        except Exception as e:
            print(f"Firestore 업데이트 오류: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("크롤링 실패")

except Exception as e:
    print(f"프로그램 실행 오류: {e}")
    import traceback
    traceback.print_exc()

finally:
    try:
        dr.quit()
    except:
        pass
    
    print("\n최신화 완료")
    processTime = time.time() - start
    minute = processTime / 60
    second = processTime % 60
    print(f"실행 시간: {math.trunc(minute)}분 {round(second)}초")
