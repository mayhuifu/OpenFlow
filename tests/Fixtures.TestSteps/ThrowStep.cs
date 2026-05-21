using OpenTap;

namespace Fixtures.TestSteps;

[Display("Throw Step", Group: "OpenFlow Fixtures")]
public class ThrowStep : TestStep
{
    public override void Run()
        => throw new InvalidOperationException("ThrowStep intentionally threw");
}
