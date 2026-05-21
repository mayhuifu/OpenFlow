namespace OpenFlow.Core;

/// <summary>
/// Plan/step verdict. Member values mirror OpenTAP's <c>OpenTap.Verdict</c> ordering
/// so mapping between the two enums is one-to-one.
/// </summary>
public enum Verdict
{
    NotSet = 0,
    Pass = 1,
    Inconclusive = 2,
    Fail = 3,
    Aborted = 4,
    Error = 5,
}
