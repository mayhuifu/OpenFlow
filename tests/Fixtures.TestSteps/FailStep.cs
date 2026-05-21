using OpenTap;

namespace Fixtures.TestSteps;

[Display("Fail Step", Group: "OpenFlow Fixtures")]
public class FailStep : TestStep
{
    public override void Run() => UpgradeVerdict(Verdict.Fail);
}
