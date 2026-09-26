import Foundation
import CoreImage
import CoreImage.CIFilterBuiltins
import SwiftUI

#if canImport(UIKit)
import UIKit
typealias PlatformImage = UIImage
#elseif canImport(AppKit)
import AppKit
typealias PlatformImage = NSImage
#endif

/// Renders a QR payload (typically the `tokenpay.space/qr-login?sid=…` URL
/// returned by `/auth/qr/login-init`) into a scalable SwiftUI `Image`.
///
/// Uses the bundled `CIQRCodeGenerator` so there is no third-party dep —
/// it ships with CoreImage on every Apple platform the SDK supports
/// (iOS 15+, macOS 12+, tvOS/watchOS/visionOS). `errorCorrection = "M"`
/// matches the web widget and ZXing settings on JVM/Android so all three
/// platforms produce visually identical codes.
enum TpidQrRenderer {

    static func render(_ text: String) -> Image? {
        guard !text.isEmpty, let data = text.data(using: .utf8) else { return nil }
        let filter = CIFilter.qrCodeGenerator()
        filter.message = data
        filter.correctionLevel = "M"
        guard let output = filter.outputImage else { return nil }

        // CIQRCodeGenerator outputs at 1 px per QR module — scale up ~12×
        // so the output stays crisp when rendered at ~200-220 pt.
        let scaled = output.transformed(by: CGAffineTransform(scaleX: 12, y: 12))

        let ctx = CIContext(options: nil)
        guard let cg = ctx.createCGImage(scaled, from: scaled.extent) else { return nil }

        #if canImport(UIKit)
        return Image(uiImage: UIImage(cgImage: cg))
            .interpolation(.none)
        #elseif canImport(AppKit)
        let ns = NSImage(cgImage: cg, size: .zero)
        return Image(nsImage: ns)
            .interpolation(.none)
        #else
        return nil
        #endif
    }
}
