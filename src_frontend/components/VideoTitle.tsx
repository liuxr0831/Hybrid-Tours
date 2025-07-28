import { observer } from "mobx-react-lite";
import { useContext } from "react";
import { GlobalStateContext } from "../stores/globalState";

function VideoTitle() {
  const globalState = useContext(GlobalStateContext);

  return (
    <div className="flex items-center justify-center w-full">
      <h1 className="text-lg font-semibold text-white">
        {globalState.selectedVideoSlug}
      </h1>
    </div>
  );
}

export default observer(VideoTitle);
