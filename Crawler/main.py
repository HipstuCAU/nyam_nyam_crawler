from selenium import webdriver
from selenium.webdriver.common.by import By
import time
import math
import json
from google.cloud import firestore
import os
os.environ["GOOGLE_APPLICATION_CREDENTIALS"]="./Doc/firebaseServiceAccountKey.json"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 시작 시간
start = time.time()

def jsonParser(data):
    with open(os.path.join(BASE_DIR, './Doc/CAUMealData.json'), 'w+', encoding='utf-8') as f :
        json.dump(data, f, ensure_ascii=False, indent='\t')



# 식당 메뉴 정보 가져오는 함수
def getMealInfo(mealSchedule):
    menuInfoList = []
    for cafeteriaIndex in range(1, 10):
        menuCount = 0
        try:
            cafeteriaName = dr.find_element(By.CSS_SELECTOR, f'#carteP005 > li > dl:nth-child({cafeteriaIndex}) > dt').text
            cafeteriaName = cafeteriaName.replace('다빈치', '안성')

            if cafeteriaIndex != 1:
                getcafeteria = dr.find_element(By.CSS_SELECTOR, f'#carteP005 > li > dl:nth-child({cafeteriaIndex}) > dt > a')
                getcafeteria.click()
                time.sleep(0.5)

            cafeteriaInfo = {'name': cafeteriaName, 'menu': []}

            for cafeteriaInfoIndex in range(2, 30):
                menuCount += 1
                try:
                    getcafeteriaInfo = dr.find_element(By.CSS_SELECTOR, f'#carteP005 > li > dl:nth-child({cafeteriaIndex}) > dd:nth-child({cafeteriaInfoIndex})')
                    MenuType = dr.find_element(By.CSS_SELECTOR, f'#carteP005 > li > dl:nth-child({cafeteriaIndex}) > dd:nth-child({cafeteriaInfoIndex}) > label > ul > li:nth-child(2) > span').text

                    getMealPrice = dr.find_element(By.CSS_SELECTOR, f'#carteP005 > li > dl:nth-child({cafeteriaIndex}) > dd:nth-child({cafeteriaInfoIndex}) > label > ul > li:nth-child(3) > span')
                    price = getMealPrice.text.replace(',', '')
                    price = price.replace(' 원', '')

                    getcafeteriaInfo.click()
                    time.sleep(0.5)
                    getMealTime = dr.find_element(By.CSS_SELECTOR, f'#carteP005 > li > dl:nth-child({cafeteriaIndex}) > dd:nth-child({cafeteriaInfoIndex}) > label > div > div.nb-p-04-02 > div.nb-p-04-02-01.nb-font-12 > p.nb-p-04-02-01-b')
                    getMealInfo = dr.find_element(By.CSS_SELECTOR, f'#carteP005 > li > dl:nth-child({cafeteriaIndex}) > dd:nth-child({cafeteriaInfoIndex}) > label > div > div.nb-p-04-03.nb-font-13.nb-p-flex.nb-wrap.ng-binding')
                    start_time, end_time = getMealTime.text.split("~")
                    mealInfo = getMealInfo.text
                    mealInfo = mealInfo.replace('<일품>', '')
                    mealInfo = mealInfo.replace('특)', '')
                    mealInfo = mealInfo.replace('(중식만가능)', '')
                    print(mealInfo)
                    mealInfo = mealInfo.split('\n')

                    print(mealInfo)
                    menu_item = {'price': price, 'startTime': start_time, 'endTime': end_time, 'menu': mealInfo}
                    cafeteriaInfo['menu'].append(menu_item)
                except:
                    pass

                if cafeteriaName != "학생식당(303관B1층)" and menuCount == 5:
                    break

            menuInfoList.append(cafeteriaInfo)

        except:
            pass

    return menuInfoList

# 데일리 메뉴 정보 가져오는 함수
def getDayOfMeal():
    dailyMenuInfoDict = {}

    for mealSchedule in range(1, 4):
        getMealSchedule = dr.find_element(By.CSS_SELECTOR, f'#P005 > div > div > div > div > ol > li > header > div.nb-right.nb-t-right > ol > li:nth-child({mealSchedule})')
        meal_time = ["breakfast", "lunch", "dinner"][mealSchedule - 1]
        dailyMenuInfoDict[meal_time] = []

        getMealSchedule.click()
        time.sleep(0.5)
        cafeterias_info = getMealInfo(mealSchedule)
        dailyMenuInfoDict[meal_time] = cafeterias_info

    return dailyMenuInfoDict



# 위클리 메뉴 정보 가져오는 함수
def getWeekOfMeal():
    weeklyMenuList = []
    #날짜 설정 ( 5일 기본 )
    weeklyIndex = 3
    campusName = ["seoul", "davinci"]
    for campus in range(1, 3) :
        weeklyMenuDict = {'campus': campusName[campus - 1], 'menuData': []}
        for dayIndex in range(weeklyIndex):
            getCampus = dr.find_element(By.CSS_SELECTOR, '#P005 > div > div > div > div > header > div > ol > li:nth-child(' + str(campus) + ') > span')
            getCampus.click()
            time.sleep(0.5)
            getDay = dr.find_element(By.CSS_SELECTOR, '#P005 > div > div > div > div > ol > li > header > div.nb-left > div > p')
            day_info = {'date': getDay.text}
            day_info.update(getDayOfMeal())
            weeklyMenuDict['menuData'].append(day_info)
            time.sleep(0.3)
            setNextDay = dr.find_element(By.CSS_SELECTOR, '#P005 > div > div > div > div > ol > li > header > div.nb-left > div > a.nb-p-time-select-next').click()
        for _ in range(weeklyIndex):
            setPrevDay = dr.find_element(By.CSS_SELECTOR, '#P005 > div > div > div > div > ol > li > header > div.nb-left > div > a.nb-p-time-select-prev').click()

        weeklyMenuList.append(weeklyMenuDict)

    return {'results': weeklyMenuList}



def runCrawler():
    test = getWeekOfMeal()
    print(test)
    jsonParser(test)
    print("크롤링 완료")

try :
    options = webdriver.ChromeOptions()
    options.add_argument("start-maximized")
    options.add_argument("lang=ko_KR")
    #options.add_argument('headless')
    options.add_argument("--no-sandbox")

    # chrome driver
    #dr = webdriver.Chrome('chromedriver', chrome_options=options)
    #dr.implicitly_wait(3)    
    #dr.get('https://mportal.cau.ac.kr/main.do')

    #run Crawler
    #runCrawler()

    #Set FireStore

    db = firestore.Client()
    
    #Test Document

    doc_ref = db.collection(u'CAU_Haksik').document('Test_Doc')
    #doc_ref = db.collection(u'CAU_Haksik').document('CAU_Cafeteria_Menu')

    try:
        with open(os.path.join(BASE_DIR, './Doc/CAUMealData.json'), 'r') as f:
            cafeteria_data_dic = json.load(f)
        doc_ref.set(cafeteria_data_dic)
    except Exception as e:
        print("예외 발생 : ", e)
        runCrawler()

except Exception as e:
    print(e)
    #dr.quit()

finally:
    print("최신화 완료")
    processTime = time.time() - start
    minute = processTime / 60
    second = processTime % 60
    print("실행 시간 :", math.trunc(minute), "분 ", round(second), "초")
    #dr.quit()
