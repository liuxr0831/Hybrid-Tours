import { observer } from "mobx-react-lite";
import { useContext } from "react";
import { GlobalStateContext } from "../stores/globalState";
import {
  TooltipProvider,
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from "@radix-ui/react-tooltip";

type VideoThumbnailProps = {
  videoSlug: string;
  videoUrl: string;
  height: string;
  is_picked: boolean;
};

function VideoThumbnail({ videoSlug, videoUrl, height, is_picked }: VideoThumbnailProps) {
  const globalState = useContext(GlobalStateContext);
  const { selectedVideoSlug, selectVideo, videoStatesStore } = globalState;
  const is_suggested = videoStatesStore[videoSlug].is_suggested_as_next_clip;
  const note = videoStatesStore[videoSlug].note;
  if (!is_picked) {
    return (
      <TooltipProvider>
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <div><VideoThumbnailUI
              onDoubleClick={() => selectVideo(videoSlug)}
              isSelected={selectedVideoSlug == videoSlug}
              videoSlug={videoSlug}
              videoUrl={videoUrl}
              height={height}
              color={globalState.videoStatesStore[videoSlug].video_color}
              is_picked={is_picked}
              is_suggested={is_suggested}
            /></div>
          </TooltipTrigger>
          <TooltipContent side="bottom" sideOffset={15} style={{zIndex:999}}>
            <p className="bg-dark-900 rounded-md p-2 px-3 text-xs">
              {note}
            </p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  } else {
    return (
      <TooltipProvider>
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <div><VideoThumbnailUI
              onDoubleClick={() => selectVideo(".temp_final_video")}
              isSelected={globalState.currentPage==="ConcatenatedVideo"}
              videoSlug={videoSlug}
              videoUrl={videoUrl}
              height={height}
              color={globalState.videoStatesStore[".temp_final_video"].video_color}
              is_picked={is_picked}
              is_suggested={is_suggested}
            /></div>
          </TooltipTrigger>
          <TooltipContent side="bottom" sideOffset={15} style={{zIndex:999}}>
            <p className="bg-dark-900 rounded-md p-2 px-3 text-xs">
              {note}
            </p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }
  
}

type VideoThumbnailUIProps = {
  videoSlug: string;
  videoUrl: string;
  height: string;
  isSelected: boolean;
  onDoubleClick: () => void;
  color: string
  is_picked: boolean
  is_suggested: boolean
};

function VideoThumbnailUI({
  videoSlug,
  videoUrl,
  height,
  isSelected,
  onDoubleClick,
  color,
  is_picked,
  is_suggested
}: VideoThumbnailUIProps) {
  if (isSelected) {
    return (
      <div
        className={
          "relative overflow-hidden rounded cursor-pointer transition-all text-center flex flex-col" + (is_suggested && " scale-110")
        }
        style={{ height: height, boxShadow: '0 0 0 5px '  + color + ', 0 4px 30px '  + color  }}
        onDoubleClick={onDoubleClick}
      >
        <video
          className="w-full h-full block rounded-sm"
          key={videoSlug}
          src={videoUrl+"#t=100"}
        />
        <p
          className={"font-semibold select-none text-2xs absolute right-0 bottom-0 block py-0.5 px-1 rounded-tl bg-dark-700 text-dark-0 border-solid "}
        >
          {videoSlug}
        </p>
      </div>
    );
  } else {
    return (
      <div
        className={
          "relative overflow-hidden rounded cursor-pointer transition-all text-center flex flex-col"  + (!is_picked && is_suggested && " scale-110")
        }
        style={{ height: height, boxShadow: ((!is_picked && is_suggested)? '0 0 0 3px ' : '0 0 0 1px ') + color }}
        onDoubleClick={onDoubleClick}
      >
        <video
          className="w-full h-full block rounded-sm"
          key={videoSlug}
          src={videoUrl+"#t=100"}
        />
        <p
          className={"font-semibold select-none text-2xs absolute right-0 bottom-0 block py-0.5 px-1 rounded-tl bg-dark-700 text-dark-0 border-solid "}
          // style={{ fontSize: "10px" }}
        >
          {videoSlug}
        </p>
      </div>
    );
  }
  
}

export default observer(VideoThumbnail);
