import Foundation
@testable import OpenPatchCore

/// Plain-text pod stand-in for the transport tests that need a pod with a memory: it enforces the replay rule of the real pod
/// (a command whose `seq` is not above the highest accepted one is dropped without any answer) and reports `LAST_SEQ`.
final class WirePodLink: FrameLink {
    var isConnected = true
    var requests: [V1.Message] = []
    /// Highest `seq` the pod accepted (persisted across the pod's reboots in the real firmware).
    var lastAccepted: UInt16 = 0
    /// `true`: answer a replayed frame with the `REPLAY` result instead of dropping it (some pods may).
    var answersReplay = false
    /// What the status reports as `LAST_SEQ` (default: the highest accepted).
    var lastSeqOverride: UInt16?
    /// Results by command type (default OK).
    var resultFor: [UInt8: V1.Result] = [:]
    /// Drop every Nth... simply: drop the next request(s) silently (the phone sees a timeout).
    var dropNext = 0
    var calibration: DriveCalibration? = .nfp608_26_45_cupMiter1_1
    var flags: UInt16 = V1.StateFlags.suspended.rawValue
    var reservoirMU: UInt32 = 0
    var drawState: UInt8?
    var drawRequestedMU: UInt32 = 0
    var drawDoneMU: UInt32 = 0
    var history: [V1.HistoryEvent] = []
    var nextEventID: UInt32 = 1
    var bolusRemainingMU: UInt32 = 0
    var tempRateMUh: UInt16 = 0
    var tempRemainingMin: UInt16 = 0

    func connect(completion: @escaping (Result<Void, TransportError>) -> Void) { isConnected = true; completion(.success(())) }
    func disconnect() { isConnected = false }

    func exchange(frame: Data, seq: UInt16, completion: @escaping (Result<Data, TransportError>) -> Void) {
        let request = try! V1.decode(frame)
        requests.append(request)
        if dropNext > 0 { dropNext -= 1; return completion(.failure(.timeout)) }
        if request.seq <= lastAccepted {
            if !answersReplay { return completion(.failure(.timeout)) }
            return completion(.success(V1.encode(V1.Message(type: request.type | V1.responseFlag, flags: V1.flagResponse, seq: request.seq,
                                                            tlvs: [V1.TLV(.result, u8: V1.Result.replay.rawValue)]))))
        }
        lastAccepted = request.seq
        var tlvs = [V1.TLV(.result, u8: (resultFor[request.type] ?? .ok).rawValue)]
        switch request.type {
        case V1.CommandID.getStatus.rawValue:
            tlvs += [V1.TLV(.stateFlags, u16: flags), V1.TLV(.reservoirMU, u32: reservoirMU), V1.TLV(.batteryMV, u16: 3_900),
                     V1.TLV(.bolusRemainingMU, u32: bolusRemainingMU), V1.TLV(.tempRateMUh, u16: tempRateMUh),
                     V1.TLV(.tempRemainingMin, u16: tempRemainingMin), V1.TLV(.deliveredMU, u32: 0), V1.TLV(.faultMask, u16: 0),
                     V1.TLV(.nextEventID, u32: nextEventID), V1.TLV(.lastSeq, u16: lastSeqOverride ?? lastAccepted)]
            if let cal = calibration {
                var w = ByteWriter()
                w.u16(cal.driveID); w.u32(cal.microUnitsPerStep); w.u16(cal.stepsPerRevolution); w.u16(cal.gearRatioTimes100)
                tlvs.append(V1.TLV(tag: V1.Tag.driveCal.rawValue, value: w.bytes))
            }
            if let state = drawState {
                tlvs += [V1.TLV(.drawState, u8: state), V1.TLV(.drawRequestedMU, u32: drawRequestedMU), V1.TLV(.drawDoneMU, u32: drawDoneMU)]
            }
        case V1.CommandID.getHistory.rawValue:
            let from = request.u32(.fromID) ?? 0
            tlvs += history.filter { $0.id >= from }.prefix(V1.historyPageSize).map { V1.TLV(tag: V1.Tag.historyEvent.rawValue, value: $0.bytes) }
            tlvs.append(V1.TLV(.nextEventID, u32: nextEventID))
        default: break
        }
        completion(.success(V1.encode(V1.Message(type: request.type | V1.responseFlag, flags: V1.flagResponse, seq: request.seq, tlvs: tlvs))))
    }

    func requests(of id: V1.CommandID) -> [V1.Message] { requests.filter { $0.type == id.rawValue } }
}
