import Foundation

public struct BasalSegment: Equatable, Codable {
    public let startOffset: TimeInterval
    public let unitsPerHour: Double
    public init(startOffset: TimeInterval, unitsPerHour: Double) {
        self.startOffset = startOffset
        self.unitsPerHour = unitsPerHour
    }
}

public enum BasalProgramError: Error, Equatable {
    case empty
    case firstSegmentMustStartAtMidnight
    case misaligned
    case notAscending
    case rateTooHigh
    case wrongSlotCount
}

/// 48 half-hour slots, each holding a rate in 0.05 U/h ticks. This is exactly what goes over the wire.
public struct BasalProgram: Equatable, Codable {
    public let slots: [UInt16]

    public init(slots: [UInt16]) throws {
        guard slots.count == PumpConstants.basalSlotCount else { throw BasalProgramError.wrongSlotCount }
        self.slots = slots
    }

    public init(segments: [BasalSegment], limits: SafetyLimits = .default) throws {
        guard let first = segments.first else { throw BasalProgramError.empty }
        guard first.startOffset == 0 else { throw BasalProgramError.firstSegmentMustStartAtMidnight }
        var previous: TimeInterval = -1
        for segment in segments {
            guard segment.startOffset.truncatingRemainder(dividingBy: PumpConstants.basalSlotDuration) == 0 else { throw BasalProgramError.misaligned }
            guard segment.startOffset > previous else { throw BasalProgramError.notAscending }
            guard segment.unitsPerHour <= limits.maxBasalRate + 1e-9 else { throw BasalProgramError.rateTooHigh }
            previous = segment.startOffset
        }
        var slots = [UInt16](repeating: 0, count: PumpConstants.basalSlotCount)
        for (index, segment) in segments.enumerated() {
            let startSlot = Int(segment.startOffset / PumpConstants.basalSlotDuration)
            let endSlot = index + 1 < segments.count ? Int(segments[index + 1].startOffset / PumpConstants.basalSlotDuration) : PumpConstants.basalSlotCount
            guard startSlot < PumpConstants.basalSlotCount else { throw BasalProgramError.misaligned }
            let ticks = UInt16(UnitConversion.pulses(forUnits: segment.unitsPerHour))
            for slot in startSlot..<min(endSlot, PumpConstants.basalSlotCount) { slots[slot] = ticks }
        }
        self.slots = slots
    }

    public static func constant(unitsPerHour: Double) throws -> BasalProgram {
        try BasalProgram(segments: [BasalSegment(startOffset: 0, unitsPerHour: unitsPerHour)], limits: SafetyLimits(maxBolus: 0, maxBasalRate: SafetyLimits.absoluteMaxBasalRate))
    }

    private func slotIndex(atOffset offset: TimeInterval) -> Int {
        let day = offset.truncatingRemainder(dividingBy: 86_400)
        let positive = day < 0 ? day + 86_400 : day
        return min(Int(positive / PumpConstants.basalSlotDuration), PumpConstants.basalSlotCount - 1)
    }

    public func unitsPerHour(atOffset offset: TimeInterval) -> Double {
        UnitConversion.units(forPulses: Int(slots[slotIndex(atOffset: offset)]))
    }

    /// Insulin scheduled over `duration` seconds starting at the given offset from local midnight (wraps).
    public func unitsDelivered(fromOffset offset: TimeInterval, duration: TimeInterval) -> Double {
        var remaining = duration
        var cursor = offset
        var total = 0.0
        while remaining > 1e-9 {
            let intoSlot = cursor.truncatingRemainder(dividingBy: PumpConstants.basalSlotDuration)
            let chunk = min(PumpConstants.basalSlotDuration - intoSlot, remaining)
            total += unitsPerHour(atOffset: cursor) * chunk / 3600
            cursor += chunk
            remaining -= chunk
        }
        return total
    }

    public var dailyTotal: Double { unitsDelivered(fromOffset: 0, duration: 86_400) }

    /// Back to segments (merges equal neighbours) - used by the UI.
    public var segments: [BasalSegment] {
        var result: [BasalSegment] = []
        for (index, ticks) in slots.enumerated() where result.isEmpty || UnitConversion.pulses(forUnits: result.last!.unitsPerHour) != Int(ticks) {
            result.append(BasalSegment(startOffset: Double(index) * PumpConstants.basalSlotDuration, unitsPerHour: UnitConversion.units(forPulses: Int(ticks))))
        }
        return result
    }
}
