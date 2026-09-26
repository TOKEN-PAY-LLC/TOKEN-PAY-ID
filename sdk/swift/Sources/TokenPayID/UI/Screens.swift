import SwiftUI
#if canImport(UIKit)
import UIKit
#endif

// MARK: - Returning user (2.6.0 account memory)

/// "Continue as <user>" welcome card shown when `SecureStorage.readLastAccount()`
/// returned a non-nil profile. Purely monochrome — no coloured avatar badges.
struct ReturningUserStepView: View {
    @ObservedObject var vm: WidgetViewModel
    var body: some View {
        if let last = vm.lastAccount {
            let displayName = (last.displayName?.isEmpty == false) ? last.displayName! : last.email
            let format = vm.t("welcome_continue_as", fallback: "Continue as %@")
            let continueLabel = String(format: format, displayName)
            let age = last.lastAuthenticatedAt.map { Date().timeIntervalSince($0) } ?? -1
            let hintKey = age >= 0 && age <= 86_400 ? "remembered_session_hint"
                : age >= 0 && age <= 604_800 ? "remembered_code_hint"
                : "remembered_password_hint"

            VStack(spacing: 14) {
                ScreenSubtitle(text: vm.t("signin_title", fallback: "Welcome back"))
                    .padding(.bottom, 8)
                HStack(spacing: 14) {
                    AccountInitial(display: displayName)
                    VStack(alignment: .leading, spacing: 4) {
                        Text(displayName)
                            .font(.system(size: 16, weight: .bold))
                            .foregroundStyle(.primary)
                        if last.email != displayName {
                            Text(last.email)
                                .font(.system(size: 12))
                                .foregroundStyle(.secondary)
                        }
                    }
                    Spacer(minLength: 0)
                }
                .padding(16)
                .frame(maxWidth: .infinity)
                .background(RoundedRectangle(cornerRadius: 20).fill(Color.primary.opacity(0.045)))
                .overlay(RoundedRectangle(cornerRadius: 20).strokeBorder(Color.primary.opacity(0.12), lineWidth: 1))
                Text(vm.t(hintKey, fallback: "Continue securely with your saved account"))
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                if let error = vm.error { TpidErrorBanner(message: error) }
                Spacer().frame(height: 2)
                TpidPrimaryButton(
                    title: continueLabel,
                    action: { vm.continueAsLast() },
                    leadingIcon: AnyView(Image(systemName: "arrow.forward").font(.system(size: 14, weight: .bold)))
                )
                TpidSecondaryButton(
                    title: vm.t("welcome_other_account", fallback: "Use another account"),
                    action: { vm.useAnotherAccount() }
                )
                TpidLinkText(text: vm.t("alt_qr", fallback: "Sign in with QR code"), action: vm.goQr)
                    .frame(maxWidth: .infinity)
                Button(action: { vm.forgetLastAccount() }) {
                    Text(vm.t("welcome_forget", fallback: "Forget this account"))
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(.secondary)
                        .padding(.vertical, 6)
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.plain)
            }
        } else {
            // Defensive fallback — should never render.
            EmptyView()
                .onAppear { vm.useAnotherAccount() }
        }
    }
}

/// Monochrome circular avatar placeholder using the first alphanumeric letter
/// of the display name.
private struct AccountInitial: View {
    @Environment(\.colorScheme) private var scheme
    let display: String
    var body: some View {
        let bg: Color = scheme == .dark ? Color.white.opacity(0.14) : Color.black.opacity(0.06)
        let fg: Color = scheme == .dark ? Color.white : Color.black
        let letter = display.first { $0.isLetter || $0.isNumber }
            .map { String($0).uppercased() } ?? "·"
        Text(letter)
            .font(.system(size: 22, weight: .bold))
            .foregroundStyle(fg)
            .frame(width: 48, height: 48)
            .background(Circle().fill(bg))
    }
}

// MARK: - Welcome (image 4)

struct WelcomeStepView: View {
    @ObservedObject var vm: WidgetViewModel
    @Environment(\.openURL) private var openURL

