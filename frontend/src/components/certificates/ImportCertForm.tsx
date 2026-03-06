import { useState } from "react";
import { useImportCert } from "../../hooks/useCertificates";
import { useCAs } from "../../hooks/useCAs";
import type { CertImportPayload } from "../../types";
import Modal from "../ui/Modal";

interface Props {
  onSuccess: (msg: string) => void;
  onError: (msg: string) => void;
}

export default function ImportCertForm({ onSuccess, onError }: Props) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<CertImportPayload>({
    root_ca_id: null,
    cert_pem: "",
    key_pem: "",
  });
  const { mutate, isPending } = useImportCert();
  const { data: cas } = useCAs();

  const handle = (e: React.FormEvent) => {
    e.preventDefault();
    mutate(
      form,
      {
        onSuccess: (cert) => {
          onSuccess(`Certificate "${cert.common_name}" imported`);
          setForm({ root_ca_id: null, cert_pem: "", key_pem: "" });
          setOpen(false);
        },
        onError: (err: unknown) => {
          const detail = (err as any)?.response?.data?.detail;
          onError(detail ?? "Failed to import certificate");
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
        ↑ Import Cert
      </button>
      {open && (
        <Modal title="Import Certificate" onClose={() => setOpen(false)} size="lg">
          <form onSubmit={handle}>
            <p className="muted" style={{ margin: "0 0 12px", fontSize: "12px" }}>
              Import an existing leaf certificate. Without the private key only cert-only download is available
              (P12 and PEM bundle require the key).
            </p>
            <label>
              Signing CA <span className="muted">(optional)</span>
              <select
                value={form.root_ca_id ?? ""}
                onChange={(e) => setForm({ ...form, root_ca_id: e.target.value || null })}
              >
                <option value="">External / Public CA (Let's Encrypt, etc.)</option>
                {cas?.map((ca) => (
                  <option key={ca.id} value={ca.id}>{ca.name}</option>
                ))}
              </select>
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
