import XCTest
@testable import OpenPatchCore

/// Pod-side rules of the two-pod system (dock gate, wear timer, activation, release, charger) on the simulator.
final class TwoPodSimulatedPodTests: XCTestCase {
    let t0 = Date(timeIntervalSince1970: 1_800_000_000)
    let pair: UInt32 = 0xA1B2C3D4
    var program: BasalProgram { try! BasalProgram(segments: [BasalSegment(startOffset: 0, unitsPerHour: 1.0)]) }

    /// paired + filled, not yet activated
    private func readyPod(role: PodRole = .a) -> SimulatedPod {
        let pod = SimulatedPod(size: .u100, startDate: t0)
        XCTAssertNotNil(ok(pod.handle(.hello(protocolVersion: 1, time: t0, utcOffsetMinutes: 0))))
        XCTAssertNotNil(ok(pod.handle(.setPairing(pairID: pair, role: role))))
        XCTAssertNotNil(ok(pod.handle(.confirmFill(pulses: 2000))))
        return pod
    }

    private func running() -> SimulatedPod {
        let pod = readyPod()
        XCTAssertNotNil(ok(pod.handle(.activatePod(pairID: pair, activationID: 1, program: program, tempBasal: nil))))
        XCTAssertNotNil(ok(pod.handle(.prime)))
        pod.advance(by: 41)
        XCTAssertNotNil(ok(pod.handle(.confirmAttached)))
        XCTAssertEqual(pod.phase, .active)
        return pod
    }

    private func ok(_ r: Response) -> PodStatus? { if case .ok(let s) = r { return s }; return nil }
    private func nack(_ r: Response) -> NackReason? { if case .rejected(let n) = r { return n }; return nil }

    func test_activate_leavesThePodWithoutDeliveryUntilResume() {
        let pod = readyPod()
        _ = pod.handle(.activatePod(pairID: pair, activationID: 1, program: program, tempBasal: nil))
        XCTAssertTrue(pod.isActivated)
        XCTAssertEqual(pod.phase, .filled)
        let before = pod.reservoirUnits
        pod.advance(by: 600)
        XCTAssertEqual(pod.reservoirUnits, before, "nothing delivered before the connector prime and the resume")
    }

    func test_undockedPodNeverDelivers_andReportsPausedUndocked() {
        let pod = running()
        pod.setDocked(false)
        let level = pod.reservoirUnits
        pod.advance(by: 3600)
        XCTAssertEqual(pod.reservoirUnits, level)
        XCTAssertEqual(pod.status.pairing?.deliveryState, .pausedUndocked)
        XCTAssertEqual(pod.status.pairing?.isDocked, false)
        pod.setDocked(true)
        pod.advance(by: 3600)
        XCTAssertLessThan(pod.reservoirUnits, level)
        XCTAssertEqual(pod.status.pairing?.deliveryState, .active)
        XCTAssertEqual(pod.drainEvents().filter { if case .docked = $0 { return true }; return false }, [.docked(false), .docked(true)])
    }

    func test_dockLossCancelsARunningBolus_andItDoesNotComeBack() {
        let pod = running()
        XCTAssertNotNil(ok(pod.handle(.bolus(id: 5, pulses: 100))))   // 5 U
        pod.advance(by: 20)
        pod.setDocked(false)
        XCTAssertNil(pod.status.bolus)
        let events = pod.drainEvents()
        XCTAssertTrue(events.contains { if case .bolusCompleted(5, _) = $0 { return true }; return false })
        pod.setDocked(true)
        let level = pod.reservoirUnits
        pod.advance(by: 300)
        XCTAssertEqual(level - pod.reservoirUnits, 0.0, accuracy: 1.1, "only basal (1 U/h) runs afterwards")
        XCTAssertEqual(nack(pod.handle(.bolus(id: 6, pulses: 20))), nil)
        pod.setDocked(false)
        XCTAssertEqual(nack(pod.handle(.bolus(id: 7, pulses: 20))), .notDocked)
        XCTAssertEqual(nack(pod.handle(.resume)), .invalidState)
    }

