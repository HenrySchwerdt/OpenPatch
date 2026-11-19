// swift-tools-version: 5.9
// OpenPatchCore: pure Swift, no LoopKit / UIKit dependency. Runs `swift test` on macOS and Linux.
// Crypto: CryptoKit on Apple platforms; swift-crypto (`Crypto`, same API) everywhere else (Linux CI).
import PackageDescription

let package = Package(
    name: "OpenPatchCore",
    platforms: [.iOS(.v15), .macOS(.v12)],
    products: [
        .library(name: "OpenPatchCore", targets: ["OpenPatchCore"])
    ],
    dependencies: [
        .package(url: "https://github.com/apple/swift-crypto.git", "3.0.0"..<"4.0.0")
    ],
    targets: [
        .target(
            name: "OpenPatchCore",
            dependencies: [.product(name: "Crypto", package: "swift-crypto", condition: .when(platforms: [.linux, .windows, .android]))]
        ),
        .testTarget(name: "OpenPatchCoreTests", dependencies: ["OpenPatchCore"])
    ]
)
