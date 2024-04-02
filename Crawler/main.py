from selenium import webdriver
from selenium.webdriver.common.by import By
import time
import math
import json
from google.cloud import firestore
import os
os.environ["GOOGLE_APPLICATION_CREDENTIALS"]="./Doc/firebaseServiceAccountKey.json"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# - Setup Start Time
start = time.time()

old_data = []
new_data = []

def jsonParser(data):
    with open(os.path.join(BASE_DIR, './Doc/CAUMealDataTest.json'), 'w+', encoding='utf-8') as f :
        json.dump(data, f, ensure_ascii=False, indent='\t')

# - Get Cafeteria Menu at Meal Schedule
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
                    mealInfo = mealInfo.split('\n')

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

# - Get Daily Menu
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

# - Get Weekly Menu
def getWeekOfMeal():
    weeklyMenuList = []
    weeklyIndex = 7     # - Set Crawer Day
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
    old_data = getWeekOfMeal()
    #print(old_data)
    jsonParser(old_data)
    print("크롤링 완료")

def parse_menu_data(results):
    parsed_data = []
    meal_type_mapping = {
        "breakfast": "아침",
        "lunch": "점심",
        "dinner": "저녁"
    }
    cafeteria_id_mapping = {
        "학생식당(303관B1층)": "K001001001",
        "참슬기식당(310관 B4층)": "K001001002",
        "생활관식당(블루미르308관)":"K001001003",
        "생활관식당(블루미르309관)":"K001001004",
        "University Club(102관11층)":"K001001005",
        "카우잇츠(cau eats)":"K001002006",
        "(안성)카우버거":"K001002007",
        "(안성)라면":"K001002008"
    }
    for result in results['results']:
        campus = result["campus"]
        for menu_data in result["menuData"]:
            date = menu_data["date"]
            cafeterias = {}
            for meal_type in ["breakfast", "lunch", "dinner"]:
                if meal_type in menu_data:
                    for cafeteria in menu_data[meal_type]:
                        cafeteria_id = cafeteria_id_mapping[cafeteria["name"]]
                        meal_info_dict = {}
                        for meal in cafeteria["menu"]:
                            meal_type_str = meal_type_mapping[meal_type]
                            if meal_type_str not in meal_info_dict:
                                meal_info_dict[meal_type_str] = {
                                    "mealType": meal_type_str,
                                    "shouldShowTime": True,
                                    "startTime": meal["startTime"],
                                    "endTime": meal["endTime"],
                                    "menus": []
                                }
                            meal_info_dict[meal_type_str]["menus"].append({
                                "menuType": "",
                                "price": meal["price"],
                                "startTime": meal["startTime"],
                                "endTime": meal["endTime"],
                                "menu": meal["menu"],
                                "calories": ""
                            })
                        if cafeteria_id in cafeterias:
                            for meal_type_str, meals in meal_info_dict.items():
                                cafeterias[cafeteria_id]["meals"].append(meals)
                        else:
                            cafeterias[cafeteria_id] = {
                                "cafeteriaID": cafeteria_id,
                                "meals": list(meal_info_dict.values())
                            }
            parsed_data.append({
                "date": date,
                "cafeterias": list(cafeterias.values())
            })
    return {"results": parsed_data}


try :
    options = webdriver.ChromeOptions()
    options.add_argument("start-maximized")
    options.add_argument("lang=ko_KR")
    options.add_argument('headless')
    options.add_argument("--no-sandbox")

    # - Run Chrome Driver
    dr = webdriver.Chrome('chromedriver', chrome_options=options)
    dr.implicitly_wait(3)    
    dr.get('https://mportal.cau.ac.kr/main.do')

    # - Run Crawler
    runCrawler()

    # - Change Data
    try:
        with open(os.path.join(BASE_DIR, './Doc/CAUMealDataTest.json'), 'r') as f:
            old_data = json.load(f)
    except Exception as e:
        print("예외 발생 : ", e)
    new_data = parse_menu_data(old_data)
    if new_data != []:
        jsonParser(new_data)

    # - Setup FireStore
    db = firestore.Client()
    
    doc_ref = db.collection(u'CAU_Haksik').document('Test_Doc') # - TEST Server
    #doc_ref = db.collection(u'CAU_Haksik').document('CAU_Cafeteria_Menu') # - Main Server

    try:
        with open(os.path.join(BASE_DIR, './Doc/CAUMealDataTest.json'), 'r') as f:
            cafeteria_data_dic = json.load(f)
        doc_ref.set(cafeteria_data_dic)
    except Exception as e:
        print("예외 발생 : ", e)
        #runCrawler()

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