    var body: some View {
        VStack(spacing: 14) {
            ScreenSubtitle(text: vm.t("welcome_subtitle", fallback: ""))
                .padding(.bottom, 14)
            TpidPrimaryButton(
                title: vm.t("welcome_sign_in", fallback: "Sign in"),
                action: { vm.goEmail() },
                leadingIcon: AnyView(Image(systemName: "arrow.forward").font(.system(size: 14, weight: .bold)))
            )
            TpidSecondaryButton(
                title: vm.t("welcome_create", fallback: "Create account"),
                action: { vm.goRegister() },
                leadingIcon: AnyView(Image(systemName: "person.badge.plus").font(.system(size: 14, weight: .semibold)))
            )
            TpidSecondaryButton(
                title: vm.t("alt_qr", fallback: "Sign in with QR code"),
                action: { vm.goQr() },
                leadingIcon: AnyView(Image(systemName: "qrcode").font(.system(size: 14, weight: .semibold)))
            )
            TpidOrDivider(text: vm.t("welcome_or", fallback: "or"))
            Button {
                if let url = URL(string: "https://tokenpay.space/") { openURL(url) }
            } label: {
                Text(vm.t("welcome_open_web", fallback: "Open tokenpay.space"))
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(.secondary)
                    .padding(.vertical, 6)
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.plain)
        }
    }
}

// MARK: - Email (image 5)

struct EmailStepView: View {
    @ObservedObject var vm: WidgetViewModel

    var body: some View {
        VStack(spacing: 16) {
            ScreenSubtitle(text: vm.t("signin_title", fallback: "Sign in"))
                .padding(.bottom, 10)
            TpidField(label: vm.t("field_email", fallback: "EMAIL"), error: vm.error) {
                TextField(vm.t("placeholder_email", fallback: "you@example.com"), text: $vm.email)
                    .textFieldStyle(.plain)
                    #if os(iOS)
                    .keyboardType(.emailAddress)
                    .textContentType(.emailAddress)
                    .autocapitalization(.none)
                    .disableAutocorrection(true)
                    #endif
                    .onSubmit(vm.submitEmail)
            }
            TpidPrimaryButton(
                title: vm.t("btn_next", fallback: "Next"),
                action: vm.submitEmail,
                enabled: vm.email.count >= 3
            )
            TpidOrDivider(text: vm.t("alt_divider", fallback: "or"))
            TpidSecondaryButton(
                title: vm.t("alt_qr", fallback: "Sign in with QR code"),
                action: { vm.goQr() },
                leadingIcon: AnyView(Image(systemName: "qrcode"))
            )
            TpidFooterInline(
                muted: vm.t("footer_no_account", fallback: "No account?"),
                link: vm.t("footer_create", fallback: "Create one"),
                action: { vm.goRegister() }
            )
        }
    }
}

// MARK: - Password

struct PasswordStepView: View {
    @ObservedObject var vm: WidgetViewModel
    @State private var visible = false

    var body: some View {
        VStack(spacing: 16) {
            TpidEmailChip(email: vm.email)
            TpidField(label: vm.t("field_password", fallback: "PASSWORD"), error: vm.error) {
                HStack {
                    Group {
                        if visible { TextField(vm.t("placeholder_password", fallback: "Your password"), text: $vm.password) }
                        else { SecureField(vm.t("placeholder_password", fallback: "Your password"), text: $vm.password) }
                    }
                    .textFieldStyle(.plain)
                    #if os(iOS)
                    .textContentType(.password)
                    .autocapitalization(.none)
                    .disableAutocorrection(true)
                    #endif
                    .onSubmit(vm.submitPassword)
                    Button { visible.toggle() } label: {
                        Image(systemName: visible ? "eye.slash" : "eye")
                            .foregroundStyle(.secondary)
                    }
                    .buttonStyle(.plain)
                }
            }
            TpidPrimaryButton(
                title: vm.t("btn_sign_in", fallback: "Sign in"),
                action: vm.submitPassword,
                enabled: vm.password.count >= 8
            )
            HStack {
                Spacer()
                // "Use email code" removed in pre.9 — the widget's old
                // password-less email-code path pointed at a backend route
                // that doesn't exist for first-time sign-ins, so the
                // button always ended in a dead-end. The e-mail OTP is now
                // part of the password flow itself.
                TpidLinkText(text: vm.t("btn_forgot", fallback: "Forgot?"), action: vm.switchToRecovery)
            }
        }
    }
}

