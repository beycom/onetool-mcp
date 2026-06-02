// Adapted from pingdotgg/t3code components/ui/popover.tsx (MIT).
import { Popover as PopoverPrimitive } from "@base-ui/react/popover";
import type { ReactNode } from "react";

export const Popover = PopoverPrimitive.Root;

export function PopoverTrigger({ children, ...props }: PopoverPrimitive.Trigger.Props & { children: ReactNode }) {
  return (
    <PopoverPrimitive.Trigger data-slot="popover-trigger" {...props}>
      {children}
    </PopoverPrimitive.Trigger>
  );
}

export function PopoverPopup({
  children,
  side = "bottom",
  align = "end",
  sideOffset = 6,
  alignOffset = 0,
  ...props
}: PopoverPrimitive.Popup.Props & {
  children: ReactNode;
  side?: PopoverPrimitive.Positioner.Props["side"];
  align?: PopoverPrimitive.Positioner.Props["align"];
  sideOffset?: PopoverPrimitive.Positioner.Props["sideOffset"];
  alignOffset?: PopoverPrimitive.Positioner.Props["alignOffset"];
}) {
  return (
    <PopoverPrimitive.Portal>
      <PopoverPrimitive.Positioner
        align={align}
        alignOffset={alignOffset}
        className="popover-positioner"
        side={side}
        sideOffset={sideOffset}
      >
        <PopoverPrimitive.Popup className="popover-popup" data-slot="popover-popup" {...props}>
          <PopoverPrimitive.Viewport className="popover-viewport" data-slot="popover-viewport">
            {children}
          </PopoverPrimitive.Viewport>
        </PopoverPrimitive.Popup>
      </PopoverPrimitive.Positioner>
    </PopoverPrimitive.Portal>
  );
}
