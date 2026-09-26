import SwiftUI

// MARK: - Brand marks (bundled PNGs)

struct TpidWordmark: View {
    let white: Bool
    var height: CGFloat = 28
    var body: some View {
        Image(white ? "tpid_wordmark_white" : "tpid_wordmark_black", bundle: .module)
            .resizable()
            .aspectRatio(contentMode: .fit)
            .frame(height: height)
            .accessibilityLabel("TOKEN PAY ID")
    }
}

struct TpidIconMark: View {
    var size: CGFloat = 18
    var body: some View {
        Image("tpid_icon", bundle: .module)
            .resizable()
            .aspectRatio(contentMode: .fit)
            .frame(width: size, height: size)
    }
}

// MARK: - Brand header (centered wordmark)

struct TpidBrandHeader: View {
    @Environment(\.colorScheme) private var scheme
    let branding: TpidConfig.Branding?
    var body: some View {
        VStack(spacing: 8) {
            TpidWordmark(white: scheme == .dark, height: 34)
                .frame(maxWidth: 240)
            if let name = branding?.appName {
                Text("for \(name)")
                    .font(.system(size: 12))
                    .foregroundStyle(.secondary)
            }
        }
        .frame(maxWidth: .infinity)
    }
}

// MARK: - Primary / secondary pill buttons

struct TpidPrimaryButton: View {
    @Environment(\.colorScheme) private var scheme
    let title: String
    let action: () -> Void
    var enabled: Bool = true
    var loading: Bool = false
    var leadingIcon: AnyView? = nil

    var body: some View {
        Button(action: action) {
            HStack(spacing: 10) {
                if loading {
                    ProgressView().controlSize(.small).tint(scheme == .dark ? .black : .white)
                } else if let leadingIcon {
                    leadingIcon
                }
                Text(title).font(.system(size: 15, weight: .bold))
            }
            .frame(maxWidth: .infinity, minHeight: 52)
            .padding(.horizontal, 20)
            .background(Capsule().fill(scheme == .dark ? Color.white : Color.black))
            .foregroundStyle(scheme == .dark ? Color.black : Color.white)
            .contentShape(Capsule())
        }
        .buttonStyle(.plain)
        .disabled(!enabled || loading)
        .opacity(enabled ? 1 : 0.35)
    }
}

struct TpidSecondaryButton: View {
    @Environment(\.colorScheme) private var scheme
    let title: String
    let action: () -> Void
    var leadingIcon: AnyView? = nil

    var body: some View {
        Button(action: action) {
            HStack(spacing: 10) {
                if let leadingIcon { leadingIcon }
                Text(title).font(.system(size: 14, weight: .semibold))
            }
            .frame(maxWidth: .infinity, minHeight: 48)
            .padding(.horizontal, 20)
            .background(
                Capsule()
                    .fill(scheme == .dark ? Color.white.opacity(0.08) : Color.black.opacity(0.04))
            )
            .overlay(
                Capsule()
                    .strokeBorder(scheme == .dark ? Color.white.opacity(0.14) : Color.black.opacity(0.12), lineWidth: 1)
            )
            .foregroundStyle(scheme == .dark ? Color.white : Color.black)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Field (uppercase label + rounded input)

struct TpidField<Input: View>: View {
    @Environment(\.colorScheme) private var scheme
    let label: String
    let error: String?
    @ViewBuilder let input: () -> Input

    init(label: String, error: String? = nil, @ViewBuilder input: @escaping () -> Input) {
        self.label = label; self.error = error; self.input = input
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(label)
                .font(.system(size: 11, weight: .bold))
                .tracking(2)
                .foregroundStyle(scheme == .dark ? Color.white.opacity(0.4) : Color.black.opacity(0.5))
                .padding(.leading, 2)
            input()
                .padding(.horizontal, 18)
                .padding(.vertical, 16)
                .background(
                    RoundedRectangle(cornerRadius: 14)
                        .fill(scheme == .dark ? Color.white.opacity(0.05) : Color.black.opacity(0.03))
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 14)
                        .strokeBorder(scheme == .dark ? Color.white.opacity(0.12) : Color.black.opacity(0.12), lineWidth: 1)
                )
            if let error {
                Text(error)
                    .font(.system(size: 12))
                    .foregroundStyle(.primary)
            }
        }
    }
}

// MARK: - Or divider

struct TpidOrDivider: View {
    @Environment(\.colorScheme) private var scheme
    let text: String
    var body: some View {
        HStack(spacing: 14) {
            Rectangle()
                .fill(scheme == .dark ? Color.white.opacity(0.08) : Color.black.opacity(0.08))
                .frame(height: 1)
            Text(text.uppercased())
                .font(.system(size: 10, weight: .semibold))
                .tracking(2)
                .foregroundStyle(scheme == .dark ? Color.white.opacity(0.25) : Color.black.opacity(0.35))
            Rectangle()
                .fill(scheme == .dark ? Color.white.opacity(0.08) : Color.black.opacity(0.08))
                .frame(height: 1)
        }
        .padding(.vertical, 18)
    }
}

// MARK: - Language chip (cycles RU → EN → ZH)

struct TpidLanguageChip: View {
    @Environment(\.colorScheme) private var scheme
    let current: TpidConfig.Language
    let onChange: (TpidConfig.Language) -> Void

