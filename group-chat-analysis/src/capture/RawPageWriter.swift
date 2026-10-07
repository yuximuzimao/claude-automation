import Darwin
import Foundation

enum RawPageWriterError: Error, CustomStringConvertible {
    case outputAlreadyExists(String)
    case syncFailed(String)

    var description: String {
        switch self {
        case let .outputAlreadyExists(path):
            return "Refusing to overwrite existing raw page: \(path)"
        case let .syncFailed(path):
            return "Failed to fsync raw capture data: \(path)"
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
    let temporary = destination.deletingLastPathComponent()
        .appendingPathComponent(".\(destination.lastPathComponent).tmp-\(UUID().uuidString)")

    do {
        try data.write(to: temporary)
        try fsyncPath(temporary)
        try fileManager.moveItem(at: temporary, to: destination)
        try fsyncDirectory(destination.deletingLastPathComponent())
    } catch {
        try? fileManager.removeItem(at: temporary)
        throw error
    }
}

private func fsyncPath(_ url: URL) throws {
    let descriptor = open(url.path, O_RDONLY)
    guard descriptor >= 0 else {
        throw RawPageWriterError.syncFailed(url.path)
    }
    defer { close(descriptor) }
    guard fsync(descriptor) == 0 else {
        throw RawPageWriterError.syncFailed(url.path)
    }
}

private func fsyncDirectory(_ url: URL) throws {
    let descriptor = open(url.path, O_RDONLY)
    guard descriptor >= 0 else {
        throw RawPageWriterError.syncFailed(url.path)
    }
    defer { close(descriptor) }
    guard fsync(descriptor) == 0 else {
        throw RawPageWriterError.syncFailed(url.path)
    }
}
