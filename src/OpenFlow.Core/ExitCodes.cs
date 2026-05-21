namespace OpenFlow.Core;

/// <summary>
/// Process exit codes used by the OpenFlow CLI.
///
/// Pass/Fail/Aborted follow common Unix conventions (0, 1, 130 for SIGINT).
/// 64..78 follow BSD sysexits.h semantics where applicable
/// (64 EX_USAGE, 65 EX_DATAERR, 66 EX_NOINPUT, 70 EX_SOFTWARE).
/// </summary>
public static class ExitCodes
{
    public const int UsageError       = 64;
    public const int PlanFileError    = 65;
    public const int PluginsDirError  = 66;
    public const int PluginLoadError  = 70;
    public const int Aborted          = 130;

    public static int ForVerdict(Verdict verdict) => verdict switch
    {
        Verdict.Pass    => 0,
        Verdict.Fail    => 1,
        Verdict.Aborted => Aborted,
        _               => 2,
    };
}
