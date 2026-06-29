import XCTest

final class PackagingScriptTests: XCTestCase {
    func testPackageScriptBuildsReleaseAppAndCreatesZip() throws {
        let testFile = URL(fileURLWithPath: #filePath)
        let cueRoot = testFile
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        let script = cueRoot.appendingPathComponent("scripts/package_app.sh")
        let content = try String(contentsOf: script, encoding: .utf8)
        let isExecutable = FileManager.default.isExecutableFile(atPath: script.path)

        XCTAssertTrue(isExecutable, "package_app.sh must be executable for pixi run package")
        XCTAssertTrue(content.contains("xcodebuild"), "package_app.sh should use xcodebuild")
        XCTAssertTrue(content.contains("-configuration Release"), "package_app.sh should build Release")
        XCTAssertTrue(content.contains("build/mac"), "package_app.sh should use the existing build/mac derived data path")
        XCTAssertTrue(content.contains("dist/CueApp.zip"), "package_app.sh should create dist/CueApp.zip")
        XCTAssertTrue(content.contains("zip"), "package_app.sh should zip the built app")
    }
}
