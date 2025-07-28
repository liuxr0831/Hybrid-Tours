import {
  Active,
  DndContext,
  DragEndEvent,
  DragOverEvent,
  DragOverlay,
  DragStartEvent,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { useContext, useState } from "react";
import { GlobalStateContext } from "../stores/globalState";
import { observer } from "mobx-react-lite";
import { sortableKeyboardCoordinates } from "@dnd-kit/sortable";
import VideoThumbnail from "./VideoThumbnail";
import {
  SortableContextConsts,
  getContainerIdFromSortableId,
  getItemIdFromSortableId,
} from "../utils/sortutils";

function VideoDndContext({ children }: React.PropsWithChildren) {
  const globalState = useContext(GlobalStateContext);
  const {
    allVideosOrder,
    pickedVideosOrder,
    reorderAllVideos,
    reorderPickedVideos,
    insertIntoPickedVideos,
    setPickedVideosContainerIsHavingValidDragOverItem,
    videoUrlGetter,
    remove_selected_video,
    pickedVideosContainerIsHavingValidDragOverItem,
  } = globalState;
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 5 },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );
  const [activeItem, setActiveItem] = useState<Active>();
  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDragEnd={handleDragEnd}
    >
      {children}
      <DragOverlay>
        {activeItem ? (
          <VideoThumbnail
            videoSlug={getItemIdFromSortableId(activeItem.id as string)}
            videoUrl={videoUrlGetter(
              getItemIdFromSortableId(activeItem.id as string)
            )}
            height={
              // @ts-ignore
              SortableContextConsts.videoThumbnailHeight[
                getContainerIdFromSortableId(activeItem.id as string)
              ]
            }
          />
        ) : null}
      </DragOverlay>
    </DndContext>
  );
  function handleDragStart(event: DragStartEvent) {
    setActiveItem(event.active);
  }

  function handleDragOver(event: DragOverEvent) {
    const { active, over } = event;
    if (over?.id == null) {
      return;
    }
    const activeId = getItemIdFromSortableId(active.id as string);
    const activeContainerId = getContainerIdFromSortableId(active.id as string);
    const overContainerId = getContainerIdFromSortableId(over.id as string);

    if (!overContainerId || !activeContainerId) {
      return;
    }
    const { videoLibraryId, pickedVideosId } = SortableContextConsts;

    // handle moving from video library to picked videos
    if (
      activeContainerId === videoLibraryId &&
      overContainerId === pickedVideosId
    ) {
      const overItems = globalState.pickedVideosOrder;
      if (overItems.includes(activeId)) {
        setPickedVideosContainerIsHavingValidDragOverItem(false);
      } else {
        setPickedVideosContainerIsHavingValidDragOverItem(true);
      }
    } else {
      setPickedVideosContainerIsHavingValidDragOverItem(undefined);
    }
  }

  function handleDragEnd(event: DragEndEvent) {
    setPickedVideosContainerIsHavingValidDragOverItem(undefined);
    setActiveItem(undefined);
    const { active, over } = event;
    if (!active || !over) return;
    const activeContainerId = getContainerIdFromSortableId(active.id as string);
    const overContainerId = getContainerIdFromSortableId(over.id as string);
    const activeId = getItemIdFromSortableId(active.id as string);
    const overId = getItemIdFromSortableId(over.id as string);

    // 1. remove picked video by dragging from picked videos to video library
    if (activeContainerId === SortableContextConsts.pickedVideosId && overContainerId !== SortableContextConsts.pickedVideosId) {
      remove_selected_video(activeId);
      // globalState.videoStatesStore['.temp_final_video'].set_is_stabilized(false);
      globalState.is_concat_changed = true;
      globalState.videoStatesStore['.temp_final_video'].set_is_stabilizable(false);
      globalState.videoStatesStore['.temp_final_video'].reset_stabilization_settings();
      return;
    }

    // 2. sort within the same container
    if (activeContainerId === overContainerId) {
      if (active.id !== over.id) {
        if (activeContainerId === SortableContextConsts.videoLibraryId) {
          const oldIndex = allVideosOrder.indexOf(activeId as string);
          const newIndex = allVideosOrder.indexOf(overId as string);
          reorderAllVideos(oldIndex, newIndex);
        } else if (activeContainerId === SortableContextConsts.pickedVideosId) {
          // globalState.videoStatesStore['.temp_final_video'].set_is_stabilized(false);
          globalState.is_concat_changed = true;
          globalState.videoStatesStore['.temp_final_video'].set_is_stabilizable(false);
          globalState.videoStatesStore['.temp_final_video'].reset_stabilization_settings();
          const oldIndex = pickedVideosOrder.indexOf(activeId);
          const newIndex = pickedVideosOrder.indexOf(overId);
          reorderPickedVideos(oldIndex, newIndex);
        }
      }
    }
    // 3. move from video library to picked videos
    if (
      activeContainerId === SortableContextConsts.videoLibraryId &&
      overContainerId === SortableContextConsts.pickedVideosId &&
      pickedVideosContainerIsHavingValidDragOverItem === true
    ) {
      // globalState.videoStatesStore['.temp_final_video'].set_is_stabilized(false);
      globalState.is_concat_changed = true;
      globalState.videoStatesStore['.temp_final_video'].set_is_stabilizable(false);
      globalState.videoStatesStore['.temp_final_video'].reset_stabilization_settings();
      insertIntoPickedVideos(activeId);
    }
  }
}

export default observer(VideoDndContext);
