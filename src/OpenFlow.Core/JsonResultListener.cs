using System.Text.Json;
using OpenTap;

namespace OpenFlow.Core;

/// <summary>
/// OpenTAP <see cref="ResultListener"/> that buffers plan and step verdicts in memory
/// and serializes them as JSON when <see cref="WriteTo"/> is called.
///
/// The OpenTAP runtime drives <c>OnTestPlanRunStart</c>, <c>OnTestStepRunCompleted</c>,
/// and <c>OnTestPlanRunCompleted</c> during a real plan execution. The internal
/// <see cref="RecordRun"/> path exists so unit tests can feed a synthetic run without
/// spinning up a real OpenTAP engine.
/// </summary>
public sealed class JsonResultListener : ResultListener
{
    private string _planName = "";
    private Verdict _planVerdict;
    private TimeSpan _planDuration;
    private readonly List<StepRecord> _steps = new();

    public JsonResultListener() : base() { Name = "JSON"; }

    public override void OnTestPlanRunStart(TestPlanRun planRun)
        => _planName = planRun.TestPlanName ?? "";

    public override void OnTestStepRunCompleted(TestStepRun stepRun)
        => _steps.Add(new StepRecord(stepRun.TestStepName ?? "", MapVerdict(stepRun.Verdict)));

    public override void OnTestPlanRunCompleted(TestPlanRun planRun, Stream logStream)
    {
        _planVerdict  = MapVerdict(planRun.Verdict);
        _planDuration = planRun.Duration;
    }

    /// <summary>Test-only entry point. Feeds the listener from a synthetic run record.</summary>
    internal void RecordRun(object fake)
    {
        var t = fake.GetType();
        _planName     = (string)t.GetProperty("PlanName")!.GetValue(fake)!;
        _planVerdict  = (Verdict)t.GetProperty("Verdict")!.GetValue(fake)!;
        _planDuration = (TimeSpan)t.GetProperty("Duration")!.GetValue(fake)!;
        var steps = (System.Collections.IEnumerable)t.GetProperty("Steps")!.GetValue(fake)!;
        foreach (var s in steps)
        {
            var st = s.GetType();
            _steps.Add(new StepRecord(
                (string)st.GetProperty("Name")!.GetValue(s)!,
                (Verdict)st.GetProperty("Verdict")!.GetValue(s)!));
        }
    }

    public void WriteTo(string path)
    {
        var doc = new
        {
            plan = _planName,
            verdict = _planVerdict.ToString(),
            durationMs = (int)_planDuration.TotalMilliseconds,
            steps = _steps.Select(s => new { name = s.Name, verdict = s.Verdict.ToString() }),
        };
        File.WriteAllText(path,
            JsonSerializer.Serialize(doc, new JsonSerializerOptions { WriteIndented = true }));
    }

    public Verdict FinalVerdict => _planVerdict;
    public TimeSpan FinalDuration => _planDuration;
    public int StepCount => _steps.Count;

    private static Verdict MapVerdict(OpenTap.Verdict v) => v switch
    {
        OpenTap.Verdict.NotSet       => Verdict.NotSet,
        OpenTap.Verdict.Pass         => Verdict.Pass,
        OpenTap.Verdict.Inconclusive => Verdict.Inconclusive,
        OpenTap.Verdict.Fail         => Verdict.Fail,
        OpenTap.Verdict.Aborted      => Verdict.Aborted,
        OpenTap.Verdict.Error        => Verdict.Error,
        _                            => Verdict.Error,
    };

    private sealed record StepRecord(string Name, Verdict Verdict);
}
