import Foundation

/// Entry point for TOKEN PAY ID SDK.
///
/// Call `TpidAuth.shared.initialize(config:)` once at app launch, then use
/// `TpidLoginButton` in SwiftUI or `TpidWidget.present(...)` programmatically.
public final class TpidAuth: @unchecked Sendable {

    public static let shared = TpidAuth()
    private init() {}

    internal struct State {
        let config: TpidConfig
        let api: ApiClient
        let storage: SecureStorage
        let telemetry: Telemetry
        let sdkConfigLoader: SdkConfigLoader
    }

    private let lock = NSLock()
    private var _state: State?

    internal var state: State? {
        lock.lock(); defer { lock.unlock() }
        return _state
    }

    /// Initialize the SDK. Safe to call multiple times; subsequent calls replace config.
    public func initialize(config: TpidConfig) {
        let storage = SecureStorage(clientId: config.clientId)
        let api = ApiClient(issuer: config.issuer, pinTLS: config.pinTLSCertificates, storage: storage)
        let telemetry = Telemetry(api: api, clientId: config.clientId, enabled: config.enableTelemetry)
        let loader = SdkConfigLoader(api: api, storage: storage)

        lock.lock()
        _state = State(config: config, api: api, storage: storage, telemetry: telemetry, sdkConfigLoader: loader)
        lock.unlock()

        Task { try? await loader.refreshConfig(clientId: config.clientId) }
    }

    internal func requireState() throws -> State {
        guard let s = state else {
            throw TpidError.configurationError(reason: "TpidAuth not initialized. Call TpidAuth.shared.initialize(config:) at app launch.")
        }
        return s
    }

    /// True if we have a cached, non-expired session.
    public var hasValidSession: Bool {
        guard let s = state, let session = s.storage.readSession() else { return false }
        return session.isValid
    }

    /// Return a valid access token, refreshing via refresh_token if needed. Returns nil if user is not signed in.
    public func getAccessToken() async throws -> String? {
        guard let s = state, let session = s.storage.readSession() else { return nil }
        if session.isValid { return session.accessToken }
        guard let refresh = session.refreshToken else { return nil }
        do {
            let refreshed = try await s.api.refreshToken(refreshToken: refresh, clientId: s.config.clientId)
            var newSession = refreshed
            if newSession.user.id.isEmpty { newSession = TpidSession(accessToken: refreshed.accessToken, refreshToken: refreshed.refreshToken, idToken: refreshed.idToken, expiresAt: refreshed.expiresAt, tokenType: refreshed.tokenType, scope: refreshed.scope, user: session.user) }
            try? s.storage.writeSession(newSession)
            return newSession.accessToken
        } catch {
            return nil
        }
    }

    /// Sign out, clearing the Keychain and optionally revoking server-side.
    public func signOut(revokeOnServer: Bool = true) {
        guard let s = state else { return }
        let tokens = s.storage.readSession()
        s.storage.clearSession()
        if revokeOnServer, let t = tokens?.refreshToken {
            Task { await s.api.revokeToken(t, clientId: s.config.clientId) }
        }
        s.telemetry.track("widget.sign_out")
    }

    /// Currently-stored user profile (from last successful login).
    public func currentUser() -> TpidUser? {
        state?.storage.readSession()?.user
    }

    // MARK: - Device Flow

    public func startDeviceFlow() async throws -> TpidDeviceFlowSession {
        let s = try requireState()
        let r = try await s.api.deviceAuthorize(clientId: s.config.clientId, scope: s.config.scopeString)
        return TpidDeviceFlowSession(
            deviceCode: r.deviceCode,
            userCode: r.userCode,
            verificationURI: r.verificationURI,
            verificationURIComplete: r.verificationURIComplete,
            expiresIn: r.expiresIn,
            interval: r.interval
        )
    }

    public func pollDeviceFlow(_ session: TpidDeviceFlowSession) async throws -> TpidSession {
        let s = try requireState()
        let result = try await s.api.pollDeviceToken(session: session, clientId: s.config.clientId)
        try? s.storage.writeSession(result)
        return result
    }
}
