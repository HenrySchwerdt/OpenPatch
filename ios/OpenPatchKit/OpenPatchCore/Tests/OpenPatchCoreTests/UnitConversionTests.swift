import XCTest
@testable import OpenPatchCore

final class UnitConversionTests: XCTestCase {
    private let cal = DriveCalibration.zwbpd006006_5_1

    func test_unitsPerStep_matchesDesignParameter() {
        // spec/design-parameters.md section 4: Rev A 5:1 gear = 0.261 ul = 0.0261 U per step (NOT the old 0.0131)
        XCTAssertEqual(cal.unitsPerStep, 0.0261, accuracy: 1e-12)
        XCTAssertEqual(cal.microUnitsPerStep, 26_100)
        XCTAssertEqual(DriveCalibration.faulhaber_16_1.unitsPerStep, 0.008156, accuracy: 1e-12)
        XCTAssertEqual(1 / DriveCalibration.faulhaber_16_1.unitsPerStep, 122.6, accuracy: 0.1)
    }

    func test_stepsForUnits_roundsToNearestStep() {
        XCTAssertEqual(UnitConversion.steps(forUnits: 0.05, calibration: cal), 2)    // 1.92 -> 2
        XCTAssertEqual(UnitConversion.steps(forUnits: 1.0, calibration: cal), 38)    // 38.31 -> 38
        XCTAssertEqual(UnitConversion.steps(forUnits: 0, calibration: cal), 0)
        XCTAssertEqual(UnitConversion.steps(forUnits: 1.0, calibration: .faulhaber_16_1), 123)  // 122.6
    }

    func test_unitsForSteps_isLinear() {
        XCTAssertEqual(UnitConversion.units(forSteps: 100, calibration: cal), 2.61, accuracy: 1e-9)
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
        var accumulator = StepAccumulator(calibration: cal)
        var totalSteps = 0
        for _ in 0..<100 { totalSteps += accumulator.steps(forUnits: 0.05) }   // 5.0 U requested
        let delivered = UnitConversion.units(forSteps: totalSteps, calibration: cal)
        XCTAssertEqual(delivered, 5.0, accuracy: cal.unitsPerStep)
        // naive 2 steps per pulse would over-deliver by ~4.4 %
        XCTAssertGreaterThan(UnitConversion.units(forSteps: 200, calibration: cal), 5.2)
    }

    func test_podSize_strokeAgreesWithStepResolution() {
        // spec/design-parameters.md §3/§4: stroke / 3.5 µm must match capacity / 0.0261 within 1 % (5:1 drive)
        XCTAssertEqual(cal.micrometresPerStep, 3.5, accuracy: 1e-9)
        for size in PodSize.allCases {
            let strokeSteps = size.strokeMillimetres / cal.micrometresPerStep * 1000
            let capacitySteps = Double(UnitConversion.steps(forUnits: size.capacityUnits, calibration: cal))
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
