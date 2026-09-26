import SwiftUI

/// Visual variants for ``TpidLoginButton``.
///
/// - `dark`     — black pill, white "TOKEN PAY ID" wordmark.
/// - `light`    — white pill with border, black wordmark.
/// - `iconOnly` — circular 1:1 button, just the T icon.
public enum TpidButtonVariant: Sendable { case dark, light, iconOnly }

/// Size presets matching the design system.
public enum TpidButtonSize: Sendable {
    case small, medium, large

    /// Overall button height / diameter.
    var height: CGFloat {
        switch self {
        case .small: return 40
        case .medium: return 48
        case .large: return 56
        }
    }
    /// Height of the wordmark image on DARK / LIGHT variants.
    /// In 2.5.0-pre.3 bumped from 16/20/24 to 18/22/26 pt — second-round
    /// user feedback ("чтобы лого был немного крупнее"). The pill heights
    /// grew proportionally so the wordmark still has breathing room.
    var wordmarkHeight: CGFloat {
        switch self {
        case .small: return 18
        case .medium: return 22
        case .large: return 26
        }
    }
    /// Size of the single-glyph icon on ICON_ONLY.
    var iconHeight: CGFloat {
        switch self {
        case .small: return 22
        case .medium: return 28
        case .large: return 34
        }
    }
    var padH: CGFloat {
        switch self {
        case .small: return 20
        case .medium: return 26
        case .large: return 32
        }
    }
}

/// Official TOKEN PAY ID login button — only the logo is rendered, so every
/// integration is visually identical. Wraps presentation of the widget sheet.
///
/// ```swift
/// TpidLoginButton(variant: .dark) { result in … }
/// ```
public struct TpidLoginButton: View {
    private let variant: TpidButtonVariant
    private let size: TpidButtonSize
    private let fullWidth: Bool
    private let onResult: @Sendable (TpidResult) -> Void
    @State private var presenting = false
    @State private var inFlight = false

    public init(
        variant: TpidButtonVariant = .dark,
        size: TpidButtonSize = .medium,
        fullWidth: Bool = false,
        onResult: @escaping @Sendable (TpidResult) -> Void
    ) {
        self.variant = variant
        self.size = size
        self.fullWidth = fullWidth
        self.onResult = onResult
    }

    public var body: some View {
        Button {
            presenting = true
            inFlight = true
        } label: {
            buttonBody
        }
        .buttonStyle(TpidLoginButtonStyle())
        .disabled(inFlight && !presenting)
        .sheet(isPresented: $presenting) {
            TpidWidgetSheet { result in
                presenting = false
                inFlight = false
                onResult(result)
            }
        }
    }

    @ViewBuilder
    private var buttonBody: some View {
        switch variant {
        case .dark, .light:
            let dark = variant == .dark
            let bg: Color = dark ? Color(red: 11/255, green: 11/255, blue: 13/255) : .white
            // Equal-weight border on both themes — fixes the feedback that the
            // black pill looked "bare" next to the outlined white one.
            // Pronounced outline — 2pt × 28% alpha reads as a clear ring
            // on both themes. Mirrors the Android 2.5.0-pre.3 bump.
            let borderCol: Color = dark
                ? Color.white.opacity(0.28)
                : Color(red: 11/255, green: 11/255, blue: 13/255).opacity(0.28)
            let shadowAlpha: Double = dark ? 0.50 : 0.18
            HStack(spacing: 0) {
                if inFlight {
                    ProgressView()
                        .controlSize(.small)
                        .tint(dark ? .white : .black)
                        .frame(height: size.wordmarkHeight)
                } else {
                    Image(dark ? "tpid_wordmark_white" : "tpid_wordmark_black", bundle: .module)
                        .resizable()
                        .aspectRatio(contentMode: .fit)
                        .frame(height: size.wordmarkHeight)
                        .accessibilityLabel("Sign in with TOKEN PAY ID")
                }
            }
            .frame(maxWidth: fullWidth ? .infinity : nil, minHeight: size.height)
            .padding(.horizontal, size.padH)
            .background(Capsule().fill(bg))
            .overlay(Capsule().strokeBorder(borderCol, lineWidth: 2.0))
            .shadow(color: Color.black.opacity(shadowAlpha), radius: 6, x: 0, y: 2)
            .contentShape(Capsule())

        case .iconOnly:
            // White-tinted saturn glyph on a soft black disc, matching the
            // round brand badge in the tokenpay.space hero. A faint white
            // ring at the edge keeps it from looking like a flat disc.
            ZStack {
                Circle().fill(Color(red: 11/255, green: 11/255, blue: 13/255))
                if inFlight {
                    ProgressView().controlSize(.small).tint(.white)
                } else {
                    Image("tpid_icon", bundle: .module)
                        .resizable()
                        .renderingMode(.template)
                        .aspectRatio(contentMode: .fit)
                        .foregroundStyle(Color.white)
                        .frame(width: size.iconHeight, height: size.iconHeight)
                }
            }
            .frame(width: size.height, height: size.height)
            .overlay(Circle().strokeBorder(Color.white.opacity(0.28), lineWidth: 2.0))
            .shadow(color: Color.black.opacity(0.45), radius: 6, x: 0, y: 2)
            .contentShape(Circle())
        }
    }
}

/// Custom button style that scales down on press — mirrors the spring
/// scale(0.965 → 1.0) animation we use on JVM and Android so the three
/// native SDKs behave identically when tapped.
private struct TpidLoginButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.965 : 1.0)
            .animation(.spring(response: 0.26, dampingFraction: 0.6), value: configuration.isPressed)
    }
}
