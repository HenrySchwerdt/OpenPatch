import XCTest
@testable import OpenPatchCore

final class PodLifecycleTests: XCTestCase {
    func test_happyPath_fromPairingToDelivery() {
        var phase = PodPhase.unpaired
        let path: [(LifecycleEvent, PodPhase)] = [
            (.paired, .paired), (.fillConfirmed, .filled), (.primeStarted, .priming),
            (.primeCompleted, .primed), (.attached, .active),
            (.suspended, .suspended), (.resumed, .active), (.deactivated, .deactivated),
            (.refillRequested, .paired)
        ]
        for (event, expected) in path {
            guard let next = PodLifecycle.transition(from: phase, event: event) else {
                return XCTFail("\(event) not allowed from \(phase)")
            }
            XCTAssertEqual(next, expected)
            phase = next
        }
    }

    func test_invalidTransitions_returnNil() {
        XCTAssertNil(PodLifecycle.transition(from: .unpaired, event: .attached))
        XCTAssertNil(PodLifecycle.transition(from: .paired, event: .primeStarted))
        XCTAssertNil(PodLifecycle.transition(from: .active, event: .resumed))
        XCTAssertNil(PodLifecycle.transition(from: .suspended, event: .suspended))
        XCTAssertNil(PodLifecycle.transition(from: .active, event: .refillRequested))
        XCTAssertNil(PodLifecycle.transition(from: .deactivated, event: .faulted))
    }

    func test_reset_alwaysReturnsToUnpaired() {
        for phase in PodPhase.allCases {
            XCTAssertEqual(PodLifecycle.transition(from: phase, event: .reset), .unpaired)
        }
    }

    func test_fault_possibleFromEveryOperationalPhase() {
        for phase in [PodPhase.paired, .filled, .priming, .primed, .active, .suspended] {
            XCTAssertEqual(PodLifecycle.transition(from: phase, event: .faulted), .faulted)
        }
    }

    func test_commandGating() {
        XCTAssertTrue(PodPhase.active.allows(.bolus))
        XCTAssertTrue(PodPhase.active.allows(.setTempBasal))
        XCTAssertFalse(PodPhase.suspended.allows(.bolus))
        XCTAssertFalse(PodPhase.suspended.allows(.setTempBasal))
        XCTAssertTrue(PodPhase.suspended.allows(.resume))
        XCTAssertFalse(PodPhase.active.allows(.resume))
        XCTAssertTrue(PodPhase.paired.allows(.confirmFill))
        XCTAssertFalse(PodPhase.active.allows(.confirmFill))
        XCTAssertTrue(PodPhase.filled.allows(.prime))
        XCTAssertTrue(PodPhase.primed.allows(.confirmAttached))
        XCTAssertFalse(PodPhase.faulted.allows(.bolus))
        XCTAssertTrue(PodPhase.faulted.allows(.deactivate))
        XCTAssertTrue(PodPhase.faulted.allows(.getStatus))
        XCTAssertTrue(PodPhase.unpaired.allows(.hello))
        XCTAssertFalse(PodPhase.unpaired.allows(.setBasalProgram))
    }

    func test_commandKind_matchesCommand() {
        XCTAssertEqual(Command.bolus(id: 1, pulses: 2).kind, .bolus)
        XCTAssertEqual(Command.cancelTempBasal.kind, .cancelTempBasal)
    }
}
