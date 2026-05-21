using OpenTap;

namespace Fixtures.TestSteps;

[Display("Pass Step", Group: "OpenFlow Fixtures")]
public class PassStep : TestStep
{
    public override void Run() => UpgradeVerdict(Verdict.Pass);
}
