using OpenFlow.Core;
using Xunit;

namespace OpenFlow.Core.Tests;

public class RunResultTests
{
    [Fact]
    public void RunResult_records_verdict_and_paths()
    {
        var result = new RunResult(
            Verdict: Verdict.Pass,
            Duration: TimeSpan.FromMilliseconds(42),
            StepCount: 3,
            OutputPath: "/tmp/r.json",
            ErrorMessage: null);

        Assert.Equal(Verdict.Pass, result.Verdict);
        Assert.Equal(3, result.StepCount);
        Assert.Equal("/tmp/r.json", result.OutputPath);
        Assert.Null(result.ErrorMessage);
    }

    [Fact]
    public void Verdict_has_expected_members()
    {
        // These names mirror OpenTAP's Verdict enum so mapping is one-to-one.
        var names = Enum.GetNames<Verdict>();
        Assert.Contains("NotSet", names);
        Assert.Contains("Pass", names);
        Assert.Contains("Inconclusive", names);
        Assert.Contains("Fail", names);
        Assert.Contains("Aborted", names);
        Assert.Contains("Error", names);
    }
}
