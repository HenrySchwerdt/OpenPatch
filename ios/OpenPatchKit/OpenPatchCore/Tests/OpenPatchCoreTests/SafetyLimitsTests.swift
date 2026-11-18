import XCTest
@testable import OpenPatchCore

final class SafetyLimitsTests: XCTestCase {
    func test_defaults_matchSpecSection7() {
        let limits = SafetyLimits()
        XCTAssertEqual(limits.maxBolus, 10)
        XCTAssertEqual(limits.maxBasalRate, 5)
        XCTAssertEqual(limits.maxHourlyDelivery, 15)
        XCTAssertEqual(limits.bolusUnitsPerMinute, 1.5)
        XCTAssertEqual(limits.occlusionThresholdUnits, 2)
        XCTAssertEqual(limits.commLossTempBasalLimit, 30 * 60)
    }

    func test_configurableLimits_areClampedToHardCaps() {
        let limits = SafetyLimits(maxBolus: 100, maxBasalRate: 100)
        XCTAssertEqual(limits.maxBolus, 25)
        XCTAssertEqual(limits.maxBasalRate, 30)
        XCTAssertEqual(SafetyLimits(maxBolus: -1, maxBasalRate: -1).maxBolus, 0)
    }

    func test_validateBolus() {
        let limits = SafetyLimits()
        XCTAssertNoThrow(try limits.validateBolus(units: 10))
        XCTAssertThrowsError(try limits.validateBolus(units: 10.05)) { XCTAssertEqual($0 as? LimitError, .bolusTooLarge) }
        XCTAssertThrowsError(try limits.validateBolus(units: 0)) { XCTAssertEqual($0 as? LimitError, .notPositive) }
    }

    func test_validateTempBasal() {
        let limits = SafetyLimits()
        XCTAssertNoThrow(try limits.validateTempBasal(unitsPerHour: 5, duration: 1800))
        XCTAssertNoThrow(try limits.validateTempBasal(unitsPerHour: 0, duration: 1800))
        XCTAssertThrowsError(try limits.validateTempBasal(unitsPerHour: 5.05, duration: 1800)) { XCTAssertEqual($0 as? LimitError, .basalRateTooHigh) }
        XCTAssertThrowsError(try limits.validateTempBasal(unitsPerHour: 1, duration: 13 * 3600)) { XCTAssertEqual($0 as? LimitError, .invalidDuration) }
        XCTAssertThrowsError(try limits.validateTempBasal(unitsPerHour: -1, duration: 1800)) { XCTAssertEqual($0 as? LimitError, .notPositive) }
    }

    func test_validateHourly() {
        let limits = SafetyLimits()
        XCTAssertNoThrow(try limits.validateHourly(requested: 5, alreadyDelivered: 10))
        XCTAssertThrowsError(try limits.validateHourly(requested: 5.05, alreadyDelivered: 10)) { XCTAssertEqual($0 as? LimitError, .hourlyLimit) }
    }
}
