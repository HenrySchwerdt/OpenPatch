import XCTest
@testable import OpenPatchCore

final class SimulatedPodTests: XCTestCase {
    private let t0 = Date(timeIntervalSince1970: 1_800_000_000)

    /// Brings a pod from unpaired to active with a constant basal of `basal` U/h.
    private func activePod(size: PodSize = .u200, fill: Double = 100, basal: Double = 1.0) throws -> SimulatedPod {
        let pod = SimulatedPod(size: size, startDate: t0)
        XCTAssertEqual(pod.handle(.hello(protocolVersion: 1, time: t0, utcOffsetMinutes: 0)).isOK, true)
        let program = try BasalProgram(segments: [BasalSegment(startOffset: 0, unitsPerHour: basal)])
        XCTAssertTrue(pod.handle(.setBasalProgram(program)).isOK)
        XCTAssertTrue(pod.handle(.confirmFill(pulses: UInt16(UnitConversion.pulses(forUnits: fill)))).isOK)
        XCTAssertTrue(pod.handle(.prime).isOK)
        pod.advance(by: Int(PumpConstants.primeDuration) + 1)
        XCTAssertEqual(pod.phase, .primed)
        XCTAssertTrue(pod.handle(.confirmAttached).isOK)
        XCTAssertEqual(pod.phase, .active)
        _ = pod.drainEvents()
        return pod
    }

    // MARK: lifecycle

    func test_activationFlow_consumesPrimeVolumeFromReservoir() throws {
        let pod = try activePod(fill: 100)
        XCTAssertEqual(pod.reservoirUnits, 100 - PumpConstants.primeUnits, accuracy: DriveCalibration.zwbpd006006_5_1.unitsPerStep)
    }

    func test_commandsRejectedInWrongPhase() {
        let pod = SimulatedPod(size: .u100, startDate: t0)
        XCTAssertEqual(pod.handle(.bolus(id: 1, pulses: 20)), .rejected(.invalidState))
        _ = pod.handle(.hello(protocolVersion: 1, time: t0, utcOffsetMinutes: 0))
        XCTAssertEqual(pod.handle(.prime), .rejected(.invalidState))
        XCTAssertEqual(pod.handle(.confirmFill(pulses: 5)), .rejected(.fillOutOfRange), "below minimum fill")
        XCTAssertEqual(pod.handle(.confirmFill(pulses: 2100)), .rejected(.fillOutOfRange), "above 100 U capacity")
    }

    func test_attachRequiresBasalProgram() {
        let pod = SimulatedPod(size: .u100, startDate: t0)
        _ = pod.handle(.hello(protocolVersion: 1, time: t0, utcOffsetMinutes: 0))
        _ = pod.handle(.confirmFill(pulses: 1000))
        _ = pod.handle(.prime)
        pod.advance(by: Int(PumpConstants.primeDuration) + 1)
        XCTAssertEqual(pod.handle(.confirmAttached), .rejected(.notConfigured))
    }

    func test_primeCompletedEventEmitted() throws {
        let pod = SimulatedPod(size: .u100, startDate: t0)
        _ = pod.handle(.hello(protocolVersion: 1, time: t0, utcOffsetMinutes: 0))
        _ = pod.handle(.confirmFill(pulses: 1000))
        _ = pod.handle(.prime)
        pod.advance(by: Int(PumpConstants.primeDuration) + 1)
        XCTAssertTrue(pod.drainEvents().contains(.primeCompleted))
    }

    // MARK: basal

    func test_basalDelivery_oneHour_matchesScheduleWithinOneStep() throws {
        let pod = try activePod(basal: 1.3)
        let before = pod.reservoirUnits
        pod.advance(by: 3600)
        XCTAssertEqual(before - pod.reservoirUnits, 1.3, accuracy: DriveCalibration.zwbpd006006_5_1.unitsPerStep * 2)
    }

    func test_suspend_stopsDelivery_resumeContinues() throws {
        let pod = try activePod(basal: 2.0)
        XCTAssertTrue(pod.handle(.suspend).isOK)
        let suspendedLevel = pod.reservoirUnits
        pod.advance(by: 1800)
        XCTAssertEqual(pod.reservoirUnits, suspendedLevel, accuracy: 1e-9)
        XCTAssertEqual(pod.handle(.bolus(id: 1, pulses: 20)), .rejected(.invalidState))
        XCTAssertTrue(pod.handle(.resume).isOK)
        pod.advance(by: 1800)
        XCTAssertEqual(suspendedLevel - pod.reservoirUnits, 1.0, accuracy: DriveCalibration.zwbpd006006_5_1.unitsPerStep * 2)
    }

