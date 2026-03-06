import { useEffect } from "react";

interface ToastProps {
  message: string;
  type: "success" | "error";
  onDone: () => void;
}

export default function Toast({ message, type, onDone }: ToastProps) {
  useEffect(() => {
    const t = setTimeout(onDone, 3500);
    return () => clearTimeout(t);
  }, [onDone]);

  return (
    <div className={`toast toast-${type}`}>{message}</div>
  );
}
