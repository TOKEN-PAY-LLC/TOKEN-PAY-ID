import Foundation
#if canImport(UIKit)
import UIKit
#endif

/// Fire-and-forget telemetry with client-side PII scrub.
final class Telemetry: @unchecked Sendable {
    private let api: ApiClient
    private let clientId: String
    private let enabled: Bool
    private let queue = DispatchQueue(label: "space.tokenpay.id.telemetry", qos: .utility)
    private var sessionId: String = UUID().uuidString

    private let forbiddenKeys: Set<String> = [
        "email", "password", "code", "otp", "totp", "token", "secret", "phone",
        "card", "pan", "cvv", "ssn", "passport", "name", "full_name", "address",
        "refresh_token", "access_token", "id_token", "verifier",
    ]

    init(api: ApiClient, clientId: String, enabled: Bool) {
        self.api = api; self.clientId = clientId; self.enabled = enabled
    }

    func newSession(_ id: String = UUID().uuidString) {
        queue.async { self.sessionId = id }
    }

    func track(_ event: String, properties: [String: Any] = [:]) {
        guard enabled else { return }
        queue.async {
            var scrubbed: [String: Any] = [:]
            for (k, v) in properties where !self.forbiddenKeys.contains(k.lowercased()) {
                if let s = v as? String { scrubbed[k] = String(s.prefix(200)) }
                else if v is Bool || v is Int || v is Double { scrubbed[k] = v }
                else { scrubbed[k] = String(describing: v).prefix(200).description }
            }
            let payload: [String: Any] = [
                "event": event,
                "client_id": self.clientId,
                "session_id": self.sessionId,
                "sdk_version": TpidVersion.string,
                "platform": Self.platform(),
                "platform_version": Self.platformVersion(),
                "ts": Int(Date().timeIntervalSince1970 * 1000),
                "properties": scrubbed,
            ]
            Task { await self.api.sendTelemetry(event: payload) }
        }
    }

    private static func platform() -> String {
        #if os(iOS)
        return "ios"
        #elseif os(macOS)
        return "macos"
        #elseif os(tvOS)
        return "tvos"
        #elseif os(watchOS)
        return "watchos"
        #elseif os(visionOS)
        return "visionos"
        #else
        return "apple"
        #endif
    }

    private static func platformVersion() -> String {
        #if canImport(UIKit) && !os(watchOS)
        return UIDevice.current.systemVersion
        #else
        let v = ProcessInfo.processInfo.operatingSystemVersion
        return "\(v.majorVersion).\(v.minorVersion).\(v.patchVersion)"
        #endif
    }
}