    private var label: String {
        switch current {
        case .ru: return "RU"
        case .zh: return "ZH"
        default: return "EN"
        }
    }

    var body: some View {
        Button {
            let order: [TpidConfig.Language] = [.ru, .en, .zh]
            let idx = max(order.firstIndex(of: current) ?? 0, 0)
            onChange(order[(idx + 1) % order.count])
        } label: {
            Text(label)
                .font(.system(size: 11, weight: .bold))
                .tracking(1)
                .foregroundStyle(scheme == .dark ? Color.white.opacity(0.55) : Color.black.opacity(0.55))
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(Capsule().fill(scheme == .dark ? Color.white.opacity(0.08) : Color.black.opacity(0.06)))
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Top icon button (circular)

struct TpidTopIconButton: View {
    @Environment(\.colorScheme) private var scheme
    let systemName: String
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            Image(systemName: systemName)
                .font(.system(size: 15, weight: .medium))
                .foregroundStyle(scheme == .dark ? Color.white.opacity(0.75) : Color.black.opacity(0.6))
                .frame(width: 36, height: 36)
                .background(Circle().fill(scheme == .dark ? Color.white.opacity(0.08) : Color.black.opacity(0.06)))
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Error banner

struct TpidErrorBanner: View {
    @Environment(\.colorScheme) private var scheme
    let message: String
    var body: some View {
        // 2.6.0 strict-monochrome: no pink accent. Semi-bold text inside a
        // bordered `onBackground`-ish box carries the same semantics.
        let bg: Color = scheme == .dark ? Color.white.opacity(0.08) : Color.black.opacity(0.06)
        let border: Color = scheme == .dark ? Color.white.opacity(0.28) : Color.black.opacity(0.20)
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: "exclamationmark.circle")
            Text(message).font(.system(size: 13, weight: .semibold))
        }
        .foregroundStyle(.primary)
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: 10).fill(bg))
        .overlay(RoundedRectangle(cornerRadius: 10).stroke(border, lineWidth: 1))
    }
}

// MARK: - Smart update banner (2.6.1)

/// Pure visual state for `TpidUpdateBanner`. Owned by `WidgetViewModel`.
///
/// The same four-state machine that backs the JVM and Android banners:
/// idle → running → done | failed. `done` auto-dismisses after ~2.8 s
/// via the `onAutoDismiss` callback.
enum UpdateBannerPhase: Sendable, Equatable {
    case idle
    case running
    case done
    case failed
}

/// 2.6.1 — Animated, state-machine-driven update banner.
///
/// The banner is a pure projection of the caller's state — HTTP and file
/// I/O live in `TpidUpdater`, which streams `TpidUpdatePhase` values up to
/// `WidgetViewModel`. The VM translates those into `phaseText` / `progress`
/// / `indeterminate` and drives this view.
///
/// Visual behaviour, matching the Compose banners pixel-for-pixel:
///  - **idle**: message + high-contrast "Update" pill → calls `onStart`.
///  - **running**: phase label + monochrome progress track (determinate or
///    indeterminate sliver shuttle). Pill morphs into a rotating arc.
///  - **done**: ✓ stroked check reveal, then auto-dismiss.
///  - **failed**: pill becomes "Retry", re-fires `onStart`.
struct TpidUpdateBanner: View {
    @Environment(\.colorScheme) private var scheme
    let phase: UpdateBannerPhase
    let message: String
    let updateLabel: String
    let retryLabel: String
    let doneText: String
    let failedText: String
    let phaseText: String
    let progress: Double
    let indeterminate: Bool
    let onStart: () -> Void
    let onAutoDismiss: () -> Void