    func test_activateIsRefusedWhenUndockedOrCharging_andLeavesNoState() {
        let pod = readyPod()
        pod.setDocked(false)
        XCTAssertEqual(nack(pod.handle(.activatePod(pairID: pair, activationID: 1, program: program, tempBasal: nil))), .notDocked)
        XCTAssertFalse(pod.isActivated)
        pod.setDocked(true)
        pod.setOnCharger(true)
        XCTAssertEqual(nack(pod.handle(.activatePod(pairID: pair, activationID: 1, program: program, tempBasal: nil))), .charging)
        pod.setOnCharger(false)
        XCTAssertEqual(nack(pod.handle(.activatePod(pairID: pair + 1, activationID: 1, program: program, tempBasal: nil))), .pairMismatch)
        XCTAssertFalse(pod.isActivated)
        XCTAssertNotNil(ok(pod.handle(.activatePod(pairID: pair, activationID: 1, program: program, tempBasal: nil))))
    }

    func test_activateTwice_sameIDIsIdempotent_differentIDIsRefused() {
        let pod = readyPod()
        _ = pod.handle(.activatePod(pairID: pair, activationID: 7, program: program, tempBasal: nil))
        XCTAssertNotNil(ok(pod.handle(.activatePod(pairID: pair, activationID: 7, program: program, tempBasal: nil))))
        XCTAssertEqual(nack(pod.handle(.activatePod(pairID: pair, activationID: 8, program: program, tempBasal: nil))), .alreadyActive)
        XCTAssertEqual(pod.activationID, 7)
    }

    func test_releasedPodRefusesDeliveryCommands() {
        let pod = readyPod()
        XCTAssertEqual(nack(pod.handle(.prime)), .released)
        XCTAssertEqual(nack(pod.handle(.resume)), .invalidState)
        let active = running()
        let report = ok(active.handle(.releasePod(pairID: pair)))?.releaseReport
        XCTAssertNotNil(report)
        XCTAssertFalse(active.isActivated)
        XCTAssertEqual(active.phase, .deactivated)
        XCTAssertEqual(nack(active.handle(.bolus(id: 1, pulses: 20))), .invalidState)
        let level = active.reservoirUnits
        active.advance(by: 3600)
        XCTAssertEqual(active.reservoirUnits, level)
    }

    func test_release_isIdempotent_andReportsTotals() {
        let pod = running()
        XCTAssertNotNil(ok(pod.handle(.bolus(id: 1, pulses: 40))))   // 2 U
        pod.advance(by: 120)
        let first = ok(pod.handle(.releasePod(pairID: pair)))
        let second = ok(pod.handle(.releasePod(pairID: pair)))
        XCTAssertEqual(first?.releaseReport, second?.releaseReport)
        let report = try! XCTUnwrap(first?.releaseReport)
        XCTAssertEqual(report.deliveredSinceActivationUnits, 2.0, accuracy: 0.2)   // prime (0.5) + 2 U bolus
        XCTAssertEqual(report.finalReservoirUnits, 100 - report.deliveredSinceActivationUnits, accuracy: 0.6)
        XCTAssertEqual(nack(pod.handle(.releasePod(pairID: pair + 1))), .pairMismatch)
        XCTAssertEqual(pod.drainEvents().filter { if case .released = $0 { return true }; return false }.count, 1)
    }

    func test_releaseWorksWhileUndocked() {
        let pod = running()
        pod.setDocked(false)
        XCTAssertNotNil(ok(pod.handle(.releasePod(pairID: pair))))
        XCTAssertFalse(pod.isActivated)
    }

    func test_charger_forcesRelease() {
        let pod = running()
        pod.setOnCharger(true)
        XCTAssertFalse(pod.isActivated)
        XCTAssertEqual(pod.status.pairing?.deliveryState, .released)
        XCTAssertTrue(pod.drainEvents().contains(.released(deliveredUnits: pod.releaseReport.deliveredSinceActivationUnits, reason: .charger)))
        pod.setOnCharger(false)
        XCTAssertFalse(pod.isActivated, "leaving the charger does not re-activate")
    }

