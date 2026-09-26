import Foundation
import SwiftUI

@MainActor
final class WidgetViewModel: ObservableObject {
    private static let rememberInstantWindow: TimeInterval = 24 * 60 * 60
    private static let rememberEmailCodeWindow: TimeInterval = 7 * 24 * 60 * 60

    @Published var step: WidgetStep = .welcome
    @Published var email: String = ""
    @Published var password: String = ""
    @Published var emailCode: String = ""
    @Published var totp: String = ""
    @Published var error: String?
    @Published var branding: TpidConfig.Branding?
    @Published var twoFactorMethods: [String] = []
    @Published var accountInfo: TpidEndpoints.AccountCheckResponse?
    @Published var language: TpidConfig.Language = .en
    @Published var strings: [String: String] = [:]
    /// `true` when the server reports a newer SDK version than `TpidVersion.string`.
    @Published var showUpdateBanner: Bool = false
    // Sign-up form fields — populated once the widget transitions to the
    // register step (triggered by accountCheck's `exists = false` branch).
    @Published var regUsername: String = ""
    @Published var regPassword: String = ""
    @Published var regCode: String = ""
    // QR login state (populated only while on the QR step).
    @Published var qrSessionId: String? = nil
    @Published var qrUrl: URL? = nil
    @Published var qrImage: Image? = nil
    /// `"loading"` | `"pending"` | `"approved"` | `"expired"` | `"error"`.
    @Published var qrStatus: String = "loading"
    /// 2.6.0 — remembered profile from the last successful sign-in (if any).
    /// Non-nil means the widget opens on [WidgetStep.returningUser].
    @Published var lastAccount: SecureStorage.LastAccount?
    /// 2.6.0 — URL the update banner's "Update" pill should open. Populated
    /// from `/sdk/config` → `remote.download_url`.
    @Published var updateDownloadUrl: URL?

    // --- 2.6.1 smart updater state -------------------------------------
    /// Banner state machine; drives the animated morph in
    /// `TpidUpdateBanner`. Owned by this VM: [startSmartUpdate] transitions
    /// idle → running, the phase stream transitions inside running, and
    /// terminal cases pin `done` / `failed` until [dismissUpdaterBanner].
    @Published var updaterPhase: UpdateBannerPhase = .idle
    /// Short phase label ("Downloading 1.2 MB / 2.1 MB", "Verifying…").
    @Published var updaterPhaseText: String = ""
    /// `[0, 1]` determinate progress; ignored when
    /// [updaterIndeterminate] is `true`.
    @Published var updaterProgress: Double = 0
    /// `true` while we don't know the download size yet (server omitted
    /// Content-Length, or we haven't started downloading).
    @Published var updaterIndeterminate: Bool = true
    /// Server-advertised version we are pulling to, cached so the Done
    /// banner ("Updated to 2.6.1") can render without another lookup.
    @Published var updaterLatestVersion: String?

    private var qrTask: Task<Void, Never>? = nil
    private var updateTask: Task<Void, Never>? = nil

    private let appState: TpidAuth.State
    private let onComplete: @Sendable (TpidResult) -> Void
    /// Cached remote config — needed so later language switches still pick up
    /// server-delivered string overrides.
    private var remote: TpidRemoteConfig = .empty

    var antiPhishingDomain: String { appState.config.issuer.host ?? "" }
    @Published var tlsPinned: Bool = false

