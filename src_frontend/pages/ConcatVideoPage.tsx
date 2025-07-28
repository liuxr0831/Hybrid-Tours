import { Button } from "@/components/ui/button";
import { GlobalStateContext } from "@/stores/globalState";
import SceneExplorer from "@/webgl-canvas/SceneExplorer";
import { useMutation } from "@tanstack/react-query";
import { observer } from "mobx-react-lite";
import { useContext } from "react";
import { Loader2 } from "lucide-react";

function ConcatVideoPage() {
  const globalState = useContext(GlobalStateContext);
  const currentCameraManager = globalState.currentCameraManager;
  const { pickedVideosOrder } = globalState;
  const { setConcatVideoFromServerResponse, sendConcatVideosRequest, sendRenderVideoRequest } =
    globalState;
  const cantConcat = pickedVideosOrder.length < 2;
  const {
    isSuccess: concatIsSuccess,
    mutate: concatMutate,
    isPending: concatIsPending,
  } = useMutation({
    mutationFn: sendConcatVideosRequest,
    onSuccess: (res) => {
      setConcatVideoFromServerResponse(res.pos, res.rot, res.ts, res.frames);;
    },
    onError: (err) => {
      // @ts-ignore
      console.error(err.response.data);
    },
  });

  const { mutate: renderMutate, isPending: renderIsPending } = useMutation({
    mutationFn: sendRenderVideoRequest,
    onSuccess: (res) => {
      alert(res.msg);
    }
  });

  return (
    <div className="w-full h-full flex-1 flex flex-col justify-center items-center ">
      {currentCameraManager && (
        <div
          className="flex justify-center space-x-2 items-start w-full px-10"
        >
          <div style={{width: '30vw'}}><SceneExplorer canvasType="ThirdPersonViewCanvas" /></div>
          <div style={{width: '30vw'}}><SceneExplorer canvasType="cameraViewCanvas" /></div>
        </div>
      )}
      <div className="mt-12 flex space-x-2">
        <Button
          variant={cantConcat ? "default" : "primary"}
          disabled={cantConcat || concatIsPending || renderIsPending}
          onClick={() => concatMutate()}
        >
          {concatIsPending && (
            <Loader2 className="mr-2 h-5 w-5 animate-spin size-24" />
          )}
          {concatIsPending
            ? "Concatenating"
            : concatIsSuccess
            ? "Concatenate Again"
            : "Concatenate Clips"}
        </Button>
        {currentCameraManager && (
          <Button
            disabled={renderIsPending || concatIsPending}
            onClick={() => renderMutate()}
          >
            {renderIsPending && (
              <Loader2 className="mr-2 h-5 w-5 animate-spin size-24" />
            )}
            {renderIsPending ? "Rendering" : "Render Video"}
          </Button>
        )}
      </div>
    </div>
  );
}

export default observer(ConcatVideoPage);
