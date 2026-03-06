import { useState } from "react";
import { useImportCA } from "../../hooks/useCAs";
import { useCAs } from "../../hooks/useCAs";
import type { CAImportPayload } from "../../types";
import Modal from "../ui/Modal";

interface Props {
  onSuccess: (msg: string) => void;
  onError: (msg: string) => void;
}

const emptyForm = (): CAImportPayload => ({
  name: "",
  cert_pem: "",
  key_pem: "",
  is_intermediate: false,
  parent_ca_id: null,
});

export default function ImportCAForm({ onSuccess, onError }: Props) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<CAImportPayload>(emptyForm());
  const { mutate, isPending } = useImportCA();
  const { data: cas } = useCAs();

  const handle = (e: React.FormEvent) => {
    e.preventDefault();
    mutate(
      { ...form, parent_ca_id: form.parent_ca_id || null },
      {
        onSuccess: (ca) => {
          onSuccess(`CA "${ca.name}" imported${ca.has_key ? " (with key)" : " (cert only)"}`);
          setForm(emptyForm());
          setOpen(false);
        },
        onError: (err: unknown) => {
          const detail = (err as any)?.response?.data?.detail;
          onError(detail ?? "Failed to import CA");
        },
      }
    );
  };

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>, field: "cert_pem" | "key_pem") => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => setForm(f => ({ ...f, [field]: ev.target?.result as string }));
    reader.readAsText(file);
  };

  return (
    <>
      <button className="btn btn-secondary" onClick={() => setOpen(true)}>
        ↑ Import CA
      </button>
      {open && (
        <Modal title="Import CA Certificate" onClose={() => setOpen(false)} size="lg">
          <form onSubmit={handle}>
            <p className="muted" style={{ margin: "0 0 12px", fontSize: "12px" }}>
              Import an existing root or intermediate CA. Without the private key it acts as a trust anchor only
              (chain building works, but you cannot issue new certificates from it).
            </p>
            <label>
              Display Name
              <input
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="My Public Root CA"
              />
            </label>
            <label>
              Certificate PEM
              <div style={{ display: "flex", gap: 6, marginBottom: 4 }}>
                <input
                  type="file"
                  accept=".pem,.crt,.cer"
                  onChange={(e) => handleFile(e, "cert_pem")}
                  style={{ flex: 1 }}
                />
              </div>
              <textarea
                required
                rows={5}
                style={{ fontFamily: "monospace", fontSize: "12px", resize: "vertical" }}
                value={form.cert_pem}
                onChange={(e) => setForm({ ...form, cert_pem: e.target.value })}
                placeholder="-----BEGIN CERTIFICATE-----&#10;...&#10;-----END CERTIFICATE-----"
              />
            </label>
            <label>
              Private Key PEM <span className="muted">(optional)</span>
              <div style={{ display: "flex", gap: 6, marginBottom: 4 }}>
                <input
                  type="file"
                  accept=".pem,.key"
                  onChange={(e) => handleFile(e, "key_pem")}
                  style={{ flex: 1 }}
                />
              </div>
              <textarea
                rows={4}
                style={{ fontFamily: "monospace", fontSize: "12px", resize: "vertical" }}
                value={form.key_pem}
                onChange={(e) => setForm({ ...form, key_pem: e.target.value })}
                placeholder="-----BEGIN RSA PRIVATE KEY-----&#10;...&#10;(leave blank if you only have the certificate)"
              />
            </label>
            <label style={{ flexDirection: "row", alignItems: "center", gap: "8px" }}>
              <input
                type="checkbox"
                checked={form.is_intermediate}
                onChange={(e) => setForm({ ...form, is_intermediate: e.target.checked })}
                style={{ width: "auto" }}
              />
              This is an intermediate CA
            </label>
            {form.is_intermediate && cas && cas.length > 0 && (
              <label>
                Parent CA <span className="muted">(optional — enables full chain downloads)</span>
                <select
                  value={form.parent_ca_id ?? ""}
                  onChange={(e) => setForm({ ...form, parent_ca_id: e.target.value || null })}
                >
                  <option value="">— none / unknown —</option>
                  {cas.filter((c) => !c.is_intermediate).map((ca) => (
                    <option key={ca.id} value={ca.id}>{ca.name}</option>
                  ))}
                </select>
              </label>
            )}
            <div className="row-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setOpen(false)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={isPending}>
                {isPending ? "Importing…" : "Import"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
