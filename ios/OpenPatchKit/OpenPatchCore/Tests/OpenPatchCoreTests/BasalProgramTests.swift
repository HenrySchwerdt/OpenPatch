import XCTest
@testable import OpenPatchCore

final class BasalProgramTests: XCTestCase {
    func test_rateLookup_acrossSegments() throws {
        let program = try BasalProgram(segments: [
            BasalSegment(startOffset: 0, unitsPerHour: 0.8),
            BasalSegment(startOffset: 6 * 3600, unitsPerHour: 1.25),
            BasalSegment(startOffset: 22 * 3600 + 1800, unitsPerHour: 0.5)
        ])
        XCTAssertEqual(program.unitsPerHour(atOffset: 0), 0.8, accuracy: 1e-9)
        XCTAssertEqual(program.unitsPerHour(atOffset: 6 * 3600 - 1), 0.8, accuracy: 1e-9)
        XCTAssertEqual(program.unitsPerHour(atOffset: 6 * 3600), 1.25, accuracy: 1e-9)
        XCTAssertEqual(program.unitsPerHour(atOffset: 23 * 3600), 0.5, accuracy: 1e-9)
        XCTAssertEqual(program.unitsPerHour(atOffset: 86_400 + 7 * 3600), 1.25, accuracy: 1e-9, "wraps past midnight")
    }

    func test_ratesAreRoundedDownToGrid() throws {
        let program = try BasalProgram(segments: [BasalSegment(startOffset: 0, unitsPerHour: 0.874)])
        XCTAssertEqual(program.unitsPerHour(atOffset: 0), 0.85, accuracy: 1e-9)
    }

    func test_dailyTotal() throws {
        let program = try BasalProgram(segments: [BasalSegment(startOffset: 0, unitsPerHour: 1.0)])
        XCTAssertEqual(program.dailyTotal, 24, accuracy: 1e-9)
        let split = try BasalProgram(segments: [BasalSegment(startOffset: 0, unitsPerHour: 1.0),
                                                BasalSegment(startOffset: 12 * 3600, unitsPerHour: 2.0)])
        XCTAssertEqual(split.dailyTotal, 36, accuracy: 1e-9)
    }

    func test_unitsDelivered_overInterval_includingMidnightWrap() throws {
        let program = try BasalProgram(segments: [BasalSegment(startOffset: 0, unitsPerHour: 1.0),
                                                  BasalSegment(startOffset: 12 * 3600, unitsPerHour: 2.0)])
        XCTAssertEqual(program.unitsDelivered(fromOffset: 11 * 3600, duration: 2 * 3600), 3.0, accuracy: 1e-9)
        XCTAssertEqual(program.unitsDelivered(fromOffset: 23 * 3600, duration: 2 * 3600), 3.0, accuracy: 1e-9)
    }

    func test_invalidSegments_throw() {
        XCTAssertThrowsError(try BasalProgram(segments: [])) { XCTAssertEqual($0 as? BasalProgramError, .empty) }
        XCTAssertThrowsError(try BasalProgram(segments: [BasalSegment(startOffset: 1800, unitsPerHour: 1)])) {
            XCTAssertEqual($0 as? BasalProgramError, .firstSegmentMustStartAtMidnight)
        }
        XCTAssertThrowsError(try BasalProgram(segments: [BasalSegment(startOffset: 0, unitsPerHour: 1), BasalSegment(startOffset: 900, unitsPerHour: 1)])) {
            XCTAssertEqual($0 as? BasalProgramError, .misaligned)
        }
        XCTAssertThrowsError(try BasalProgram(segments: [BasalSegment(startOffset: 0, unitsPerHour: 1), BasalSegment(startOffset: 3600, unitsPerHour: 1), BasalSegment(startOffset: 3600, unitsPerHour: 1)])) {
            XCTAssertEqual($0 as? BasalProgramError, .notAscending)
        }
        XCTAssertThrowsError(try BasalProgram(segments: [BasalSegment(startOffset: 0, unitsPerHour: 5.5)])) {
            XCTAssertEqual($0 as? BasalProgramError, .rateTooHigh)
        }
        XCTAssertNoThrow(try BasalProgram(segments: [BasalSegment(startOffset: 0, unitsPerHour: 5.5)], limits: SafetyLimits(maxBolus: 10, maxBasalRate: 8)))
    }

    func test_slotsInitializerValidatesCount() {
        XCTAssertThrowsError(try BasalProgram(slots: [1, 2, 3]))
        XCTAssertNoThrow(try BasalProgram(slots: Array(repeating: 20, count: 48)))
    }
}
