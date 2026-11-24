import XCTest
@testable import OpenPatchCore

/// The cup pod: assisted PRESSURE fill only (the user pushes the syringe while the pod retracts its plunger), never a suction
/// draw; unknown drives are refused; the simulator behaves like the firmware where the app relies on it.
final class AssistedFillTests: XCTestCase {
    private let t0 = Date(timeIntervalSince1970: 1_800_000_000)
    private let cup = DriveCalibration.nfp608_26_45_cupMiter1_1

    private func undockedCupPod(size: PodSize = .u100) -> SimulatedPod {
        let pod = SimulatedPod(size: size, startDate: t0, calibration: cup)
        pod.setDocked(false)
        _ = pod.handle(.hello(protocolVersion: PumpConstants.protocolVersion, time: t0, utcOffsetMinutes: 0))
        return pod
    }

    private func fillStatus(_ pod: SimulatedPod) -> FillStatus { pod.status.fill! }

    // MARK: Drive presets

    func test_cupPresetIsKnown_andOnlyAssistedPressureIsAllowed() {
        XCTAssertTrue(cup.isKnown)
        XCTAssertEqual(cup.presetName, "nfp-608-26-45-cup-miter-1-1")
        XCTAssertFalse(cup.allowsSuctionDraw, "no check valve: a suction draw could pull from the cannula side")
        XCTAssertEqual(cup.allowedFillModes, [.assistedPressure])
        XCTAssertTrue(cup.supportsAssistedFill)
        XCTAssertEqual(cup.unitsPerStep, 0.00703, accuracy: 1e-8)
        XCTAssertEqual(cup.assistedFillUnitsPerSecond, 1.406, accuracy: 0.001, "200 steps per second x 7.03 mU")
        XCTAssertEqual(cup.maxPrimeSteps, 74, "0.524 U of needle volume / 7.03 mU")
    }

    func test_cup59PresetIsKnown_isTheBiggerBore_andOnlyAssistedPressureIsAllowed() {
        let cup59 = DriveCalibration.nfp608_26_45_cup59Miter1_1
        XCTAssertTrue(cup59.isKnown)
        XCTAssertEqual(cup59.driveID, 0x27)
        XCTAssertEqual(cup59.presetName, "nfp-608-26-45-cup59-miter-1-1")
        XCTAssertFalse(cup59.allowsSuctionDraw, "same pod, same missing check valve")
        XCTAssertEqual(cup59.allowedFillModes, [.assistedPressure])
        XCTAssertEqual(cup59.unitsPerStep, 0.007508, accuracy: 1e-8)
        XCTAssertEqual(cup59.maxPrimeSteps, 69, "0.524 U of needle volume / 7.508 mU")
        XCTAssertEqual(cup59.quantizedUnits(1.0), 133 * 0.007508, accuracy: 1e-9)
        XCTAssertEqual(DriveCalibration.firmwarePresets.first, cup59, "the current CAD's drive comes first")
        // the id pins the volume per step: 0x27 with the 0x26 numbers (or the reverse) is refused
        XCTAssertFalse(DriveCalibration(driveID: 0x27, microUnitsPerStep: 7_030, stepsPerRevolution: 20, gearRatioTimes100: 2_645).isKnown)
        XCTAssertFalse(DriveCalibration(driveID: 0x26, microUnitsPerStep: 7_508, stepsPerRevolution: 20, gearRatioTimes100: 2_645).isKnown)
    }

    func test_theOtherAcceptedFirmwareDriveMayDrawButUsesAssistedPressureFirst() {
        XCTAssertEqual(DriveCalibration.nfp608_26_45_g16_20.allowedFillModes, [.assistedPressure, .suctionDraw])
        XCTAssertEqual(DriveCalibration.zwbpd006006_5_1.allowedFillModes, [.manualConfirm], "the C reference has no AssistedFill")
        XCTAssertFalse(DriveCalibration.zwbpd006006_5_1.supportsAssistedFill)
    }

