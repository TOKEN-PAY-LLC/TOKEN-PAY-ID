import Foundation
import CryptoKit

/// PKCE S256 helper per RFC 7636.
enum PkceUtils {
    struct Pair: Sendable {
        let verifier: String
        let challenge: String
        let method = "S256"
    }

    static func generate() -> Pair {
        var bytes = Data(count: 32)
        _ = bytes.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, 32, $0.baseAddress!) }
        let verifier = base64URLEncode(bytes)
        let digest = SHA256.hash(data: Data(verifier.utf8))
        let challenge = base64URLEncode(Data(digest))
        return .init(verifier: verifier, challenge: challenge)
    }

    static func randomState(bytes: Int = 24) -> String {
        var buf = Data(count: bytes)
        _ = buf.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, bytes, $0.baseAddress!) }
        return base64URLEncode(buf)
    }

    static func randomNonce() -> String { randomState(bytes: 16) }

    static func base64URLEncode(_ data: Data) -> String {
        data.base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }
}
