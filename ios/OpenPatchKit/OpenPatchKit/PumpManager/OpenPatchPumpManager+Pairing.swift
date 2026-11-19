import Foundation
import OpenPatchCore

/// Application layer pairing (docs/04-protocol.md section 5.1): once per pod, with the button pressed, creates the 32 byte pairing
/// secret that every later connection uses for its session key agreement. The secret lives in the keychain, never in `rawState`.
extension OpenPatchPumpManager {
    /// Creates the pairing secret of the pod behind `transport` unless one is stored already. Simulated pods and
    /// transports that are not `V1Transport` (tests) need none.
    func ensurePairingSecret(on transport: OpenPatchTransport, peripheral: UUID?, simulated: Bool, completion: @escaping (Error?) -> Void) {
        guard !simulated, let v1 = transport as? V1Transport, let key = peripheral?.uuidString else { return completion(nil) }
        if Self.pairingSecretStore.secret(for: key) != nil { return completion(nil) }
        createPairingSecret(on: v1, key: key, completion: completion)
    }

    private func createPairingSecret(on v1: V1Transport, key: String, completion: @escaping (Error?) -> Void) {
        let pairIt = {
            v1.pair { result in
                switch result {
                case .failure(let error):
                    // `.sessionFailed` here = the pairing window is closed or the exchange was altered: ask for the button
                    completion(error == .sessionFailed ? OpenPatchError.needsPairing : OpenPatchError.transport(error))
                case .success(let secret):
                    do { try Self.pairingSecretStore.save(secret, for: key); completion(nil) } catch { completion(OpenPatchError.secretNotStored) }
                }
            }
        }
        if v1.isConnected { return pairIt() }
        v1.connect { result in
            if case .failure(let error) = result { return completion(OpenPatchError.transport(error)) }
            pairIt()
        }
    }

    /// Pairs the pod of the active transport again (the user pressed its button): replaces the stored secret. For a pod that was
    /// reset or paired by another phone.
    public func pairAgain(completion: @escaping (Error?) -> Void) {
        guard let v1 = transport as? V1Transport, let key = Self.podKey(for: state) else { return completion(nil) }
        v1.setPairingSecret(nil)
        createPairingSecret(on: v1, key: key, completion: completion)
    }

    /// Whether this pod has a pairing secret on this phone (shown in the settings).
    public var isPodPaired: Bool {
        guard let key = Self.podKey(for: state) else { return state.usesSimulatedPod }
        return Self.pairingSecretStore.secret(for: key) != nil
    }

    /// The secured session of the current connection is up (shown in the settings).
    public var hasSecureSession: Bool { (transport as? V1Transport)?.hasSession ?? false }
}
