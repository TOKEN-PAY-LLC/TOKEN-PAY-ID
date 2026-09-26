import Foundation
import CryptoKit

#if canImport(UIKit)
import UIKit
#elseif canImport(AppKit)
import AppKit
#endif

/// Typed responses for TOKEN PAY ID endpoints.
enum TpidEndpoints {
    struct AccountCheckResponse: Decodable, Sendable {
        let exists: Bool
        let methods: [String]
        let suggestedNextStep: String
        let hasPasskey: Bool
        let has2FA: Bool

        enum CodingKeys: String, CodingKey {
            case exists, methods
            case suggestedNextStep = "suggested_next_step"
            case hasPasskey = "has_passkey"
            case has2FA = "has_2fa"
        }
    }

    struct DeviceAuthResponse: Decodable, Sendable {
        let deviceCode: String
        let userCode: String
        let verificationURI: URL
        let verificationURIComplete: URL
        let expiresIn: Int
        let interval: Int

        enum CodingKeys: String, CodingKey {
            case deviceCode = "device_code"
            case userCode = "user_code"
            case verificationURI = "verification_uri"
            case verificationURIComplete = "verification_uri_complete"
            case expiresIn = "expires_in"
            case interval
        }
    }

    struct TokenResponse: Decodable, Sendable {
        let accessToken: String
        let refreshToken: String?
        let idToken: String?
        let expiresIn: Int
        let tokenType: String?
        let scope: String?
        let user: TpidUser?

        enum CodingKeys: String, CodingKey {
            case accessToken = "access_token"
            case refreshToken = "refresh_token"
            case idToken = "id_token"
            case expiresIn = "expires_in"
            case tokenType = "token_type"
            case scope, user
        }
    }
}

/// Thin HTTP client wrapping URLSession with optional SPKI pinning.
final class ApiClient: NSObject, URLSessionDelegate, @unchecked Sendable {
    private let issuer: URL
    private let storage: SecureStorage
    private let pinTLS: Bool
    private var pinnedSPKIs: Set<Data> = []
    private let pinMismatchLock = NSLock()
    private var rejectedPinHost: String?
    var hasActivePins: Bool { pinTLS && !pinnedSPKIs.isEmpty }

    private lazy var session: URLSession = {
        let cfg = URLSessionConfiguration.ephemeral
        cfg.timeoutIntervalForRequest = 30
        cfg.timeoutIntervalForResource = 60
        cfg.waitsForConnectivity = false
        cfg.httpMaximumConnectionsPerHost = 4
        cfg.httpAdditionalHeaders = [
            "User-Agent": Self.userAgent(),
            "Accept": "application/json",
            "X-TPID-SDK": "swift:\(TpidVersion.string)",
        ]
        return URLSession(configuration: cfg, delegate: self, delegateQueue: nil)
    }()

    init(issuer: URL, pinTLS: Bool, storage: SecureStorage) {
        self.issuer = issuer
        self.storage = storage
        self.pinTLS = pinTLS
        super.init()
        if pinTLS { loadCachedPins() }
    }

    private func loadCachedPins() {
        guard let raw = storage.getString(forKey: StorageKeys.tlsPins),
              let arr = try? JSONSerialization.jsonObject(with: Data(raw.utf8)) as? [String] else { return }
        pinnedSPKIs = Set(arr.compactMap { Data(base64Encoded: $0) }.filter { $0.count == 32 })
    }

    func refreshPins(_ pins: [String]) {
        let valid = pins.filter { Data(base64Encoded: $0)?.count == 32 }
        pinnedSPKIs = Set(valid.compactMap { Data(base64Encoded: $0) })
        let payload = try? JSONSerialization.data(withJSONObject: valid)
        storage.setString(payload.flatMap { String(data: $0, encoding: .utf8) }, forKey: StorageKeys.tlsPins)
        storage.setDate(Date(), forKey: StorageKeys.tlsPinsFetched)
    }

    // MARK: - URLSessionDelegate (pinning)

