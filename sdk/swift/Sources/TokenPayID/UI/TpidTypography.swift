import SwiftUI
import CoreText

#if canImport(UIKit)
import UIKit
#elseif canImport(AppKit)
import AppKit
#endif

/// Registers the bundled Comfortaa variable TTF with CoreText and exposes a
/// small set of ``Font`` presets used across the widget. Runs exactly once per
/// process, guarded by a `dispatch_once`-style flag.
///
/// The TTF lives at `Resources/Fonts/Comfortaa-Variable.ttf` and is declared
/// in `Package.swift` as a processed resource — CoreText can therefore pick it
/// up directly from the SPM bundle.
///
/// Keep this file aligned with the Android ``TpidTypography.kt`` and the
/// JVM ``TpidTypography.kt`` so the three native SDKs render identical text.
enum TpidTypography {
    private static let registrationFlag: Void = {
        guard let url = Bundle.module.url(
            forResource: "Comfortaa-Variable",
            withExtension: "ttf",
            subdirectory: "Fonts"
        ) ?? Bundle.module.url(
            forResource: "Comfortaa-Variable",
            withExtension: "ttf"
        ) else {
            // Resource missing — fall back to the system font silently.
            return ()
        }
        var error: Unmanaged<CFError>?
        CTFontManagerRegisterFontsForURL(url as CFURL, .process, &error)
        return ()
    }()

    /// Force one-shot registration. Call before handing out any fonts below.
    static func register() { _ = registrationFlag }

    /// Canonical font family name baked into the TTF. If registration fails
    /// SwiftUI falls through to its default.
    static let familyName = "Comfortaa"

    static func font(size: CGFloat, weight: Font.Weight = .regular) -> Font {
        register()
        return .custom(familyName, size: size).weight(weight)
    }

    // MARK: - Role presets (mirror MaterialTheme.Typography / iOS TextStyle)

    static var displayLarge:  Font { font(size: 40, weight: .bold) }
    static var displayMedium: Font { font(size: 32, weight: .bold) }
    static var displaySmall:  Font { font(size: 28, weight: .bold) }
    static var headlineLarge: Font { font(size: 26, weight: .bold) }
    static var headlineMedium: Font { font(size: 22, weight: .bold) }
    static var headlineSmall:  Font { font(size: 20, weight: .semibold) }
    static var titleLarge:  Font { font(size: 18, weight: .semibold) }
    static var titleMedium: Font { font(size: 16, weight: .semibold) }
    static var titleSmall:  Font { font(size: 14, weight: .medium) }
    static var bodyLarge:   Font { font(size: 16, weight: .regular) }
    static var bodyMedium:  Font { font(size: 14, weight: .regular) }
    static var bodySmall:   Font { font(size: 12, weight: .regular) }
    static var labelLarge:  Font { font(size: 14, weight: .semibold) }
    static var labelMedium: Font { font(size: 12, weight: .semibold) }
    static var labelSmall:  Font { font(size: 11, weight: .medium) }
}

/// View modifier that applies the Comfortaa family to every `Text` in the
/// hierarchy — used at the root of the widget so every child view picks it
/// up automatically via `.environment(\.font, …)`.
struct TpidComfortaaFontEnvironment: ViewModifier {
    func body(content: Content) -> some View {
        TpidTypography.register()
        return content.environment(\.font, TpidTypography.bodyMedium)
    }
}

extension View {
    /// Apply the bundled Comfortaa font as the default for this subtree.
    func tpidComfortaaFont() -> some View { modifier(TpidComfortaaFontEnvironment()) }
}