    // MARK: bolus

    func test_bolus_deliversAtOnePointFiveUnitsPerMinute() throws {
        let pod = try activePod(basal: 0)
        let before = pod.reservoirUnits
        guard case .ok(let status) = pod.handle(.bolus(id: 42, pulses: 60)) else { return XCTFail() }  // 3.0 U
        XCTAssertEqual(status.bolus?.id, 42)
        pod.advance(by: 60)
        XCTAssertEqual(before - pod.reservoirUnits, 1.5, accuracy: DriveCalibration.zwbpd006006_5_1.unitsPerStep * 2)
        XCTAssertNotNil(pod.status.bolus)
        pod.advance(by: 61)
        XCTAssertNil(pod.status.bolus)
        XCTAssertEqual(before - pod.reservoirUnits, 3.0, accuracy: DriveCalibration.zwbpd006006_5_1.unitsPerStep * 2)
        XCTAssertEqual(pod.drainEvents().first, .bolusCompleted(id: 42, deliveredPulses: 60))
    }

    func test_secondBolusWhileRunning_isBusy() throws {
        let pod = try activePod(basal: 0)
        _ = pod.handle(.bolus(id: 1, pulses: 60))
        XCTAssertEqual(pod.handle(.bolus(id: 2, pulses: 20)), .rejected(.busy))
    }

    func test_cancelBolus_reportsPartialDelivery() throws {
        let pod = try activePod(basal: 0)
        _ = pod.handle(.bolus(id: 5, pulses: 100))   // 5 U over 200 s
        pod.advance(by: 60)                         // ~1.5 U
        guard case .ok(let status) = pod.handle(.cancelBolus) else { return XCTFail() }
        XCTAssertNil(status.bolus)
        let events = pod.drainEvents()
        guard case .bolusCompleted(let id, let delivered)? = events.first else { return XCTFail("\(events)") }
        XCTAssertEqual(id, 5)
        XCTAssertEqual(UnitConversion.units(forPulses: Int(delivered)), 1.5, accuracy: 0.1)
        pod.advance(by: 300)
        XCTAssertEqual(pod.deliveredUnitsTotal, 1.5, accuracy: 0.1, "nothing delivered after cancel")
    }

    func test_bolusAbovePodLimit_isRejected() throws {
        let pod = try activePod(basal: 0)
        XCTAssertEqual(pod.handle(.bolus(id: 1, pulses: 201)), .rejected(.limitExceeded))   // 10.05 U
        XCTAssertTrue(pod.handle(.bolus(id: 1, pulses: 200)).isOK)
    }

    func test_hourlyLimit_isEnforcedAcrossBoluses() throws {
        let pod = try activePod(basal: 0)
        pod.handle(.setLimits(SafetyLimits(maxBolus: 10, maxBasalRate: 5))).discard()
        XCTAssertTrue(pod.handle(.bolus(id: 1, pulses: 200)).isOK)   // 10 U
        pod.advance(by: 400)
        XCTAssertTrue(pod.handle(.bolus(id: 2, pulses: 100)).isOK)   // 5 U -> 15 U within the hour
        pod.advance(by: 300)
        XCTAssertEqual(pod.handle(.bolus(id: 3, pulses: 20)), .rejected(.hourlyLimit))
        pod.advance(by: 3600)
        XCTAssertTrue(pod.handle(.bolus(id: 3, pulses: 20)).isOK, "window rolled over")
    }

    func test_bolusLimitCommand_lowersPodLimit() throws {
        let pod = try activePod(basal: 0)
        XCTAssertTrue(pod.handle(.setLimits(SafetyLimits(maxBolus: 3, maxBasalRate: 5))).isOK)
        XCTAssertEqual(pod.handle(.bolus(id: 1, pulses: 61)), .rejected(.limitExceeded))
    }

    // MARK: temp basal

    func test_tempBasal_overridesSchedule_thenEndsWithEvent() throws {
        let pod = try activePod(basal: 1.0)
        XCTAssertTrue(pod.handle(.setTempBasal(rateTicks: 40, durationMinutes: 30)).isOK)   // 2.0 U/h
        let before = pod.reservoirUnits
        pod.advance(by: 1800)
        XCTAssertEqual(before - pod.reservoirUnits, 1.0, accuracy: DriveCalibration.zwbpd006006_5_1.unitsPerStep * 2)
        XCTAssertTrue(pod.drainEvents().contains(.tempBasalEnded))
        XCTAssertNil(pod.status.tempBasal)
        let afterTemp = pod.reservoirUnits
        pod.advance(by: 3600)
        XCTAssertEqual(afterTemp - pod.reservoirUnits, 1.0, accuracy: DriveCalibration.zwbpd006006_5_1.unitsPerStep * 2, "scheduled rate resumes")
    }

