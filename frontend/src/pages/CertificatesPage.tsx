import IssueForm from "../components/certificates/IssueForm";
import CertTable from "../components/certificates/CertTable";
import BulkDownloadButton from "../components/certificates/BulkDownloadButton";
import ImportCertForm from "../components/certificates/ImportCertForm";
import { useAppStore } from "../store/appStore";

interface Props {
  onSuccess: (msg: string) => void;
  onError: (msg: string) => void;
}

export default function CertificatesPage({ onSuccess, onError }: Props) {
  const { selectedCAId } = useAppStore();

  return (
    <div className="page">
      <div className="page-header">
        <h2>Certificates</h2>
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          <BulkDownloadButton caId={selectedCAId} />
          <ImportCertForm onSuccess={onSuccess} onError={onError} />
          <IssueForm onSuccess={onSuccess} onError={onError} />
        </div>
      </div>
      <CertTable onError={onError} />
    </div>
  );
}
