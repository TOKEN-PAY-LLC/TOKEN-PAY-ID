import Foundation

/// Loads + caches /sdk/config — branding, TLS pins, endpoints.
final class SdkConfigLoader: @unchecked Sendable {
    private let api: ApiClient
    private let storage: SecureStorage

    init(api: ApiClient, storage: SecureStorage) {
        self.api = api; self.storage = storage
    }

    @discardableResult
    func refreshConfig(clientId: String) async throws -> TpidConfig.Branding? {
        let obj = try await api.fetchSdkConfig(clientId: clientId)
        if let data = try? JSONSerialization.data(withJSONObject: obj) {
            storage.setString(String(data: data, encoding: .utf8), forKey: StorageKeys.sdkConfig)
            storage.setDate(Date(), forKey: StorageKeys.sdkConfigFetched)
        }
        // Extract TLS pins if server returned them inline in sdk/config
        if let tls = obj["tls_pinning"] as? [String: Any],
           let pins = tls["pins"] as? [String], !pins.isEmpty {
            api.refreshPins(pins)
        } else if let pins = obj["tls_pins"] as? [String], !pins.isEmpty {
            api.refreshPins(pins)
        } else if let pins = try? await api.fetchTlsPins() {
            api.refreshPins(pins)
        }
        return Self.parseBranding(obj["branding"] as? [String: Any])
    }

    func cachedBranding() -> TpidConfig.Branding? {
        guard let raw = storage.getString(forKey: StorageKeys.sdkConfig),
              let obj = try? JSONSerialization.jsonObject(with: Data(raw.utf8)) as? [String: Any] else { return nil }
        return Self.parseBranding(obj["branding"] as? [String: Any])
    }

    private static func parseBranding(_ br: [String: Any]?) -> TpidConfig.Branding? {
        guard let br else { return nil }
        return TpidConfig.Branding(
            logoURL: ((br["logo_url"] ?? br["logo_uri"] ?? br["app_icon_url"]) as? String)
                .flatMap(URL.init(string:)),
            primaryColorHex: br["primary_color"] as? String,
            appName: (br["app_name"] ?? br["client_name"]) as? String,
            appDomain: (br["app_domain"] ?? br["client_uri"]) as? String
        )
    }
}
