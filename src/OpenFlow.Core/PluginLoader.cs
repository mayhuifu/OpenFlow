using OpenTap;

namespace OpenFlow.Core;

/// <summary>
/// Thin wrapper over <see cref="OpenTap.PluginManager"/> that loads vendor plugin
/// DLLs from a single directory and surfaces the <see cref="ITestStep"/>-derived
/// types that were discovered.
///
/// Single responsibility: take a directory path, populate <see cref="DiscoveredStepTypes"/>.
/// Plan loading and execution live elsewhere.
/// </summary>
public sealed class PluginLoader
{
    private readonly List<Type> _stepTypes = new();

    public IReadOnlyList<Type> DiscoveredStepTypes => _stepTypes;

    public void Load(string pluginsDir)
    {
        if (!Directory.Exists(pluginsDir))
            throw new DirectoryNotFoundException($"Plugins directory not found: {pluginsDir}");

        PluginManager.DirectoriesToSearch.Clear();
        PluginManager.DirectoriesToSearch.Add(pluginsDir);
        PluginManager.SearchAsync().Wait();

        _stepTypes.Clear();
        foreach (var td in TypeData.GetDerivedTypes<ITestStep>())
        {
            if (!td.CanCreateInstance) continue;
            var sysType = (td as TypeData)?.Type;
            if (sysType != null) _stepTypes.Add(sysType);
        }
    }
}
