// swift-tools-version: 5.9
// OpenPatchCore: pure Swift, no LoopKit / UIKit dependency. Runs `swift test` on macOS.
import PackageDescription

let package = Package(
    name: "OpenPatchCore",
    platforms: [.iOS(.v15), .macOS(.v12)],
    products: [
        .library(name: "OpenPatchCore", targets: ["OpenPatchCore"])
    ],
    targets: [
        .target(name: "OpenPatchCore"),
        .testTarget(name: "OpenPatchCoreTests", dependencies: ["OpenPatchCore"])
    ]
)
