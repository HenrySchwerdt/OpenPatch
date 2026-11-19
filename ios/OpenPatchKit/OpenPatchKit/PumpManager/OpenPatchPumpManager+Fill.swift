import Foundation
import OpenPatchCore

/// Refill of the pod (bench: WATER only). The cup pod is filled by the assisted PRESSURE fill only: the user pushes the syringe
/// through the septum while the pod retracts its plunger at a fixed rate. There is no suction draw on this pod (no check valve),
/// the app never offers one and `startFill(mode: .suctionDraw)` is refused for it.
extension OpenPatchPumpManager {
    /// Fill methods this pod's drive allows (empty until the pod reported a known drive).
    public var allowedFillModes: [FillMode] { state.driveCalibration?.allowedFillModes ?? [] }

    /// Starts a fill of `units`. The pod must be suspended and NOT docked; progress arrives in `state.fill` with every status read.
    public func startFill(mode: FillMode? = nil, units: Double, completion: @escaping (Error?) -> Void) {
        if let block = setupBlock(state) { return completion(block) }
        guard let calibration = state.driveCalibration else { return completion(OpenPatchError.calibration(.missing)) }
        let allowed = calibration.allowedFillModes
        let chosen = mode ?? allowed.first
        guard let chosen, allowed.contains(chosen) else { return completion(OpenPatchError.fillModeNotAllowed(mode ?? .assistedPressure)) }
        do { try state.podSize.validateFill(units: units) } catch {
            return completion(OpenPatchError.fill(error as? FillError ?? .tooSmall(minimum: PodSize.minimumFillUnits)))
        }
        switch chosen {
        case .manualConfirm:
            confirmFill(units: units, completion: completion)
        case .assistedPressure, .suctionDraw:
            let pulses = UnitConversion.pulses(forUnits: units)
            mutateState { $0.fill = nil }
            send(.assistedFill(pulses: UInt16(clamping: pulses))) { result in
                if case .failure(let failure) = result { completion(failure.error) } else { completion(nil) }
            }
        }
    }

    /// Stops a running fill; what was drawn so far stays in the reservoir.
    public func cancelFill(completion: @escaping (Error?) -> Void) {
        send(.cancelAssistedFill) { result in
            if case .failure(let failure) = result { completion(failure.error) } else { completion(nil) }
        }
    }
}
