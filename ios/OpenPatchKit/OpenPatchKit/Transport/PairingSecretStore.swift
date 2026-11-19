import Foundation
import Security

/// Where the application layer pairing secret (32 bytes, docs/04-protocol.md section 4.1) of each pod lives. It must never be part of
/// `rawState` (that goes into Trio's persisted manager state and backups): one item per physical pod, keyed by the pod's
/// peripheral identifier, in the keychain of THIS device only.
public protocol PairingSecretStore: AnyObject {
    func secret(for podKey: String) -> [UInt8]?
    func save(_ secret: [UInt8], for podKey: String) throws
    func remove(for podKey: String)
}

public struct PairingSecretStoreError: Error, Equatable { public let status: OSStatus }

/// iOS keychain: generic password items, `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly` (readable by the background
/// Bluetooth wake-ups while the phone is locked, never restored to another device).
public final class KeychainPairingSecretStore: PairingSecretStore {
    public static let service = "org.openpatch.pairing-secret"
    private let service: String

    public init(service: String = KeychainPairingSecretStore.service) { self.service = service }

    private func query(_ podKey: String) -> [String: Any] {
        [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: podKey]
    }

    public func secret(for podKey: String) -> [UInt8]? {
        var q = query(podKey)
        q[kSecReturnData as String] = true
        q[kSecMatchLimit as String] = kSecMatchLimitOne
        var item: CFTypeRef?
        guard SecItemCopyMatching(q as CFDictionary, &item) == errSecSuccess, let data = item as? Data, data.count == 32 else { return nil }
        return [UInt8](data)
    }

    public func save(_ secret: [UInt8], for podKey: String) throws {
        let data = Data(secret)
        let status = SecItemUpdate(query(podKey) as CFDictionary, [kSecValueData as String: data] as CFDictionary)
        if status == errSecSuccess { return }
        guard status == errSecItemNotFound else { throw PairingSecretStoreError(status: status) }
        var add = query(podKey)
        add[kSecValueData as String] = data
        add[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        let added = SecItemAdd(add as CFDictionary, nil)
        guard added == errSecSuccess else { throw PairingSecretStoreError(status: added) }
    }

    public func remove(for podKey: String) { SecItemDelete(query(podKey) as CFDictionary) }
}

/// For tests, previews and the simulated pod.
public final class InMemoryPairingSecretStore: PairingSecretStore {
    private let lock = NSLock()
    private var secrets: [String: [UInt8]] = [:]
    public init() {}

    public func secret(for podKey: String) -> [UInt8]? { lock.lock(); defer { lock.unlock() }; return secrets[podKey] }
    public func save(_ secret: [UInt8], for podKey: String) throws { lock.lock(); secrets[podKey] = secret; lock.unlock() }
    public func remove(for podKey: String) { lock.lock(); secrets[podKey] = nil; lock.unlock() }
}
