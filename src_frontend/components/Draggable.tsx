import { useSortable } from "@dnd-kit/sortable";
import { observer } from "mobx-react-lite";
import { CSS } from "@dnd-kit/utilities";

function Draggable(props: {
  id: string;
  containerId: string;
  children: React.ReactNode;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: props.id, data: { containerId: props.containerId } });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0 : 1,
  };
  return (
    <div ref={setNodeRef} style={style} {...listeners} {...attributes}>
      {props.children}
    </div>
  );
}

export default observer(Draggable);
