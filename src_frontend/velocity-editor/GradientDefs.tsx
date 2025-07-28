import { Colors } from "@/utils/colorUtils";
import { LinearGradient } from "@visx/gradient";
import { observer } from "mobx-react-lite";

export const areaBackgroundGradientId = "area-background-gradient";
export const areaGradientId = "area-gradient";
export const diffAreaGradientId = "diff-area-gradient";
export const correlationAreaGradientId = "correlation-area-gradient";
export const whiteAreaGradientId = "white-area-gradient";
export const velocityAreaGradientId = "velocity-area-gradient";
export const velocityDotGradientId = "velocity-dot-gradient";

export const GradientDefs = observer(() => {
  return (
    <g>
      <LinearGradient id={whiteAreaGradientId} from={"#ffff"} to={"#fff0"} />
      <LinearGradient
        id={areaBackgroundGradientId}
        from={Colors.dark}
        to={Colors.dark}
        fromOpacity={0.8}
        toOpacity={0.8}
      />
      <LinearGradient
        id={areaGradientId}
        from={Colors.accentColor}
        to={Colors.accentColor}
        toOpacity={0.1}
      />
      <LinearGradient
        id={diffAreaGradientId}
        from={Colors.diffLight}
        to={Colors.diffDark}
        toOpacity={0.1}
      />
      <LinearGradient
        id={correlationAreaGradientId}
        from={Colors.correlationLight}
        to={Colors.correlationDark}
        toOpacity={0.1}
      />
      <LinearGradient
        id={velocityAreaGradientId}
        from={Colors.lightYellow}
        to={Colors.lightYellow}
        fromOpacity={1}
        toOpacity={0.05}
      />
      <LinearGradient
        id={velocityDotGradientId}
        from={Colors.extraLightYellow}
        to={Colors.extraLightYellow}
        // fromOpacity={0.2}
        // toOpacity={0}
      />
    </g>
  );
});
