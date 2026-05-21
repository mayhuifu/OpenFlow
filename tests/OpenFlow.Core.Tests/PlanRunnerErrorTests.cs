using OpenFlow.Core;
using Xunit;

namespace OpenFlow.Core.Tests;

public class PlanRunnerErrorTests
{
    [Fact]
    public async Task RunAsync_missing_plan_file_returns_Error_with_message()
    {
        var pluginsDir = TestPaths.CopyFixturesToTempPluginDir();
        using var tempFile = new TempFile(".json");

        var runner = new PlanRunner();
        var result = await runner.RunAsync(
            new RunOptions("/path/does/not/exist.TapPlan", pluginsDir, tempFile.Path),
            CancellationToken.None);

        Assert.Equal(Verdict.Error, result.Verdict);
        Assert.NotNull(result.ErrorMessage);
        Assert.Contains("Plan file not found", result.ErrorMessage!);
    }

    [Fact]
    public async Task RunAsync_missing_plugins_dir_throws_DirectoryNotFound()
    {
        // Plan file must exist so the plugins-dir check is the one that fires.
        using var planFile   = new TempFile(".TapPlan");
        using var outputFile = new TempFile(".json");
        File.WriteAllText(planFile.Path, "<TestPlan/>");

        var runner = new PlanRunner();

        await Assert.ThrowsAsync<DirectoryNotFoundException>(
            () => runner.RunAsync(
                new RunOptions(planFile.Path, "/nonexistent", outputFile.Path),
                CancellationToken.None));
    }

    [Fact]
    public async Task RunAsync_throwing_step_returns_Error_verdict()
    {
        var pluginsDir = TestPaths.CopyFixturesToTempPluginDir();
        var planPath   = Path.Combine(pluginsDir, "plans", "throw.TapPlan");
        using var tempFile = new TempFile(".json");

        var runner = new PlanRunner();
        var result = await runner.RunAsync(
            new RunOptions(planPath, pluginsDir, tempFile.Path),
            CancellationToken.None);

        Assert.Equal(Verdict.Error, result.Verdict);
    }
}
