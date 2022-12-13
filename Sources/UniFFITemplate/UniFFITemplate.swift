import UniFFITemplateBindings

public enum UniFFITemplate {
    public static func add(a: UInt32, b: UInt32) -> UInt32 {
        UniFFITemplateBindings.add(a: a, b: b)
    }
}