    init(appState: TpidAuth.State, onComplete: @escaping @Sendable (TpidResult) -> Void) {
        self.appState = appState
        self.onComplete = onComplete
        self.tlsPinned = appState.api.hasActivePins
        self.branding = appState.config.brandingOverride ?? appState.sdkConfigLoader.cachedBranding()

        let eff = TpidStrings.resolveLanguage(appState.config.language)
        self.language = eff
        self.strings = TpidStrings.of(eff)

        // 2.6.0: honour prefillEmail first; otherwise fall back to the last
        // successfully-signed-in account and open on `.returningUser`.
        let prefill = appState.config.prefillEmail?.isEmpty == false
        if prefill {
            self.email = appState.config.prefillEmail ?? ""
            self.lastAccount = nil
            self.step = .email
        } else if let last = appState.storage.readLastAccount() {
            self.email = last.email
            self.lastAccount = last
            self.step = .returningUser
        } else {
            self.email = ""
            self.lastAccount = nil
            self.step = .welcome
        }

        appState.telemetry.track("widget.step_shown", properties: ["step": String(describing: step)])
        Task { [weak self] in
            guard let self else { return }
            if let br = try? await appState.sdkConfigLoader.refreshConfig(clientId: appState.config.clientId) {
                await MainActor.run {
                    self.branding = appState.config.brandingOverride ?? br
                    self.tlsPinned = appState.api.hasActivePins
                }
            }
        }
        // Separate fetch for UI-only remote overrides so a failure there
        // doesn't bring down the branding/pins refresh above.
        Task { [weak self] in
            guard let self else { return }
            let r = await TpidRemoteConfig.fetch(api: appState.api, clientId: appState.config.clientId)
            await MainActor.run {
                self.remote = r
                self.strings = self.mergedStrings(for: self.language, from: r)
                self.showUpdateBanner = r.isOlderThan(r.recommendedSdkVersion) || r.isOlderThan(r.minSdkVersion)
                // 2.6.0: propagate the download URL so the banner's Update
                // pill has somewhere real to go.
                if let dl = r.downloadUrl, !dl.isEmpty, let url = URL(string: dl) {
                    self.updateDownloadUrl = url
                }
            }
        }
    }

    func setLanguage(_ lang: TpidConfig.Language) {
        let eff = TpidStrings.resolveLanguage(lang)
        language = eff
        strings = mergedStrings(for: eff, from: remote)
    }

    /// Compose the visible strings map for [lang] by layering the server's
    /// `strings_override[<lang>]` on top of the locally-bundled translations.
    private func mergedStrings(for lang: TpidConfig.Language, from r: TpidRemoteConfig) -> [String: String] {
        let base = TpidStrings.of(lang)
        let code: String
        switch TpidStrings.resolveLanguage(lang) {
        case .ru: code = "ru"
        case .zh: code = "zh"
        default:  code = "en"
        }
        guard let overrides = r.stringsOverride[code], !overrides.isEmpty else { return base }
        return base.merging(overrides) { _, new in new }
    }

    func t(_ key: String, fallback: String = "") -> String { strings[key] ?? fallback }

    func goEmail() {
        step = .email; error = nil
        appState.telemetry.track("widget.step_shown", properties: ["step": "email"])
    }

    /// Jump directly to the sign-up form. Used by the Welcome screen's
    /// Create Account button and the Email screen's "No account? Create one"
    /// footer link — both of which previously routed through `goEmail()`
    /// and stranded users on the sign-in path when they wanted to register.
    func goRegister() {
        step = .register(codeSent: false); error = nil
        appState.telemetry.track("widget.step_shown", properties: ["step": "register"])
    }

    func cancel() {
        appState.telemetry.track("widget.closed_cancel", properties: ["step": String(describing: step)])
        onComplete(.cancelled)
    }

    func back() {
        // 2.6.0: if the widget opened on `.returningUser`, backing out of
        // interior steps should return to that card rather than dumping
        // the user onto an empty Email field.
        let backLanding: WidgetStep = (lastAccount != nil) ? .returningUser : .welcome
        switch step {
        case .email:
            step = backLanding; error = nil
        case .password, .emailCode, .twoFactor, .passkey, .recovery:
            // If the typed email still matches the remembered account,
            // going back should return to ReturningUser; otherwise to the
            // generic Email step.
            let dest: WidgetStep = {
                if let last = lastAccount, email == last.email { return .returningUser }
                return .email
            }()
            step = dest; password = ""; emailCode = ""; totp = ""; error = nil
        case .register:
            step = .email; regUsername = ""; regPassword = ""; regCode = ""; error = nil
        case .qrCode:
            qrTask?.cancel()
            step = backLanding
            qrSessionId = nil; qrUrl = nil; qrImage = nil; qrStatus = "loading"
            error = nil
        default:
            cancel()
        }
    }

    // MARK: - QR login

    /// Enter the QR step and start a fresh session.
    func goQr() {
        qrTask?.cancel()
        qrSessionId = nil; qrUrl = nil; qrImage = nil
        qrStatus = "loading"; error = nil
        step = .qrCode
        appState.telemetry.track("widget.step_shown", properties: ["step": "qr"])
        startQrPolling()
    }

