import { observer } from "mobx-react-lite";
import { GlobalStateContext } from "../stores/globalState";
import { useContext, useMemo } from "react";
import {
  SortableContext,
  horizontalListSortingStrategy,
} from "@dnd-kit/sortable";
import { useDroppable } from "@dnd-kit/core";
import VideoThumbnail from "./VideoThumbnail";
import {
  SortableContextConsts,
  sortableIdGetterFactory,
} from "../utils/sortutils";
import Draggable from "./Draggable";
import { ColorConsts } from "../utils/colorUtils";
import { Button } from "./ui/button";

function PickedVideos() {
  const globalState = useContext(GlobalStateContext);
  const {
    pickedVideosOrder: videosOrder,
    videoUrlGetter,
    pickedVideosContainerIsHavingValidDragOverItem,
  } = globalState;

  return (
    <PickedVideosUI
      isHavingValidDragOverItem={pickedVideosContainerIsHavingValidDragOverItem}
      videosOrder={videosOrder}
      videoUrlGetter={videoUrlGetter}
    />
  );
}

type PickedVideosUIProps = {
  videosOrder: string[];
  videoUrlGetter: (slug: string) => string;
  isHavingValidDragOverItem?: boolean;
};

const { pickedVideosId, videoThumbnailHeight } = SortableContextConsts;
const sortableIdGetter = sortableIdGetterFactory(pickedVideosId);
function PickedVideosUI({
  videosOrder,
  videoUrlGetter,
  isHavingValidDragOverItem,
}: PickedVideosUIProps) {
  const { setNodeRef } = useDroppable({ id: pickedVideosId });
  const sortableIds = useMemo(
    () => videosOrder.map(sortableIdGetter),
    [videosOrder]
  );
  const globalState = useContext(GlobalStateContext);
  const {suggest_clips} = globalState;
  return (
    <SortableContext
      items={sortableIds}
      strategy={horizontalListSortingStrategy}
    >
      <div
        className={
          ColorConsts.panelBackGround_1 +
          "rounded-md flex justify-center items-center p-2 space-x-4 " +
          (isHavingValidDragOverItem === undefined
            ? " ring-dark-300 ring-1"
            : isHavingValidDragOverItem
            ? " ring-lightGreen ring-2"
            : " ring-lightRed ring-2")
        }
        ref={setNodeRef}
      >
        {videosOrder.length === 0 && (
          <div style={{height: `${videoThumbnailHeight.pickedVideos}`, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
            <div className="text-xs text-dark-300 py-3 px-4">
              Drop videos here
            </div>
          </div>
        )}
        {videosOrder.length > 0 &&
          videosOrder.map((videoSlug, index) => (
            <Draggable
              id={sortableIds[index]}
              key={videoSlug}
              containerId={pickedVideosId}
            >
              <VideoThumbnail
                height={videoThumbnailHeight.pickedVideos}
                videoSlug={videoSlug}
                videoUrl={videoUrlGetter(videoSlug)}
                is_picked = {true}
              />
            </Draggable>
          ))}
      </div>
      <Button onClick={() => suggest_clips()} disabled={!(videosOrder.length >= 2)}>
          Suggest Clips
      </Button>
    </SortableContext>
  );
}

export default observer(PickedVideos);
