import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Page } from "@/components/Page";
import { InspectorView, parseTab } from "@/components/inspector/InspectorView";

/** One piece version, inspected (piece-inspector); the view itself is `InspectorView`. */
export default function PieceInspector() {
  const { packageId = "", version: versionParam = "" } = useParams();
  const navigate = useNavigate();
  // `?tab=` and `?render=`: the open tab and the render chosen on the Renders tab (two-tier-renders).
  const [params, setParams] = useSearchParams();

  return (
    <Page>
      <p className="text-sm">
        <Link to="/pieces" className="underline">
          Back to pieces
        </Link>
      </p>
      <h1>{`${packageId}, version ${versionParam}`}</h1>
      <InspectorView
        packageId={packageId}
        version={Number(versionParam)}
        versionLabel={versionParam}
        onChoose={(next) => {
          const tab = params.get("tab");
          navigate(`/pieces/${encodeURIComponent(packageId)}/versions/${next}${tab ? `?tab=${tab}` : ""}`);
        }}
        place={{ tab: parseTab(params.get("tab")), render: params.get("render") }}
        onPlace={(next) =>
          setParams(
            () => {
              const kept = new URLSearchParams();
              if (next.tab !== "model") kept.set("tab", next.tab);
              if (next.render) kept.set("render", next.render);
              return kept;
            },
            { replace: true },
          )
        }
      />
    </Page>
  );
}
