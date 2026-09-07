// Compile together with the application's real DataManager and model sources.
import Foundation

final class JsonManager {
    static let shared = JsonManager()
    func jsonToString() -> String? {
        try? String(contentsOfFile: CommandLine.arguments[1], encoding: .utf8)
    }
}

@main
struct SwiftDTOCheck {
    static func main() throws {
        let data = try Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1]))
        typealias Menu = [String: String]
        typealias DTO = [String: [String: [String: [String: [String: Menu]]]]]
        let dto = try JSONDecoder().decode(DTO.self, from: data)
        var total = 0
        for campus in ["0", "1"] {
            let expected = dto[campus]!.values.reduce(0) { dayCount, day in
                dayCount + day.values.reduce(0) { mealCount, meal in
                    mealCount + meal.values.reduce(0) { $0 + $1.count }
                }
            }
            let meals = DataManager.getMealsForDay(campus)
            precondition(meals.count == expected, "DTO entries lost during app parsing")
            precondition(meals.allSatisfy { $0.cafeteria != .none }, "Unmapped cafeteria")
            precondition(meals.allSatisfy { !$0.menu.isEmpty && $0.menu != [""] })
            precondition(meals.allSatisfy { !$0.price.isEmpty })
            let weeks = DataManager.getMealsForWeeks(campus == "0" ? .seoul : .ansung)
            precondition(!weeks.isEmpty, "No current data reaches the weekly UI collection")
            print("campus \(campus): \(meals.count) meals parsed, \(weeks.count) visible days")
            total += meals.count
        }
        print("Swift DTO check passed: \(total) meals")
    }
}
