import { useQueryClient } from "@tanstack/react-query";
import { useCertificates, useDeleteCert } from "../../hooks/useCertificates";
import { useAppStore } from "../../store/appStore";
import { useCAs } from "../../hooks/useCAs";
import { CertsAPI } from "../../api/client";
import DownloadMenu from "./DownloadMenu";

interface Props {
  onError: (msg: string) => void;
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString();
}

export default function CertTable({ onError }: Props) {
  const { selectedCAId, setSelectedCAId } = useAppStore();
  const { data: cas } = useCAs();
  const { data: certs, isLoading } = useCertificates(selectedCAId);
  const { mutate: deleteCert } = useDeleteCert();
  const qc = useQueryClient();

  const handleDelete = (id: string, cn: string) => {
    if (!confirm(`Delete certificate for "${cn}"?`)) return;
    deleteCert(id, {
      onError: () => onError("Failed to delete certificate"),
    });
  };

  const handleAlertToggle = async (id: string, current: boolean) => {
    try {
      await CertsAPI.setAlert(id, !current);
      qc.invalidateQueries({ queryKey: ["certificates"] });
    } catch {
      onError("Failed to update alert setting");
    }
  };

  const caName = (id: string | null) =>
    id ? (cas?.find((c) => c.id === id)?.name ?? id.slice(0, 8)) : "External";

  return (
    <div>
      <div className="table-toolbar">
        <h3>Certificate History</h3>
        <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
          Filter by CA:
          <select
            value={selectedCAId ?? ""}
            onChange={(e) => setSelectedCAId(e.target.value || null)}
          >
            <option value="">All CAs</option>
            {cas?.map((ca) => (
              <option key={ca.id} value={ca.id}>
                {ca.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      {isLoading ? (
        <p className="muted">Loading…</p>
      ) : !certs?.length ? (
        <p className="muted">No certificates yet.</p>
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Common Name</th>
                <th>SANs</th>
                <th>Root CA</th>
                <th>Valid Until</th>
                <th>Key</th>
                <th>Created</th>
                <th>Alert</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {certs.map((cert) => (
                <tr key={cert.id}>
                  <td>
                    <strong>{cert.common_name}</strong>
                  </td>
                  <td>
                    <div className="san-pills">
                      {cert.sans.map((s, i) => (
                        <span key={i} className={`pill pill-${s.type}`}>
                          {s.type.toUpperCase()}: {s.value}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td>{caName(cert.root_ca_id)}</td>
                  <td>{fmtDate(cert.not_after)}</td>
                  <td>{cert.key_size} bit</td>
                  <td>{fmtDate(cert.created_at)}</td>
                  <td>
                    <input
                      type="checkbox"
                      checked={cert.alert_enabled}
                      onChange={() => handleAlertToggle(cert.id, cert.alert_enabled)}
                      title="Send expiry alert for this certificate"
                      style={{ width: "auto", cursor: "pointer" }}
                    />
                  </td>
                  <td>
                    <div className="action-cell">
                      <DownloadMenu certId={cert.id} commonName={cert.common_name} hasKey={cert.has_key} />
                      {!cert.has_key && (
                        <span className="badge" title="No private key stored — cert-only download available">No key</span>
                      )}
                      <button
                        className="btn btn-danger btn-sm"
                        onClick={() => handleDelete(cert.id, cert.common_name)}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
