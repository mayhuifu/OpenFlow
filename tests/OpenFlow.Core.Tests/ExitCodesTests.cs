using OpenFlow.Core;
using Xunit;

namespace OpenFlow.Core.Tests;

public class ExitCodesTests
{
    [Theory]
    [InlineData(Verdict.Pass, 0)]
    [InlineData(Verdict.Fail, 1)]
    [InlineData(Verdict.Error, 2)]
    [InlineData(Verdict.Aborted, 130)]
    [InlineData(Verdict.NotSet, 2)]         // unknown → treat as error
    [InlineData(Verdict.Inconclusive, 2)]   // unknown → treat as error
    public void ForVerdict_maps_to_expected_exit_code(Verdict v, int expected)
    {
        Assert.Equal(expected, ExitCodes.ForVerdict(v));
    }

    [Fact]
    public void Named_exit_codes_match_spec()
    {
        Assert.Equal(64, ExitCodes.UsageError);
        Assert.Equal(65, ExitCodes.PlanFileError);
        Assert.Equal(66, ExitCodes.PluginsDirError);
        Assert.Equal(70, ExitCodes.PluginLoadError);
    }
}
