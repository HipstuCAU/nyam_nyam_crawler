import argparse
import json
import os
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "Doc" / "CAUMealData.json"
PORTAL_URL = "https://mportal2.cau.ac.kr/main.do"


def write_json(data):
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent="\t"), encoding="utf-8")


def text_of(element, selector):
    """Return text for both visible and collapsed Angular menu nodes."""
    try:
        return element.find_element(By.CSS_SELECTOR, selector).get_attribute("textContent").strip()
    except Exception:
        return ""


def wait_for_menu(driver):
    wait = WebDriverWait(driver, 20)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#convTab .nb-p-tab")))
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#convTab #carteP005")))
    wait.until(lambda browser: len(browser.find_elements(By.CSS_SELECTOR, "#convTab .nb-p-tab > li")) >= 2)
    return wait


def active_date(driver):
    return driver.find_element(
        By.CSS_SELECTOR, "#convTab .nb-p-tab-sections > li.on .nb-p-time-select-current"
    ).text.strip()


def collect_active_meal(driver):
    """Collect every restaurant in the selected campus/date/meal tab."""
    restaurants = driver.find_elements(
        By.CSS_SELECTOR, "#convTab .nb-p-tab-sections > li.on #carteP005 > li.on dl.nb-p-04-list-02"
    )
    menus = {}

    for restaurant in restaurants:
        name = text_of(restaurant, "dt span") or text_of(restaurant, "dt")
        if not name:
            continue

        courses = {}
        for row in restaurant.find_elements(By.CSS_SELECTOR, "dd"):
            course = text_of(row, 'span[ng-bind="row.course"]') or "기타"
            menu = "|".join(
                item.get_attribute("textContent").strip()
                for item in row.find_elements(By.CSS_SELECTOR, "div.nb-p-04-03 p")
                if item.get_attribute("textContent").strip()
            )
            if not menu:
                menu = text_of(row, "div.nb-p-04-03")
            price = text_of(row, 'span[ng-bind="row.price"]')
            serving_time = text_of(row, 'span[ng-bind="row.time"]')
            if menu or price or serving_time:
                courses[course] = {"time": serving_time, "price": price, "menu": menu}

        if courses:
            menus[name] = courses

    return menus


def collect_day(driver, wait):
    result = {}
    meal_tabs = driver.find_elements(By.CSS_SELECTOR, "#convTab .nb-p-04-list > li")
    if len(meal_tabs) != 3:
        raise RuntimeError(f"expected 3 meal tabs, found {len(meal_tabs)}")

    for meal_index in range(3):
        tabs = driver.find_elements(By.CSS_SELECTOR, "#convTab .nb-p-04-list > li")
        driver.execute_script("arguments[0].click();", tabs[meal_index])
        wait.until(lambda browser: "on" in browser.find_elements(
            By.CSS_SELECTOR, "#convTab .nb-p-04-list > li"
        )[meal_index].get_attribute("class"))
        wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR, "#convTab .nb-p-tab-sections > li.on #carteP005"
        )))
        result[str(meal_index)] = collect_active_meal(driver)
    return result


def collect_week(driver):
    wait = wait_for_menu(driver)
    result = {}
    campus_count = len(driver.find_elements(By.CSS_SELECTOR, "#convTab .nb-p-tab > li"))
    if campus_count != 2:
        raise RuntimeError(f"expected 2 campus tabs, found {campus_count}")

    for campus_index in range(campus_count):
        campus_tabs = driver.find_elements(By.CSS_SELECTOR, "#convTab .nb-p-tab > li")
        driver.execute_script("arguments[0].click();", campus_tabs[campus_index])
        wait.until(lambda browser: "on" in browser.find_elements(
            By.CSS_SELECTOR, "#convTab .nb-p-tab > li"
        )[campus_index].get_attribute("class"))

        campus_data = {}
        for day_index in range(7):
            date = active_date(driver)
            campus_data[date] = collect_day(driver, wait)
            if day_index < 6:
                previous_date = date
                next_button = driver.find_element(
                    By.CSS_SELECTOR, "#convTab .nb-p-tab-sections > li.on .nb-p-time-select-next"
                )
                driver.execute_script("arguments[0].click();", next_button)
                wait.until(lambda browser: active_date(browser) != previous_date)

        for _ in range(6):
            previous_button = driver.find_element(
                By.CSS_SELECTOR, "#convTab .nb-p-tab-sections > li.on .nb-p-time-select-prev"
            )
            driver.execute_script("arguments[0].click();", previous_button)

        result[str(campus_index)] = campus_data
    return result


def menu_count(data):
    return sum(
        len(courses)
        for campus in data.values()
        for day in campus.values()
        for meal in day.values()
        for courses in meal.values()
    )


def upload_to_firestore(data):
    from google.cloud import firestore

    credential_path = BASE_DIR / "firebaseServiceAccountKey.json"
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(credential_path)
    firestore.Client().collection("CAU_Haksik").document("CAU_Cafeteria_Menu").set(data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-upload", action="store_true", help="crawl and validate without writing Firestore")
    args = parser.parse_args()

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=ko-KR")

    with webdriver.Chrome(options=options) as driver:
        driver.get(PORTAL_URL)
        data = collect_week(driver)

    count = menu_count(data)
    if count == 0:
        raise RuntimeError("crawler collected zero menu entries; refusing to overwrite Firestore")

    write_json(data)
    print(f"Crawled {count} menu entries.")
    if not args.no_upload:
        upload_to_firestore(data)
        print("Firestore updated.")


if __name__ == "__main__":
    started_at = time.monotonic()
    try:
        main()
    finally:
        print(f"Elapsed: {time.monotonic() - started_at:.1f}s")
