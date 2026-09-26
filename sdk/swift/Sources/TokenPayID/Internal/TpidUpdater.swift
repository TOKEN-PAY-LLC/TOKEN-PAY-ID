import Foundation
import CryptoKit

/// 2.6.1 — Smart in-place SDK updater (Apple platforms).
///
/// On iOS / iPadOS / tvOS, Apple policy forbids replacing the app's own
/// binary at runtime — the App Store wants every executable byte signed by
/// you and reviewed by them. What `TpidUpdater` *can* do honestly is:
///
///  1. Force-refresh `TpidRemoteConfig` so everything the server can
///     push — translated strings, theme tokens, feature flags — applies
///     live inside the running widget the instant the banner finishes
///     its animation. This is the real "in-place update" the user sees.
///  2. Download the SDK tarball (source + .xcframework) into the app's
///     Application Support directory and verify its SHA-256 (when the
///     server advertised one). That gives integrators a fresh artefact
///     for their next build without bouncing through a browser.
///  3. Emit a fine-grained `Phase` stream to the widget so the animated
///     update banner can draw a real progress bar, not a fake spinner.
///
/// The updater lives in `Internal/` and is driven by `WidgetViewModel` —
/// the UI never touches it directly, so Compose-style banners on the
/// JVM / Android side and the SwiftUI banner here share the same mental
/// model and (roughly) the same code flow.
struct TpidUpdaterInfo: Sendable {
    /// `true` iff the server-recommended version is strictly newer.
    let hasUpdate: Bool
    /// Version we're currently running.
    let currentVersion: String
    /// Version the server considers the latest.
    let latestVersion: String?
    /// HTTPS URL of the tarball; may be empty.
    let downloadURL: String
    /// Expected SHA-256 of `downloadURL`; `nil` when server omits it.
    let sha256: String?
    /// Optional changelog, surfaced as the banner's tooltip text.
    let updateNotes: String
}

/// Fine-grained updater state for the animated banner.
enum TpidUpdatePhase: Sendable, Equatable {
    /// Preparing the download, no bytes yet.
    case checking
    /// Actively downloading; `total == nil` when the server omitted
    /// Content-Length (the banner switches to an indeterminate bar).
    case downloading(bytes: Int64, total: Int64?)
    /// SHA-256 check in progress.
    case verifying
    /// Extracting / moving files into the cache.
    case installing
    /// Rolling the new `TpidRemoteConfig` into the running widget.
    case refreshingConfig
    /// Terminal — success.
    case done(cachedPath: URL?, newConfig: TpidRemoteConfig)
    /// Terminal — error; the updater cleaned up any partial files.
    case failed(reason: String)

    static func == (lhs: TpidUpdatePhase, rhs: TpidUpdatePhase) -> Bool {
        switch (lhs, rhs) {
        case (.checking, .checking),
             (.verifying, .verifying),
             (.installing, .installing),
             (.refreshingConfig, .refreshingConfig):
            return true
        case let (.downloading(a, b), .downloading(c, d)):
            return a == c && b == d
        case let (.done(a, _), .done(b, _)):
            return a == b
        case let (.failed(a), .failed(b)):
            return a == b
        default:
            return false
        }
    }
}

/// Session / filesystem-aware updater. The `session` and `cacheRoot`
/// parameters exist for testability — production code uses the defaults.
final class TpidUpdater: @unchecked Sendable {
    private let api: ApiClient
    private let clientId: String
    private let session: URLSession
    private let cacheRoot: URL

    init(
        api: ApiClient,
        clientId: String,
        session: URLSession = .shared,
        cacheRoot: URL? = nil
    ) {
        self.api = api
        self.clientId = clientId
        self.session = session
        self.cacheRoot = cacheRoot ?? Self.defaultCacheRoot()
    }

    /// Query the server without hitting the in-memory cache. Never throws;
    /// a network failure collapses to `hasUpdate=false` so the banner
    /// disappears instead of throwing an ugly error at the user.
    func checkForUpdate() async -> TpidUpdaterInfo {
        TpidRemoteConfig.invalidateCache()
        let cfg = await TpidRemoteConfig.fetch(api: api, clientId: clientId)
        let current = TpidVersion.string
        let latest = cfg.recommendedSdkVersion
        let isNewer = cfg.isOlderThan(latest)
        let url = cfg.downloadUrl ?? ""
        return TpidUpdaterInfo(
            hasUpdate: isNewer && !url.isEmpty,
            currentVersion: current,
            latestVersion: latest,
            downloadURL: url,
            sha256: (cfg.downloadSha256?.isEmpty == false) ? cfg.downloadSha256 : nil,
            updateNotes: cfg.updateNotes ?? ""
        )
    }

