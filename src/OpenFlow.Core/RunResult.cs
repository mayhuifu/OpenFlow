namespace OpenFlow.Core;

public sealed record RunResult(
    Verdict Verdict,
    TimeSpan Duration,
    int StepCount,
    string OutputPath,
    string? ErrorMessage);
