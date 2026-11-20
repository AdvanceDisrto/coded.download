# Unreal Bridge (source template, not compiled)

Add `WorldBridgeComponent.h/.cpp` to the `Source/Civilization1/` directory of a newly generated C++ Unreal project. Add `WebSockets` to its `*.Build.cs` dependencies. Build in your *installed* Unreal engine. Create a Blueprint with this component, call `ConnectToLocalSimulation`, bind `OnWorldState`, parse `world.tick`, `world.crisis_index`, etc., using your engine's supported JSON facilities.

The remote feed is **synthetic and read-only**. The Unreal version/MetaHuman plugin is **not validated** in this package. No real biometric scanner is present.
