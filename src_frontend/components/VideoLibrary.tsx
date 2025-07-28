import { observer } from "mobx-react-lite";
import { GlobalStateContext } from "../stores/globalState";
import { useContext, useMemo } from "react";
import {
  SortableContext,
  horizontalListSortingStrategy,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { useDroppable } from "@dnd-kit/core";
import VideoThumbnail from "./VideoThumbnail";
import {
  SortableContextConsts,
  SortableIdSeparator,
  sortableIdGetterFactory,
} from "../utils/sortutils";
import Draggable from "./Draggable";
import { ColorConsts } from "../utils/colorUtils";

function VideoLibrary() {
  const globalState = useContext(GlobalStateContext);
  const { allVideosOrder: videosOrder, videoUrlGetter } = globalState;
  return (
    <VideoLibraryUI videosOrder={videosOrder} videoUrlGetter={videoUrlGetter} />
  );
}

type VideoLibraryUIProps = {
  videosOrder: string[];
  videoUrlGetter: (slug: string) => string;
};

const { videoLibraryId, videoThumbnailHeight } = SortableContextConsts;
const sortableIdGetter = sortableIdGetterFactory(videoLibraryId);
function VideoLibraryUI({ videosOrder, videoUrlGetter }: VideoLibraryUIProps) {
  const { setNodeRef } = useDroppable({ id: videoLibraryId });
  const sortableIds = useMemo(
    () => videosOrder.map(sortableIdGetter),
    [videosOrder]
  );

  return (
    <SortableContext
      items={sortableIds}
      strategy={horizontalListSortingStrategy}
    >
      <div
        className={
          "rounded-md flex space-x-4 p-2 h-max justify-center items-center ring-1 ring-dark-300" +
          ColorConsts.panelBackGround_1
        }
        ref={setNodeRef}
      >
        {videosOrder.length === 0 && (
          <div style={{height: `${videoThumbnailHeight.pickedVideos}`, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
            <div className="text-xs text-dark-300 py-3 px-4">
              Open Project to View Videos
            </div>
          </div>
        )}
        {videosOrder.length > 0 && videosOrder.map((videoSlug, index) => (
          <Draggable
            id={sortableIds[index]}
            key={videoSlug}
            containerId={videoLibraryId}
          >
            <VideoThumbnail
              height={videoThumbnailHeight.videoLibrary}
              videoSlug={videoSlug}
              videoUrl={videoUrlGetter(videoSlug)}
              is_picked = {false}
            />
          </Draggable>
        ))}
      </div>
    </SortableContext>
  );
}

export default observer(VideoLibrary);
