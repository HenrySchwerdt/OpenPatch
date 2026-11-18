import Foundation
import LoopKit

/// Bolus progress for Loop's UI, estimated from the commanded rate (1.5 U/min). Ticks once per second.
final class OpenPatchDoseProgressReporter: DoseProgressReporter {
    private let dose: OpenPatchDose
    private let queue: DispatchQueue
    private let observers = WeakSynchronizedSet<DoseProgressObserver>()
    private var timerRunning = false
    private let lock = NSLock()

    init(dose: OpenPatchDose, reportingQueue: DispatchQueue) {
        self.dose = dose
        self.queue = reportingQueue
    }

    var progress: DoseProgress {
        let delivered = dose.deliveredUnits()
        return DoseProgress(deliveredUnits: delivered, percentComplete: dose.units > 0 ? min(delivered / dose.units, 1) : 1)
    }

    func addObserver(_ observer: DoseProgressObserver) {
        observers.insert(observer, queue: queue)
        lock.lock(); defer { lock.unlock() }
        guard !timerRunning else { return }
        timerRunning = true
        tick()
    }

    func removeObserver(_ observer: DoseProgressObserver) { observers.removeElement(observer) }

    private func tick() {
        queue.asyncAfter(deadline: .now() + 1) { [weak self] in
            guard let self else { return }
            self.observers.forEach { $0.doseProgressReporterDidUpdate(self) }
            if self.progress.isComplete {
                self.lock.lock(); self.timerRunning = false; self.lock.unlock()
            } else {
                self.tick()
            }
        }
    }
}
