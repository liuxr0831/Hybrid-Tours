import { observer } from "mobx-react-lite";
import { withParentSize } from "@visx/responsive";
import Background from "./Background";
import {
  GradientDefs,
  velocityAreaGradientId,
  velocityDotGradientId,
  areaBackgroundGradientId
} from "./GradientDefs";
import { GlobalStateContext } from "@/stores/globalState";
import { useCallback, useContext, useEffect } from "react";
import { localPoint } from "@visx/event";
import { Colors } from "@/utils/colorUtils";
import { Drag } from "@visx/drag";
import { curveMonotoneX } from "@visx/curve";
import { LinePath } from "@visx/shape";
import { HandlerArgs } from "@visx/drag/lib/useDrag";
import { Line, AreaClosed } from "@visx/shape";
import { Axis, Orientation } from "@visx/axis";
import _, { remove } from "lodash";
const Margin = {
  top: 10,
  right: 30,
  bottom: 25,
  left: 30,
};

const xLabelTickLabelProps = {
  fill: Colors.extraLightYellow,
  fontSize: 11,
  fontWeight: "bold",
  fontFamily: "inter",
  textAnchor: "middle",
} as const;

const yLabelTickLabelProps = {
  fill: Colors.extraLightYellow,
  fontSize: 11,
  fontWeight: "bold",
  fontFamily: "inter",
  textAnchor: "end",
  verticalAnchor: "middle",
  dx: "-4px",
} as const;

