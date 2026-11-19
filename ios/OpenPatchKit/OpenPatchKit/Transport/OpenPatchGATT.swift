import CoreBluetooth
import OpenPatchCore

/// GATT layout of the OpenPatch pod, from firmware/docs/openpatch-protocol.md section 1.
public enum OpenPatchGATT {
    public static let service = CBUUID(string: "2E092A48-506C-477E-ADD4-448BF1490001")
    /// Phone -> pod. Write / Write Without Response. Exactly one protocol frame per write.
    public static let commandCharacteristic = CBUUID(string: "2E092A48-506C-477E-ADD4-448BF1490002")
    /// Pod -> phone. Notify. Exactly one protocol frame per notification.
    public static let responseCharacteristic = CBUUID(string: "2E092A48-506C-477E-ADD4-448BF1490003")
    /// Pod -> phone, notify (optional): unsolicited frames of type 0x90 (draw progress, faults, diagnostics). Alarms and doses are
    /// still read by polling status and history: a notification can be lost.
    public static let alertCharacteristic = CBUUID(string: "2E092A48-506C-477E-ADD4-448BF1490004")

    /// Advertised name is `OpenPatch-XXXX` (last 4 hex digits of the address).
    public static let advertisedNamePrefix = "OpenPatch"
    public static let restorationIdentifier = "org.openpatch.central"
    public static let responseTimeout: TimeInterval = 8
    public static let connectTimeout: TimeInterval = 20
    /// Frames are not fragmented: the negotiated ATT payload must hold a full frame (MTU >= 247).
    public static let requiredWritePayload = V1.maxFrameSize
}
