import { useState } from "react";
import { useCSRs, useDeleteCSR, useImportCSRCert, useSignCSR } from "../../hooks/useCSRs";
import { useCAs } from "../../hooks/useCAs";
import Modal from "../ui/Modal";
import SANEditor from "../certificates/SANEditor";
import type { CSRImportCertPayload, CSRRecord, CSRSignPayload, SANEntry } from "../../types";
import { CSRsAPI } from "../../api/client";

interface Props {
  onSuccess: (msg: string) => void;
  onError: (msg: string) => void;
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString();
}

interface SignState {
  csr: CSRRecord;
  caId: string;
  validDays: number;
  sans: SANEntry[];
}

interface ImportCertState {
  csr: CSRRecord;
  caId: string;
  certPem: string;
}

export default function CSRTable({ onSuccess, onError }: Props) {
  const { data: csrs, isLoading } = useCSRs();
  const { data: cas } = useCAs();
  const { mutate: deleteCSR } = useDeleteCSR();
  const { mutate: signCSR, isPending: isSigning } = useSignCSR();
  const { mutate: importCert, isPending: isImporting } = useImportCSRCert();
  const [signing, setSigning] = useState<SignState | null>(null);
  const [importing, setImporting] = useState<ImportCertState | null>(null);

  const openSign = (csr: CSRRecord) => {
    const firstCA = cas?.find((c) => c.has_key);
    if (!firstCA) {
      onError("No CA with a private key — create or import one first");
      return;
    }
    setSigning({ csr, caId: firstCA.id, validDays: 365, sans: csr.sans });
  };

  const openImportCert = (csr: CSRRecord) => {
    const firstCA = cas?.[0];
    setImporting({ csr, caId: firstCA?.id ?? "", certPem: "" });
  };

  const submitSign = () => {
    if (!signing) return;
    const payload: CSRSignPayload = {
      ca_id: signing.caId,
      valid_days: signing.validDays,
      sans: signing.sans,
    };
    signCSR(
      { id: signing.csr.id, payload },
      {
        onSuccess: () => {
          onSuccess(`CSR "${signing.csr.filename}" signed`);
          setSigning(null);
        },
        onError: () => onError("Failed to sign CSR"),
      }
    );
  };

  const submitImportCert = () => {
    if (!importing) return;
    const payload: CSRImportCertPayload = {
      cert_pem: importing.certPem,
      ca_id: importing.caId,
    };
    importCert(
      { id: importing.csr.id, payload },
      {
        onSuccess: () => {
          onSuccess(`Signed cert imported for "${importing.csr.filename}"`);
          setImporting(null);
        },
        onError: (err: unknown) => {
          const detail = (err as any)?.response?.data?.detail;
          onError(detail ?? "Failed to import certificate");
        },
      }
    );
  };

  const handleDelete = (id: string, filename: string) => {
    if (!confirm(`Delete CSR "${filename}"?`)) return;
    deleteCSR(id, {
      onSuccess: () => onSuccess(`CSR "${filename}" deleted`),
      onError: () => onError("Failed to delete CSR"),
    });
  };

  return (
    <div>
      {isLoading ? (
        <p className="muted">Loading…</p>
      ) : !csrs?.length ? (
        <p className="muted">No CSRs yet. Generate one or upload an external CSR.</p>
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Source</th>
                <th>Common Name</th>
                <th>SANs</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {csrs.map((csr) => (
                <tr key={csr.id}>
                  <td>
                    <span className={`badge ${csr.has_key ? "badge-intermediate" : ""}`}
                      title={csr.has_key ? "Generated in-app (key stored)" : "Uploaded externally"}>
                      {csr.has_key ? "Generated" : "Uploaded"}
                    </span>
                    <div style={{ fontSize: "11px", color: "var(--muted)", marginTop: "2px" }}>
                      {csr.filename}
                    </div>
                  </td>
                  <td><strong>{csr.common_name}</strong></td>
                  <td>
                    <div className="san-pills">
                      {csr.sans.map((s, i) => (
                        <span key={i} className={`pill pill-${s.type}`}>
                          {s.type.toUpperCase()}: {s.value}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td>
                    {csr.signed_cert_id ? (
                      <span className="badge" style={{ color: "var(--success)" }}>Signed</span>
                    ) : (
                      <span className="badge">Pending</span>
                    )}
                  </td>
                  <td>{fmtDate(csr.created_at)}</td>
                  <td>
                    <div className="action-cell">
                      {/* Download CSR */}
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => CSRsAPI.downloadCSR(csr.id)}
                        title="Download CSR file"
                      >
                        ↓ CSR
                      </button>
                      {/* Download key (generated only) */}
                      {csr.has_key && (
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => CSRsAPI.downloadKey(csr.id)}
                          title="Download private key"
                        >
                          ↓ Key
                        </button>
                      )}
                      {/* Sign with internal CA (unsigned only) */}
                      {!csr.signed_cert_id && (
                        <button
                          className="btn btn-primary btn-sm"
                          onClick={() => openSign(csr)}
                        >
                          Sign (internal)
                        </button>
                      )}
                      {/* Import cert returned by external CA */}
                      {!csr.signed_cert_id && (
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => openImportCert(csr)}
                          title="Import the signed certificate from an external CA"
                        >
                          Import cert
                        </button>
                      )}
                      <button
                        className="btn btn-danger btn-sm"
                        onClick={() => handleDelete(csr.id, csr.filename)}
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

      {/* Sign with internal CA modal */}
      {signing && (
        <Modal title={`Sign with Internal CA: ${signing.csr.filename}`} onClose={() => setSigning(null)}>
          <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            <label>
              Signing CA
              <select
                value={signing.caId}
                onChange={(e) => setSigning({ ...signing, caId: e.target.value })}
              >
                {cas?.filter((c) => c.has_key).map((ca) => (
                  <option key={ca.id} value={ca.id}>{ca.name}</option>
                ))}
              </select>
            </label>
            <label>
              Valid Days
              <input
                type="number"
                min={1}
                max={3650}
                value={signing.validDays}
                onChange={(e) => setSigning({ ...signing, validDays: Number(e.target.value) })}
              />
            </label>
            <label style={{ color: "var(--muted)", fontSize: "13px" }}>Subject Alternative Names</label>
            <SANEditor
              value={signing.sans}
              onChange={(sans) => setSigning({ ...signing, sans })}
            />
            <div className="row-actions">
              <button className="btn btn-secondary" onClick={() => setSigning(null)}>Cancel</button>
              <button className="btn btn-primary" onClick={submitSign} disabled={isSigning}>
                {isSigning ? "Signing…" : "Sign Certificate"}
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Import cert from external CA modal */}
      {importing && (
        <Modal title={`Import Signed Cert: ${importing.csr.filename}`} onClose={() => setImporting(null)}>
          <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            <p className="muted" style={{ margin: 0, fontSize: "12px" }}>
              Paste the signed certificate you received from the external CA.
              {importing.csr.has_key && " The private key stored with this CSR will be linked automatically."}
            </p>
            <label>
              Signing CA <span className="muted">(select which CA in this system signed it)</span>
              <select
                value={importing.caId}
                onChange={(e) => setImporting({ ...importing, caId: e.target.value })}
              >
                {cas?.map((ca) => (
                  <option key={ca.id} value={ca.id}>{ca.name}</option>
                ))}
              </select>
            </label>
            <label>
              Signed Certificate PEM
              <textarea
                rows={8}
                style={{ fontFamily: "monospace", fontSize: "12px", resize: "vertical" }}
                value={importing.certPem}
                onChange={(e) => setImporting({ ...importing, certPem: e.target.value })}
                placeholder="-----BEGIN CERTIFICATE-----&#10;...&#10;-----END CERTIFICATE-----"
              />
            </label>
            <div className="row-actions">
              <button className="btn btn-secondary" onClick={() => setImporting(null)}>Cancel</button>
              <button
                className="btn btn-primary"
                onClick={submitImportCert}
                disabled={isImporting || !importing.certPem.trim()}
              >
                {isImporting ? "Importing…" : "Import Certificate"}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
