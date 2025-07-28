import * as React from "react";
import * as SliderPrimitive from "@radix-ui/react-slider";

import { cn } from "../../utils/styleUtils";

const VerticalSlider = React.forwardRef<
  React.ElementRef<typeof SliderPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SliderPrimitive.Root>
>(({ className, ...props }, ref) => (
  <SliderPrimitive.Root
    ref={ref}
    className={cn(
      "relative flex flex-col h-full touch-none select-none items-center",
      className
    )}
    orientation="vertical"
    {...props}
  >
    <SliderPrimitive.Track className="relative w-2 h-full grow overflow-hidden rounded-full bg-dark-500">
      <SliderPrimitive.Range className="absolute left-0 w-full bg-white" />
    </SliderPrimitive.Track>
    <SliderPrimitive.Thumb className="cursor-pointer block h-5 w-5 rounded-full border-2 border-primary bg-white ring-offset-background transition-colors focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50" />
  </SliderPrimitive.Root>
));
VerticalSlider.displayName = SliderPrimitive.Root.displayName;

export { VerticalSlider };
