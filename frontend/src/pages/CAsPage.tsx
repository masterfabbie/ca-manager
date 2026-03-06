import { useCAs, useDeleteCA } from "../hooks/useCAs";
import CreateCAForm from "../components/ca/CreateCAForm";
import CreateIntermediateCAForm from "../components/ca/CreateIntermediateCAForm";
import ImportCAForm from "../components/ca/ImportCAForm";
import { CAsAPI } from "../api/client";
import type { RootCA } from "../types";

interface Props {
  onSuccess: (msg: string) => void;
  onError: (msg: string) => void;
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString();
}

function buildHierarchy(cas: RootCA[]): RootCA[] {
  // Order: root CAs first, then intermediate CAs under their parent
  const roots = cas.filter((c) => !c.is_intermediate);
  const intermediates = cas.filter((c) => c.is_intermediate);
  const result: RootCA[] = [];
  for (const root of roots) {
    result.push(root);
    for (const inter of intermediates.filter((i) => i.parent_ca_id === root.id)) {
      result.push(inter);
    }
  }
  // Add any orphaned intermediates at the end
  for (const inter of intermediates.filter(
    (i) => !roots.some((r) => r.id === i.parent_ca_id)
  )) {
    result.push(inter);
  }
  return result;
}

export default function CAsPage({ onSuccess, onError }: Props) {
  const { data: cas, isLoading } = useCAs();
  const { mutate: deleteCA } = useDeleteCA();

  const rootCAs = cas?.filter((c) => !c.is_intermediate) ?? [];
  const ordered = cas ? buildHierarchy(cas) : [];

  const handleDelete = (id: string, name: string) => {
    if (
      !confirm(
        `Delete CA "${name}"?\nThis will also delete all certificates issued by it.`
      )
    )
      return;
    deleteCA(id, {
      onSuccess: () => onSuccess(`CA "${name}" deleted`),
      onError: () => onError("Failed to delete CA"),
    });
  };

  return (
    <div className="page">
      <div className="page-header">
        <h2>Certificate Authorities</h2>
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          <CreateCAForm onSuccess={onSuccess} onError={onError} />
          <CreateIntermediateCAForm
            rootCAs={rootCAs}
            onSuccess={onSuccess}
            onError={onError}
          />
          <ImportCAForm onSuccess={onSuccess} onError={onError} />
        </div>
      </div>

      {isLoading ? (
        <p className="muted">Loading…</p>
      ) : !cas?.length ? (
        <p className="muted">No CAs yet. Create one to get started.</p>
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Common Name</th>
                <th>Key Size</th>
                <th>Valid Until</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {ordered.map((ca) => (
                <tr key={ca.id}>
                  <td>
                    <span className={ca.is_intermediate ? "ca-indent" : undefined}>
                      <strong>{ca.name}</strong>
                      {ca.is_intermediate && (
                        <span className="badge badge-intermediate">Intermediate</span>
                      )}
                      {!ca.has_key && (
                        <span className="badge" title="Imported without private key — cannot issue certificates">No key</span>
                      )}
                    </span>
                  </td>
                  <td>{ca.common_name}</td>
                  <td>{ca.key_size} bit</td>
                  <td>{fmtDate(ca.not_after)}</td>
                  <td>{fmtDate(ca.created_at)}</td>
                  <td>
                    <div className="action-cell">
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => CAsAPI.downloadCert(ca.id)}
                      >
                        Download Cert
                      </button>
                      <button
                        className="btn btn-danger btn-sm"
                        onClick={() => handleDelete(ca.id, ca.name)}
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