function VelocityEditorChart({
  parentWidth: width,
  parentHeight: height,
}: {
  parentWidth: number;
  parentHeight: number;
}) {
  const graphWidth = width - Margin.left - Margin.right;
  const graphHeight = height - Margin.top - Margin.bottom;
  const globalState = useContext(GlobalStateContext);
  const current_video_state = globalState.currentVideoState;
  const {
    controlPoints: data,
    yDomain,
    setControlPoints: setData,
    setXRange,
    setYRange,
    xScale,
    yScale,
    yGlobalScale,
  } = globalState.currentVideoState.velocityEditorState;
  const { is_stabilized, stabilized_trim_start, stabilized_trim_end, sampled_percents, cur_trim_start, cur_trim_end } = current_video_state;

  useEffect(() => {
    setXRange([Margin.left, graphWidth + Margin.left]);
    setYRange([graphHeight + Margin.top, Margin.top]);
  }, [graphWidth, graphHeight, setXRange, setYRange]);

  const handleDoubleClick = useCallback(
    (event: React.MouseEvent) => {
      const { x, y } = localPoint(event) || { x: 0, y: 0 };
      const newX = xScale.invert(x);
      const newY = yScale.invert(y);
      console.log(newY);
      const newData = [...data, { x: newX, y: newY }];
      newData.sort((a, b) => a.x - b.x);
      setData(newData);
      event.stopPropagation();
    },
    [xScale, yScale, data, setData]
  );

  const currentCameraManager = globalState.currentCameraManager;
  if (!currentCameraManager) {
    throw new Error("Camera manager not set");
  }
  const { currentProgress, setCurrentProgress, set_current_progress_by_original_progress, cur_original_progress } = currentCameraManager;
  const yellow_line_progress = is_stabilized? cur_original_progress : currentProgress;

  const handleMouseMove = useCallback(
    (event: React.MouseEvent) => {
      currentCameraManager.setIsDraggingProgressBar(true);
      const { x } = localPoint(event) || { x: 0 };
      const newX = xScale.invert(x);
      if (is_stabilized) {
        set_current_progress_by_original_progress(newX, sampled_percents[stabilized_trim_start], sampled_percents[stabilized_trim_end])
      } else {
        setCurrentProgress(newX);
      }
      // currentCameraManager.setIsDraggingProgressBar(false);
    },
    [currentCameraManager, xScale, is_stabilized, stabilized_trim_start, stabilized_trim_end]
  );

  const handleMouseOut = useCallback(
    (event: React.MouseEvent) => {
      currentCameraManager.setIsDraggingProgressBar(false);
    }, []
  )

  const handleDragFactory = useCallback(
    (i: number) => (e: HandlerArgs) => {
      const newData = [...data];
      const { x, y, dx, dy } = e;
      if (!y || !x || !dx || !dy) {
        return;
      }
      const newX = xScale.invert(x + dx);
      const newY = yScale.invert(y + dy);
      if (i!==0 && i!==newData.length-1 && newX>0 && newX<1) {
        newData[i].x = newX;
      }
      if (newY>yDomain[0] && newY<=yDomain[1]) {
        newData[i].y = newY;
      }
      currentCameraManager.setIsDraggingProgressBar(true);
      set_current_progress_by_original_progress(newData[i].x, sampled_percents[stabilized_trim_start], sampled_percents[stabilized_trim_end])
      newData.sort((a, b) => a.x - b.x);
      setData(newData);
    },
    [data, setData, xScale, yScale]
  );

  

  return (
    <svg width={width} height={height}>
      <GradientDefs />
      <g transform={`translate(${Margin.left} ${Margin.top})`}>
        <Background width={graphWidth} height={graphHeight} />
      </g>
      <AreaClosed
        curve={curveMonotoneX}
        data={is_stabilized? data : [
          { x: 0, y: 1 },
          { x: 1, y: 1 },
        ]}
        x={(d) => xScale(d.x)}
        y={(d) => yScale(d.y)}
        yScale={yScale}
        strokeWidth={2}
        fill={`url(#${velocityAreaGradientId})`}
      />
      <rect
        x={xScale(0)}
        y={yScale(yDomain[1])}
        width={is_stabilized? graphWidth * (sampled_percents[stabilized_trim_start]) : 0}
        height={is_stabilized? graphHeight : 0}
        fill={`url(#${areaBackgroundGradientId})`}
      />
      <rect
        x={xScale(sampled_percents[stabilized_trim_end])}
        y={yScale(yDomain[1])}
        width={is_stabilized? graphWidth * (1-sampled_percents[stabilized_trim_end]) : 0}
        height={is_stabilized? graphHeight : 0}
        fill={`url(#${areaBackgroundGradientId})`}
      />
      <Axis
        orientation={Orientation.bottom}
        top={Margin.top + graphHeight}
        scale={xScale}
        // tickFormat={tickFormat}
        stroke={Colors.extraLightYellow}
        tickStroke={Colors.extraLightYellow}
        tickLabelProps={xLabelTickLabelProps}
        // tickValues={[0, 2, 4, 6, 8, 10]}
        numTicks={6}
        label={"label"}
        labelProps={{
          x: width + 30,
          y: -10,
          fill: Colors.lightYellow,
          fontSize: 18,
          strokeWidth: 0,
          stroke: "#fff",
          paintOrder: "stroke",
          fontFamily: "sans-serif",
          textAnchor: "start",
        }}
      />
      <Axis
        orientation={Orientation.left}
        scale={is_stabilized? yGlobalScale : yScale}
        left={Margin.left}
        // tickFormat={tickFormat}
        stroke={Colors.extraLightYellow}
        tickStroke={Colors.extraLightYellow}
        tickLabelProps={yLabelTickLabelProps}
        // tickValues={[0, 2, 4, 6, 8, 10]}
        numTicks={4}
        label={"label"}
        labelProps={{
          x: width + 30,
          y: -10,
          fill: Colors.lightYellow,
          fontSize: 18,
          strokeWidth: 0,
          stroke: "#fff",
          paintOrder: "stroke",
          fontFamily: "sans-serif",
          textAnchor: "start",
        }}
      />
      <Line
        from={{
          x: xScale(yellow_line_progress),
          y: yScale(yDomain[0]),
        }}
        to={{
          x: xScale(yellow_line_progress),
          y: yScale(yDomain[1]),
        }}
        strokeWidth={1}
        className="stroke-lightYellow"
        pointerEvents="none"
        strokeDasharray="5,2"
      />
      <Line
        from={{
          x: xScale(is_stabilized? sampled_percents[cur_trim_start] : 0),
          y: yScale(yDomain[0]),
        }}
        to={{
          x: xScale(is_stabilized? sampled_percents[cur_trim_start] : 0),
          y: yScale(yDomain[1]),
        }}
        strokeWidth={1}
        className="stroke-white"
        pointerEvents="none"
        strokeDasharray="5,2"
      />
      <Line
        from={{
          x: xScale(is_stabilized? sampled_percents[cur_trim_end] : 1),
          y: yScale(yDomain[0]),
        }}
        to={{
          x: xScale(is_stabilized? sampled_percents[cur_trim_end] : 1),
          y: yScale(yDomain[1]),
        }}
        strokeWidth={1}
        className="stroke-white"
        pointerEvents="none"
        strokeDasharray="5,2"
      />
      <LinePath
        curve={curveMonotoneX}
        className="stroke-dark-0"
        // strokeOpacity={0.5}
        data={is_stabilized? data : [
          { x: 0, y: 1 },
          { x: 1, y: 1 },
        ]}
        x={(d) => xScale(d.x)}
        y={(d) => yScale(d.y)}
        strokeWidth={1}
      />
      <rect
        x={Margin.left}
        y={Margin.top}
        width={graphWidth}
        height={graphHeight}
        fill="transparent"
        rx={14}
        onDoubleClick={is_stabilized? handleDoubleClick : undefined}
        onMouseMove={handleMouseMove}
        onMouseOut={handleMouseOut}
      />
      {(is_stabilized? data : [
          { x: 0, y: 1 },
          { x: 1, y: 1 },
        ]).map((d, i) => (
        <Drag
          key={`drag-${i}`}
          width={width}
          height={height}
          x={xScale(d.x)}
          y={yScale(d.y)}
          onDragStart={is_stabilized? handleDragFactory(i) : undefined}
          onDragMove={is_stabilized? handleDragFactory(i) : undefined}
          onDragEnd={is_stabilized? handleDragFactory(i) : undefined}
          // restrict={{
          //   xMin:
          //     i === 0
          //       ? xScale(0)
          //       : i === data.length - 1
          //       ? xScale(1)
          //       : undefined,
          //   xMax:
          //     i === 0
          //       ? xScale(0)
          //       : i === data.length - 1
          //       ? xScale(1)
          //       : undefined,
          // }}
        >
          {({ dragStart, dragEnd, dragMove, isDragging, x, y, dx, dy }) => (
            <circle
              key={`dot-${d}`}
              cx={x}
              cy={y}
              r="0.38vw"
              fill={`url(#${velocityDotGradientId})`}
              transform={`translate(${dx}, ${dy})`}
              strokeWidth={2}
              onMouseMove={is_stabilized? dragMove : undefined}
              onMouseUp={is_stabilized? dragEnd : undefined}
              onMouseDown={is_stabilized? dragStart : undefined}
              onTouchStart={is_stabilized? dragStart : undefined}
              onTouchMove={is_stabilized? dragMove : undefined}
              onTouchEnd={is_stabilized? dragEnd : undefined}
              onDoubleClick={() => {
                // remove point
                if (is_stabilized && i !== 0 && i!==data.length-1) {
                  const newData = [...data];
                  remove(newData, (_, index) => index === i);
                  setData(newData);
                }
              }}
            />
          )}
        </Drag>
      ))}
    </svg>
  );
}

export default withParentSize(observer(VelocityEditorChart));