    var body: some View {
        let fg: Color = scheme == .dark ? Color.white.opacity(0.85) : Color.black.opacity(0.70)
        let bg: Color = scheme == .dark ? Color.white.opacity(0.09) : Color.black.opacity(0.06)
        let border: Color = scheme == .dark ? Color.white.opacity(0.18) : Color.black.opacity(0.08)
        let accent: Color = scheme == .dark ? Color.white : Color.black
        let accentFg: Color = scheme == .dark ? Color.black : Color.white
        let track: Color = scheme == .dark ? Color.white.opacity(0.16) : Color.black.opacity(0.10)

        let leftText: String = {
            switch phase {
            case .idle: return message
            case .running: return phaseText.isEmpty ? message : phaseText
            case .done: return doneText
            case .failed: return failedText
            }
        }()

        HStack(alignment: .center, spacing: 12) {
            VStack(alignment: .leading, spacing: 6) {
                Text(leftText)
                    .font(TpidTypography.font(size: 12, weight: .medium))
                    .foregroundStyle(fg)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .transition(.opacity)
                    .id(leftText) // animate text changes
                if phase == .running {
                    TpidUpdateProgressTrack(
                        progress: max(0, min(1, progress)),
                        indeterminate: indeterminate,
                        trackColor: track,
                        fillColor: accent
                    )
                    .frame(height: 4)
                }
            }
            Group {
                switch phase {
                case .idle:
                    pill(updateLabel, bg: accent, fg: accentFg, action: onStart)
                case .running:
                    TpidInlineSpinner(color: accent)
                        .frame(width: 22, height: 22)
                case .done:
                    TpidInlineCheck(color: accent)
                        .frame(width: 22, height: 22)
                case .failed:
                    pill(retryLabel, bg: accent, fg: accentFg, action: onStart)
                }
            }
            .transition(.opacity)
            .id(phase)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(RoundedRectangle(cornerRadius: 12).fill(bg))
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(border, lineWidth: 1))
        .animation(.easeInOut(duration: 0.2), value: phase)
        .animation(.easeInOut(duration: 0.2), value: leftText)
        .onChange(of: phase) { newPhase in
            guard newPhase == .done else { return }
            Task {
                try? await Task.sleep(nanoseconds: 2_800_000_000)
                await MainActor.run { onAutoDismiss() }
            }
        }
    }

    private func pill(_ label: String, bg: Color, fg: Color, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(label)
                .font(.system(size: 11, weight: .bold))
                .foregroundStyle(fg)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(Capsule().fill(bg))
        }
        .buttonStyle(.plain)
    }
}

/// Monochrome progress track matching the Compose `UpdateProgressTrack`.
private struct TpidUpdateProgressTrack: View {
    let progress: Double
    let indeterminate: Bool
    let trackColor: Color
    let fillColor: Color
    @State private var shuttle: Double = -0.4

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                Capsule().fill(trackColor)
                if indeterminate {
                    Capsule()
                        .fill(fillColor)
                        .frame(width: max(0, geo.size.width * 0.4))
                        .offset(x: shuttle * geo.size.width)
                        .onAppear {
                            withAnimation(
                                .linear(duration: 1.2).repeatForever(autoreverses: false)
                            ) { shuttle = 1.0 }
                        }
                } else {
                    Capsule()
                        .fill(fillColor)
                        .frame(width: max(0, CGFloat(progress) * geo.size.width))
                        .animation(.easeInOut(duration: 0.22), value: progress)
                }
            }
            .clipShape(Capsule())
        }
    }
}

/// Rotating arc stand-in for the pill during `.running`.
private struct TpidInlineSpinner: View {
    let color: Color
    @State private var angle: Double = 0
    var body: some View {
        Circle()
            .trim(from: 0, to: 0.75)
            .stroke(color, style: StrokeStyle(lineWidth: 2.4, lineCap: .round))
            .padding(2)
            .rotationEffect(.degrees(angle))
            .onAppear {
                withAnimation(.linear(duration: 1.1).repeatForever(autoreverses: false)) {
                    angle = 360
                }
            }
    }
}

/// Two-stroke check-mark reveal for `.done`.
private struct TpidInlineCheck: View {
    let color: Color
    @State private var reveal: CGFloat = 0

    var body: some View {
        Canvas { ctx, size in
            let p1 = CGPoint(x: size.width * 0.22, y: size.height * 0.55)
            let p2 = CGPoint(x: size.width * 0.42, y: size.height * 0.75)
            let p3 = CGPoint(x: size.width * 0.80, y: size.height * 0.30)
            let seg1: CGFloat = 1.0 / 3.0
            var path = Path()
            if reveal <= seg1 {
                let t = reveal / seg1
                path.move(to: p1)
                path.addLine(to: CGPoint(
                    x: p1.x + (p2.x - p1.x) * t,
                    y: p1.y + (p2.y - p1.y) * t
                ))
            } else {
                path.move(to: p1)
                path.addLine(to: p2)
                let t = min(1, max(0, (reveal - seg1) / (1 - seg1)))
                path.addLine(to: CGPoint(
                    x: p2.x + (p3.x - p2.x) * t,
                    y: p2.y + (p3.y - p2.y) * t
                ))
            }
            ctx.stroke(
                path,
                with: .color(color),
                style: StrokeStyle(lineWidth: 2.4, lineCap: .round, lineJoin: .round)
            )
        }
        .padding(2)
        .onAppear {
            reveal = 0
            withAnimation(.easeInOut(duration: 0.36)) { reveal = 1 }
        }
    }
}