    /// Re-initialise the QR session (e.g. after expiry).
    func refreshQr() {
        qrTask?.cancel()
        qrSessionId = nil; qrUrl = nil; qrImage = nil
        qrStatus = "loading"; error = nil
        startQrPolling()
    }

    /// Paste a `tokenpay.space/qr-login?sid=…` URL from the clipboard and
    /// jump straight into polling with that session ID.
    func pasteQrFromClipboard() {
        #if canImport(UIKit)
        let raw = UIPasteboard.general.string ?? ""
        #elseif canImport(AppKit)
        let raw = NSPasteboard.general.string(forType: .string) ?? ""
        #else
        let raw = ""
        #endif
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        if let sid = extractSid(from: trimmed) {
            qrTask?.cancel()
            qrSessionId = sid
            qrUrl = URL(string: trimmed)
            qrImage = nil
            qrStatus = "pending"; error = nil
            startQrPolling()
        } else {
            qrStatus = "error"
            error = t("qr_paste_prompt",
                      fallback: "Paste the tokenpay.space/qr-login?sid=… link")
        }
    }

    private func extractSid(from text: String) -> String? {
        guard let regex = try? NSRegularExpression(pattern: #"[?&]sid=([A-Za-z0-9\-]+)"#) else { return nil }
        let ns = text as NSString
        guard let match = regex.firstMatch(in: text,
                                           range: NSRange(location: 0, length: ns.length)),
              match.numberOfRanges > 1 else { return nil }
        return ns.substring(with: match.range(at: 1))
    }

    private func startQrPolling() {
        // Snapshot the main-actor-isolated bits so the polling Task doesn't
        // need to hop back to the main actor on every read.
        let preexistingSid = qrSessionId
        let preexistingUrl = qrUrl?.absoluteString
        let api = appState.api
        let clientId = appState.config.clientId
        let storage = appState.storage
        let telemetry = appState.telemetry
        let onComplete = onComplete
        let errText = t("qr_status_error", fallback: "Couldn't start QR session")

        qrTask = Task { @MainActor [weak self] in
            guard let self else { return }
            // Step 1 — acquire (or reuse) a session ID.
            let sessionId: String
            if let existing = preexistingSid {
                sessionId = existing
                let urlString = preexistingUrl
                    ?? "https://tokenpay.space/qr-login?sid=\(existing)"
                let img = TpidQrRenderer.render(urlString)
                self.qrImage = img
                self.qrStatus = img == nil ? "error" : "pending"
                if img == nil { self.error = errText; return }
            } else {
                do {
                    let init_ = try await api.qrLoginInit(clientId: clientId)
                    self.qrSessionId = init_.sessionId
                    self.qrUrl = init_.qrUrl
                    // CoreImage occasionally refuses to render very long
                    // URLs on older OS builds — bail out with a visible
                    // error state instead of a silent infinite spinner.
                    let img = TpidQrRenderer.render(init_.qrUrl.absoluteString)
                    self.qrImage = img
                    if img == nil {
                        self.qrStatus = "error"
                        self.error = errText
                        return
                    }
                    self.qrStatus = "pending"
                    self.error = nil
                    sessionId = init_.sessionId
                } catch {
                    self.qrStatus = "error"
                    self.error = errText
                    return
                }
            }

            // Step 2 — poll until approved/expired/cancelled.
            let deadline = Date().addingTimeInterval(300)
            while !Task.isCancelled && Date() < deadline {
                do {
                    let result = try await api.qrLoginPoll(sessionId: sessionId)
                    switch result {
                    case .approved(let session):
                        try? storage.writeSession(session)
                        // 2.6.0: remember the account so the next open
                        // shows "Continue as X" instead of Welcome.
                        storage.writeLastAccount(.init(
                            email: session.user.email,
                            displayName: session.user.name?.nilIfBlank,
                            avatarUrl: session.user.avatarURL.flatMap { url in url.absoluteString.nilIfBlank },
                            lastAuthenticatedAt: Date()))
                        self.qrStatus = "approved"
                        self.step = .success
                        telemetry.track("widget.qr_approved", properties: [:])
                        try? await Task.sleep(nanoseconds: 600_000_000)
                        onComplete(.success(session))
                        return
                    case .expired:
                        self.qrStatus = "expired"
                        return
                    case .pending:
                        break
                    }
                } catch {
                    // Transient network blip — keep polling up to deadline.
                }
                try? await Task.sleep(nanoseconds: 2_000_000_000)
            }
            if !Task.isCancelled {
                self.qrStatus = "expired"
            }
        }
    }

    // MARK: — Sign-up

    /// Phase A → Phase B: ask the server to email a verification code for
    /// registration, then flip `register(codeSent:)` to `true`.
    func sendRegisterCode() {
        guard regUsername.count >= 3 else {
            error = t("error_username_short", fallback: "Username too short"); return
        }
        if regUsername.range(of: #"^[a-z0-9._]{3,30}$"#, options: .regularExpression) == nil {
            error = t("error_username_invalid",
                      fallback: "Lowercase letters, digits, dots and underscores only")
            return
        }
        guard regPassword.count >= 8 else {
            error = t("error_password_short", fallback: "Password too short"); return
        }
        step = .loading(t("loading_sending", fallback: "Sending…")); error = nil
        let _email = email
        Task { [weak self] in
            guard let self else { return }
            do {
                try await appState.api.requestEmailCode(email: _email, clientId: appState.config.clientId, type: "register")
                await MainActor.run {
                    self.step = .register(codeSent: true)
                    self.error = nil
                }
                appState.telemetry.track("widget.step_shown", properties: ["step": "register_code"])
            } catch let e as TpidError {
                await MainActor.run { self.step = .register(codeSent: false); self.error = e.description }
            } catch {
                await MainActor.run { self.step = .register(codeSent: false); self.error = self.t("err_title_generic", fallback: "Failed") }
            }
        }
    }

    /// Phase B: user typed the 6-digit code. POST to `/auth/register`; the
    /// response already contains the final token pair so we skip the OAuth
    /// code exchange entirely.
    func submitRegister() {
        guard regCode.count == 6 else { error = t("error_code_len", fallback: "Invalid code"); return }
        step = .loading(t("loading_creating", fallback: "Creating account…")); error = nil
        let _email = email, _password = regPassword, _username = regUsername, _code = regCode
        Task { [weak self] in
            guard let self else { return }
            do {
                let session = try await appState.api.register(
                    email: _email, password: _password, username: _username,
                    emailCode: _code, config: appState.config
                )
                try? appState.storage.writeSession(session)
                appState.storage.writeLastAccount(.init(
                    email: session.user.email,
                    displayName: session.user.name?.nilIfBlank,
                    avatarUrl: session.user.avatarURL.flatMap { url in url.absoluteString.nilIfBlank },
                    lastAuthenticatedAt: Date()))
                await MainActor.run { self.step = .success }
                appState.telemetry.track("widget.register_success", properties: [:])
                try? await Task.sleep(nanoseconds: 600_000_000)
                self.onComplete(.success(session))
            } catch let e as TpidError {
                await MainActor.run {
                    self.step = .register(codeSent: true)
                    self.error = e.description
                    self.regCode = ""
                }
                appState.telemetry.track("widget.step_submit_error", properties: ["step": "register", "code": e.code])
            } catch {
                await MainActor.run {
                    self.step = .register(codeSent: true)
                    self.error = self.t("err_title_generic", fallback: "Something went wrong")
                    self.regCode = ""
                }
            }
        }
    }

    func submitEmail() {
        guard isValidEmail(email) else { error = t("error_invalid_email", fallback: "Invalid email"); return }
        step = .loading(t("loading_checking", fallback: "Checking…"))
        error = nil
        appState.telemetry.track("widget.step_submit_ok", properties: ["step": "email"])
        Task { [weak self] in
            guard let self else { return }
            do {
                let info = try await appState.api.accountCheck(email: email, clientId: appState.config.clientId)
                // Existing user → always go to the password step. The
                // backend-controlled e-mail OTP is the second factor of the
                // password login itself (`/auth/login` returns
                // `requires_email_code: true` after accepting the password),
                // not an alternative entry point.
                let next: WidgetStep = {
                    if info.exists { return .password }
                    // Brand-new email → jump straight into the sign-up form.
                    return .register(codeSent: false)
                }()
                await MainActor.run {
                    self.accountInfo = info
                    self.step = next
                }
                appState.telemetry.track("widget.step_shown", properties: ["step": String(describing: next)])
            } catch let e as TpidError {
                await MainActor.run { self.step = .email; self.error = e.description }
                appState.telemetry.track("widget.step_submit_error", properties: ["step": "email", "code": e.code])
            } catch {
                await MainActor.run { self.step = .email; self.error = self.t("err_title_generic", fallback: "Something went wrong") }
            }
        }
    }

    /// First call in the password flow: `{email, password}`. Expected happy
    /// path is `requires_email_code` → flip to `.emailCode` step.
    func submitPassword() {
        guard password.count >= 8 else { error = t("error_password_short", fallback: "Password too short"); return }
        step = .loading(t("loading_signing", fallback: "Signing in…")); error = nil
        runPasswordLogin(from: .password, telemetryStep: "password")
    }

    /// Second call in the password flow: `{email, password, email_code}`.
    /// On success receives tokens, otherwise either a 2FA challenge or a
    /// new `requires_email_code` if the previous code expired in-flight.
    func submitEmailCode() {
        guard emailCode.count == 6 else { error = t("error_code_len", fallback: "Invalid code"); return }
        step = .loading(t("loading_verifying", fallback: "Verifying…")); error = nil
        runPasswordLogin(from: .emailCode, telemetryStep: "email_code")
    }

    /// Third (rare) call: `{email, password, email_code, two_factor_code}`.
    /// Only reached when the account has TOTP enabled — normally the e-mail
    /// code alone completes the login.
    func submitTotp() {
        guard totp.count == 6 else { error = t("error_code_len", fallback: "Invalid code"); return }
        step = .loading(t("loading_verifying", fallback: "Verifying…")); error = nil
        runPasswordLogin(from: .twoFactor, telemetryStep: "2fa")
    }

    /// Shared implementation for all three password-flow submits so the
    /// ADT branching on [LoginOutcome] lives in one place. [from] is the
    /// step the widget was on when the user submitted, used as the fallback
    /// step on error.
    private func runPasswordLogin(from currentStep: WidgetStep, telemetryStep: String) {
        let _email = email
        let _password = password
        let _emailCode: String? = (currentStep == .emailCode || currentStep == .twoFactor) ? emailCode : nil
        let _totp: String? = currentStep == .twoFactor ? totp : nil
        let _lang: String? = {
            switch appState.config.language {
            case .ru: return "ru"
            case .zh: return "zh"
            case .en: return "en"
            case .system: return nil
            }
        }()
        Task { [weak self] in
            guard let self else { return }
            do {
                let outcome: ApiClient.LoginOutcome
                if _password.isEmpty, let _emailCode {
                    outcome = try await appState.api.quickLogin(
                        email: _email, emailCode: _emailCode,
                        clientId: appState.config.clientId,
                        twoFactorCode: _totp, lang: _lang
                    )
                } else {
                    outcome = try await appState.api.login(
                        email: _email, password: _password,
                        clientId: appState.config.clientId,
                        emailCode: _emailCode, twoFactorCode: _totp, lang: _lang
                    )
                }
                switch outcome {
                case .success(let session):
                    try? self.appState.storage.writeSession(session)
                    self.appState.storage.writeLastAccount(.init(
                        email: session.user.email,
                        displayName: session.user.name?.nilIfBlank,
                        avatarUrl: session.user.avatarURL.flatMap { url in url.absoluteString.nilIfBlank },
                        lastAuthenticatedAt: Date()))
                    self.appState.telemetry.track("widget.closed_success", properties: [:])
                    await MainActor.run { self.step = .success }
                    try? await Task.sleep(nanoseconds: 600_000_000)
                    self.onComplete(.success(session))
                case .requiresEmailCode:
                    await MainActor.run {
                        self.step = .emailCode
                        self.emailCode = ""
                        self.error = nil
                    }
                    self.appState.telemetry.track("widget.step_shown",
                        properties: ["step": "email_code", "reason": "password_login"])
                case .requiresTwoFactor:
                    await MainActor.run {
                        self.step = .twoFactor
                        self.totp = ""
                        self.twoFactorMethods = ["totp"]
                        self.error = nil
                    }
                    self.appState.telemetry.track("widget.step_shown",
                        properties: ["step": "2fa"])
                }
            } catch let e as TpidError {
                await MainActor.run {
                    switch e {
                    case .accountLocked, .emailNotVerified, .phishingDetected, .configurationError, .serverError:
                        self.step = .errorFatal(e); self.error = nil
                    default:
                        self.step = currentStep
                        self.error = e.description
                        if currentStep == .emailCode { self.emailCode = "" }
                        if currentStep == .twoFactor { self.totp = "" }
                    }
                }
                self.appState.telemetry.track("widget.step_submit_error",
                    properties: ["step": telemetryStep, "code": e.code])
            } catch {
                await MainActor.run {
                    self.step = currentStep
                    self.error = self.t("err_title_generic", fallback: "Unexpected error")
                }
            }
        }
    }

    /// No-op kept for API compatibility — the widget no longer exposes a
    /// "log in with email code only" path because the backend has no such
    /// endpoint for first-time sign-ins.
    func switchToEmailCode() { /* intentionally empty */ }

    func switchToRecovery() { step = .recovery; error = nil }

    func resetToStart() {
        step = .email; password = ""; emailCode = ""; totp = ""; error = nil
    }

    // MARK: - Account memory (2.6.0)

    func continueAsLast() {
        guard let last = lastAccount else { return }
        email = last.email
        password = ""
        emailCode = ""
        totp = ""
        error = nil
        if let lastAuth = last.lastAuthenticatedAt,
           (0...Self.rememberInstantWindow).contains(Date().timeIntervalSince(lastAuth)) {
            step = .loading(t("loading_signing", fallback: "Signing in…"))
            Task { [weak self] in
                guard let self else { return }
                do {
                    guard let stored = appState.storage.readSession() else {
                        throw TpidError.invalidCredentials(reason: "Session expired")
                    }
                    guard stored.user.email.caseInsensitiveCompare(last.email) == .orderedSame else {
                        throw TpidError.invalidCredentials(reason: "Saved session belongs to a different account")
                    }
                    let session: TpidSession
                    if stored.isValid {
                        session = stored
                    } else if let refresh = stored.refreshToken {
                        let refreshed = try await appState.api.refreshToken(refreshToken: refresh, clientId: appState.config.clientId)
                        if refreshed.user.id.isEmpty {
                            session = TpidSession(
                                accessToken: refreshed.accessToken,
                                refreshToken: refreshed.refreshToken,
                                idToken: refreshed.idToken,
                                expiresAt: refreshed.expiresAt,
                                tokenType: refreshed.tokenType,
                                scope: refreshed.scope,
                                user: stored.user
                            )
                        } else {
                            session = refreshed
                        }
                        try? appState.storage.writeSession(session)
                    } else {
                        throw TpidError.invalidCredentials(reason: "Session expired")
                    }
                    appState.storage.writeLastAccount(.init(
                        email: session.user.email,
                        displayName: session.user.name?.nilIfBlank,
                        avatarUrl: session.user.avatarURL.flatMap { url in url.absoluteString.nilIfBlank },
                        lastAuthenticatedAt: Date()))
                    appState.telemetry.track("widget.remembered_instant_success", properties: [:])
                    await MainActor.run { self.step = .success }
                    self.onComplete(.success(session))
                } catch {
                    do {
                        try await appState.api.requestEmailCode(email: last.email, clientId: appState.config.clientId, type: "login")
                        await MainActor.run {
                            self.step = .emailCode
                            self.emailCode = ""
                            self.error = nil
                        }
                        self.appState.telemetry.track("widget.step_shown",
                            properties: ["step": "email_code", "source": "last_account"])
                    } catch let e as TpidError {
                        await MainActor.run {
                            self.step = .returningUser
                            self.error = e.description
                        }
                    } catch {
                        await MainActor.run {
                            self.step = .returningUser
                            self.error = self.t("err_title_generic", fallback: "Unexpected error")
                        }
                    }
                }
            }
            return
        }
        if let lastAuth = last.lastAuthenticatedAt,
           (0...Self.rememberEmailCodeWindow).contains(Date().timeIntervalSince(lastAuth)) {
            step = .loading(t("loading_sending", fallback: "Sending code…"))
            Task { [weak self] in
                guard let self else { return }
                do {
                    try await appState.api.requestEmailCode(email: last.email, clientId: appState.config.clientId, type: "login")
                    await MainActor.run {
                        self.step = .emailCode
                        self.emailCode = ""
                        self.error = nil
                    }
                    self.appState.telemetry.track("widget.step_shown",
                        properties: ["step": "email_code", "source": "last_account"])
                } catch let e as TpidError {
                    await MainActor.run {
                        self.step = .returningUser
                        self.error = e.description
                    }
                } catch {
                    await MainActor.run {
                        self.step = .returningUser
                        self.error = self.t("err_title_generic", fallback: "Unexpected error")
                    }
                }
            }
            return
        }
        step = .password
        appState.telemetry.track("widget.step_shown",
            properties: ["step": "password", "source": "last_account"])
    }

    /// "Use another account" → wipe typed state, go to the full Email step.
    func useAnotherAccount() {
        email = ""
        password = ""
        emailCode = ""
        totp = ""
        error = nil
        step = .email
        appState.telemetry.track("widget.step_shown",
            properties: ["step": "email", "source": "other_account"])
    }

    /// "Forget this account" → clear the Keychain slot and fall back to the
    /// regular Welcome step.
    func forgetLastAccount() {
        appState.storage.clearLastAccount()
        lastAccount = nil
        email = ""
        step = .welcome
        appState.telemetry.track("widget.last_account_forgotten")
    }

    private func isValidEmail(_ s: String) -> Bool {
        let regex = try? NSRegularExpression(pattern: #"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"#)
        return regex?.firstMatch(in: s, range: NSRange(location: 0, length: s.utf16.count)) != nil
    }

    // MARK: - 2.6.1 smart update ------------------------------------------

    /// Kick off (or retry) an in-place smart update. Safe to call more
    /// than once — any in-flight download is cancelled first so the
    /// banner never desynchronises from reality.
    func startSmartUpdate() {
        updateTask?.cancel()
        let latest = remote.recommendedSdkVersion ?? TpidVersion.string
        updaterLatestVersion = latest
        updaterPhase = .running
        updaterPhaseText = t("update_checking", fallback: "Checking for updates…")
        updaterProgress = 0.03
        updaterIndeterminate = true
        appState.telemetry.track(
            "widget.update_started",
            properties: ["sdk": "swift", "from": TpidVersion.string, "to": latest]
        )
        let updater = TpidUpdater(
            api: appState.api,
            clientId: appState.config.clientId
        )
        // Strings are captured *immediately* so a language change mid-update
        // doesn't scramble the banner text. The fallback chain mirrors
        // every other caller — English is the untranslated baseline.
        let strs = strings
        let checkingLabel = strs["update_checking"] ?? "Checking for updates…"
        let verifyingLabel = strs["update_verifying"] ?? "Verifying download…"
        let installingLabel = strs["update_installing"] ?? "Installing…"
        let refreshingLabel = strs["update_refreshing"] ?? "Applying new settings…"
        let doneLabel = (strs["update_done"] ?? "Updated to %1$@")
            .replacingOccurrences(of: "%1$@", with: latest)
            .replacingOccurrences(of: "%1$s", with: latest)
        let failedTmpl = strs["update_failed"] ?? "Update failed — please try again."
        let dlTmpl = strs["update_downloading"] ?? "Downloading %1$@ / %2$@"
        let dlUnknownTmpl = strs["update_downloading_unknown"] ?? "Downloading %1$@…"

        updateTask = Task { [weak self] in
            // `TpidUpdater.performUpdate` is `nonisolated`; it calls
            // `onPhase` on arbitrary queues. We route every tick back to
            // the main actor so SwiftUI observes coherent state.
            let terminal = await updater.performUpdate { [weak self] phase in
                Task { @MainActor [weak self] in
                    guard let self else { return }
                    let ui = tpidMapPhaseToUI(
                        phase,
                        checkingLabel: checkingLabel,
                        downloading: { bytes, total in
                            let got = tpidHumanBytes(bytes)
                            if let tot = total, tot > 0 {
                                let tstr = tpidHumanBytes(tot)
                                return dlTmpl
                                    .replacingOccurrences(of: "%1$@", with: got)
                                    .replacingOccurrences(of: "%1$s", with: got)
                                    .replacingOccurrences(of: "%2$@", with: tstr)
                                    .replacingOccurrences(of: "%2$s", with: tstr)
                            } else {
                                return dlUnknownTmpl
                                    .replacingOccurrences(of: "%1$@", with: got)
                                    .replacingOccurrences(of: "%1$s", with: got)
                            }
                        },
                        verifyingLabel: verifyingLabel,
                        installingLabel: installingLabel,
                        refreshingLabel: refreshingLabel,
                        doneLabel: doneLabel,
                        failedFmt: { reason in
                            failedTmpl
                                .replacingOccurrences(of: "%1$@", with: reason)
                                .replacingOccurrences(of: "%1$s", with: reason)
                        }
                    )
                    self.updaterPhaseText = ui.text
                    self.updaterProgress = ui.progress
                    self.updaterIndeterminate = ui.indeterminate
                }
            }
            await MainActor.run { [weak self] in
                guard let self else { return }
                switch terminal {
                case let .done(_, newConfig):
                    self.remote = newConfig
                    self.strings = self.mergedStrings(for: self.language, from: newConfig)
                    // Any fresh `remote.download_url` wins.
                    if let dl = newConfig.downloadUrl, !dl.isEmpty,
                       let url = URL(string: dl) {
                        self.updateDownloadUrl = url
                    }
                    // Server no longer considers us stale: either the
                    // tarball cache is fresh or the recommended version
                    // is the one we're running.
                    self.showUpdateBanner = false
                    self.updaterPhase = .done
                    self.appState.telemetry.track(
                        "widget.update_done",
                        properties: ["sdk": "swift", "version": latest]
                    )
                case let .failed(reason):
                    self.updaterPhase = .failed
                    self.appState.telemetry.track(
                        "widget.update_failed",
                        properties: ["sdk": "swift", "reason": reason]
                    )
                default:
                    // Non-terminal phases never escape `performUpdate`;
                    // this branch exists only for exhaustiveness.
                    break
                }
            }
        }
    }

    /// Collapse the banner back to idle — invoked by the Compose /
    /// SwiftUI auto-dismiss after ~2.8 s of `done`.
    func dismissUpdaterBanner() {
        updaterPhase = .idle
        updaterPhaseText = ""
        updaterProgress = 0
        updaterIndeterminate = true
    }
}

private extension String {
    /// 2.6.0 — returns the receiver trimmed, or nil if it is empty / blank.
    /// Used to filter out backend-sent empty-string `name` fields (U8 fix).
    var nilIfBlank: String? {
        let trimmed = trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }
}

enum WidgetStep: Equatable {
    case welcome
    /// 2.6.0 — "Continue as X" card. Seeded from [SecureStorage.readLastAccount]
    /// on widget init when no explicit `prefillEmail` was passed.
    case returningUser
    case email
    case password
    case emailCode
    case twoFactor
    case passkey
    /// QR login step — widget renders a QR from `/auth/qr/login-init` and
    /// polls `login-poll/:sid` until the phone confirms.
    case qrCode
    case recovery
    /// Sign-up screen. `codeSent == false` → user is still typing name/password;
    /// `codeSent == true` → verification e-mail sent, code input visible.
    case register(codeSent: Bool)
    case loading(String)
    case success
    case errorFatal(TpidError)

    static func == (lhs: WidgetStep, rhs: WidgetStep) -> Bool {
        switch (lhs, rhs) {
        case (.welcome, .welcome), (.returningUser, .returningUser),
             (.email, .email), (.password, .password), (.emailCode, .emailCode),
             (.twoFactor, .twoFactor), (.passkey, .passkey), (.qrCode, .qrCode),
             (.recovery, .recovery), (.success, .success):
            return true
        case let (.register(a), .register(b)): return a == b
        case let (.loading(a), .loading(b)): return a == b
        case let (.errorFatal(a), .errorFatal(b)): return a.code == b.code
        default: return false
        }
    }
}
