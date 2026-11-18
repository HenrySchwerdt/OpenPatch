import XCTest
@testable import OpenPatchCore

final class UnitConversionTests: XCTestCase {
    func test_unitsPerStep_matchesDesignParameter() {
        XCTAssertEqual(PumpConstants.unitsPerStep, 0.0131, accuracy: 1e-12)
    }

    func test_stepsForUnits_roundsToNearestStep() {
        XCTAssertEqual(UnitConversion.steps(forUnits: 0.05), 4)    // 3.82 -> 4
        XCTAssertEqual(UnitConversion.steps(forUnits: 1.0), 76)    // 76.34 -> 76
        XCTAssertEqual(UnitConversion.steps(forUnits: 0), 0)
    }

    func test_unitsForSteps_isLinear() {
        XCTAssertEqual(UnitConversion.units(forSteps: 100), 1.31, accuracy: 1e-9)
    }

    func test_pulsesForUnits_floorsOnTheFiveHundredthGrid() {
        XCTAssertEqual(UnitConversion.pulses(forUnits: 0.05), 1)
        XCTAssertEqual(UnitConversion.pulses(forUnits: 0.0999), 1)
        XCTAssertEqual(UnitConversion.pulses(forUnits: 0.15), 3, "binary-float 0.15/0.05 = 2.9999… must not floor to 2")
        XCTAssertEqual(UnitConversion.pulses(forUnits: 0.04), 0)
        XCTAssertEqual(UnitConversion.pulses(forUnits: -1), 0)
    }

    func test_unitsForPulses_hasNoFloatingPointNoise() {
        XCTAssertEqual(UnitConversion.units(forPulses: 3), 0.15)
        XCTAssertEqual(UnitConversion.units(forPulses: 20), 1.0)
    }

    func test_roundDownToPulse_neverExceedsRequest() {
        for raw in stride(from: 0.0, through: 10.0, by: 0.013) {
            let rounded = UnitConversion.roundDownToPulse(raw)
            XCTAssertLessThanOrEqual(rounded, raw + 1e-9)
            XCTAssertGreaterThan(rounded, raw - 0.05 - 1e-9)
        }
    }

    func test_bolusDuration_usesOnePointFiveUnitsPerMinute() {
        XCTAssertEqual(UnitConversion.bolusDuration(forUnits: 1.5), 60, accuracy: 1e-9)
        XCTAssertEqual(UnitConversion.bolusDuration(forUnits: 3.0), 120, accuracy: 1e-9)
    }

    func test_supportedVolumes_areOnGridAndInclusive() {
        let volumes = UnitConversion.supportedVolumes(maximum: 25)
        XCTAssertEqual(volumes.first, 0.05)
        XCTAssertEqual(volumes.last, 25.0)
        XCTAssertEqual(volumes.count, 500)
    }

    func test_stepAccumulator_carriesRemainderSoSmallDosesDoNotDrift() {
        var accumulator = StepAccumulator()
        var totalSteps = 0
        for _ in 0..<100 { totalSteps += accumulator.steps(forUnits: 0.05) }   // 5.0 U requested
        let delivered = UnitConversion.units(forSteps: totalSteps)
        XCTAssertEqual(delivered, 5.0, accuracy: PumpConstants.unitsPerStep)
        // naive 4 steps per pulse would over-deliver by ~4.8 %
        XCTAssertGreaterThan(UnitConversion.units(forSteps: 400), 5.2)
    }

    func test_podSize_strokeAgreesWithStepResolution() {
        // spec/design-parameters.md §3/§4: stroke / 1.75 µm must match capacity / 0.0131 within 1 %
        for size in PodSize.allCases {
            let strokeSteps = size.strokeMillimetres / PumpConstants.micrometresPerStep * 1000
            let capacitySteps = Double(UnitConversion.steps(forUnits: size.capacityUnits))
            XCTAssertEqual(strokeSteps / capacitySteps, 1.0, accuracy: 0.01, "\(size)")
        }
    }

    func test_podSize_fillValidation() {
        XCTAssertNoThrow(try PodSize.u100.validateFill(units: 100))
        XCTAssertThrowsError(try PodSize.u100.validateFill(units: 100.05))
        XCTAssertThrowsError(try PodSize.u70.validateFill(units: 5))
        XCTAssertEqual(PodSize.allCases.map(\.capacityUnits), [70, 100, 200])
    }
}
