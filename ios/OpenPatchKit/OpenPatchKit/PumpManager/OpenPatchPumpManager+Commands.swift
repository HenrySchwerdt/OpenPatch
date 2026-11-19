import Foundation
import LoopKit
import OpenPatchCore

/// A failed command and whether the pod may nevertheless have executed it.
struct CommandFailure: Error {
    let error: OpenPatchError
    let deliveryUncertain: Bool
}

extension OpenPatchPumpManager {
    // MARK: Transport plumbing

    func ensureConnected(_ completion: @escaping (Result<Void, TransportError>) -> Void) {
        if transport.isConnected { return completion(.success(())) }
        transport.connect(completion: completion)
    }

    /// Connects if needed, sends one command and folds the returned pod status into the state.
    /// If the reply of a delivery-affecting command is lost the delivery state becomes uncertain.
    func send(_ command: Command, completion: @escaping (Result<PodStatus, CommandFailure>) -> Void) {
        ensureConnected { [weak self] connection in
            guard let self else { return }
            if case .failure(let error) = connection {
                return completion(.failure(CommandFailure(error: .transport(error), deliveryUncertain: false)))
            }
            self.transport.send(command) { [weak self] result in
                guard let self else { return }
                switch result {
                case .success(.ok(let status)):
                    self.reconcile(with: status, at: Date())
                    completion(.success(status))
                case .success(.rejected(let reason)):
                    completion(.failure(CommandFailure(error: .rejected(reason), deliveryUncertain: false)))
                case .failure(let error):
                    let lostReply = error == .timeout || error == .disconnected
                    let uncertain = command.affectsDelivery && lostReply
                    if uncertain { self.markUncertain(after: command) }
                    completion(.failure(CommandFailure(error: .transport(error), deliveryUncertain: uncertain)))
                }
            }
        }
    }

    // MARK: Error mapping

    static func map(_ error: OpenPatchError) -> PumpManagerError {
        switch error {
        case .transport(let t) where t == .notConnected || t == .bluetoothUnavailable:
            return .connection(error)
        case .transport(.notPaired), .transport(.sessionFailed), .needsPairing, .secretNotStored:
            return .deviceState(error)
        case .transport:
            return .communication(error)
        case .fillModeNotAllowed:
            return .configuration(error)
        case .deliveryUncertain:
            return .uncertainDelivery
        case .rejected, .notReady, .bolusInProgress, .suspended, .noBolusToCancel, .podFault, .calibration, .swapInProgress, .notActivePod:
            return .deviceState(error)
        case .swap(.unreachable), .swap(.ambiguous):
            return .communication(error)
        case .swap:
            return .deviceState(error)
        case .invalidAmount, .limit, .notConfigured, .fill:
            return .configuration(error)
        }
    }

    static func map(_ failure: CommandFailure) -> PumpManagerError {
        failure.deliveryUncertain ? .uncertainDelivery : map(failure.error)
    }
}