    func test_wearTimer_warningAt44h_stopAt52h() {
        let pod = running()
        pod.advance(by: 43 * 3600)
        XCTAssertEqual(pod.status.pairing?.wearWarning, false)
        pod.advance(by: 3600)
        XCTAssertEqual(pod.status.pairing?.wearWarning, true)
        XCTAssertTrue(pod.drainEvents().contains(.wearWarning))
        XCTAssertNil(pod.status.faultCode)
        pod.advance(by: 8 * 3600)
        XCTAssertEqual(pod.status.faultCode, .wearExpired)
        XCTAssertEqual(pod.status.pairing?.deliveryState, .stoppedWear)
        XCTAssertTrue(pod.drainEvents().contains(.wearExpired))
        let level = pod.reservoirUnits
        pod.advance(by: 3600)
        XCTAssertEqual(pod.reservoirUnits, level)
    }

    func test_newActivationRestartsTheWearTimer() {
        let pod = running()
        pod.advance(by: 52 * 3600)
        XCTAssertEqual(pod.status.faultCode, .wearExpired)
        _ = pod.handle(.releasePod(pairID: pair))
        _ = pod.handle(.hello(protocolVersion: 1, time: pod.now, utcOffsetMinutes: 0))   // refill cycle
        _ = pod.handle(.confirmFill(pulses: 2000))
        XCTAssertNotNil(ok(pod.handle(.activatePod(pairID: pair, activationID: 2, program: program, tempBasal: nil))))
        XCTAssertEqual(pod.wearSeconds, 0)
        XCTAssertNil(pod.status.faultCode)
    }

    func test_handoverTempBasalStartsWithTheResume() {
        let pod = readyPod()
        _ = pod.handle(.activatePod(pairID: pair, activationID: 1, program: program, tempBasal: HandoverTempBasal(rateTicks: 40, remainingMinutes: 90)))
        XCTAssertNil(pod.status.tempBasal)
        _ = pod.handle(.prime); pod.advance(by: 41)
        _ = pod.handle(.confirmAttached)
        XCTAssertEqual(pod.status.tempBasal?.rateTicks, 40)
        XCTAssertEqual(pod.status.tempBasal?.remainingMinutes, 90)
    }

    func test_pairingIsRefusedWhileActive() {
        let pod = running()
        XCTAssertEqual(nack(pod.handle(.setPairing(pairID: 5, role: .b))), .invalidState)
    }

    func test_podReportsItsCalibration() {
        XCTAssertEqual(readyPod().status.driveCalibration, .zwbpd006006_5_1)
        let other = SimulatedPod(size: .u100, startDate: t0, calibration: .faulhaber_16_1)
        XCTAssertEqual(other.status.driveCalibration, .faulhaber_16_1)
        let legacy = SimulatedPod(size: .u100, startDate: t0)
        legacy.reportsCalibration = false
        XCTAssertNil(legacy.status.driveCalibration)
    }

    func test_faulhaberPodDeliversTheSameInsulinWithMoreSteps() {
        let a = SimulatedPod(size: .u100, startDate: t0)
        let b = SimulatedPod(size: .u100, startDate: t0, calibration: .faulhaber_16_1)
        for pod in [a, b] {
            _ = pod.handle(.hello(protocolVersion: 1, time: t0, utcOffsetMinutes: 0))
            _ = pod.handle(.confirmFill(pulses: 2000))
            _ = pod.handle(.setBasalProgram(program))
            _ = pod.handle(.prime); pod.advance(by: 41)
            _ = pod.handle(.confirmAttached)
        }
        let beforeA = a.reservoirUnits, beforeB = b.reservoirUnits
        a.advance(by: 6 * 3600); b.advance(by: 6 * 3600)
        XCTAssertEqual(beforeA - a.reservoirUnits, 6.0, accuracy: 0.03)
        XCTAssertEqual(beforeB - b.reservoirUnits, 6.0, accuracy: 0.01)
    }
}