    func test_anUnknownOrWrongDriveGetsNoFillModeAtAll() {
        let wrongNumbers = DriveCalibration(driveID: 0x26, microUnitsPerStep: 7_031, stepsPerRevolution: 20, gearRatioTimes100: 2_645)
        XCTAssertFalse(wrongNumbers.isKnown, "the id alone is not enough: the volume per step must match")
        XCTAssertEqual(wrongNumbers.allowedFillModes, [])
        XCTAssertFalse(wrongNumbers.allowsSuctionDraw)
        XCTAssertNil(wrongNumbers.presetName)
        let foreign = DriveCalibration(driveID: 0x77, microUnitsPerStep: 7_030, stepsPerRevolution: 20, gearRatioTimes100: 2_645)
        XCTAssertEqual(CalibrationProblem.check(foreign), .unknown(driveID: 0x77, microUnitsPerStep: 7_030))
        XCTAssertEqual(foreign.allowedFillModes, [])
    }

    func test_quantizationNeverRoundsUp() {
        XCTAssertEqual(cup.quantizedUnits(0.05), 7 * 0.00703, accuracy: 1e-9)
        XCTAssertLessThanOrEqual(cup.quantizedUnits(0.05), 0.05)
        XCTAssertEqual(cup.quantizedUnits(1.0), 142 * 0.00703, accuracy: 1e-9)
        XCTAssertEqual(cup.quantizedUnits(0), 0)
    }

    // MARK: The pod model

    func test_assistedFill_drawsAtAFixedRate_andEndsDoneWithPrimeRequired() throws {
        let pod = undockedCupPod()
        XCTAssertEqual(pod.handle(.assistedFill(pulses: 400)), .ok(pod.status))   // 20 U
        XCTAssertEqual(fillStatus(pod).state, .drawing)
        pod.advance(by: 1)
        XCTAssertEqual(fillStatus(pod).drawnUnits, 200 * 0.00703, accuracy: 1e-9, "200 steps in the first second")
        XCTAssertEqual(pod.phase, .paired, "nothing is confirmed until the job ends")
        pod.advance(by: 20)
        let done = fillStatus(pod)
        XCTAssertEqual(done.state, .done)
        XCTAssertEqual(done.drawnUnits, 20, accuracy: cup.unitsPerStep)
        XCTAssertEqual(pod.reservoirUnits, done.drawnUnits, accuracy: 1e-9, "the reservoir is exactly what was drawn")
        XCTAssertTrue(done.primeRequired)
        XCTAssertEqual(pod.phase, .filled)
    }

    func test_assistedFill_isRefusedWhileDocked_whenBusy_aboveCapacity_andOnPodsWithoutIt() {
        let docked = SimulatedPod(size: .u100, startDate: t0, calibration: cup)
        _ = docked.handle(.hello(protocolVersion: PumpConstants.protocolVersion, time: t0, utcOffsetMinutes: 0))
        XCTAssertEqual(docked.handle(.assistedFill(pulses: 100)), .rejected(.podDocked))

        let pod = undockedCupPod()
        _ = pod.handle(.assistedFill(pulses: 100))
        XCTAssertEqual(pod.handle(.assistedFill(pulses: 100)), .rejected(.busy))
        pod.advance(by: 60)
        XCTAssertEqual(pod.handle(.assistedFill(pulses: 2_000)), .rejected(.fillOutOfRange), "5 U in, 100 U more would overflow the 100 U reservoir")

        let legacy = SimulatedPod(size: .u100, startDate: t0, calibration: .zwbpd006006_5_1)
        legacy.setDocked(false)
        _ = legacy.handle(.hello(protocolVersion: PumpConstants.protocolVersion, time: t0, utcOffsetMinutes: 0))
        XCTAssertEqual(legacy.handle(.assistedFill(pulses: 100)), .rejected(.unsupported))
        XCTAssertNil(legacy.status.fill, "a pod without AssistedFill reports no fill state")
    }

