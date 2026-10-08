import { Link, useParams } from "react-router-dom";
import { Page } from "@/components/Page";
import { InspectorView } from "@/components/inspector/InspectorView";

/** One piece version, inspected (piece-inspector); the view itself is `InspectorView`. */
export default function PieceInspector() {
  const { packageId = "", version: versionParam = "" } = useParams();

  return (
    <Page>
      <p className="text-sm">
        <Link to="/pieces" className="underline">
          Back to pieces
        </Link>
      </p>
      <h1>{`${packageId}, version ${versionParam}`}</h1>
      <InspectorView packageId={packageId} version={Number(versionParam)} versionLabel={versionParam} />
    </Page>
  );
}