    func test_zeroTempBasal_stopsBasal() throws {
        let pod = try activePod(basal: 3.0)
        XCTAssertTrue(pod.handle(.setTempBasal(rateTicks: 0, durationMinutes: 60)).isOK)
        let before = pod.reservoirUnits
        pod.advance(by: 1800)
        XCTAssertEqual(before - pod.reservoirUnits, 0, accuracy: 1e-9)
    }

    func test_cancelTempBasal() throws {
        let pod = try activePod(basal: 1.0)
        _ = pod.handle(.setTempBasal(rateTicks: 0, durationMinutes: 60))
        XCTAssertNotNil(pod.status.tempBasal)
        XCTAssertTrue(pod.handle(.cancelTempBasal).isOK)
        XCTAssertNil(pod.status.tempBasal)
    }

    func test_tempBasalAbovePodMax_isRejected() throws {
        let pod = try activePod(basal: 1.0)
        XCTAssertEqual(pod.handle(.setTempBasal(rateTicks: 101, durationMinutes: 30)), .rejected(.limitExceeded))  // 5.05 U/h
    }

    func test_commLoss_revertsTempBasalAfterThirtyMinutes() throws {
        let pod = try activePod(basal: 1.0)
        _ = pod.handle(.setTempBasal(rateTicks: 0, durationMinutes: 180))
        pod.advance(by: 29 * 60)
        XCTAssertNotNil(pod.status.tempBasal)
        pod.advance(by: 2 * 60)
        XCTAssertNil(pod.status.tempBasal)
        XCTAssertTrue(pod.drainEvents().contains(.tempBasalRevertedCommLoss))
    }

    func test_contactRefreshesCommLossTimer() throws {
        let pod = try activePod(basal: 1.0)
        _ = pod.handle(.setTempBasal(rateTicks: 0, durationMinutes: 180))
        for _ in 0..<5 {
            pod.advance(by: 20 * 60)
            _ = pod.handle(.getStatus)
        }
        XCTAssertNotNil(pod.status.tempBasal)
    }

    // MARK: reservoir & faults

    func test_lowReservoirEvent_thenEmptyFault() throws {
        let pod = try activePod(size: .u70, fill: 12, basal: 5.0)
        pod.advance(by: 3600)   // 12 - 0.5 prime - 5 = 6.5 U left
        XCTAssertTrue(pod.drainEvents().contains { if case .lowReservoir = $0 { return true } else { return false } })
        pod.advance(by: 3600 + 1800)   // 6.5 U at 5 U/h: empty after 78 min
        XCTAssertEqual(pod.phase, .faulted)
        XCTAssertEqual(pod.status.faultCode, .reservoirEmpty)
        XCTAssertEqual(pod.reservoirUnits, 0, accuracy: DriveCalibration.zwbpd006006_5_1.unitsPerStep)
        XCTAssertTrue(pod.drainEvents().contains(.fault(.reservoirEmpty)))
    }

    func test_occlusionInjection_haltsDeliveryAndRejectsBolus() throws {
        let pod = try activePod(basal: 2.0)
        _ = pod.handle(.bolus(id: 1, pulses: 60))
        pod.injectFault(.occlusion)
        let level = pod.reservoirUnits
        pod.advance(by: 600)
        XCTAssertEqual(pod.reservoirUnits, level, accuracy: 1e-9)
        XCTAssertEqual(pod.phase, .faulted)
        XCTAssertEqual(pod.handle(.bolus(id: 2, pulses: 20)), .rejected(.invalidState))
        XCTAssertTrue(pod.handle(.silenceAlarm).isOK)
        XCTAssertTrue(pod.handle(.deactivate).isOK)
        XCTAssertEqual(pod.phase, .deactivated)
    }

    func test_refillCycle_afterDeactivation() throws {
        let pod = try activePod(basal: 1.0)
        XCTAssertTrue(pod.handle(.deactivate).isOK)
        XCTAssertTrue(pod.handle(.hello(protocolVersion: 1, time: t0, utcOffsetMinutes: 0)).isOK)
        XCTAssertEqual(pod.phase, .paired, "hello on a deactivated reusable pod starts a refill")
        XCTAssertTrue(pod.handle(.confirmFill(pulses: 1000)).isOK)
    }


}

private extension Response {
    var isOK: Bool { if case .ok = self { return true } else { return false } }
    func discard() {}
}