    func test_cancel_keepsWhatWasDrawn() {
        let pod = undockedCupPod()
        _ = pod.handle(.assistedFill(pulses: 400))
        pod.advance(by: 3)
        _ = pod.handle(.cancelAssistedFill)
        let status = fillStatus(pod)
        XCTAssertEqual(status.state, .aborted)
        XCTAssertEqual(status.drawnUnits, 600 * 0.00703, accuracy: 1e-9)
        XCTAssertEqual(pod.reservoirUnits, status.drawnUnits, accuracy: 1e-9)
        XCTAssertEqual(pod.phase, .filled)
        XCTAssertEqual(pod.handle(.cancelAssistedFill), .rejected(.invalidState), "nothing left to cancel")
    }

    func test_aStalledFill_reportsTheRealVolume() {
        let pod = undockedCupPod()
        pod.fillStallsAfterUnits = 8
        _ = pod.handle(.assistedFill(pulses: 600))      // 30 U asked
        pod.advance(by: 30)
        let status = fillStatus(pod)
        XCTAssertEqual(status.state, .stalled)
        XCTAssertEqual(status.drawnUnits, 8, accuracy: cup.unitsPerStep)
        XCTAssertLessThan(status.progress, 0.3)
    }

    func test_aRefillStartsFromAnEmptyJob() {
        let pod = undockedCupPod()
        _ = pod.handle(.assistedFill(pulses: 200))
        pod.advance(by: 20)
        XCTAssertEqual(pod.phase, .filled)
        _ = pod.handle(.deactivate)
        _ = pod.handle(.hello(protocolVersion: PumpConstants.protocolVersion, time: t0, utcOffsetMinutes: 0))
        XCTAssertEqual(pod.phase, .paired)
        XCTAssertEqual(fillStatus(pod).state, .idle, "the old job is gone with the old fill")
        XCTAssertEqual(pod.reservoirUnits, 0)
    }

    func test_smbSizedBolusesDeliverWhatWasAsked_theFractionOfAStepIsCarried() {
        let pod = SimulatedPod(size: .u100, startDate: t0, calibration: cup)
        pod.setDocked(false)
        _ = pod.handle(.hello(protocolVersion: PumpConstants.protocolVersion, time: t0, utcOffsetMinutes: 0))
        _ = pod.handle(.assistedFill(pulses: 1_000))    // 50 U
        pod.advance(by: 60)
        pod.setDocked(true)
        _ = pod.handle(.prime); pod.advance(by: Int(PumpConstants.primeDuration) + 2)
        _ = pod.handle(.setBasalProgram(try! BasalProgram(segments: [BasalSegment(startOffset: 0, unitsPerHour: 0)])))
        _ = pod.handle(.confirmAttached)
        let before = pod.reservoirUnits
        for id in 1...100 {
            XCTAssertNotEqual(pod.handle(.bolus(id: UInt16(id), pulses: 1)), .rejected(.busy))   // 0.05 U = 7.11 steps
            pod.advance(by: 3)
        }
        XCTAssertEqual(before - pod.reservoirUnits, 5.0, accuracy: cup.unitsPerStep * 1.01, "100 x 0.05 U = 5.0 U within one step, not 100 x floor = 4.92 U")
    }

    // MARK: Domain command plumbing

    func test_assistedFillIsAPhaseGatedDomainCommand() {
        XCTAssertTrue(PodPhase.paired.allows(.assistedFill))
        XCTAssertTrue(PodPhase.filled.allows(.assistedFill), "a top-up after a stall")
        XCTAssertFalse(PodPhase.active.allows(.assistedFill), "never while delivering")
        XCTAssertFalse(PodPhase.suspended.allows(.assistedFill))
        XCTAssertFalse(Command.assistedFill(pulses: 1).affectsDelivery)
    }
}
