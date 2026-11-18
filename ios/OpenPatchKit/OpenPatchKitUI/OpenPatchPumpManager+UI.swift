import LoopKit
import LoopKitUI
import OpenPatchCore
import OpenPatchKit
import SwiftUI
import UIKit

extension OpenPatchPumpManager: PumpManagerUI {
    private var appName: String {
        (Bundle.main.object(forInfoDictionaryKey: "CFBundleDisplayName") as? String) ?? "App"
    }

    public static var onboardingImage: UIImage? { UIImage(systemName: "cross.vial.fill") }
    public var smallImage: UIImage? { UIImage(systemName: "cross.vial.fill") }

    public static func setupViewController(initialSettings settings: PumpManagerSetupSettings,
                                           bluetoothProvider: BluetoothProvider,
                                           colorPalette: LoopUIColorPalette,
                                           allowDebugFeatures: Bool,
                                           prefersToSkipUserInteraction: Bool,
                                           allowedInsulinTypes: [InsulinType]) -> SetupUIResult<PumpManagerViewController, PumpManagerUI> {
        var state = OpenPatchPumpManagerState()
        state.maxBasalRate = settings.maxBasalRateUnitsPerHour
        state.maxBolus = settings.maxBolusUnits
        state.basalSegments = settings.basalSchedule.items.map { BasalSegment(startOffset: $0.startTime, unitsPerHour: $0.value) }
        state.timeZoneIdentifier = settings.basalSchedule.timeZone.identifier
        state.insulinType = allowedInsulinTypes.first
        let manager = OpenPatchPumpManager(state: state)
        let coordinator = OpenPatchUICoordinator(manager: manager, mode: .setup, colorPalette: colorPalette,
                                                 allowDebugFeatures: allowDebugFeatures, allowedInsulinTypes: allowedInsulinTypes)
        return .userInteractionRequired(coordinator)
    }

    public func settingsViewController(bluetoothProvider: BluetoothProvider,
                                       colorPalette: LoopUIColorPalette,
                                       allowDebugFeatures: Bool,
                                       allowedInsulinTypes: [InsulinType]) -> PumpManagerViewController {
        OpenPatchUICoordinator(manager: self, mode: .settings, colorPalette: colorPalette,
                               allowDebugFeatures: allowDebugFeatures, allowedInsulinTypes: allowedInsulinTypes)
    }

    public func deliveryUncertaintyRecoveryViewController(colorPalette: LoopUIColorPalette,
                                                          allowDebugFeatures: Bool) -> (UIViewController & CompletionNotifying) {
        OpenPatchRecoveryViewController(manager: self, appName: appName)
    }

    public func hudProvider(bluetoothProvider: BluetoothProvider, colorPalette: LoopUIColorPalette,
                            allowedInsulinTypes: [InsulinType]) -> HUDProvider? { nil }

    public static func createHUDView(rawValue: HUDProvider.HUDViewRawState) -> BaseHUDView? { nil }
}

// MARK: - PumpStatusIndicator

extension OpenPatchPumpManager {
    public var pumpStatusHighlight: DeviceStatusHighlight? {
        let st = state
        if st.deliveryUncertainSince != nil {
            return PumpStatusHighlight(localizedMessage: L("Comms Issue"), imageName: "exclamationmark.circle.fill", state: .critical)
        }
        switch st.phase {
        case .faulted:
            return PumpStatusHighlight(localizedMessage: st.faultCode == .reservoirEmpty ? L("No Insulin") : L("Pump Error"),
                                       imageName: "exclamationmark.circle.fill", state: .critical)
        case .suspended:
            return PumpStatusHighlight(localizedMessage: L("Insulin Suspended"), imageName: "pause.circle.fill", state: .warning)
        case .deactivated:
            return PumpStatusHighlight(localizedMessage: L("No Pod"), imageName: "exclamationmark.circle.fill", state: .warning)
        default:
            return nil
        }
    }

    /// Reusable pod: no fixed lifetime. Reservoir level is shown instead of a progress bar.
    public var pumpLifecycleProgress: DeviceLifecycleProgress? { nil }
    public var pumpStatusBadge: DeviceStatusBadge? { nil }
}
