import type { SANEntry } from "../../types";

interface Props {
  value: SANEntry[];
  onChange: (sans: SANEntry[]) => void;
}

export default function SANEditor({ value, onChange }: Props) {
  const add = () => onChange([...value, { type: "dns", value: "" }]);
  const remove = (i: number) => onChange(value.filter((_, idx) => idx !== i));
  const update = (i: number, patch: Partial<SANEntry>) =>
    onChange(value.map((s, idx) => (idx === i ? { ...s, ...patch } : s)));

  return (
    <div className="san-editor">
      {value.map((san, i) => (
        <div key={i} className="san-row">
          <select
            value={san.type}
            onChange={(e) => update(i, { type: e.target.value as "dns" | "ip" })}
          >
            <option value="dns">DNS</option>
            <option value="ip">IP</option>
          </select>
          <input
            value={san.value}
            onChange={(e) => update(i, { value: e.target.value })}
            placeholder={san.type === "dns" ? "example.com" : "192.168.1.1"}
          />
          <button
            type="button"
            className="btn-icon btn-danger"
            onClick={() => remove(i)}
          >
            ✕
          </button>
        </div>
      ))}
      <button type="button" className="btn btn-secondary btn-sm" onClick={add}>
        + Add SAN
      </button>
    </div>
  );
}
