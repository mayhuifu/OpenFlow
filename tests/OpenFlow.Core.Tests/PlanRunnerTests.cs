using System.Text.Json;
using OpenFlow.Core;
using Xunit;

namespace OpenFlow.Core.Tests;

public class PlanRunnerTests
{
    [Fact]
    public async Task RunAsync_pass_plan_returns_Pass_and_writes_json()
    {
        var pluginsDir = TestPaths.CopyFixturesToTempPluginDir();
        var planPath   = Path.Combine(pluginsDir, "plans", "pass.TapPlan");
        using var tempFile = new TempFile(".json");

        var runner = new PlanRunner();
        var result = await runner.RunAsync(
            new RunOptions(planPath, pluginsDir, tempFile.Path),
            CancellationToken.None);

        Assert.Equal(Verdict.Pass, result.Verdict);
        Assert.Equal(1, result.StepCount);
        Assert.Null(result.ErrorMessage);
        Assert.True(File.Exists(tempFile.Path));

        using var doc = JsonDocument.Parse(File.ReadAllText(tempFile.Path));
        Assert.Equal("Pass", doc.RootElement.GetProperty("verdict").GetString());
    }

    [Fact]
    public async Task RunAsync_fail_plan_returns_Fail()
    {
        var pluginsDir = TestPaths.CopyFixturesToTempPluginDir();
        var planPath   = Path.Combine(pluginsDir, "plans", "fail.TapPlan");
        using var tempFile = new TempFile(".json");

        var runner = new PlanRunner();
        var result = await runner.RunAsync(
            new RunOptions(planPath, pluginsDir, tempFile.Path),
            CancellationToken.None);

        Assert.Equal(Verdict.Fail, result.Verdict);
    }
}