    func urlSession(_ session: URLSession,
                    didReceive challenge: URLAuthenticationChallenge,
                    completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void) {
        guard pinTLS,
              !pinnedSPKIs.isEmpty,
              challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
              let serverTrust = challenge.protectionSpace.serverTrust else {
            completionHandler(.performDefaultHandling, nil)
            return
        }
        // Evaluate default trust first
        var error: CFError?
        guard SecTrustEvaluateWithError(serverTrust, &error) else {
            completionHandler(.cancelAuthenticationChallenge, nil); return
        }
        // Walk the chain and check SPKI pins
        let count = SecTrustGetCertificateCount(serverTrust)
        for i in 0..<count {
            guard let cert = SecTrustGetCertificateAtIndex(serverTrust, i),
                  let spki = Self.spkiHash(of: cert) else { continue }
            if pinnedSPKIs.contains(spki) {
                completionHandler(.useCredential, URLCredential(trust: serverTrust))
                return
            }
        }
        // No pin matched → possible MITM
        pinMismatchLock.lock()
        rejectedPinHost = challenge.protectionSpace.host
        pinMismatchLock.unlock()
        completionHandler(.cancelAuthenticationChallenge, nil)
    }

    /// Hash the complete DER SubjectPublicKeyInfo, including its algorithm identifier.
    /// SecKeyCopyExternalRepresentation returns only the key bytes and is not an SPKI pin.
    private static func spkiHash(of certificate: SecCertificate) -> Data? {
        let bytes = [UInt8](SecCertificateCopyData(certificate) as Data)
        typealias Element = (tag: UInt8, content: Int, end: Int)

        func element(at offset: Int, limit: Int) -> Element? {
            guard offset >= 0, offset + 2 <= limit, limit <= bytes.count else { return nil }
            let tag = bytes[offset]
            let lengthByte = Int(bytes[offset + 1])
            var content = offset + 2
            var length = 0
            if lengthByte & 0x80 == 0 {
                length = lengthByte
            } else {
                let count = lengthByte & 0x7f
                guard count > 0, count <= 4, content + count <= limit else { return nil }
                for index in 0..<count { length = (length << 8) | Int(bytes[content + index]) }
                content += count
            }
            guard length <= limit - content else { return nil }
            return (tag, content, content + length)
        }

        guard let certificateSequence = element(at: 0, limit: bytes.count),
              certificateSequence.tag == 0x30,
              let tbs = element(at: certificateSequence.content, limit: certificateSequence.end),
              tbs.tag == 0x30 else { return nil }

        var cursor = tbs.content
        if let version = element(at: cursor, limit: tbs.end), version.tag == 0xa0 {
            cursor = version.end
        }
        // TBSCertificate: serialNumber, signature, issuer, validity, subject, SPKI.
        for _ in 0..<5 {
            guard let field = element(at: cursor, limit: tbs.end) else { return nil }
            cursor = field.end
        }
        guard let spki = element(at: cursor, limit: tbs.end), spki.tag == 0x30 else { return nil }
        return Data(SHA256.hash(data: Data(bytes[cursor..<spki.end])))
    }

    // MARK: - HTTP helpers

