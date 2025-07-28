import { Key } from "lucide-react";
import { observer } from "mobx-react-lite";
import { ReactNode } from "react";
import {
  FaArrowLeft,
  FaArrowRight,
  FaArrowUp,
  FaArrowDown,
} from "react-icons/fa";
import LookLeftIcon from "./ui/LookLeftIcon";

function InfoPanel() {
  return (
    <div className="grid items-stretch justify-stretch grid-cols-4 grid-rows-4 h-44">
      <KeyboardControlInfo
        keyString={"Q"}
        functionIcon={<LookLeftIcon />}
        description={"Look Left"}
      />
      <KeyboardControlInfo
        keyString={"W"}
        functionIcon={<Key />}
        description={"Move Forward"}
      />
      <KeyboardControlInfo
        keyString={"E"}
        functionIcon={<Key />}
        description={"Look Right"}
      />
      <KeyboardControlInfo
        keyString={"R"}
        functionIcon={<Key />}
        description={"Look Up"}
      />
      <KeyboardControlInfo
        keyString={"A"}
        functionIcon={<Key />}
        description={"Move Left"}
      />
      <KeyboardControlInfo
        keyString={"S"}
        functionIcon={<Key />}
        description={"Move Backward"}
      />
      <KeyboardControlInfo
        keyString={"D"}
        functionIcon={<Key />}
        description={"Move Right"}
      />
      <KeyboardControlInfo
        keyString={"F"}
        functionIcon={<Key />}
        description={"Look Down"}
      />
      <KeyboardControlInfo
        keyString={"Shift"}
        functionIcon={<Key />}
        description={"Move Down"}
      />
      <KeyboardControlInfo
        keyString={"Z"}
        functionIcon={<Key />}
        description={"Roll Left"}
      />
      <KeyboardControlInfo
        keyString={"C"}
        functionIcon={<Key />}
        description={"Roll Right"}
      />
      <KeyboardControlInfo
        keyString={"Space"}
        functionIcon={<Key />}
        description={"Move Up"}
      />
    </div>
  );
}

type KeyboardControlInfoProps = {
  keyString: string;
  functionIcon: ReactNode;
  description: string;
};

function KeyboardControlInfo({
  keyString,
  functionIcon,
  description,
}: KeyboardControlInfoProps) {
  // console.log(keyString);
  return (
    <div className="w-full h-full">
      <p className="text-sm">{keyString}</p>
      <div>
        {/* <p>{functionIcon}</p> */}
        <p className="text-2xs">{description}</p>
      </div>
    </div>
  );
}

export default observer(InfoPanel);
