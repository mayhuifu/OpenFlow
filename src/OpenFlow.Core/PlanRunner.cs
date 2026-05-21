using System.Diagnostics;
using OpenTap;

namespace OpenFlow.Core;

/// <summary>
/// Orchestrates the v1 happy path: load plugins, load a <c>.TapPlan</c>, execute it
/// via OpenTAP with a <see cref="JsonResultListener"/> attached, write the result
/// file, and return a <see cref="RunResult"/>.
///
/// Cancellation is propagated to <see cref="TestPlan.ExecuteAsync"/> so a Ctrl+C
/// in the CLI causes OpenTAP to abort the plan and report <see cref="Verdict.Aborted"/>.
/// </summary>
public sealed class PlanRunner
{
    public async Task<RunResult> RunAsync(RunOptions options, CancellationToken ct)
    {
        if (!File.Exists(options.PlanPath))
            return new RunResult(Verdict.Error, TimeSpan.Zero, 0, options.OutputPath,
                $"Plan file not found: {options.PlanPath}");

        var loader = new PluginLoader();
        loader.Load(options.PluginsDir);   // may throw DirectoryNotFoundException

        var stopwatch = Stopwatch.StartNew();
        TestPlan plan;
        try
        {
            plan = TestPlan.Load(options.PlanPath);
        }
        catch (Exception ex)
        {
            return new RunResult(Verdict.Error, TimeSpan.Zero, 0, options.OutputPath,
                $"Failed to load plan: {ex.Message}");
        }

        var listener = new JsonResultListener();

        // OpenTAP 9.27 ExecuteAsync signature:
        //   ExecuteAsync(IEnumerable<IResultListener>, IEnumerable<ResultParameter>,
        //                HashSet<ITestStep>, CancellationToken)
        await plan.ExecuteAsync(
            new IResultListener[] { listener },
            metaDataParameters: null,
            stepsOverride: null,
            cancellationToken: ct);

        stopwatch.Stop();

        listener.WriteTo(options.OutputPath);
        return new RunResult(
            Verdict: listener.FinalVerdict,
            Duration: stopwatch.Elapsed,
            StepCount: listener.StepCount,
            OutputPath: options.OutputPath,
            ErrorMessage: null);
    }
}
