import { makeAutoObservable, toJS } from "mobx";
import { scaleLinear } from "@visx/scale";
import { VideoStates } from "./VideoStates";
import * as d3 from "d3-shape";
export type ControlPoint = { x: number; y: number };

export class VelocityEditorState {
  linkedVideoStates: VideoStates;
  controlPoints: ControlPoint[] = [
    { x: 0, y: 1 },
    { x: 1, y: 1 },
  ];

  xRange = [0, 1]; // should be set to graph x range, will need to be updated when graph is updated
  yRange = [0, 1]; // should be set to graph y range, will need to be updated when graph is updated

  yDomain = [0.1, 3];

  globalVelocityMultiplier = 1;

  get totalTime() {
    return this.linkedVideoStates.totalTime;
  }

  get xDomain() {
    // return this.totalTime ? [0, this.totalTime] : [0, 1];
    return [0, 1];
  }

  get xScale() {
    return scaleLinear({
      domain: this.xDomain,
      range: this.xRange,
    });
  }
  get yScale() {
    return scaleLinear({
      domain: this.yDomain,
      range: this.yRange,
    });
  }

  get yGlobalDomain() {
    return [
      this.yDomain[0] * this.globalVelocityMultiplier,
      this.yDomain[1] * this.globalVelocityMultiplier,
    ];
  }

  get yGlobalScale() {
    return scaleLinear({
      domain: this.yGlobalDomain,
      range: this.yRange,
    });
  }

  setXRange(range: [number, number]) {
    this.xRange = range;
  }

  setYRange(range: [number, number]) {
    this.yRange = range;
  }

  setControlPoints(controlPoints: ControlPoint[]) {
    this.controlPoints = controlPoints;
  }

  setGlobalVelocityMultiplier(multiplier: number) {
    this.globalVelocityMultiplier = multiplier;
  }

  get curvePath() {
    const lineGenerator = d3
      .line<ControlPoint>()
      .x((d) => d.x)
      .y((d) => d.y * this.globalVelocityMultiplier)
      .curve(d3.curveMonotoneX);
    return lineGenerator(this.controlPoints) || "";
  }

  // t is in [0, 1]
  sampleCurve(progress: number, path: SVGPathElement, path_total_length: number, start_progress: number, end_progress: number) {
    const point = path.getPointAtLength(progress * path_total_length);
    return { x: (point.x - start_progress) / (end_progress - start_progress), y: point.y };
  }

  find_x(target_x: number, path: SVGPathElement, path_total_length: number, lower_bound: number, upper_bound: number, tolerance: number = 0.001): number {
    const middle = (lower_bound + upper_bound) / 2;
    const cur_point = path.getPointAtLength(middle * path_total_length);
    const cur_x = cur_point.x;
    const err = Math.abs(cur_x - target_x);
    if (err < tolerance) {
      return middle;
    } else if (cur_x > target_x) {
      return this.find_x(target_x, path, path_total_length, lower_bound, middle);
    } else {
      return this.find_x(target_x, path, path_total_length, middle, upper_bound);
    }
  }

  getSamples(numSamples: number, start_percent: number, end_percent: number) {
    // create a path element
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", this.curvePath);
    const path_total_length = path.getTotalLength();
    // get the range of progress to sample
    const start_progress = this.find_x(start_percent, path, path_total_length, 0.0, 1.0);
    const end_progress = this.find_x(end_percent, path, path_total_length, 0.0, 1.0);
    console.log(start_progress, end_progress)
    return Array.from({ length: numSamples }, (_, i) =>
      this.sampleCurve(start_progress + (i / (numSamples - 1)) * (end_progress - start_progress), path, path_total_length, start_percent, end_percent)
    );
  }

  constructor(videoStates: VideoStates) {
    this.linkedVideoStates = videoStates;
    makeAutoObservable(this, {}, { autoBind: true });
  }
}
