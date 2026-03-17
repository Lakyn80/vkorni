export type ExportState = "idle" | "sending" | "ok" | "error";

export type Profile = {
  id: string;
  name: string;
  text: string;
  photos: string[];
  photoSources?: Record<string, string>;
  selectedPhoto?: string;
  birth?: string | null;
  death?: string | null;
  loading?: boolean;
  error?: string;
  exportState?: ExportState;
  exportMessage?: string;
};
