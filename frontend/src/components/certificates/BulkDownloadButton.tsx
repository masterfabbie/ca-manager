import { CertsAPI } from "../../api/client";

interface Props {
  caId?: string | null;
}

export default function BulkDownloadButton({ caId }: Props) {
  return (
    <button
      className="btn btn-secondary"
      onClick={() => CertsAPI.bulkDownload(caId)}
      title="Download all visible certificates as PEM bundles in a ZIP"
    >
      ⬇ Download All as ZIP
    </button>
  );
}
