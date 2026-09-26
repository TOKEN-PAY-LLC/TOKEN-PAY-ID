import Foundation

/// Runtime-fetched configuration for the TOKEN PAY ID widget on Apple
/// platforms.
///
/// Mirrors the Android and JVM `RemoteConfig` classes. Integrators don't have
/// to rebuild their app to pick up new colour tokens, translated strings, or
/// feature-flag toggles — the widget calls
/// `GET /api/v1/sdk/config?client_id=…` once per launch and merges the
/// `remote` section on top of the bundled defaults.
struct TpidRemoteConfig: Sendable {
    /// `name` (or `dark.name` / `light.name`) → `#RRGGBB`.
    let themeTokens: [String: String]
    /// `lang` → `key` → translated string.
    let stringsOverride: [String: [String: String]]
    /// `name` → `true` / `false`.
    let featureFlags: [String: Bool]
    /// SDKs older than this receive a "mandatory update" banner.
    let minSdkVersion: String?
    /// SDKs older than this receive a gentle "update recommended" banner.
    let recommendedSdkVersion: String?
    /// 2.6.0 — URL the update banner's "Update" pill opens in the default
    /// browser. Populated from `remote.download_url` in `/sdk/config`.
    let downloadUrl: String?
    /// 2.6.0 — short changelog for the update banner tooltip.
    let updateNotes: String?
    /// 2.6.1 — SHA-256 of the `downloadUrl` tarball (lowercase hex).
    /// `TpidUpdater` verifies this byte-for-byte before moving the cached
    /// download into its final slot. `nil` means the server didn't emit
    /// one; the updater still succeeds but cannot self-attest integrity.
    let downloadSha256: String?

    static let empty = TpidRemoteConfig(
        themeTokens: [:], stringsOverride: [:], featureFlags: [:],
        minSdkVersion: nil, recommendedSdkVersion: nil,
        downloadUrl: nil, updateNotes: nil, downloadSha256: nil
    )

    // Process-wide cache (keyed on client id). Never throws — a network or
    // parse failure simply returns an empty config.
    private static let lock = NSLock()
    private static var cachedClientId: String?
    private static var cached: TpidRemoteConfig = .empty

    /// Fetch the config for [clientId] via [api]. Safe to call multiple times:
    /// the result is memoised for the lifetime of the process.
    static func fetch(api: ApiClient, clientId: String) async -> TpidRemoteConfig {
        lock.lock()
        if cachedClientId == clientId {
            let hit = cached
            lock.unlock()
            return hit
        }
        lock.unlock()

        let parsed: TpidRemoteConfig
        do {
            let payload = try await api.fetchSdkConfig(clientId: clientId)
            parsed = parse(payload: payload)
        } catch {
            parsed = .empty
        }

        lock.lock()
        cached = parsed
        cachedClientId = clientId
        lock.unlock()
        return parsed
    }

    /// 2.6.1 — Drop the memoised snapshot. `TpidUpdater` calls this before
    /// its force-refresh so the next `fetch(api:clientId:)` goes to the
    /// network and any hot-pushed strings / theme / flags apply live in
    /// the running widget.
    static func invalidateCache() {
        lock.lock()
        cachedClientId = nil
        cached = .empty
        lock.unlock()
    }

    private static func parse(payload: [String: Any]) -> TpidRemoteConfig {
        guard let remote = payload["remote"] as? [String: Any] else { return .empty }

        let theme: [String: String] = (remote["theme_tokens"] as? [String: Any])?
            .compactMapValues { ($0 as? String) } ?? [:]

        let strings: [String: [String: String]]
        if let rawStrings = remote["strings_override"] as? [String: Any] {
            var built: [String: [String: String]] = [:]
            for (lang, entry) in rawStrings {
                if let dict = entry as? [String: Any] {
                    let ov = dict.compactMapValues { $0 as? String }
                    if !ov.isEmpty { built[lang] = ov }
                }
            }
            strings = built
        } else {
            strings = [:]
        }

        let flags: [String: Bool]
        if let rawFlags = remote["feature_flags"] as? [String: Any] {
            // Backend emits strings like "true" / "false" — accept both.
            flags = rawFlags.compactMapValues { raw in
                if let b = raw as? Bool { return b }
                if let s = raw as? String { return s.lowercased() == "true" }
                return nil
            }
        } else {
            flags = [:]
        }

        return TpidRemoteConfig(
            themeTokens: theme,
            stringsOverride: strings,
            featureFlags: flags,
            minSdkVersion: remote["min_sdk_version"] as? String,
            recommendedSdkVersion: remote["recommended_sdk_version"] as? String,
            downloadUrl: remote["download_url"] as? String,
            updateNotes: remote["update_notes"] as? String,
            downloadSha256: remote["download_sha256"] as? String,
        )
    }

    /// Returns `true` when the currently running SDK build is older than
    /// [other]. A missing [other] is treated as "no newer build available",
    /// so the caller never shows a banner spuriously.
    func isOlderThan(_ other: String?) -> Bool {
        guard let other else { return false }
        return Self.compareSemver(TpidVersion.string, other) < 0
    }

    /// Good-enough semver comparison for the two version strings we handle.
    /// Pre-release suffixes (`-pre.N`, `-rc.N`) sort *before* the same bare
    /// version, which matches integrator intuition.
    static func compareSemver(_ a: String, _ b: String) -> Int {
        func split(_ v: String) -> (nums: [Int], hasSuffix: Bool, suffix: String) {
            let parts = v.split(separator: "-", maxSplits: 1, omittingEmptySubsequences: false)
            let core = String(parts[0])
            let suffix = parts.count > 1 ? String(parts[1]) : ""
            let nums = core.split(separator: ".").compactMap { Int($0) }
            return (nums, !suffix.isEmpty, suffix)
        }
        let lhs = split(a)
        let rhs = split(b)
        let count = max(lhs.nums.count, rhs.nums.count)
        for i in 0..<count {
            let l = i < lhs.nums.count ? lhs.nums[i] : 0
            let r = i < rhs.nums.count ? rhs.nums[i] : 0
            if l != r { return l < r ? -1 : 1 }
        }
        if lhs.hasSuffix != rhs.hasSuffix {
            // No suffix ("2.5.0") is newer than "2.5.0-pre.2".
            return lhs.hasSuffix ? -1 : 1
        }
        if lhs.suffix != rhs.suffix {
            return lhs.suffix < rhs.suffix ? -1 : 1
        }
        return 0
    }
}
