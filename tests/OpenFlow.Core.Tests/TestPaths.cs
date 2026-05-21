using System.IO;
using System.Reflection;

namespace OpenFlow.Core.Tests;

internal static class TestPaths
{
    public static string FixtureBuildOutput()
    {
        // tests/OpenFlow.Core.Tests/bin/<Cfg>/net8.0/ → tests/Fixtures.TestSteps/bin/<Cfg>/net8.0/
        var testDir = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location)!;
        var cfgDir  = Path.GetFileName(Path.GetDirectoryName(testDir))!; // "Debug" or "Release"
        var repoRoot = Path.GetFullPath(Path.Combine(testDir, "..", "..", "..", "..", ".."));
        return Path.Combine(repoRoot, "tests", "Fixtures.TestSteps", "bin", cfgDir, "net8.0");
    }

    public static string CopyFixturesToTempPluginDir()
    {
        var src  = FixtureBuildOutput();
        var dest = Path.Combine(Path.GetTempPath(), "openflow-plugins-" + Path.GetRandomFileName());
        Directory.CreateDirectory(dest);

        // Copy the fixture DLL + every dependency next to it (OpenTap.dll etc.)
        foreach (var file in Directory.EnumerateFiles(src))
            File.Copy(file, Path.Combine(dest, Path.GetFileName(file)), overwrite: true);
        if (Directory.Exists(Path.Combine(src, "plans")))
        {
            var plansDest = Path.Combine(dest, "plans");
            Directory.CreateDirectory(plansDest);
            foreach (var p in Directory.EnumerateFiles(Path.Combine(src, "plans")))
                File.Copy(p, Path.Combine(plansDest, Path.GetFileName(p)), overwrite: true);
        }
        return dest;
    }
}
