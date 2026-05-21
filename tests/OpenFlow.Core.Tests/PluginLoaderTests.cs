using OpenFlow.Core;
using Xunit;

namespace OpenFlow.Core.Tests;

public class PluginLoaderTests
{
    [Fact]
    public void Load_discovers_fixture_step_types()
    {
        var pluginsDir = TestPaths.CopyFixturesToTempPluginDir();
        var loader = new PluginLoader();

        loader.Load(pluginsDir);

        var typeNames = loader.DiscoveredStepTypes.Select(t => t.FullName).ToList();
        Assert.Contains("Fixtures.TestSteps.PassStep", typeNames);
        Assert.Contains("Fixtures.TestSteps.FailStep", typeNames);
        Assert.Contains("Fixtures.TestSteps.ThrowStep", typeNames);
    }

    [Fact]
    public void Load_throws_for_missing_directory()
    {
        var loader = new PluginLoader();
        Assert.Throws<DirectoryNotFoundException>(
            () => loader.Load("/nonexistent/openflow-plugins"));
    }
}
