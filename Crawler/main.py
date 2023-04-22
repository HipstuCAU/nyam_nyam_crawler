from selenium import webdriver
from selenium.webdriver.common.by import By
import time
import math
import json
from google.cloud import firestore
import os
os.environ["GOOGLE_APPLICATION_CREDENTIALS"]='./Doc/hasikServiceAccountKey.json'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 시작 시간
start = time.time()

def jsonParser(data):
    with open(os.path.join(BASE_DIR, './Doc/CAUMealData.json'), 'w+', encoding='utf-8') as f :
        json.dump(data, f, ensure_ascii=False, indent='\t')



# 식당 메뉴 정보 가져오는 함수
def getMealInfo(mealSchedule) :
    menuInfoDict = {}
    for cafeteriaIndex in range(1, 10) :
        menuCount = 0
        try :
            cafeteriaName = dr.find_element(By.CSS_SELECTOR, '#carteP005 > li > dl:nth-child('+ str(cafeteriaIndex) +') > dt').text
            menuInfoDict[cafeteriaName] = {}
            if cafeteriaIndex != 1 :
                getcafeteria = dr.find_element(By.CSS_SELECTOR, '#carteP005 > li > dl:nth-child('+ str(cafeteriaIndex) +') > dt > a')
                getcafeteria.click()
                time.sleep(0.5)
            for cafeteriaInfoIndex in range(2, 30) :
                menuCount += 1
                try :
                    getcafeteriaInfo = dr.find_element(By.CSS_SELECTOR, '#carteP005 > li > dl:nth-child('+ str(cafeteriaIndex) +') > dd:nth-child('+ str(cafeteriaInfoIndex) +')')
                    MenuType = dr.find_element(By.CSS_SELECTOR, '#carteP005 > li > dl:nth-child('+ str(cafeteriaIndex) +') > dd:nth-child('+ str(cafeteriaInfoIndex) +') > label > ul > li:nth-child(2) > span').text
                    menuInfoDict[cafeteriaName][MenuType] = {}
                    getMealPrice = dr.find_element(By.CSS_SELECTOR, '#carteP005 > li > dl:nth-child('+ str(cafeteriaIndex) +') > dd:nth-child('+ str(cafeteriaInfoIndex) +') > label > ul > li:nth-child(3) > span')
                    menuInfoDict[cafeteriaName][MenuType]['price'] = getMealPrice.text
                    getcafeteriaInfo.click()
                    time.sleep(0.5)
                    getMealTime = dr.find_element(By.CSS_SELECTOR, '#carteP005 > li > dl:nth-child('+ str(cafeteriaIndex) +') > dd:nth-child('+ str(cafeteriaInfoIndex) +') > label > div > div.nb-p-04-02 > div.nb-p-04-02-01.nb-font-12 > p.nb-p-04-02-01-b')
                    getMealInfo = dr.find_element(By.CSS_SELECTOR, '#carteP005 > li > dl:nth-child('+ str(cafeteriaIndex) +') > dd:nth-child('+ str(cafeteriaInfoIndex) +') > label > div > div.nb-p-04-03.nb-font-13.nb-p-flex.nb-wrap.ng-binding')
                    menuInfoDict[cafeteriaName][MenuType]['time'] = getMealTime.text
                    mealInfo = getMealInfo.text
                    mealInfo = mealInfo.replace('<일품>', '')
                    mealInfo = mealInfo.replace('특)', '')
                    menuInfoDict[cafeteriaName][MenuType]['menu'] = mealInfo.replace('\n', '|')
                except :
                    pass
                if cafeteriaName != "학생식당(303관B1층)" and menuCount == 5 : break
        except :
            pass
    return menuInfoDict

# 데일리 메뉴 정보 가져오는 함수
def getDayOfMeal() :
    dailyMenuInfoDict = {}
    for mealSchedule in range(1, 2) :
        getMealSchedule = dr.find_element(By.CSS_SELECTOR, '#P005 > div > div > div > div > ol > li > header > div.nb-right.nb-t-right > ol > li:nth-child('+ str(mealSchedule) +')')
        dailyMenuInfoDict[mealSchedule-1] = {}
        getMealSchedule.click()
        time.sleep(0.5)
        dailyMenuInfoDict[mealSchedule-1] = getMealInfo(mealSchedule)
    return dailyMenuInfoDict

# 위클리 메뉴 정보 가져오는 함수
def getWeekOfMeal() :
    weeklyMenuDict = {}
    weeklyIndex = 1
    for campus in range(1, 2):
        weeklyMenuDict[campus-1] = {}
        for day in range(weeklyIndex) :
            getCampus = dr.find_element(By.CSS_SELECTOR, '#P005 > div > div > div > div > header > div > ol > li:nth-child(' + str(campus) + ') > span')
            getCampus.click()
            time.sleep(0.5)
            getDay = dr.find_element(By.CSS_SELECTOR, '#P005 > div > div > div > div > ol > li > header > div.nb-left > div > p')
            weeklyMenuDict[campus-1][getDay.text] = getDayOfMeal()
            time.sleep(0.3)
            setNextDay = dr.find_element(By.CSS_SELECTOR, '#P005 > div > div > div > div > ol > li > header > div.nb-left > div > a.nb-p-time-select-next').click()
            setNextDay
        for day in range(weeklyIndex):
            setPrevDay = dr.find_element(By.CSS_SELECTOR, '#P005 > div > div > div > div > ol > li > header > div.nb-left > div > a.nb-p-time-select-prev').click()
            setPrevDay
    return weeklyMenuDict

def runCrawler():
    jsonParser(getWeekOfMeal())
    print("크롤링 완료")

try :
    options = webdriver.ChromeOptions()
    options.add_argument("start-maximized")
    options.add_argument("lang=ko_KR")
    options.add_argument('headless')
    options.add_argument("--no-sandbox")

    # chrome driver
    dr = webdriver.Chrome('chromedriver', chrome_options=options)
    dr.implicitly_wait(3)    
    dr.get('https://mportal.cau.ac.kr/main.do')

    #run Crawler
    runCrawler()

    #Set FireStore
    db = firestore.Client()
    doc_ref = db.collection(u'CAU_Haksik').document('Test_Doc')

    try:
        with open(os.path.join(BASE_DIR, './Doc/CAUMealData.json'), 'r') as f:
            cafeteria_data_dic = json.load(f)
        doc_ref.set(cafeteria_data_dic)
    except Exception as e:
        print("예외 발생 : ", e)
        runCrawler()

except Exception as e:
    print(e)
    dr.quit()

finally:
    print("최신화 완료")
    processTime = time.time() - start
    minute = processTime / 60
    second = processTime % 60
    print("실행 시간 :", math.trunc(minute), "분 ", round(second), "초")
    dr.quit()