// MARK: - Email code

struct EmailCodeStepView: View {
    @ObservedObject var vm: WidgetViewModel
    var body: some View {
        VStack(spacing: 16) {
            ScreenSubtitle(text: "\(vm.t("email_code_sent", fallback: "Code sent to")) \(vm.email)")
            TpidField(label: vm.t("field_code", fallback: "CODE"), error: vm.error) {
                TextField(vm.t("placeholder_code", fallback: "000000"), text: $vm.emailCode)
                    .textFieldStyle(.plain)
                    .tracking(8)
                    .multilineTextAlignment(.center)
                    #if os(iOS)
                    .keyboardType(.numberPad)
                    .textContentType(.oneTimeCode)
                    #endif
                    .onChange(of: vm.emailCode) { newValue in
                        vm.emailCode = String(newValue.filter(\.isNumber).prefix(6))
                    }
                    .onSubmit(vm.submitEmailCode)
            }
            TpidPrimaryButton(
                title: vm.t("btn_confirm", fallback: "Confirm"),
                action: vm.submitEmailCode,
                enabled: vm.emailCode.count == 6
            )
            TpidLinkText(text: vm.t("btn_resend", fallback: "Resend code"), action: vm.switchToEmailCode)
                .frame(maxWidth: .infinity)
        }
    }
}

// MARK: - 2FA TOTP

struct TwoFactorStepView: View {
    @ObservedObject var vm: WidgetViewModel
    var body: some View {
        VStack(spacing: 16) {
            ScreenSubtitle(text: vm.t("two_factor_hint", fallback: ""))
            TpidField(label: vm.t("field_totp", fallback: "CODE"), error: vm.error) {
                TextField(vm.t("placeholder_code", fallback: "000000"), text: $vm.totp)
                    .textFieldStyle(.plain)
                    .tracking(8)
                    .multilineTextAlignment(.center)
                    #if os(iOS)
                    .keyboardType(.numberPad)
                    #endif
                    .onChange(of: vm.totp) { newValue in
                        vm.totp = String(newValue.filter(\.isNumber).prefix(6))
                    }
                    .onSubmit(vm.submitTotp)
            }
            TpidPrimaryButton(
                title: vm.t("btn_confirm", fallback: "Confirm"),
                action: vm.submitTotp,
                enabled: vm.totp.count == 6
            )
        }
    }
}

// MARK: - Passkey

struct PasskeyStepView: View {
    @ObservedObject var vm: WidgetViewModel
    var body: some View {
        VStack(spacing: 20) {
            ScreenSubtitle(text: vm.t("passkey_hint", fallback: ""))
            Image(systemName: "faceid")
                .font(.system(size: 64))
                .padding(.vertical, 16)
            if let err = vm.error { TpidErrorBanner(message: err) }
            TpidPrimaryButton(
                title: vm.t("passkey_title", fallback: "Sign in with passkey"),
                action: { vm.resetToStart() }
            )
            TpidLinkText(text: vm.t("btn_use_password", fallback: "Use password"), action: vm.resetToStart)
                .frame(maxWidth: .infinity)
        }
    }
}

// MARK: - Register (sign-up)

/// Swift mirror of `RegisterStep` from the JVM widget and `RegisterScreen`
/// on Android. Shows one of two visually consistent layouts depending on
/// `codeSent`:
///  - `false` → name + password fields + "Send verification code" button.
///  - `true`  → fields freeze at 55 % alpha, a code input appears, and
///              the primary button becomes "Create account".
struct RegisterStepView: View {
    @ObservedObject var vm: WidgetViewModel
    let codeSent: Bool
    @State private var revealPassword = false

