import { useEffect, useRef } from "react";
import {
  BookOpen,
  Camera,
  ChartNoAxesColumnIncreasing,
  Download,
  Info,
  Leaf,
  Search,
  Settings2,
  Utensils,
  X,
} from "lucide-react";
import { useWorkspace } from "../state/workspace";
import type { Page } from "../lib/types";
import { Brand } from "./Brand";
import { IconButton } from "./Primitives";

const mainLinks = [
  { page: "capture", label: "Camera", icon: Camera },
  { page: "manual", label: "Enter food", icon: Utensils },
  { page: "journal", label: "Saved meals", icon: BookOpen },
  { page: "settings", label: "Settings", icon: Settings2 },
] as const;
const moreLinks = [
  { page: "insights", label: "Insights", icon: ChartNoAxesColumnIncreasing },
  { page: "recipes", label: "Recipes", icon: Leaf },
  { page: "catalog", label: "Food library", icon: Search },
  { page: "about", label: "About", icon: Info },
] as const;

export function Navigation({
  open,
  onClose,
}: {
  open: boolean;
  onClose(): void;
}) {
  const { page, setPage, api, connected } = useWorkspace();
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (open && !dialog.current?.open) dialog.current?.showModal();
    if (!open && dialog.current?.open) dialog.current.close();
  }, [open]);
  const navigate = (next: Page) => {
    setPage(next);
    onClose();
  };
  const link = ({
    page: target,
    label,
    icon: Icon,
  }: (typeof mainLinks)[number] | (typeof moreLinks)[number]) => (
    <button
      key={target}
      className={page === target ? "selected" : ""}
      onClick={() => navigate(target)}
      aria-current={page === target ? "page" : undefined}
    >
      {/* <Icon size={20} strokeWidth={1.5} /> */}
      <span>
        <strong>{label}</strong>
      </span>
    </button>
  );
  return (
    <dialog
      ref={dialog}
      className="navigation-dialog simple-navigation"
      aria-label="Menu"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="navigation-content">
        <div className="navigation-top">
          <Brand light />
          <IconButton label="Close menu" onClick={onClose}>
            <X size={20} />
          </IconButton>
        </div>
        <nav>{mainLinks.map(link)}</nav>
        {/* <details className="nav-more">
          {/* <summary>More tools</summary> 
          <nav>{moreLinks.map(link)}</nav>
        </details>*/}
        <div className="navigation-bottom">
          <p className="fine-print">
            {connected && api.mode === "live"
              ? "Connected to local server"
              : "Demo · image recognition needs a local vision model"}
          </p>
          <a
            href="/downloads/nteam-nutritensor.zip"
            download
            className="nav-about"
          >
            <Download size={16} /> Full project. not recommended for general purpose
          </a>
          <span className="nav-version">science day model from ssphs by nteam</span>
        </div>
      </div>
    </dialog>
  );
}
