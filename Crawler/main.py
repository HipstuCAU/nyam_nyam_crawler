"""Collect the public CAU menu JSON API into the existing iOS/Firestore DTO."""
import argparse
from datetime import datetime, timedelta
import html
import json
import os
from pathlib import Path
import re
import time
from zoneinfo import ZoneInfo

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "Doc" / "CAUMealData.json"
API_URL = "https://mportal2.cau.ac.kr/portlet/p005/p005.ajax"
CAMPUS_CODES = {"0": "1", "1": "2"}
MEAL_CODES = {"0": "10", "1": "20", "2": "40"}
KST = ZoneInfo("Asia/Seoul")


class CrawlError(RuntimeError):
    """An incomplete or unexpected response must never replace published data."""


def make_session():
    session = requests.Session()
    # These POST requests only read menus; retry transient server failures.
    retry = Retry(total=2, backoff_factor=0.5,
                  status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=frozenset({"POST"}))
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({"Accept": "application/json"})
    return session


def fetch_rows(session, campus, meal, daily):
    params = {"tabs": campus, "tabs2": meal, "daily": daily}
    try:
        response = session.post(API_URL, json=params, timeout=(10, 30),
                                allow_redirects=False)
        response.raise_for_status()
        if response.status_code != 200:
            raise CrawlError(f"menu API returned HTTP {response.status_code}: {params}")
        # The server can return an HTML error page with status 200.
        payload = response.json()
    except (requests.RequestException, ValueError) as error:
        raise CrawlError(f"menu API request/JSON failed: {params}: {error}") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("list"), list):
        raise CrawlError(f"menu API missing list: {params}")
    if payload.get("isEmpty") not in ("Y", "N"):
        raise CrawlError(f"menu API missing valid isEmpty flag: {params}")
    # Y still includes restaurant/date placeholders with null menu fields.
    # Reject actual menu content under Y, not the presence of metadata rows.
    if payload["isEmpty"] == "Y" and any(
        isinstance(row, dict) and row.get("menuDetail") not in (None, "")
        for row in payload["list"]
    ):
        raise CrawlError(f"menu API inconsistent empty flag: {params}")
    return payload["list"]


def menu_text(value):
    # Same comma-separated dish rendering as p005Controller.getRowData.
    text = html.unescape(value)
    for marker in ("<일품>", "특)", "(중식만가능)"):
        text = text.replace(marker, "")
    return "|".join(part.strip() for part in re.split(r"[,\r\n|]+", text) if part.strip())


def convert_rows(rows, campus, meal, date):
    restaurants = {}
    for index, row in enumerate(rows):
        label = f"campus={campus} meal={meal} date={date} row={index}"
        if not isinstance(row, dict):
            raise CrawlError(f"non-object row: {label}")
        for field in ("date", "rest"):
            if not isinstance(row.get(field), str):
                raise CrawlError(f"missing/string field {field}: {label}")
        if row["date"] != date:
            raise CrawlError(f"response date mismatch: {label}")
        if "menuDetail" not in row:
            raise CrawlError(f"missing menuDetail: {label}")
        # Unpublished slots contain restaurant/date metadata with all other
        # fields null. Validate those metadata before skipping the placeholder.
        if row["menuDetail"] is None:
            continue
        if not isinstance(row["menuDetail"], str):
            raise CrawlError(f"non-string menuDetail: {label}")
        for field in ("camp", "mCd", "course", "time", "price"):
            if not isinstance(row.get(field), str):
                raise CrawlError(f"missing/string field {field}: {label}")
        if (row["camp"], row["mCd"]) != (campus, meal):
            raise CrawlError(f"response campus/meal mismatch: {label}")
        name = row["rest"].strip()
        course = row["course"].strip()
        if not name or not course:
            raise CrawlError(f"empty restaurant/course: {label}")
        # The shipped iOS client recognizes the current 다빈치 names.
        name = name.replace("(안성)", "(다빈치)")
        menu = menu_text(row["menuDetail"])
        if not menu:
            continue
        dto = {"time": row["time"].strip(), "price": row["price"].strip(), "menu": menu}
        courses = restaurants.setdefault(name, {})
        if course in courses and courses[course] != dto:
            raise CrawlError(f"conflicting duplicate course {name}/{course}: {label}")
        courses[course] = dto
    return restaurants


def menu_count(data):
    return sum(len(courses) for campus in data.values()
               for day in campus.values() for meal in day.values()
               for courses in meal.values())


def collect_week(session, days=7, start_date=None):
    if not 1 <= days <= 7:
        raise ValueError("days must be between 1 and 7")
    today = datetime.now(KST).date()
    start_date = start_date or today
    data = {campus: {} for campus in CAMPUS_CODES}
    for campus, api_campus in CAMPUS_CODES.items():
        for offset in range(days):
            date = start_date + timedelta(days=offset)
            daily = (date - today).days
            date_key = date.strftime("%Y.%m.%d")
            day = {}
            for meal, api_meal in MEAL_CODES.items():
                rows = fetch_rows(session, api_campus, api_meal, daily)
                day[meal] = convert_rows(rows, api_campus, api_meal, date_key)
                time.sleep(0.1)
            data[campus][date_key] = day
    if datetime.now(KST).date() != today:
        raise CrawlError("KST date changed while crawling; retry to avoid mixed daily offsets")
    # Empty weekend slots are valid; a wholly empty result is not publishable.
    if menu_count(data) == 0:
        raise CrawlError("zero menu entries; refusing to overwrite saved/published data")
    return data


def write_json(data, output=DATA_PATH):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replacement after the entire crawl has been validated.
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                     dir=output.parent, delete=False) as handle:
        temporary = Path(handle.name)
        json.dump(data, handle, ensure_ascii=False, indent="\t")
        handle.write("\n")
    try:
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)


def upload_to_firestore(data):
    from google.cloud import firestore
    # Respect an explicitly supplied credential, otherwise accept the workflow's
    # root-level key as well as the historical Crawler/ key location.
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        candidates = (BASE_DIR / "firebaseServiceAccountKey.json",
                      BASE_DIR.parent / "firebaseServiceAccountKey.json")
        credential = next((p for p in candidates if p.is_file()), None)
        if credential is None:
            raise CrawlError("Firebase credential file not found")
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(credential)
    firestore.Client().collection("CAU_Haksik").document("CAU_Cafeteria_Menu").set(data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-upload", action="store_true")
    parser.add_argument("--output", type=Path, default=DATA_PATH)
    parser.add_argument("--days", type=int, default=7, choices=range(1, 8))
    args = parser.parse_args(argv)
    if not args.no_upload and args.days != 7:
        parser.error("--days less than 7 requires --no-upload; refusing partial publication")
    with make_session() as session:
        data = collect_week(session, days=args.days)
    write_json(data, args.output)
    print(f"Crawled {menu_count(data)} menu entries from {len(data)} campuses.")
    print(f"DTO: {args.output.resolve()}")
    if not args.no_upload:
        upload_to_firestore(data)
        print("Firestore updated.")


if __name__ == "__main__":
    started_at = time.monotonic()
    try:
        main()
    finally:
        print(f"Elapsed: {time.monotonic() - started_at:.1f}s")
