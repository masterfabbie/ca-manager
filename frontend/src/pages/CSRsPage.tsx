import CSRUpload from "../components/csrs/CSRUpload";
import CSRGenerate from "../components/csrs/CSRGenerate";
import CSRTable from "../components/csrs/CSRTable";

interface Props {
  onSuccess: (msg: string) => void;
  onError: (msg: string) => void;
}

export default function CSRsPage({ onSuccess, onError }: Props) {
  return (
    <div className="page">
      <div className="page-header">
        <h2>Certificate Signing Requests</h2>
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          <CSRGenerate onSuccess={onSuccess} onError={onError} />
          <CSRUpload onSuccess={onSuccess} onError={onError} />
        </div>
      </div>
      <CSRTable onSuccess={onSuccess} onError={onError} />
    </div>
  );
}