    /// Drive the full update state machine. `onPhase` is invoked on
    /// whichever queue the caller drove the `await` from — typically a
    /// `@MainActor` context. Cancellation aborts cleanly and deletes any
    /// partial download.
    ///
    /// The method always resolves to a terminal phase (`.done` or
    /// `.failed`) — the caller never needs to handle "stuck" state.
    func performUpdate(
        onPhase: @Sendable @escaping (TpidUpdatePhase) -> Void
    ) async -> TpidUpdatePhase {
        var partial: URL?
        func fail(_ reason: String) -> TpidUpdatePhase {
            if let p = partial { try? FileManager.default.removeItem(at: p) }
            let f = TpidUpdatePhase.failed(reason: reason)
            onPhase(f)
            return f
        }
        onPhase(.checking)

        let info = await checkForUpdate()
        if !info.hasUpdate {
            // No newer tarball to fetch — still refresh the config so the
            // user sees *something* from clicking Update. This is the
            // whole point of a smart update button.
            let cfg = await TpidRemoteConfig.fetch(api: api, clientId: clientId)
            onPhase(.refreshingConfig)
            let done = TpidUpdatePhase.done(cachedPath: nil, newConfig: cfg)
            onPhase(done)
            return done
        }

        guard let url = URL(string: info.downloadURL) else {
            return fail("invalid downloadUrl: \(info.downloadURL)")
        }

        let versionDir = cacheRoot
            .appendingPathComponent(info.latestVersion ?? "latest", isDirectory: true)
        try? FileManager.default.createDirectory(
            at: versionDir, withIntermediateDirectories: true
        )
        let fileName = url.lastPathComponent.isEmpty ? "sdk.tar.gz" : url.lastPathComponent
        let target = versionDir.appendingPathComponent(fileName)
        let tempTarget = versionDir.appendingPathComponent(fileName + ".part")
        try? FileManager.default.removeItem(at: tempTarget)
        partial = tempTarget

        // --- download ---
        var req = URLRequest(url: url)
        req.setValue("TokenPayID-Swift/\(TpidVersion.string)", forHTTPHeaderField: "User-Agent")

        let bytes: URLSession.AsyncBytes
        let response: URLResponse
        do {
            (bytes, response) = try await session.bytes(for: req)
        } catch {
            return fail("download failed: \(error.localizedDescription)")
        }
        if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
            return fail("download failed: HTTP \(http.statusCode)")
        }
        let total: Int64? = (response as? HTTPURLResponse)?.expectedContentLength
            .map { $0 > 0 ? Int64($0) : Int64(0) }
            .flatMap { $0 > 0 ? $0 : nil }
        onPhase(.downloading(bytes: 0, total: total))

        guard FileManager.default.createFile(atPath: tempTarget.path, contents: nil) else {
            return fail("cannot create cache file at \(tempTarget.path)")
        }
        let handle: FileHandle
        do {
            handle = try FileHandle(forWritingTo: tempTarget)
        } catch {
            return fail("cannot open cache file: \(error.localizedDescription)")
        }
        defer { try? handle.close() }

        var received: Int64 = 0
        var lastEmitBytes: Int64 = 0
        var buffer = Data()
        buffer.reserveCapacity(64 * 1024)

        do {
            for try await byte in bytes {
                buffer.append(byte)
                received += 1
                if buffer.count >= 64 * 1024 {
                    try handle.write(contentsOf: buffer)
                    buffer.removeAll(keepingCapacity: true)
                }
                if received - lastEmitBytes >= 64 * 1024 {
                    let snapshot = received
                    onPhase(.downloading(bytes: snapshot, total: total))
                    lastEmitBytes = snapshot
                }
            }
            if !buffer.isEmpty {
                try handle.write(contentsOf: buffer)
                buffer.removeAll(keepingCapacity: true)
            }
        } catch is CancellationError {
            try? FileManager.default.removeItem(at: tempTarget)
            return fail("download cancelled")
        } catch {
            return fail("download failed mid-stream: \(error.localizedDescription)")
        }
        onPhase(.downloading(bytes: received, total: total ?? received))

        // --- verify ---
        onPhase(.verifying)
        let actualSha = Self.sha256Hex(of: tempTarget)
        if let expected = info.sha256,
           expected.lowercased() != actualSha.lowercased() {
            return fail("sha256 mismatch: expected \(expected), got \(actualSha)")
        }

        // --- install ---
        onPhase(.installing)
        try? FileManager.default.removeItem(at: target)
        do {
            try FileManager.default.moveItem(at: tempTarget, to: target)
        } catch {
            // Cross-volume fallback.
            do {
                try FileManager.default.copyItem(at: tempTarget, to: target)
                try? FileManager.default.removeItem(at: tempTarget)
            } catch {
                return fail("install failed: \(error.localizedDescription)")
            }
        }
        partial = nil

        // Breadcrumb for any future `TpidUpdateBootstrap`-style integration.
        let markerURL = cacheRoot.appendingPathComponent("current")
        let marker = "\(info.latestVersion ?? "unknown")\t\(target.path)\t\(actualSha)\n"
        try? marker.data(using: .utf8)?.write(to: markerURL)

        // --- refresh live config ---
        onPhase(.refreshingConfig)
        TpidRemoteConfig.invalidateCache()
        let fresh = await TpidRemoteConfig.fetch(api: api, clientId: clientId)

        let done = TpidUpdatePhase.done(cachedPath: target, newConfig: fresh)
        onPhase(done)
        return done
    }

    // MARK: - helpers

    private static func defaultCacheRoot() -> URL {
        let fm = FileManager.default
        let base: URL
        if let support = try? fm.url(
            for: .applicationSupportDirectory,
            in: .userDomainMask,
            appropriateFor: nil,
            create: true
        ) {
            base = support
        } else {
            base = fm.temporaryDirectory
        }
        let dir = base.appendingPathComponent("tokenpay-id/sdk", isDirectory: true)
        try? fm.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    /// Streaming SHA-256 computation. Avoids loading the whole tarball
    /// into memory on low-RAM devices.
    private static func sha256Hex(of file: URL) -> String {
        guard let handle = try? FileHandle(forReadingFrom: file) else { return "" }
        defer { try? handle.close() }
        var hasher = SHA256()
        while true {
            let chunk: Data
            do {
                chunk = try handle.read(upToCount: 128 * 1024) ?? Data()
            } catch {
                return ""
            }
            if chunk.isEmpty { break }
            hasher.update(data: chunk)
        }
        return hasher.finalize().map { String(format: "%02x", $0) }.joined()
    }
}
