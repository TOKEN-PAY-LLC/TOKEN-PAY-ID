import SwiftUI
#if canImport(UIKit)
import UIKit
#elseif canImport(AppKit)
import AppKit
#endif

struct TpidWidgetSheet: View {
    let onResult: @Sendable (TpidResult) -> Void

    var body: some View {
        Group {
            if let state = TpidAuth.shared.state {
                TpidWidgetContent(appState: state, onResult: onResult)
            } else {
                ConfigErrorView(onClose: { onResult(.failure(.configurationError(reason: "SDK not initialized"))) })
            }
        }
        #if os(iOS)
        .presentationDetents([.medium, .large])
        #endif
    }
}

private struct TpidWidgetContent: View {
    @StateObject private var vm: WidgetViewModel
    @Environment(\.colorScheme) private var systemScheme
    @Environment(\.openURL) private var openURL
    private let themeOverride: TpidConfig.Theme

    init(appState: TpidAuth.State, onResult: @escaping @Sendable (TpidResult) -> Void) {
        _vm = StateObject(wrappedValue: WidgetViewModel(appState: appState, onComplete: onResult))
        themeOverride = appState.config.theme
    }

    var body: some View {
        GeometryReader { geo in
            ZStack {
                pageBackground.ignoresSafeArea()
                ScrollView {
                    VStack {
                        card
                            .frame(maxWidth: 420)
                            .padding(.horizontal, 20)
                            .padding(.vertical, 16)
                        Spacer(minLength: 0)
                    }
                    .frame(minHeight: geo.size.height)
                    .frame(maxWidth: .infinity)
                }
            }
        }
        .preferredColorScheme(colorSchemeForTheme())
    }

    // MARK: - Layout

    private var pageBackground: some View {
        let dark = effectiveScheme() == .dark
        return (dark ? Color(red: 5/255, green: 5/255, blue: 7/255) : Color(red: 245/255, green: 245/255, blue: 247/255))
    }

    private var card: some View {
        VStack(spacing: 0) {
            topBar
                .padding(.top, 4)
                .padding(.bottom, 8)
            TpidBrandHeader(branding: vm.branding)
                .padding(.vertical, 12)
            if vm.showUpdateBanner || vm.updaterPhase != .idle {
                // 2.6.1 — drive the state-machine banner directly from the
                // VM. Tapping "Update" (or "Retry") kicks off TpidUpdater,
                // whose phase stream is translated to `phaseText/progress/
                // indeterminate` for the banner. Fresh config + tarball
                // land in `Application Support/tokenpay-id/sdk/<v>` on
                // success and every remote-controllable string / theme /
                // flag applies live in the running widget.
                let latest = vm.updaterLatestVersion ?? TpidVersion.string
                TpidUpdateBanner(
                    phase: vm.updaterPhase,
                    message: vm.t("update_available",
                                  fallback: "A newer TOKEN PAY ID SDK is available — please update.") +
                        (latest != TpidVersion.string ? " (\(latest))" : ""),
                    updateLabel: vm.t("btn_download_sdk", fallback: "Open SDK"),
                    retryLabel: vm.t("btn_retry", fallback: "Retry"),
                    doneText: vm.t("update_done", fallback: "Updated to %1$@")
                        .replacingOccurrences(of: "%1$@", with: latest)
                        .replacingOccurrences(of: "%1$s", with: latest),
                    failedText: vm.t("update_failed",
                                     fallback: "Update failed — please try again."),
                    phaseText: vm.updaterPhaseText,
                    progress: vm.updaterProgress,
                    indeterminate: vm.updaterIndeterminate,
                    onStart: {
                        if let url = URL(string: "https://tokenpay.space/sdk#swift") { openURL(url) }
                        vm.showUpdateBanner = false
                        vm.dismissUpdaterBanner()
                    },
                    onAutoDismiss: { vm.dismissUpdaterBanner() }
                )
                .padding(.bottom, 8)
            }
            // Animated step switcher — mirrors the AnimatedContent block on
            // JVM and the AnimatedStepContent on Android. The id() keeps
            // SwiftUI from crossfading the underlying ViewModel data.
            currentScreen
                .padding(.top, 12)
                .id(stepId(vm.step))
                .transition(
                    .asymmetric(
                        insertion: .move(edge: .trailing).combined(with: .opacity),
                        removal: .move(edge: .leading).combined(with: .opacity)
                    )
                )
                .animation(.easeInOut(duration: 0.22), value: stepId(vm.step))
            Text("id.tokenpay.space")
                .font(TpidTypography.font(size: 11, weight: .medium))
                .foregroundStyle(.secondary.opacity(0.6))
                .padding(.top, 20)
                .padding(.bottom, 4)
        }
        .padding(.horizontal, 24)
        .padding(.vertical, 20)
        .background(RoundedRectangle(cornerRadius: 24).fill(cardBackground))
        .overlay(RoundedRectangle(cornerRadius: 24).strokeBorder(cardBorder, lineWidth: 1))
        .tpidComfortaaFont()
    }

