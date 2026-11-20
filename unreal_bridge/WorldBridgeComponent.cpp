#include "WorldBridgeComponent.h"
#include "WebSocketsModule.h"

UWorldBridgeComponent::UWorldBridgeComponent() {
    PrimaryComponentTick.bCanEverTick = false;
}

void UWorldBridgeComponent::ConnectToLocalSimulation() {
    if (Socket.IsValid()) { Socket->Close(); Socket.Reset(); }
    Socket = FWebSocketsModule::Get().CreateWebSocket(TEXT("ws://127.0.0.1:8765"));
    const TWeakObjectPtr<UWorldBridgeComponent> WeakThis(this);
    Socket->OnMessage().AddLambda([WeakThis](const FString& Message) {
        if (WeakThis.IsValid()) { WeakThis->OnWorldState.Broadcast(Message); }
    });
    Socket->Connect();
}

void UWorldBridgeComponent::EndPlay(const EEndPlayReason::Type Reason) {
    if (Socket.IsValid()) { Socket->OnMessage().Clear(); Socket->Close(); Socket.Reset(); }
    Super::EndPlay(Reason);
}
