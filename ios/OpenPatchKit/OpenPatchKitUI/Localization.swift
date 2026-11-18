import Foundation

private final class BundleToken {}

extension Bundle {
    static var openPatchUI: Bundle { Bundle(for: BundleToken.self) }
}

/// English text is the key. Translations live in Resources/{en,de}.lproj/Localizable.strings.
func L(_ key: String) -> String {
    NSLocalizedString(key, bundle: .openPatchUI, comment: "")
}

func L(_ key: String, _ args: CVarArg...) -> String {
    String(format: NSLocalizedString(key, bundle: .openPatchUI, comment: ""), arguments: args)
}