    private func buildRequest(path: String, method: String, jsonBody: [String: Any]? = nil) throws -> URLRequest {
        var url = issuer
        url.appendPathComponent(path.hasPrefix("/") ? String(path.dropFirst()) : path)
        var req = URLRequest(url: url)
        req.httpMethod = method
        if let jsonBody {
            req.httpBody = try JSONSerialization.data(withJSONObject: jsonBody)
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        return req
    }

    private func send(_ req: URLRequest) async throws -> (Data, HTTPURLResponse) {
        do {
            let (data, response) = try await session.data(for: req)
            guard let http = response as? HTTPURLResponse else {
                throw TpidError.unknown(underlying: nil)
            }
            return (data, http)
        } catch let err as URLError {
            switch err.code {
            case .cancelled:
                pinMismatchLock.lock()
                let rejected = rejectedPinHost == req.url?.host
                if rejected { rejectedPinHost = nil }
                pinMismatchLock.unlock()
                if rejected {
                    storage.clearSession()
                    throw TpidError.phishingDetected(host: req.url?.host ?? "unknown")
                }
                throw TpidError.userCancelled
            case .secureConnectionFailed, .serverCertificateUntrusted,
                 .serverCertificateHasBadDate, .serverCertificateNotYetValid,
                 .serverCertificateHasUnknownRoot, .clientCertificateRequired:
                storage.clearSession()
                throw TpidError.phishingDetected(host: req.url?.host ?? "unknown")
            case .notConnectedToInternet, .networkConnectionLost, .cannotFindHost, .cannotConnectToHost:
                throw TpidError.noNetwork
            case .timedOut:
                throw TpidError.timeout
            default:
                throw TpidError.unknown(underlying: err)
            }
        }
    }

    private func parseError(_ data: Data, _ http: HTTPURLResponse) -> TpidError {
        let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
        let err = obj?["error"] as? String
        let msg = obj?["error_description"] as? String ?? obj?["message"] as? String

        switch http.statusCode {
        case 401:  return .invalidCredentials(reason: msg)
        case 403 where err == "email_not_verified": return .emailNotVerified
        case 423:  return .accountLocked(until: obj?["locked_until"] as? String)
        case 428:  return .twoFactorRequired(methods: (obj?["methods"] as? [String]) ?? ["totp"])
        case 429:
            let retry = (http.value(forHTTPHeaderField: "Retry-After").flatMap(Int.init))
                     ?? (obj?["retry_after"] as? Int) ?? 60
            return .rateLimited(retryAfterSec: retry)
        case 500...599: return .serverError(status: http.statusCode, reason: msg)
        default:
            if let err { return .oauthError(code: err, description: msg) }
            return .serverError(status: http.statusCode, reason: msg)
        }
    }

    // MARK: - Endpoints

    func fetchSdkConfig(clientId: String?) async throws -> [String: Any] {
        var path = "/api/v1/sdk/config"
        if let clientId { path += "?client_id=\(clientId)" }
        var req = try buildRequest(path: path, method: "GET")
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        let (data, http) = try await send(req)
        guard 200..<300 ~= http.statusCode else { throw parseError(data, http) }
        return (try JSONSerialization.jsonObject(with: data) as? [String: Any]) ?? [:]
    }

    func fetchTlsPins() async throws -> [String] {
        let req = try buildRequest(path: "/api/v1/sdk/tls-pins", method: "GET")
        let (data, http) = try await send(req)
        guard 200..<300 ~= http.statusCode else { throw parseError(data, http) }
        let obj = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        return obj?["pins"] as? [String] ?? []
    }

    func accountCheck(email: String, clientId: String) async throws -> TpidEndpoints.AccountCheckResponse {
        let req = try buildRequest(
            path: "/api/v1/auth/account-check",
            method: "POST",
            jsonBody: ["email": email, "client_id": clientId]
        )
        let (data, http) = try await send(req)
        guard 200..<300 ~= http.statusCode else { throw parseError(data, http) }
        return try JSONDecoder().decode(TpidEndpoints.AccountCheckResponse.self, from: data)
    }

    /// Result of a single `/auth/login` call.
    ///
    /// The backend requires every password login to also clear an e-mail OTP
    /// second factor, and optionally a TOTP — so the endpoint is effectively a
    /// state machine that this ADT captures:
    /// - `.requiresEmailCode` — server just sent a fresh 6-digit code to the
    ///   user's mailbox; replay the call with `emailCode` filled in.
    /// - `.requiresTwoFactor` — e-mail code was accepted; replay with
    ///   `twoFactorCode` filled in as well.
    /// - `.success` — login is complete, tokens attached.
    enum LoginOutcome: Sendable {
        case requiresEmailCode(requires2FA: Bool)
        case requiresTwoFactor(emailCodeVerified: Bool)
        case success(TpidSession)
    }

    /// POST /api/v1/auth/login.
    ///
    /// Historically the SDK treated this as an OAuth "authorization code"
    /// endpoint and called [exchangeCode] with the returned `code` — but the
    /// real backend never exposed a code flow here. On success it returns
    /// `{accessToken, refreshToken, user, session_id}` directly, and on the
    /// first call (no `email_code` yet) it replies with
    /// `{requires_email_code: true}` after auto-sending a verification
    /// e-mail. The widget calls this three times at most:
    /// 1. `{email, password}` → `.requiresEmailCode`
    /// 2. `{email, password, email_code}` → `.success` or `.requiresTwoFactor`
    /// 3. `{email, password, email_code, two_factor_code}` → `.success`
    func login(email: String, password: String, clientId: String,
               emailCode: String? = nil, twoFactorCode: String? = nil,
               lang: String? = nil) async throws -> LoginOutcome {
        var body: [String: Any] = [
            "email": email,
            "password": password,
            "client_id": clientId,
        ]
        if let emailCode, !emailCode.isEmpty { body["email_code"] = emailCode }
        if let twoFactorCode, !twoFactorCode.isEmpty { body["two_factor_code"] = twoFactorCode }
        if let lang, !lang.isEmpty { body["lang"] = lang }
        let req = try buildRequest(path: "/api/v1/auth/login", method: "POST", jsonBody: body)
        let (data, http) = try await send(req)
        guard 200..<300 ~= http.statusCode else { throw parseError(data, http) }
        let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] ?? [:]
        if (obj["requires_email_code"] as? Bool) == true {
            return .requiresEmailCode(requires2FA: (obj["requires_2fa"] as? Bool) ?? false)
        }
        if (obj["requires_2fa"] as? Bool) == true {
            return .requiresTwoFactor(
                emailCodeVerified: (obj["email_code_verified"] as? Bool) ?? false
            )
        }
        // Success: backend returns camelCase keys (`accessToken`, `refreshToken`).
        guard let accessToken = obj["accessToken"] as? String ?? obj["access_token"] as? String else {
            throw TpidError.oauthError(code: "no_access_token", description: "login missing access token")
        }
        let refreshToken = obj["refreshToken"] as? String ?? obj["refresh_token"] as? String
        let idToken = obj["idToken"] as? String ?? obj["id_token"] as? String
        let expiresIn = (obj["expiresIn"] as? Int) ?? (obj["expires_in"] as? Int) ?? 3600
        let tokenType = obj["tokenType"] as? String ?? obj["token_type"] as? String ?? "Bearer"
        let scope = (obj["scope"] as? String) ?? ""
        let user: TpidUser? = {
            guard let userRaw = obj["user"] as? [String: Any],
                  let userData = try? JSONSerialization.data(withJSONObject: userRaw) else { return nil }
            return try? JSONDecoder().decode(TpidUser.self, from: userData)
        }()
        return .success(TpidSession(
            accessToken: accessToken,
            refreshToken: refreshToken,
            idToken: idToken,
            expiresAt: Date().addingTimeInterval(TimeInterval(expiresIn)),
            tokenType: tokenType,
            scope: scope,
            user: user ?? TpidUser(
                id: "", email: email, emailVerified: true,
                name: nil, avatarURL: nil, locale: lang,
                has2FA: false, hasPasskey: false, createdAt: ""
            )
        ))
    }

