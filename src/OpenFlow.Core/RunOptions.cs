namespace OpenFlow.Core;

public sealed record RunOptions(
    string PlanPath,
    string PluginsDir,
    string OutputPath,
    LogVerbosity Verbosity = LogVerbosity.Normal);

public enum LogVerbosity { Quiet, Normal, Verbose }
