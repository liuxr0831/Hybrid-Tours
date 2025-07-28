import { Button } from "@/components/ui/button";
import {
  GlobalStateContext,
  PageType,
  pageTypeFormatter,
} from "@/stores/globalState";
import {
  TooltipProvider,
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from "@radix-ui/react-tooltip";
import { Film, Globe, Waypoints, FolderOpen, Settings } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useContext } from "react";
const IconStyle = "w-6 h-6 font-thin";
function PageSelector() {
  return (
    <div className="fixed left-0 h-screen flex flex-col justify-center items-center ">
      <PageButton controlledPage={"OpenCreateProject"}>
        <FolderOpen className={IconStyle} />
      </PageButton>
      <div className="h-1"></div>
      <PageButton controlledPage={"EnvironmentExplorer"}>
        <Globe className={IconStyle} />
      </PageButton>
      <div className="h-1"></div>
      <PageButton controlledPage={"SingleVideoEditor"}>
        <Film className={IconStyle} />
      </PageButton>
      <div className="h-1"></div>
      <PageButton controlledPage={"ConcatenatedVideo"}>
        <Waypoints className={IconStyle} />
      </PageButton>
      <div className="h-1"></div>
      <PageButton controlledPage={"Setting"}>
        <Settings className={IconStyle} />
      </PageButton>
    </div>
  );
}

type PageButtonProps = {
  controlledPage: PageType;
};

const PageButton = observer(
  ({ controlledPage, children }: React.PropsWithChildren<PageButtonProps>) => {
    const globalState = useContext(GlobalStateContext);
    const currentPage = globalState.currentPage;
    const onClick = () => {
      globalState.setCurrentPage(controlledPage);
    };
    return (
      <TooltipProvider>
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <Button
              onClick={onClick}
              variant={currentPage === controlledPage ? "primary" : "default"}
              size={"pageSelector"}
            >
              {children}
            </Button>
          </TooltipTrigger>
          <TooltipContent side="right" sideOffset={15}>
            <p className="bg-dark-900 rounded-md p-2 px-3 text-xs">
              {pageTypeFormatter(controlledPage)}
            </p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }
);

export default observer(PageSelector);
