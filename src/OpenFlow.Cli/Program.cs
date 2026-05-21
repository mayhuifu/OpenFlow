using System.CommandLine;
using OpenFlow.Core;

var planArg = new Argument<FileInfo>(
    name: "plan",
    description: "Path to the .TapPlan file to execute.");

var pluginsOpt = new Option<DirectoryInfo>(
    aliases: new[] { "--plugins", "-p" },
    description: "Directory containing plugin DLLs.")
{ IsRequired = true };

var outOpt = new Option<FileInfo>(
    aliases: new[] { "--out", "-o" },
    description: "Path to write the JSON result file.")
{ IsRequired = true };

var verbosityOpt = new Option<LogVerbosity>(
    aliases: new[] { "--verbosity", "-v" },
    getDefaultValue: () => LogVerbosity.Normal,
    description: "Log verbosity.");

var runCmd = new Command("run", "Execute a .TapPlan and write results to JSON.")
{
    planArg, pluginsOpt, outOpt, verbosityOpt,
};

runCmd.SetHandler(async (plan, plugins, output, verbosity) =>
{
    if (!plan.Exists)
    {
        Console.Error.WriteLine($"error: plan file not found: {plan.FullName}");
        Environment.Exit(ExitCodes.PlanFileError);
    }
    if (!plugins.Exists)
    {
        Console.Error.WriteLine($"error: plugins directory not found: {plugins.FullName}");
        Environment.Exit(ExitCodes.PluginsDirError);
    }

    try
    {
        var runner = new PlanRunner();
        var result = await runner.RunAsync(
            new RunOptions(plan.FullName, plugins.FullName, output.FullName, verbosity),
            CancellationToken.None);

        if (result.ErrorMessage is not null)
            Console.Error.WriteLine($"error: {result.ErrorMessage}");

        Console.WriteLine($"{result.Verdict} · {result.StepCount} step(s) · {result.Duration.TotalMilliseconds:N0} ms · {output.FullName}");
        Environment.Exit(ExitCodes.ForVerdict(result.Verdict));
    }
    catch (DirectoryNotFoundException ex)
    {
        Console.Error.WriteLine($"error: {ex.Message}");
        Environment.Exit(ExitCodes.PluginsDirError);
    }
    catch (System.Reflection.ReflectionTypeLoadException ex)
    {
        Console.Error.WriteLine($"error: plugin load failed");
        foreach (var le in ex.LoaderExceptions)
            if (le is not null) Console.Error.WriteLine("  " + le.Message);
        Environment.Exit(ExitCodes.PluginLoadError);
    }
}, planArg, pluginsOpt, outOpt, verbosityOpt);

var root = new RootCommand("OpenFlow — lightweight CLI test runner for RF/BB hardware automation.")
{
    runCmd,
};

return await root.InvokeAsync(args);
