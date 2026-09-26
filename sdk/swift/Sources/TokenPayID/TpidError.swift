import Foundation

/// Errors that can terminate a widget session.
public enum TpidError: Error, Sendable, CustomStringConvertible, LocalizedError {
    case userCancelled
    case noNetwork
    case timeout
    case invalidCredentials(reason: String?)
    case accountLocked(until: String?)
    case emailNotVerified
    case twoFactorRequired(methods: [String])
    case passkeyFailed(reason: String)
    case rateLimited(retryAfterSec: Int)
    case phishingDetected(host: String)
    case oauthError(code: String, description: String?)
    case configurationError(reason: String)
    case serverError(status: Int, reason: String?)
    case unknown(underlying: Error?)

    public var code: String {
        switch self {
        case .userCancelled:          return "user_cancelled"
        case .noNetwork:              return "no_network"
        case .timeout:                return "timeout"
        case .invalidCredentials:     return "invalid_credentials"
        case .accountLocked:          return "account_locked"
        case .emailNotVerified:       return "email_not_verified"
        case .twoFactorRequired:      return "totp_required"
        case .passkeyFailed:          return "passkey_failed"
        case .rateLimited:            return "rate_limited"
        case .phishingDetected:       return "phishing_detected"
        case .oauthError(let c, _):   return c
        case .configurationError:     return "config_error"
        case .serverError(let s, _):  return "server_error_\(s)"
        case .unknown:                return "unknown"
        }
    }

    public var description: String {
        switch self {
        case .userCancelled:                 return "User cancelled"
        case .noNetwork:                     return "No network connection"
        case .timeout:                       return "Request timed out"
        case .invalidCredentials(let r):     return r ?? "Invalid credentials"
        case .accountLocked(let u):          return "Account locked" + (u.map { " until \($0)" } ?? "")
        case .emailNotVerified:              return "Email not verified"
        case .twoFactorRequired:             return "Two-factor authentication required"
        case .passkeyFailed(let r):          return "Passkey failed: \(r)"
        case .rateLimited(let s):            return "Rate limited; retry in \(s)s"
        case .phishingDetected(let h):       return "TLS pin mismatch for \(h)"
        case .oauthError(let c, let d):      return "\(c): \(d ?? "")"
        case .configurationError(let r):     return "Configuration error: \(r)"
        case .serverError(let s, let r):     return "Server error \(s)" + (r.map { ": \($0)" } ?? "")
        case .unknown(let e):                return e?.localizedDescription ?? "Unknown error"
        }
    }

    public var errorDescription: String? { description }
}
