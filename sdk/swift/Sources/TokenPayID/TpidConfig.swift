import Foundation

/// Configuration for TOKEN PAY ID native widget.
public struct TpidConfig: Sendable, Equatable {
    public let clientId: String
    public let redirectURI: URL
    public let scopes: [String]
    public let issuer: URL
    public let theme: Theme
    public let language: Language
    public let presentation: Presentation
    public let prefillEmail: String?
    public let allowRegister: Bool
    public let allowPasskey: Bool
    public let allowRecovery: Bool
    public let pinTLSCertificates: Bool
    public let enableTelemetry: Bool
    public let brandingOverride: Branding?

    public init(
        clientId: String,
        redirectURI: URL,
        scopes: [String] = ["openid", "profile", "email"],
        issuer: URL = URL(string: "https://id.tokenpay.space")!,
        theme: Theme = .auto,
        language: Language = .system,
        presentation: Presentation = .sheet,
        prefillEmail: String? = nil,
        allowRegister: Bool = true,
        allowPasskey: Bool = true,
        allowRecovery: Bool = true,
        pinTLSCertificates: Bool = true,
        enableTelemetry: Bool = true,
        brandingOverride: Branding? = nil
    ) {
        precondition(clientId.hasPrefix("tpid_pk_"), "clientId must start with 'tpid_pk_'")
        precondition(!scopes.isEmpty, "at least one scope required")
        precondition(issuer.scheme == "https", "issuer must be HTTPS")
        self.clientId = clientId
        self.redirectURI = redirectURI
        self.scopes = scopes
        self.issuer = issuer
        self.theme = theme
        self.language = language
        self.presentation = presentation
        self.prefillEmail = prefillEmail
        self.allowRegister = allowRegister
        self.allowPasskey = allowPasskey
        self.allowRecovery = allowRecovery
        self.pinTLSCertificates = pinTLSCertificates
        self.enableTelemetry = enableTelemetry
        self.brandingOverride = brandingOverride
    }

    public enum Theme: String, Sendable, Codable { case light, dark, auto }

    public enum Language: String, Sendable, Codable {
        case system, ru, en, zh
        public static func fromCode(_ code: String?) -> Language {
            Language(rawValue: code ?? "system") ?? .system
        }
    }

    public enum Presentation: Sendable, Equatable {
        case sheet         // modal sheet on iOS, sheet on macOS
        case fullScreen    // fullScreenCover on iOS
        case embedded      // caller embeds in own view tree
    }

    public struct Branding: Sendable, Equatable, Codable {
        public let logoURL: URL?
        public let primaryColorHex: String?
        public let appName: String?
        public let appDomain: String?
        public init(logoURL: URL? = nil, primaryColorHex: String? = nil, appName: String? = nil, appDomain: String? = nil) {
            self.logoURL = logoURL
            self.primaryColorHex = primaryColorHex
            self.appName = appName
            self.appDomain = appDomain
        }
    }

    public var scopeString: String { scopes.joined(separator: " ") }
}
