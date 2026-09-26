// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "TokenPayID",
    defaultLocalization: "en",
    platforms: [
        .iOS(.v15),
        .macOS(.v12),
        .tvOS(.v15),
        .watchOS(.v8),
        .visionOS(.v1),
    ],
    products: [
        .library(
            name: "TokenPayID",
            targets: ["TokenPayID"]
        ),
    ],
    targets: [
        .target(
            name: "TokenPayID",
            path: "Sources/TokenPayID",
            resources: [
                .process("Resources"),
            ]
        ),
        .testTarget(
            name: "TokenPayIDTests",
            dependencies: ["TokenPayID"],
            path: "Tests/TokenPayIDTests"
        ),
    ]
)
