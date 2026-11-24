# Fixture

The adapter starts the [qualified synthetic HTTP fixture](../../../feasibility/fixture.py) on a randomly selected container-loopback port. Each case group gets fresh sessions and revision 0. The fixture is shared across the case group, so the baseline reads initial state before the editor updates it. The existing [application checks](../../../feasibility/app_assertions.py) and [plan generator](../../../feasibility/plan.py) supply the original witnesses and plan jobs.
