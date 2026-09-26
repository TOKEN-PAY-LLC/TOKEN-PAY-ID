import Foundation

/// Result of a widget session.
public enum TpidResult: Sendable {
    case success(TpidSession)
    case cancelled
    case failure(TpidError)
}

public struct TpidSession: Sendable, Codable, Equatable {
    public let accessToken: String
    public let refreshToken: String?
    public let idToken: String?
    public let expiresAt: Date
    public let tokenType: String
    public let scope: String
    public let user: TpidUser

    public var isValid: Bool { expiresAt.timeIntervalSinceNow > 30 }
}

public struct TpidUser: Sendable, Codable, Equatable {
    public let id: String
    public let email: String
    public let emailVerified: Bool
    public let name: String?
    public let avatarURL: URL?
    public let locale: String?
    public let has2FA: Bool
    public let hasPasskey: Bool
    public let createdAt: String

    public init(
        id: String, email: String, emailVerified: Bool,
        name: String? = nil, avatarURL: URL? = nil, locale: String? = nil,
        has2FA: Bool = false, hasPasskey: Bool = false, createdAt: String = ""
    ) {
        self.id = id; self.email = email; self.emailVerified = emailVerified
        self.name = name; self.avatarURL = avatarURL; self.locale = locale
        self.has2FA = has2FA; self.hasPasskey = hasPasskey; self.createdAt = createdAt
    }
}
