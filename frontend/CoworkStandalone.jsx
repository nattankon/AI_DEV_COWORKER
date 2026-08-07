import CoworkApp from "./CoworkApp";

export default function CoworkStandalone({
  bridge,
  bridgeState = "dev",
  coworkModel = "",
  coworkModelLabel = "",
  coworkUiState = "idle",
  sessionStorageAdapter,
}) {
  return (
    <div className="h-screen w-screen overflow-hidden bg-white text-[#2f2f2d]">
      <CoworkApp
        bridge={bridge}
        bridgeState={bridgeState}
        coworkModel={coworkModel}
        coworkModelLabel={coworkModelLabel}
        coworkUiState={coworkUiState}
        sessionStorageAdapter={sessionStorageAdapter}
      />
    </div>
  );
}
