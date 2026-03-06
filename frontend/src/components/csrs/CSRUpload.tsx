import { useRef, useState } from "react";
import { useUploadCSR } from "../../hooks/useCSRs";
import Modal from "../ui/Modal";

interface Props {
  onSuccess: (msg: string) => void;
  onError: (msg: string) => void;
}

export default function CSRUpload({ onSuccess, onError }: Props) {
  const [open, setOpen] = useState(false);
  const [pem, setPem] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const { mutate, isPending } = useUploadCSR();

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    const arg: File | string | null = file ?? (pem.trim() ? pem.trim() : null);
    if (!arg) {
      onError("Provide a CSR file or paste PEM text");
      return;
    }
    mutate(arg, {
      onSuccess: (rec) => {
        onSuccess(`CSR "${rec.filename}" uploaded (CN: ${rec.common_name})`);
        setPem("");
        if (fileRef.current) fileRef.current.value = "";
        setOpen(false);
      },
      onError: () => onError("Failed to upload CSR"),
    });
  };

  return (
    <>
      <button className="btn btn-primary" onClick={() => setOpen(true)}>
        + Upload CSR
      </button>
      {open && (
        <Modal title="Upload Certificate Signing Request" onClose={() => setOpen(false)} size="md">
          <form onSubmit={submit}>
            <label>
              CSR File (.csr / .pem)
              <input type="file" accept=".csr,.pem,.txt" ref={fileRef} />
            </label>
            <label>
              Or paste PEM text
              <textarea
                rows={6}
                style={{ fontFamily: "monospace", fontSize: "12px", resize: "vertical" }}
                value={pem}
                onChange={(e) => setPem(e.target.value)}
                placeholder="-----BEGIN CERTIFICATE REQUEST-----&#10;...&#10;-----END CERTIFICATE REQUEST-----"
              />
            </label>
            <div className="row-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setOpen(false)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={isPending}>
                {isPending ? "Uploading…" : "Upload"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