    var body: some View {
        VStack(spacing: 16) {
            ScreenSubtitle(text: vm.t("register_title", fallback: "Create your account"))
            if !codeSent {
                // Clarifies to the user why the widget is on the sign-up form
                // when all they did was enter an unknown email.
                Text(vm.t("register_hint",
                          fallback: "This email isn't registered yet — fill in the form below to create a new account."))
                    .font(.system(size: 12))
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: .infinity)
                    .padding(.bottom, 4)
            }
            if vm.email.isEmpty {
                // Reached Register straight from Welcome → user hasn't typed
                // an email yet. Give them the field inline.
                TpidField(label: vm.t("field_email", fallback: "EMAIL"),
                          error: codeSent ? nil : vm.error) {
                    TextField(vm.t("placeholder_email", fallback: "you@example.com"), text: $vm.email)
                        .textFieldStyle(.plain)
                        .disabled(codeSent)
                        #if os(iOS)
                        .keyboardType(.emailAddress)
                        .textContentType(.emailAddress)
                        .autocapitalization(.none)
                        .disableAutocorrection(true)
                        #endif
                }
                .opacity(codeSent ? 0.55 : 1)
            } else {
                TpidEmailChip(email: vm.email)
            }
            TpidField(label: vm.t("field_username", fallback: "USERNAME"),
                      error: codeSent ? nil : vm.error) {
                TextField(vm.t("placeholder_username", fallback: "your_login"), text: $vm.regUsername)
                    .textFieldStyle(.plain)
                    .disabled(codeSent)
                    #if os(iOS)
                    .textContentType(.username)
                    .autocapitalization(.none)
                    .disableAutocorrection(true)
                    #endif
                    .onChange(of: vm.regUsername) { newValue in
                        // Mirror server regex `^[a-z0-9._]{3,30}$` — auto
                        // lowercase + drop illegal chars so paste sanitises
                        // silently instead of firing validation errors per
                        // keystroke.
                        let allowed = Set("abcdefghijklmnopqrstuvwxyz0123456789._")
                        let sanitised = newValue.lowercased().filter { allowed.contains($0) }
                        let trimmed = String(sanitised.prefix(30))
                        if trimmed != vm.regUsername { vm.regUsername = trimmed }
                    }
                    .onSubmit { if !codeSent { vm.sendRegisterCode() } }
            }
            .opacity(codeSent ? 0.55 : 1)
            Text(vm.t("hint_username",
                      fallback: "Lowercase letters, digits, dots, underscores (3-30)"))
                .font(.system(size: 11))
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.leading, 4)

