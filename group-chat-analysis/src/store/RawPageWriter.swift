import Foundation

enum RawPageWriterError: Error, CustomStringConvertible {
    case outputAlreadyExists(String)

    var description: String {
        switch self {
        case let .outputAlreadyExists(path):
            return "Refusing to overwrite existing raw page: \(path)"
        }
    }
}

func writeRawPageAtomically(_ page: RawCapturePage, to path: String) throws {
    let destination = URL(fileURLWithPath: path)
    let fileManager = FileManager.default

    if fileManager.fileExists(atPath: destination.path) {
        throw RawPageWriterError.outputAlreadyExists(destination.path)
    }

    try fileManager.createDirectory(
        at: destination.deletingLastPathComponent(),
        withIntermediateDirectories: true
    )

    let encoder = JSONEncoder()
    encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
    let data = try encoder.encode(page)

    let temp = destination
        .deletingLastPathComponent()
        .appendingPathComponent(".\(destination.lastPathComponent).tmp-\(UUID().uuidString)")

    do {
        try data.write(to: temp)
        try fileManager.moveItem(at: temp, to: destination)
    } catch {
        try? fileManager.removeItem(at: temp)
        throw error
    }
}
