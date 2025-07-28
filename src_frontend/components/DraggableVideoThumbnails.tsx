import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { observer } from "mobx-react-lite";

type VideoThumbnailProps = {
  videoSlug: string;
  videoUrl: string;
  width: string;
  containerId: string;
};
function DraggableVideoThumbnail({
  videoSlug,
  videoUrl,
  width,
  containerId,
}: VideoThumbnailProps) {
  const { attributes, listeners, setNodeRef, transform, transition } =
    useSortable({ id: videoSlug, data: { containerId } });
  return (
    <div
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      style={{
        width: width,
        overflow: "hidden",
        borderRadius: "5px",
        cursor: "pointer",
        transform: CSS.Transform.toString(transform),
        transition,
      }}
    >
      <video
        key={videoSlug}
        src={videoUrl}
        style={{ width: "100%", height: "100%", display: "block" }}
      />
      {/* {videoSlug} */}
    </div>
  );
}

export default observer(DraggableVideoThumbnail);