            TpidField(label: vm.t("field_password", fallback: "PASSWORD"),
                      error: codeSent ? nil : vm.error) {
                HStack {
                    Group {
                        if revealPassword { TextField(vm.t("placeholder_password_new", fallback: "At least 8 characters"), text: $vm.regPassword) }
                        else { SecureField(vm.t("placeholder_password_new", fallback: "At least 8 characters"), text: $vm.regPassword) }
                    }
                    .textFieldStyle(.plain)
                    .disabled(codeSent)
                    #if os(iOS)
                    .textContentType(.newPassword)
                    .autocapitalization(.none)
                    .disableAutocorrection(true)
                    #endif
                    .onSubmit { if !codeSent { vm.sendRegisterCode() } }
                    if !codeSent {
                        Button { revealPassword.toggle() } label: {
                            Image(systemName: revealPassword ? "eye.slash" : "eye")
                                .foregroundStyle(.secondary)
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
            .opacity(codeSent ? 0.55 : 1)

            if codeSent {
                ScreenSubtitle(text: "\(vm.t("register_code_sent", fallback: "Verification code sent to")) \(vm.email)")
                TpidField(label: vm.t("field_code", fallback: "CODE"), error: vm.error) {
                    TextField(vm.t("placeholder_code", fallback: "000000"), text: $vm.regCode)
                        .textFieldStyle(.plain)
                        .tracking(8)
                        .multilineTextAlignment(.center)
                        #if os(iOS)
                        .keyboardType(.numberPad)
                        .textContentType(.oneTimeCode)
                        #endif
                        .onChange(of: vm.regCode) { newValue in
                            vm.regCode = String(newValue.filter(\.isNumber).prefix(6))
                        }
                        .onSubmit(vm.submitRegister)
                }
                TpidPrimaryButton(
                    title: vm.t("btn_create_account", fallback: "Create account"),
                    action: vm.submitRegister,
                    enabled: vm.regCode.count == 6
                )
                TpidLinkText(text: vm.t("btn_resend_code", fallback: "Resend code"),
                             action: vm.sendRegisterCode)
                    .frame(maxWidth: .infinity)
            } else {
                TpidPrimaryButton(
                    title: vm.t("btn_send_code", fallback: "Send verification code"),
                    action: vm.sendRegisterCode,
                    enabled: vm.regUsername.count >= 3 && vm.regPassword.count >= 8
                )
            }
        }
    }
}

// MARK: - QR login

/// QR login step. The VM owns the session + polling state; this view just
/// renders whatever is in `vm.qrImage` / `vm.qrStatus`.
struct QrStepView: View {
    @ObservedObject var vm: WidgetViewModel

    var body: some View {
        VStack(spacing: 16) {
            ScreenSubtitle(text: vm.t("qr_title", fallback: "Sign in with QR code"))
            Text(vm.t("qr_hint",
                      fallback: "On a device where you are already signed in, open id.tokenpay.space and scan this code."))
                .font(.system(size: 12))
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: .infinity)
                .padding(.horizontal, 8)
            let secondary = vm.strings["qr_hint_secondary"] ?? ""
            if !secondary.isEmpty {
                Text(secondary)
                    .font(.system(size: 11))
                    .foregroundStyle(.tertiary)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: .infinity)
                    .padding(.horizontal, 8)
            }

            ZStack {
                RoundedRectangle(cornerRadius: 16)
                    .fill(Color(white: 0.96))
                    .overlay(RoundedRectangle(cornerRadius: 16)
                        .stroke(Color.black.opacity(0.08), lineWidth: 1))

                switch vm.qrStatus {
                case "expired":
                    // 2.6.0 strict-monochrome: panel is light in both
                    // themes, so a black semi-bold label stays legible
                    // without the earlier red accent.
                    Text(vm.t("qr_status_expired", fallback: "QR code expired"))
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(Color.black)
                        .multilineTextAlignment(.center)
                case "error":
                    Text(vm.error ?? vm.t("qr_status_error", fallback: "Couldn't start QR session"))
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundStyle(Color.black)
                        .multilineTextAlignment(.center)
                        .padding(12)
                default:
                    if let img = vm.qrImage {
                        img
                            .resizable()
                            .interpolation(.none)
                            .scaledToFit()
                            .frame(width: 200, height: 200)
                    } else {
                        ProgressView()
                            .controlSize(.regular)
                    }
                }
            }
            .frame(width: 220, height: 220)

            Text(statusText)
                .font(.system(size: 12))
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)

            if vm.qrStatus == "expired" || vm.qrStatus == "error" {
                TpidPrimaryButton(
                    title: vm.t("qr_refresh", fallback: "Refresh"),
                    action: { vm.refreshQr() },
                    leadingIcon: AnyView(Image(systemName: "arrow.clockwise"))
                )
            }
            TpidSecondaryButton(
                title: vm.t("qr_paste", fallback: "Paste QR link"),
                action: { vm.pasteQrFromClipboard() },
                leadingIcon: AnyView(Image(systemName: "doc.on.clipboard"))
            )
        }
    }

    private var statusText: String {
        switch vm.qrStatus {
        case "approved": return vm.t("qr_status_approved", fallback: "Confirmed on your other device")
        case "expired":  return vm.t("qr_status_expired",  fallback: "QR code expired")
        case "error":    return vm.t("qr_status_error",    fallback: "Couldn't start QR session")
        default:         return vm.t("qr_status_pending",  fallback: "Waiting for confirmation…")
        }
    }
}

// MARK: - Recovery

