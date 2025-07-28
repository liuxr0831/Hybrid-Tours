export const SortableContextConsts = {
  videoLibraryId: "videoLibrary",
  pickedVideosId: "pickedVideos",
  videoThumbnailHeight: {
    videoLibrary: "8vh",
    pickedVideos: "8vh",
  },
};

export const SortableIdSeparator = "--";

export function sortableIdGetter(itemId: string, containerId: string) {
  return containerId + SortableIdSeparator + itemId;
}

export function sortableIdGetterFactory(containerId: string) {
  return (itemId: string) => sortableIdGetter(itemId, containerId);
}

export function getContainerIdFromSortableId(sortableId: string) {
  return sortableId.split(SortableIdSeparator)[0];
}

export function getItemIdFromSortableId(sortableId: string) {
  return sortableId.split(SortableIdSeparator)[1];
}

export function arrayInsert<T>(array: T[], index: number, item: T) {
  return [...array.slice(0, index), item, ...array.slice(index)];
}
