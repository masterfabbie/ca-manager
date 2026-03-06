import { useState } from "react";
import { CertsAPI } from "../../api/client";
import Modal from "../ui/Modal";

interface Props {
  certId: string;
  commonName: string;
  hasKey: boolean;
}

export default function DownloadMenu({ certId, commonName, hasKey }: Props) {
  const [open, setOpen] = useState(false);
  const [p12Modal, setP12Modal] = useState(false);
  const [p12Password, setP12Password] = useState("");

  return (
    <>
      <div className="dropdown">
        <button className="btn btn-secondary btn-sm" onClick={() => setOpen(!open)}>
          Download ▾
        </button>
        {open && (
          <div className="dropdown-menu" onMouseLeave={() => setOpen(false)}>
            <button
              disabled={!hasKey}
              title={!hasKey ? "No private key stored" : undefined}
              onClick={() => {
                setOpen(false);
                setP12Modal(true);
              }}
            >
              PKCS#12 (.p12){!hasKey && " —"}
            </button>
            <button
              disabled={!hasKey}
              title={!hasKey ? "No private key stored" : undefined}
              onClick={() => {
                setOpen(false);
                CertsAPI.downloadPEM(certId);
              }}
            >
              PEM Bundle{!hasKey && " —"}
            </button>
            <button
              onClick={() => {
                setOpen(false);
                CertsAPI.downloadCert(certId);
              }}
            >
              Certificate only
            </button>
          </div>
        )}
      </div>

      {p12Modal && (
        <Modal title={`Download P12 — ${commonName}`} onClose={() => setP12Modal(false)}>
          <label>
            Password (optional)
            <input
              type="password"
              value={p12Password}
              onChange={(e) => setP12Password(e.target.value)}
              placeholder="Leave blank for unencrypted"
              autoFocus
            />
          </label>
          <div className="row-actions" style={{ marginTop: 12 }}>
            <button
              className="btn btn-secondary"
              onClick={() => setP12Modal(false)}
            >
              Cancel
            </button>
            <button
              className="btn btn-primary"
              onClick={() => {
                CertsAPI.downloadP12(certId, p12Password || undefined);
                setP12Modal(false);
                setP12Password("");
              }}
            >
              Download
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
