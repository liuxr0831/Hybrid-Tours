import { observer } from "mobx-react-lite";
import VelocityEditorChart from "./VelocityEditorChart";
import { VerticalSlider } from "@/components/ui/verticalSlider";
import { useContext } from "react";
import { GlobalStateContext } from "@/stores/globalState";

function VelocityEditor() {
  const globalState = useContext(GlobalStateContext);
  const current_video_state = globalState.currentVideoState;
  const { velocityEditorState } = globalState.currentVideoState;
  const { globalVelocityMultiplier, setGlobalVelocityMultiplier } =
    velocityEditorState;

  return (
    <div className="flex flex-1">
      <div className="w-8 h-full py-4 relative bottom-1">
        <VerticalSlider
          disabled = {!current_video_state.is_stabilized}
          value={current_video_state.is_stabilized? [globalVelocityMultiplier] : [1]}
          min={0.1}
          max={3}
          step={0.001}
          onValueChange={([value]) => {
            setGlobalVelocityMultiplier(value);
          }}
        />
      </div>
      <div className="grow cursor-pointer">
        <VelocityEditorChart />
      </div>
    </div>
  );
}

export default observer(VelocityEditor);