    /// POST `/api/v1/auth/send-code` — asks the server to e-mail a 6-digit
    /// verification code to [email]. The `type` parameter (`"login"` or
    /// `"register"`) is mandatory since late-2025; the server throws
    /// `missing_fields` without it.
    ///
    /// Replaces the pre-2.5.0-pre.3 `/auth/magic-link/request` path which
    /// never shipped and always returned 404.
    func requestEmailCode(email: String, clientId: String, type: String = "login") async throws {
        let req = try buildRequest(
            path: "/api/v1/auth/send-code",
            method: "POST",
            jsonBody: ["email": email, "client_id": clientId, "type": type]
        )
        let (data, http) = try await send(req)
        guard 200..<300 ~= http.statusCode else { throw parseError(data, http) }
    }

    func quickLogin(email: String, emailCode: String, clientId: String,
                    twoFactorCode: String? = nil, lang: String? = nil) async throws -> LoginOutcome {
        var body: [String: Any] = [
            "email": email,
            "email_code": emailCode,
            "client_id": clientId,
        ]
        if let twoFactorCode, !twoFactorCode.isEmpty { body["two_factor_code"] = twoFactorCode }
        if let lang, !lang.isEmpty { body["lang"] = lang }
        let req = try buildRequest(path: "/api/v1/auth/quick-login", method: "POST", jsonBody: body)
        let (data, http) = try await send(req)
        guard 200..<300 ~= http.statusCode else { throw parseError(data, http) }
        let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] ?? [:]
        if (obj["requires_2fa"] as? Bool) == true {
            return .requiresTwoFactor(emailCodeVerified: (obj["email_code_verified"] as? Bool) ?? true)
        }
        guard let accessToken = obj["accessToken"] as? String ?? obj["access_token"] as? String else {
            throw TpidError.oauthError(code: "no_access_token", description: "quick-login missing access token")
        }
        let refreshToken = obj["refreshToken"] as? String ?? obj["refresh_token"] as? String
        let idToken = obj["idToken"] as? String ?? obj["id_token"] as? String
        let expiresIn = (obj["expiresIn"] as? Int) ?? (obj["expires_in"] as? Int) ?? 3600
        let tokenType = obj["tokenType"] as? String ?? obj["token_type"] as? String ?? "Bearer"
        let scope = (obj["scope"] as? String) ?? ""
        let user: TpidUser? = {
            guard let userRaw = obj["user"] as? [String: Any],
                  let userData = try? JSONSerialization.data(withJSONObject: userRaw) else { return nil }
            return try? JSONDecoder().decode(TpidUser.self, from: userData)
        }()
        return .success(TpidSession(
            accessToken: accessToken,
            refreshToken: refreshToken,
            idToken: idToken,
            expiresAt: Date().addingTimeInterval(TimeInterval(expiresIn)),
            tokenType: tokenType,
            scope: scope,
            user: user ?? TpidUser(
                id: "", email: email, emailVerified: true,
                name: nil, avatarURL: nil, locale: lang,
                has2FA: false, hasPasskey: false, createdAt: ""
            )
        ))
    }

    func verifyEmailCode(email: String, code: String, config: TpidConfig,
                        codeChallenge: String, state: String, nonce: String) async throws -> String {
        let body: [String: Any] = [
            "email": email, "code": code,
            "client_id": config.clientId,
            "redirect_uri": config.redirectURI.absoluteString,
            "scope": config.scopeString,
            "code_challenge": codeChallenge,
            "code_challenge_method": "S256",
            "state": state, "nonce": nonce,
        ]
        let req = try buildRequest(path: "/api/v1/auth/verify", method: "POST", jsonBody: body)
        let (data, http) = try await send(req)
        guard 200..<300 ~= http.statusCode else { throw parseError(data, http) }
        let obj = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        guard let code = obj?["code"] as? String else {
            throw TpidError.oauthError(code: "no_code", description: "verify missing code")
        }
        return code
    }

    /// POST `/api/v1/auth/register` — finish sign-up for a brand-new e-mail.
    ///
    /// Caller must have previously requested a `type = "register"` code via
    /// [requestEmailCode(email:clientId:type:)]. Unlike OAuth token exchange,
    /// this endpoint returns the access/refresh token pair directly; sign-up
    /// therefore completes in a single round-trip without going through
    /// `/oauth/token`.
    func register(email: String, password: String, username: String,
                  emailCode: String, config: TpidConfig) async throws -> TpidSession {
        let lang: String = {
            switch config.language {
            case .ru: return "ru"
            case .zh: return "zh"
            case .en: return "en"
            case .system: return "en"
            }
        }()
        let body: [String: Any] = [
            "email": email,
            "password": password,
            "username": username,
            "email_code": emailCode,
            "client_id": config.clientId,
            "lang": lang,
        ]
        let req = try buildRequest(path: "/api/v1/auth/register", method: "POST", jsonBody: body)
        let (data, http) = try await send(req)
        guard 200..<300 ~= http.statusCode else { throw parseError(data, http) }
        // `/auth/register` returns camelCase keys (`accessToken`, `refreshToken`)
        // directly — it's not an OAuth RFC 6749 token endpoint, so the
        // snake_case CodingKeys on [TokenResponse] would silently miss them.
        // Parse by hand so sign-up completes in one call without introducing
        // a second decoder type.
        let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] ?? [:]
        guard let accessToken = obj["accessToken"] as? String ?? obj["access_token"] as? String else {
            throw TpidError.oauthError(code: "no_access_token", description: "register missing access token")
        }
        let refreshToken = obj["refreshToken"] as? String ?? obj["refresh_token"] as? String
        let idToken = obj["idToken"] as? String ?? obj["id_token"] as? String
        let expiresIn = (obj["expiresIn"] as? Int) ?? (obj["expires_in"] as? Int) ?? 3600
        let tokenType = obj["tokenType"] as? String ?? obj["token_type"] as? String ?? "Bearer"
        let scope = (obj["scope"] as? String) ?? config.scopeString
        // Server returns a camelCase `user` object — map it through the
        // TpidUser init by round-tripping via JSON so the Decodable logic
        // stays in one place.
        let user: TpidUser? = {
            guard let userRaw = obj["user"] as? [String: Any],
                  let userData = try? JSONSerialization.data(withJSONObject: userRaw) else { return nil }
            return try? JSONDecoder().decode(TpidUser.self, from: userData)
        }()
        return TpidSession(
            accessToken: accessToken,
            refreshToken: refreshToken,
            idToken: idToken,
            expiresAt: Date().addingTimeInterval(TimeInterval(expiresIn)),
            tokenType: tokenType,
            scope: scope,
            user: user ?? TpidUser(
                id: "", email: email, emailVerified: true,
                name: username, avatarURL: nil, locale: lang,
                has2FA: false, hasPasskey: false, createdAt: ""
            )
        )
    }

    func exchangeCode(code: String, codeVerifier: String, config: TpidConfig) async throws -> TpidSession {
        let body: [String: Any] = [
            "grant_type": "authorization_code",
            "code": code,
            "client_id": config.clientId,
            "redirect_uri": config.redirectURI.absoluteString,
            "code_verifier": codeVerifier,
        ]
        let req = try buildRequest(path: "/api/v1/oauth/token", method: "POST", jsonBody: body)
        let (data, http) = try await send(req)
        guard 200..<300 ~= http.statusCode else { throw parseError(data, http) }
        let resp = try JSONDecoder().decode(TpidEndpoints.TokenResponse.self, from: data)
        return Self.sessionFromResponse(resp)
    }

    func refreshToken(refreshToken: String, clientId: String) async throws -> TpidSession {
        let body: [String: Any] = [
            "grant_type": "refresh_token",
            "refresh_token": refreshToken,
            "client_id": clientId,
        ]
        let req = try buildRequest(path: "/api/v1/oauth/token", method: "POST", jsonBody: body)
        let (data, http) = try await send(req)
        guard 200..<300 ~= http.statusCode else { throw parseError(data, http) }
        let resp = try JSONDecoder().decode(TpidEndpoints.TokenResponse.self, from: data)
        return Self.sessionFromResponse(resp)
    }

    func revokeToken(_ token: String, clientId: String) async {
        guard let req = try? buildRequest(
            path: "/api/v1/oauth/revoke",
            method: "POST",
            jsonBody: ["token": token, "client_id": clientId]
        ) else { return }
        _ = try? await send(req)
    }

    // QR login (desktop-style flow reused on iPad / macOS widgets).

    struct QrInit: Sendable {
        let sessionId: String
        let qrUrl: URL
        let ttlSeconds: Int
    }

    /// POST /api/v1/auth/qr/login-init → { sessionId, qrUrl, ttl }
    func qrLoginInit(clientId: String, sdk: String = "swift") async throws -> QrInit {
        let req = try buildRequest(
            path: "/api/v1/auth/qr/login-init",
            method: "POST",
            jsonBody: ["client_id": clientId, "sdk": sdk]
        )
        let (data, http) = try await send(req)
        guard 200..<300 ~= http.statusCode else { throw parseError(data, http) }
        let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] ?? [:]
        let sid = obj["sessionId"] as? String ?? obj["session_id"] as? String ?? ""
        guard !sid.isEmpty else {
            throw TpidError.oauthError(code: "missing_sid", description: "qr-init missing sessionId")
        }
        let urlString = obj["qrUrl"] as? String
            ?? obj["qr_url"] as? String
            ?? "https://tokenpay.space/qr-login?sid=\(sid)"
        let url = URL(string: urlString) ?? URL(string: "https://tokenpay.space/qr-login?sid=\(sid)")!
        let ttl = obj["ttl"] as? Int ?? 300
        return QrInit(sessionId: sid, qrUrl: url, ttlSeconds: ttl)
    }

    enum QrPollResult {
        case pending
        case expired
        case approved(TpidSession)
    }

    /// GET /api/v1/auth/qr/login-poll/:sessionId
    func qrLoginPoll(sessionId: String) async throws -> QrPollResult {
        let req = try buildRequest(
            path: "/api/v1/auth/qr/login-poll/\(sessionId)",
            method: "GET"
        )
        let (data, http) = try await send(req)
        guard 200..<300 ~= http.statusCode else { throw parseError(data, http) }
        let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] ?? [:]
        switch obj["status"] as? String {
        case "approved":
            guard let access = obj["accessToken"] as? String ?? obj["access_token"] as? String else {
                throw TpidError.oauthError(code: "no_access_token",
                                           description: "approved QR missing access token")
            }
            let refresh = obj["refreshToken"] as? String ?? obj["refresh_token"] as? String
            let idTok = obj["idToken"] as? String ?? obj["id_token"] as? String
            let expiresIn = (obj["expiresIn"] as? Int) ?? (obj["expires_in"] as? Int) ?? 3600
            let scope = obj["scope"] as? String
            let userObj = obj["user"] as? [String: Any]
            let user: TpidUser
            if let u = userObj {
                user = TpidUser(
                    id: (u["id"] as? String) ?? (u["sub"] as? String) ?? "",
                    email: (u["email"] as? String) ?? "",
                    emailVerified: (u["email_verified"] as? Bool) ?? true,
                    name: u["name"] as? String,
                    avatarURL: (u["avatar_url"] as? String).flatMap(URL.init(string:))
                        ?? (u["picture"] as? String).flatMap(URL.init(string:)),
                    locale: u["locale"] as? String
                )
            } else {
                user = TpidUser(id: "", email: "", emailVerified: true,
                                name: nil, avatarURL: nil, locale: nil)
            }
            let session = TpidSession(
                accessToken: access,
                refreshToken: refresh,
                idToken: idTok,
                expiresAt: Date().addingTimeInterval(TimeInterval(expiresIn)),
                tokenType: "Bearer",
                scope: scope ?? "",
                user: user
            )
            return .approved(session)
        case "expired":
            return .expired
        default:
            return .pending
        }
    }

    // Device flow

    func deviceAuthorize(clientId: String, scope: String) async throws -> TpidEndpoints.DeviceAuthResponse {
        let req = try buildRequest(
            path: "/api/v1/oauth/device",
            method: "POST",
            jsonBody: ["client_id": clientId, "scope": scope]
        )
        let (data, http) = try await send(req)
        guard 200..<300 ~= http.statusCode else { throw parseError(data, http) }
        return try JSONDecoder().decode(TpidEndpoints.DeviceAuthResponse.self, from: data)
    }

    func pollDeviceToken(session: TpidDeviceFlowSession, clientId: String) async throws -> TpidSession {
        let deadline = Date().addingTimeInterval(TimeInterval(session.expiresIn))
        var interval = max(session.interval, 1)
        while Date() < deadline {
            try? await Task.sleep(nanoseconds: UInt64(interval) * 1_000_000_000)
            let req = try buildRequest(
                path: "/api/v1/oauth/device/token",
                method: "POST",
                jsonBody: [
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": session.deviceCode,
                    "client_id": clientId,
                ]
            )
            let (data, http) = try await send(req)
            if 200..<300 ~= http.statusCode {
                let resp = try JSONDecoder().decode(TpidEndpoints.TokenResponse.self, from: data)
                return Self.sessionFromResponse(resp)
            }
            let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
            switch obj?["error"] as? String {
            case "authorization_pending": continue
            case "slow_down": interval += 5
            case "expired_token":
                throw TpidError.oauthError(code: "expired_token", description: "Code expired")
            case "access_denied":
                throw TpidError.oauthError(code: "access_denied", description: "User denied")
            default:
                throw parseError(data, http)
            }
        }
        throw TpidError.oauthError(code: "expired_token", description: "Device flow timed out")
    }

    // Telemetry

    func sendTelemetry(event: [String: Any]) async {
        guard let req = try? buildRequest(path: "/api/v1/telemetry/event", method: "POST", jsonBody: event) else { return }
        _ = try? await send(req)
    }

    // MARK: - helpers

    private static func sessionFromResponse(_ r: TpidEndpoints.TokenResponse) -> TpidSession {
        TpidSession(
            accessToken: r.accessToken,
            refreshToken: r.refreshToken,
            idToken: r.idToken,
            expiresAt: Date().addingTimeInterval(TimeInterval(r.expiresIn)),
            tokenType: r.tokenType ?? "Bearer",
            scope: r.scope ?? "",
            user: r.user ?? TpidUser(id: "", email: "", emailVerified: false)
        )
    }

    private static func userAgent() -> String {
        #if os(iOS)
        let os = "iOS \(UIDevice.current.systemVersion)"
        #elseif os(macOS)
        let os = "macOS \(ProcessInfo.processInfo.operatingSystemVersionString)"
        #elseif os(tvOS)
        let os = "tvOS \(UIDevice.current.systemVersion)"
        #elseif os(watchOS)
        let os = "watchOS"
        #else
        let os = "Apple"
        #endif
        return "TokenPayID-Swift-SDK/\(TpidVersion.string) (\(os))"
    }
}

/// Public device flow session struct.
public struct TpidDeviceFlowSession: Sendable {
    public let deviceCode: String
    public let userCode: String
    public let verificationURI: URL
    public let verificationURIComplete: URL
    public let expiresIn: Int
    public let interval: Int
}

enum TpidVersion {
    static let string = "3.0.1"
}
