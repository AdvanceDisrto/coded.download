// Source template only: requires integration into a real Unreal C++ project.
#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "IWebSocket.h"
#include "WorldBridgeComponent.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnWorldState, const FString&, JsonData);

UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class CIVILIZATION1_API UWorldBridgeComponent : public UActorComponent {
    GENERATED_BODY()
public:
    UWorldBridgeComponent();
    UFUNCTION(BlueprintCallable, Category="CODED") void ConnectToLocalSimulation();
    UPROPERTY(BlueprintAssignable, Category="CODED") FOnWorldState OnWorldState;
protected:
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
private:
    TSharedPtr<IWebSocket> Socket;
};