    /// Stable per-step identifier used both as the `.id(…)` of the animated
    /// container and the `value:` of the animation modifier, so swapping
    /// between two steps with associated values (e.g. two `.loading(_)`
    /// messages) still re-animates.
    private func stepId(_ s: WidgetStep) -> String {
        switch s {
        case .welcome:            return "welcome"
        case .returningUser:      return "returningUser"
        case .email:              return "email"
        case .password:           return "password"
        case .emailCode:          return "emailCode"
        case .twoFactor:          return "twoFactor"
        case .passkey:            return "passkey"
        case .qrCode:             return "qrCode"
        case .recovery:           return "recovery"
        case .register(let sent): return "register:\(sent)"
        case .loading(let m):     return "loading:\(m)"
        case .success:            return "success"
        case .errorFatal:         return "errorFatal"
        }
    }

    private var cardBackground: Color {
        effectiveScheme() == .dark ? Color(red: 14/255, green: 14/255, blue: 17/255) : Color.white
    }
    private var cardBorder: Color {
        effectiveScheme() == .dark ? Color.white.opacity(0.08) : Color.black.opacity(0.08)
    }

    private var topBar: some View {
        HStack(spacing: 8) {
            // Hide Back arrow on Welcome / ReturningUser / Success — those
            // are landing screens, not "pushed" steps.
            let hideBack = vm.step == .welcome || vm.step == .returningUser
            if !hideBack, case .success = vm.step { Spacer().frame(width: 36) }
            else if !hideBack { TpidTopIconButton(systemName: "arrow.left", action: vm.back) }
            else { Spacer().frame(width: 36) }
            Spacer()
            TpidLanguageChip(current: vm.language, onChange: vm.setLanguage)
            TpidTopIconButton(systemName: "xmark", action: vm.cancel)
        }
    }

    @ViewBuilder
    private var currentScreen: some View {
        switch vm.step {
        case .welcome:            WelcomeStepView(vm: vm)
        case .returningUser:      ReturningUserStepView(vm: vm)
        case .email:              EmailStepView(vm: vm)
        case .password:           PasswordStepView(vm: vm)
        case .emailCode:          EmailCodeStepView(vm: vm)
        case .twoFactor:          TwoFactorStepView(vm: vm)
        case .passkey:            PasskeyStepView(vm: vm)
        case .qrCode:             QrStepView(vm: vm)
        case .recovery:           RecoveryStepView(vm: vm)
        case .register(let sent): RegisterStepView(vm: vm, codeSent: sent)
        case .loading(let m):     LoadingStepView(message: m)
        case .success:            SuccessStepView(email: vm.email, title: vm.t("success_title", fallback: "Signed in"))
        case .errorFatal(let e):  FatalErrorStepView(error: e, strings: vm.strings, onRetry: vm.resetToStart, onClose: vm.cancel)
        }
    }

    // MARK: - Theme helpers

    private func colorSchemeForTheme() -> ColorScheme? {
        switch themeOverride {
        case .light: return .light
        case .dark:  return .dark
        case .auto:  return nil
        }
    }

    private func effectiveScheme() -> ColorScheme {
        switch themeOverride {
        case .light: return .light
        case .dark:  return .dark
        case .auto:
            return systemScheme
        }
    }
}

// MARK: - Error config view

private struct ConfigErrorView: View {
    let onClose: () -> Void
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 42))
                .foregroundStyle(.red)
            Text("SDK not initialized")
                .font(.title3.bold())
            Text("Call TpidAuth.shared.initialize(config:) at app launch before presenting the widget.")
                .multilineTextAlignment(.center)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Button("Close", action: onClose)
                .buttonStyle(.borderedProminent)
        }
        .padding(32)
    }
}
