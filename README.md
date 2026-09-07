# nyam_nyam_crawler
오늘 먹을 메뉴를 고민하고 있는 학우들을 위해 만들었습니다.

## API crawler

The current portal reads `POST https://mportal2.cau.ac.kr/portlet/p005/p005.ajax`
with a **JSON body**, not form-encoded fields:

```json
{"tabs":"1","tabs2":"20","daily":0}
```

- `tabs`: `1` Seoul, `2` Da Vinci.
- `tabs2`: `10` breakfast, `20` lunch, `40` dinner.
- `daily`: offset from today's date in Asia/Seoul.

The crawler makes 42 read requests for two campuses, seven days, and three
mealtimes. It no longer loads the portal page or requires Chrome/Selenium.
HTTP errors, HTML error pages, malformed payloads, mismatched dates/campuses,
and conflicting duplicate courses fail the run before replacing saved data.
Explicit null/unpublished menus are skipped; a wholly empty crawl cannot publish.

```bash
python -m pip install -r Crawler/Doc/requirements.txt
python -m unittest discover -s Crawler -v
python Crawler/main.py --no-upload --output Crawler/Doc/CAUMealData.api.json
```

The DTO remains compatible with the shipped iOS DataManager:

```json
{
  "0": {
    "2026.09.07": {
      "1": {
        "참슬기식당(310관 B4층)": {
          "중식(한식)": {
            "time": "11:00~13:30",
            "price": "4,500 원",
            "menu": "고구마치즈돈까스|야채샐러드|과즙음료|단무지"
          }
        }
      }
    }
  }
}
```

Top-level `0`/`1` are the app's campus identifiers. Mealtime keys `0`/`1`/`2`
mean breakfast/lunch/dinner. All leaf fields are strings. Preserve current
`(다빈치)` cafeteria names for the app's enum mapping.

GitHub Actions first tests and crawls without publishing, then retains the DTO
as `CAUMealData-DTO`. `ValidateCrawler.yml` runs on PRs with read-only permissions,
without Firebase secrets or any publishing steps.
Scheduled/develop push runs in `RunCrawler.yml` publish to Firestore and verify
the document by reading it back. Manual runs default to validation only;
`publish=true` publishes only on `develop`.

The production workflow is temporarily disabled while the direct deployment is
reverted on `develop`. Re-enable it **only after this full API fix PR is merged**;
see [incident analysis and activation steps](docs/crawler-api-incident.md).

`Crawler/tests/SwiftDTOCheck.swift` is a local integration check: compile it with
the iOS app's DataManager, Meal, MealsForDay, Campus, String+, and Date+ source
files, then pass the generated JSON path. It uses the real parser and checks
that all menus survive conversion and populate the current weekly UI data.
