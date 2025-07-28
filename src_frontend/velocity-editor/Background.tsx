import { areaBackgroundGradientId } from "./GradientDefs";

type BackgroundProps = {
  width: number;
  height: number;
};
function Background({ width, height }: BackgroundProps) {
  return (
    <rect
      // className="fill-dark-800"
      width={width}
      height={height}
      fill={`url(#${areaBackgroundGradientId})`}
      rx={5}
    />
  );
}

export default Background;
