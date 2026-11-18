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

    public var errorDescription: String? {
        switch self {
        case .notReady(let phase): return String(format: NSLocalizedString("Pod is not ready (state: %@).", bundle: .openPatchKit, comment: "Error"), "\(phase)")
        case .bolusInProgress: return NSLocalizedString("A bolus is already in progress.", bundle: .openPatchKit, comment: "Error")
        case .suspended: return NSLocalizedString("Insulin delivery is suspended.", bundle: .openPatchKit, comment: "Error")
        case .noBolusToCancel: return NSLocalizedString("No bolus is running.", bundle: .openPatchKit, comment: "Error")
        case .invalidAmount: return NSLocalizedString("Invalid insulin amount.", bundle: .openPatchKit, comment: "Error")
        case .limit(let e): return String(format: NSLocalizedString("Delivery limit exceeded (%@).", bundle: .openPatchKit, comment: "Error"), "\(e)")
        case .rejected(let r): return String(format: NSLocalizedString("The pod rejected the command (%@).", bundle: .openPatchKit, comment: "Error"), "\(r)")
        case .transport(let t): return String(format: NSLocalizedString("Communication with the pod failed (%@).", bundle: .openPatchKit, comment: "Error"), "\(t)")
        case .notConfigured: return NSLocalizedString("The basal schedule has not been set yet.", bundle: .openPatchKit, comment: "Error")
        case .fill(let e): return String(format: NSLocalizedString("Invalid fill amount (%@).", bundle: .openPatchKit, comment: "Error"), "\(e)")
        case .podFault(let c): return String(format: NSLocalizedString("The pod reported a fault (%@).", bundle: .openPatchKit, comment: "Error"), "\(c)")
        }
    }
}

extension Bundle {
    static var openPatchKit: Bundle { Bundle(for: OpenPatchPumpManager.self) }
}