/// Helper that maps a `TpidUpdatePhase` to a localisable progress label,
/// a `[0..1]` progress value and an `indeterminate` flag. Mirrors the
/// JVM / Android translators so all three SDKs share the same UX.
///
/// `downloadingFmt` and `downloadingUnknownFmt` receive the English
/// sprintf-style template (`"Downloading %1$s / %2$s"`, etc.); the caller
/// supplies already-formatted byte strings.
struct TpidUpdaterUIState: Sendable, Equatable {
    let text: String
    let progress: Double
    let indeterminate: Bool
}

func tpidMapPhaseToUI(
    _ phase: TpidUpdatePhase,
    checkingLabel: String,
    downloading: (Int64, Int64?) -> String,
    verifyingLabel: String,
    installingLabel: String,
    refreshingLabel: String,
    doneLabel: String,
    failedFmt: (String) -> String
) -> TpidUpdaterUIState {
    switch phase {
    case .checking:
        return TpidUpdaterUIState(text: checkingLabel, progress: 0.03, indeterminate: true)
    case let .downloading(bytes, total):
        let ratio: Double? = total.map { t in
            t > 0 ? Double(bytes) / Double(t) : 0
        }
        let indet = ratio == nil
        let p = indet ? 0 : 0.05 + 0.70 * (ratio ?? 0)
        return TpidUpdaterUIState(
            text: downloading(bytes, total),
            progress: max(0, min(1, p)),
            indeterminate: indet
        )
    case .verifying:
        return TpidUpdaterUIState(text: verifyingLabel, progress: 0.80, indeterminate: false)
    case .installing:
        return TpidUpdaterUIState(text: installingLabel, progress: 0.90, indeterminate: false)
    case .refreshingConfig:
        return TpidUpdaterUIState(text: refreshingLabel, progress: 0.96, indeterminate: false)
    case .done:
        return TpidUpdaterUIState(text: doneLabel, progress: 1, indeterminate: false)
    case let .failed(reason):
        return TpidUpdaterUIState(text: failedFmt(reason), progress: 0, indeterminate: false)
    }
}

/// Format a byte count as a short, locale-independent string (B / KB / MB).
/// Used by the banner's progress label so every locale sees "1.4 MB of
/// 2.1 MB" rendered identically.
func tpidHumanBytes(_ n: Int64) -> String {
    if n < 0 { return "" }
    if n < 1024 { return "\(n) B" }
    let kb = Double(n) / 1024.0
    if kb < 1024 { return String(format: "%.1f KB", kb) }
    let mb = kb / 1024.0
    if mb < 1024 { return String(format: "%.1f MB", mb) }
    let gb = mb / 1024.0
    return String(format: "%.2f GB", gb)
}

// MARK: - Screen subtitle (centered muted text)

struct ScreenSubtitle: View {
    let text: String
    var body: some View {
        if text.isEmpty {
            EmptyView()
        } else {
            Text(text)
                .font(.system(size: 14))
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: .infinity)
        }
    }
}

// MARK: - Email chip (compact summary pill)

struct TpidEmailChip: View {
    @Environment(\.colorScheme) private var scheme
    let email: String
    var body: some View {
        HStack {
            Image(systemName: "person.crop.circle").imageScale(.small)
            Text(email)
                .font(.system(size: 14, weight: .medium))
            Spacer()
        }
        .foregroundStyle(scheme == .dark ? Color.white.opacity(0.7) : Color.black.opacity(0.7))
        .padding(.horizontal, 16).padding(.vertical, 12)
        .background(RoundedRectangle(cornerRadius: 12).fill(scheme == .dark ? Color.white.opacity(0.08) : Color.black.opacity(0.05)))
    }
}

// MARK: - Link-style text button

struct TpidLinkText: View {
    @Environment(\.colorScheme) private var scheme
    let text: String
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            Text(text)
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(scheme == .dark ? Color.white.opacity(0.55) : Color.black.opacity(0.55))
                .padding(.vertical, 6)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Footer "No account? Create" inline

struct TpidFooterInline: View {
    @Environment(\.colorScheme) private var scheme
    let muted: String
    let link: String
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            (Text(muted + " ").foregroundColor(scheme == .dark ? Color.white.opacity(0.4) : Color.black.opacity(0.5))
             + Text(link).fontWeight(.bold).foregroundColor(scheme == .dark ? Color.white : Color.black))
                .font(.system(size: 13))
        }
        .buttonStyle(.plain)
    }
}
