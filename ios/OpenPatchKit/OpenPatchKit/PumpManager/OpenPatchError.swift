import Foundation
import OpenPatchCore

public enum OpenPatchError: LocalizedError, Equatable {
    case notReady(PodPhase)
    case bolusInProgress
    case suspended
    case noBolusToCancel
    case invalidAmount
    case limit(LimitError)
    case rejected(NackReason)
    case transport(TransportError)
    case notConfigured
    case fill(FillError)
    case podFault(FaultCode)
    /// The pod's drive calibration is missing or not a known drive: the app refuses to operate this pod.
    case calibration(CalibrationProblem)
    case swapInProgress
    case swap(SwapFailure)
    case notActivePod
    /// The requested fill method is not allowed for this pod's drive (suction draw on the cup pod, manual fill on an assisted pod).
    case fillModeNotAllowed(FillMode)
    /// The pod belongs to another phone (or was reset): its button must be pressed and the pod paired again.
    case needsPairing
    /// The pairing secret could not be stored in the keychain (nothing was changed on the pod's side that the app can use).
    case secretNotStored
    /// A previous bolus command is unresolved (its reply was lost): no second bolus until the pod's history says what happened.
    case deliveryUncertain

    public var errorDescription: String? {
        switch self {
        case .notReady(let phase): return String(format: NSLocalizedString("Pod is not ready (state: %@).", bundle: .openPatchKit, comment: "Error"), "\(phase)")
        case .bolusInProgress: return NSLocalizedString("A bolus is already in progress.", bundle: .openPatchKit, comment: "Error")
        case .suspended: return NSLocalizedString("Insulin delivery is suspended.", bundle: .openPatchKit, comment: "Error")
        case .noBolusToCancel: return NSLocalizedString("No bolus is running.", bundle: .openPatchKit, comment: "Error")
        case .invalidAmount: return NSLocalizedString("Invalid insulin amount.", bundle: .openPatchKit, comment: "Error")
        case .limit(let e): return String(format: NSLocalizedString("Delivery limit exceeded (%@).", bundle: .openPatchKit, comment: "Error"), "\(e)")
        case .rejected(let r): return String(format: NSLocalizedString("The pod rejected the command (%@).", bundle: .openPatchKit, comment: "Error"), "\(r)")
        case .transport(.notPaired): return OpenPatchError.needsPairing.errorDescription
        case .transport(.sessionFailed): return NSLocalizedString("The secure connection to the pod could not be set up (wrong key or an altered exchange). Do not retry blindly: press the pod's button and pair it again.", bundle: .openPatchKit, comment: "Error")
        case .transport(let t): return String(format: NSLocalizedString("Communication with the pod failed (%@).", bundle: .openPatchKit, comment: "Error"), "\(t)")
        case .notConfigured: return NSLocalizedString("The basal schedule has not been set yet.", bundle: .openPatchKit, comment: "Error")
        case .fill(let e): return String(format: NSLocalizedString("Invalid fill amount (%@).", bundle: .openPatchKit, comment: "Error"), "\(e)")
        case .calibration(.missing): return NSLocalizedString("The pod does not report its drive calibration. It cannot be used: the insulin volume per step is unknown.", bundle: .openPatchKit, comment: "Error")
        case .calibration(.unknown(let id, let uu)): return String(format: NSLocalizedString("The pod reports an unknown drive (id %d, %d µU per step). It cannot be used.", bundle: .openPatchKit, comment: "Error"), Int(id), Int(uu))
        case .swapInProgress: return NSLocalizedString("A pod swap is in progress. Finish or cancel it first.", bundle: .openPatchKit, comment: "Error")
        case .notActivePod: return NSLocalizedString("This pod is not the active pod.", bundle: .openPatchKit, comment: "Error")
        case .swap(let failure): return Self.describe(failure)
        case .fillModeNotAllowed(let mode): return Self.describe(mode)
        case .needsPairing: return NSLocalizedString("This pod does not know this phone (it was paired with another phone or reset). Press the button on the pod to open its pairing window, then pair it again.", bundle: .openPatchKit, comment: "Error")
        case .deliveryUncertain: return NSLocalizedString("The pod did not confirm the previous bolus. Another bolus is blocked until the pump has found out what happened.", bundle: .openPatchKit, comment: "Error")
        case .secretNotStored: return NSLocalizedString("The pairing key could not be saved in the keychain. The pod was not paired.", bundle: .openPatchKit, comment: "Error")
        case .podFault(let c): return String(format: NSLocalizedString("The pod reported a fault (%@).", bundle: .openPatchKit, comment: "Error"), "\(c)")
        }
    }
}

extension OpenPatchError {
    static func describe(_ mode: FillMode) -> String {
        switch mode {
        case .suctionDraw: return NSLocalizedString("This pod has no check valve and never draws by itself. Fill it with the assisted pressure fill: you push the syringe, the pod retracts.", bundle: .openPatchKit, comment: "Error")
        case .manualConfirm: return NSLocalizedString("This pod is filled with the assisted pressure fill only: the pod retracts its plunger while you push the syringe.", bundle: .openPatchKit, comment: "Error")
        case .assistedPressure: return NSLocalizedString("This pod does not support the assisted pressure fill.", bundle: .openPatchKit, comment: "Error")
        }
    }

    static func describe(_ failure: SwapFailure) -> String {
        func name(_ role: PodRole) -> String { String(format: NSLocalizedString("pod %@", bundle: .openPatchKit, comment: "Pod name in an error"), role.label) }
        switch failure {
        case .unreachable(let role):
            return String(format: NSLocalizedString("Cannot reach %@. Move the phone closer and wake the pod with its button.", bundle: .openPatchKit, comment: "Error"), name(role))
        case .ambiguous(let role):
            return String(format: NSLocalizedString("The connection to %@ was lost while sending. The pod may or may not have executed the command.", bundle: .openPatchKit, comment: "Error"), name(role))
        case .rejected(let role, let reason):
            return String(format: NSLocalizedString("%@ rejected the command (%@).", bundle: .openPatchKit, comment: "Error"), name(role), "\(reason)")
        case .calibration(let role, let problem):
            return String(format: NSLocalizedString("%@ cannot be used: ", bundle: .openPatchKit, comment: "Error"), name(role)) + (OpenPatchError.calibration(problem).errorDescription ?? "")
        case .notDocked(let role):
            return String(format: NSLocalizedString("%@ is not docked on the cannula yet.", bundle: .openPatchKit, comment: "Error"), name(role))
        case .spareNotReady:
            return NSLocalizedString("The spare pod is not ready (charge it and fill it) - the swap was not started and the active pod keeps running.", bundle: .openPatchKit, comment: "Error")
        case .notAllowed(let text):
            return String(format: NSLocalizedString("Not possible right now (%@).", bundle: .openPatchKit, comment: "Error"), text)
        }
    }
}

extension Bundle {
    static var openPatchKit: Bundle { Bundle(for: OpenPatchPumpManager.self) }
}
