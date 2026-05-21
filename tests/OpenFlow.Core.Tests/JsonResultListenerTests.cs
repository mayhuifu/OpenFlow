using System.Text.Json;
using OpenFlow.Core;
using Xunit;

namespace OpenFlow.Core.Tests;

public class JsonResultListenerTests
{
    [Fact]
    public void Write_emits_plan_and_step_verdicts()
    {
        using var tempFile = new TempFile(".json");
        var listener = new JsonResultListener();
        var run = new FakePlanRun("MyPlan", Verdict.Pass, TimeSpan.FromMilliseconds(50));
        run.AddStep("Step A", Verdict.Pass);
        run.AddStep("Step B", Verdict.Pass);

        listener.RecordRun(run);
        listener.WriteTo(tempFile.Path);

        using var doc = JsonDocument.Parse(File.ReadAllText(tempFile.Path));
        var root = doc.RootElement;
        Assert.Equal("MyPlan",  root.GetProperty("plan").GetString());
        Assert.Equal("Pass",    root.GetProperty("verdict").GetString());
        Assert.Equal(50,        root.GetProperty("durationMs").GetInt32());
        Assert.Equal(2,         root.GetProperty("steps").GetArrayLength());
        Assert.Equal("Step A",  root.GetProperty("steps")[0].GetProperty("name").GetString());
        Assert.Equal("Pass",    root.GetProperty("steps")[0].GetProperty("verdict").GetString());
    }
}

internal sealed class TempFile : IDisposable
{
    public string Path { get; }
    public TempFile(string ext) => Path = System.IO.Path.Combine(
        System.IO.Path.GetTempPath(),
        "openflow-test-" + System.IO.Path.GetRandomFileName() + ext);
    public void Dispose() { try { File.Delete(Path); } catch { /* best effort */ } }
}

internal sealed record FakeStep(string Name, Verdict Verdict);

internal sealed class FakePlanRun
{
    public string PlanName { get; }
    public Verdict Verdict { get; }
    public TimeSpan Duration { get; }
    public List<FakeStep> Steps { get; } = new();

    public FakePlanRun(string planName, Verdict verdict, TimeSpan duration)
        => (PlanName, Verdict, Duration) = (planName, verdict, duration);

    public void AddStep(string name, Verdict v) => Steps.Add(new FakeStep(name, v));
}
