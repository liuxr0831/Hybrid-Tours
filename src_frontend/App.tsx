import "./App.css";
import VideoLibrary from "./components/VideoLibrary";
import VideoDndContext from "./components/VideoDndContext";
import PickedVideos from "./components/PickedVideos";
import { useContext } from "react";
import { observer } from "mobx-react-lite";
import { GlobalStateContext } from "./stores/globalState";
import OpenCreateProject from "./pages/OpenCreateProject";
import EnvironmentExplorer from "./pages/EnvironmentExplorer";
import SingleVideoEditor from "./pages/SingleVideoEditor";
import Setting from "./pages/SettingPage";
import PageSelector from "./pages/PageSelector";

function App() {
  const globalState = useContext(GlobalStateContext);

  const currentPage = globalState.currentPage;
  return (
    <div className=" w-screen h-screen p-3 bg-dark-1000 text-white text-center flex flex-col justify-center items-center space-y-2">
      <div className="w-full h-full flex flex-col space-y-2 items-center justify-start">
        <VideoDndContext>
          <VideoLibrary />
          <PickedVideos />
        </VideoDndContext>
        <div className="flex flex-col flex-1 py-2">
          {currentPage === "OpenCreateProject" && <OpenCreateProject />}
          {currentPage === "EnvironmentExplorer" && <EnvironmentExplorer />}
          {(currentPage === "SingleVideoEditor" || currentPage === "ConcatenatedVideo") && <SingleVideoEditor />}
          {currentPage === "Setting" && <Setting />}
        </div>
        <PageSelector />
      </div>
    </div>
  );
}

export default observer(App);