struct RecoveryStepView: View {
    @ObservedObject var vm: WidgetViewModel
    var body: some View {
        VStack(spacing: 16) {
            ScreenSubtitle(text: "\(vm.t("email_code_sent", fallback: "")) \(vm.email)")
            if let err = vm.error { TpidErrorBanner(message: err) }
            TpidPrimaryButton(
                title: vm.t("btn_send_recovery", fallback: "Send recovery email"),
                action: vm.switchToEmailCode
            )
            TpidLinkText(text: vm.t("btn_back_signin", fallback: "Back"), action: vm.resetToStart)
                .frame(maxWidth: .infinity)
        }
    }
}

// MARK: - Loading / Success / Fatal

struct LoadingStepView: View {
    let message: String
    var body: some View {
        VStack(spacing: 16) {
            ProgressView().controlSize(.large)
            Text(message).font(.system(size: 14)).foregroundStyle(.secondary)
        }
        .padding(.vertical, 48)
    }
}

struct SuccessStepView: View {
    let email: String
    let title: String
    var body: some View {
        VStack(spacing: 12) {
            // 2.6.0 strict-monochrome: no green tint on success. The
            // `SuccessGlyph` is a pure stroke that reads equally well
            // on dark and light themes.
            SuccessGlyph(size: 64)
            Text(title).font(.system(size: 22, weight: .bold))
            if !email.isEmpty {
                Text(email).font(.system(size: 13)).foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 32)
    }
}

/// 2.6.0 — strict-monochrome success glyph. Stroked circle + tick, tinted
/// with the environment's primary foreground colour so it reads as
/// white-on-dark or black-on-light without any chromatic accent.
struct SuccessGlyph: View {
    let size: CGFloat
    var body: some View {
        Canvas { ctx, canvasSize in
            let s = min(canvasSize.width, canvasSize.height)
            let stroke = s / 12.0
            let rect = CGRect(x: stroke / 2, y: stroke / 2,
                              width: s - stroke, height: s - stroke)
            ctx.stroke(Path(ellipseIn: rect),
                       with: .color(.primary),
                       style: StrokeStyle(lineWidth: stroke))
            var tick = Path()
            tick.move(to: CGPoint(x: s * 0.28, y: s * 0.52))
            tick.addLine(to: CGPoint(x: s * 0.46, y: s * 0.68))
            tick.addLine(to: CGPoint(x: s * 0.74, y: s * 0.36))
            ctx.stroke(tick,
                       with: .color(.primary),
                       style: StrokeStyle(lineWidth: stroke,
                                          lineCap: .round, lineJoin: .round))
        }
        .frame(width: size, height: size)
    }
}

struct FatalErrorStepView: View {
    let error: TpidError
    let strings: [String: String]
    let onRetry: () -> Void
    let onClose: () -> Void

    var body: some View {
        VStack(spacing: 16) {
            // 2.6.0: strict-monochrome — no red fatal-error tint. The
            // bold title below already signals severity.
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 56))
                .foregroundStyle(.primary)
            Text(title).font(.system(size: 20, weight: .bold)).multilineTextAlignment(.center)
            Text(error.description).font(.system(size: 14))
                .foregroundStyle(.secondary).multilineTextAlignment(.center)
            TpidPrimaryButton(title: strings["btn_try_again"] ?? "Try again", action: onRetry)
            TpidSecondaryButton(title: strings["btn_close"] ?? "Close", action: onClose)
        }
        .padding(.vertical, 24)
    }

    private var title: String {
        let key: String
        switch error {
        case .noNetwork:             key = "err_title_network"
        case .timeout:               key = "err_title_timeout"
        case .accountLocked:         key = "err_title_locked"
        case .emailNotVerified:      key = "err_title_not_verified"
        case .rateLimited:           key = "err_title_rate_limited"
        case .phishingDetected:      key = "err_title_phishing"
        case .serverError:           key = "err_title_server"
        case .configurationError:    key = "err_title_config"
        case .oauthError:            key = "err_title_oauth"
        default:                     key = "err_title_generic"
        }
        return strings[key] ?? "Error"
    }
}
