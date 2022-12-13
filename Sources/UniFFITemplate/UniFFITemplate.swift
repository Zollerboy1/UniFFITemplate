import UniFFITemplateBindings

public enum UniFFITemplate {
    public static func add(a: Int32, b: Int32) -> Int32 {
        UniFFITemplateBindings.add(a: a, b: b)
    }
}
