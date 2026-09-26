import Foundation
import Security

/// Persistent, Keychain-backed storage for tokens and SDK state.
final class SecureStorage: @unchecked Sendable {
    private let serviceName: String
    private let account: String

    init(clientId: String) {
        self.serviceName = "space.tokenpay.id"
        self.account = "tpid.\(clientId.suffix(24))"
    }

    // MARK: - Tokens

    struct StoredTokens: Codable, Sendable {
        let session: TpidSession
    }

    func writeSession(_ session: TpidSession) throws {
        let data = try JSONEncoder().encode(StoredTokens(session: session))
        try writeKeychain(key: "tokens", data: data)
    }

    func readSession() -> TpidSession? {
        guard let data = readKeychain(key: "tokens"),
              let wrapper = try? JSONDecoder().decode(StoredTokens.self, from: data) else { return nil }
        return wrapper.session
    }

    func clearSession() { try? deleteKeychain(key: "tokens") }

    // MARK: - Account memory (2.6.0)

    /// Minimal profile kept across sign-outs so the widget can open with a
    /// "Continue as X" card instead of an empty email field on the next
    /// launch. Deliberately a subset of `TpidSession.user` — no tokens, no
    /// scopes — so it is safe to preserve when the user explicitly signs out.
    struct LastAccount: Codable, Sendable, Equatable {
        let email: String
        let displayName: String?
        let avatarUrl: String?
        let lastAuthenticatedAt: Date?
    }

    func writeLastAccount(_ account: LastAccount) {
        guard let data = try? JSONEncoder().encode(account) else { return }
        try? writeKeychain(key: "last-account", data: data)
    }

    func readLastAccount() -> LastAccount? {
        guard let data = readKeychain(key: "last-account") else { return nil }
        return try? JSONDecoder().decode(LastAccount.self, from: data)
    }

    func clearLastAccount() { try? deleteKeychain(key: "last-account") }

    // MARK: - PKCE

    struct PendingPKCE: Codable { let verifier: String; let state: String; let nonce: String }

    func writePKCE(verifier: String, state: String, nonce: String) throws {
        let data = try JSONEncoder().encode(PendingPKCE(verifier: verifier, state: state, nonce: nonce))
        try writeKeychain(key: "pkce", data: data)
    }

    func readPKCE() -> PendingPKCE? {
        guard let data = readKeychain(key: "pkce") else { return nil }
        return try? JSONDecoder().decode(PendingPKCE.self, from: data)
    }

    func clearPKCE() { try? deleteKeychain(key: "pkce") }

    // MARK: - Generic kv (non-secret)

    private let userDefaults = UserDefaults(suiteName: "space.tokenpay.id") ?? .standard

    func setString(_ value: String?, forKey key: String) {
        if let value { userDefaults.set(value, forKey: key) }
        else { userDefaults.removeObject(forKey: key) }
    }
    func getString(forKey key: String) -> String? { userDefaults.string(forKey: key) }
    func setDate(_ d: Date, forKey key: String) { userDefaults.set(d.timeIntervalSince1970, forKey: key) }
    func getDate(forKey key: String) -> Date? {
        let ts = userDefaults.double(forKey: key)
        return ts > 0 ? Date(timeIntervalSince1970: ts) : nil
    }

    // MARK: - Keychain primitives

    private func keychainQuery(key: String) -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: "\(account).\(key)",
        ]
    }

    private func writeKeychain(key: String, data: Data) throws {
        var q = keychainQuery(key: key)
        SecItemDelete(q as CFDictionary)
        q[kSecValueData as String] = data
        q[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        let status = SecItemAdd(q as CFDictionary, nil)
        guard status == errSecSuccess else {
            throw TpidError.configurationError(reason: "Keychain write failed: \(status)")
        }
    }

    private func readKeychain(key: String) -> Data? {
        var q = keychainQuery(key: key)
        q[kSecReturnData as String] = true
        q[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: AnyObject?
        let status = SecItemCopyMatching(q as CFDictionary, &result)
        return status == errSecSuccess ? (result as? Data) : nil
    }

    private func deleteKeychain(key: String) throws {
        let q = keychainQuery(key: key)
        let status = SecItemDelete(q as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw TpidError.configurationError(reason: "Keychain delete failed: \(status)")
        }
    }
}

// MARK: - UserDefaults keys (shared)

enum StorageKeys {
    static let tlsPins = "tpid.tls.pins"
    static let tlsPinsFetched = "tpid.tls.pins.ts"
    static let sdkConfig = "tpid.sdk.config"
    static let sdkConfigFetched = "tpid.sdk.config.ts"
    static let sessionVersion = "tpid.session.version"
}
