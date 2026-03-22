export type ExportState = "idle" | "sending" | "ok" | "error";

export type BatchJobStatus = "queued" | "running" | "done" | "failed" | "retrying";

export type BatchJob = {
  name: string;
  status: BatchJobStatus;
  error?: string;
};

export type BatchStatus = {
  batch_id: string;
  total: number;
  queued: number;
  running: number;
  done: number;
  failed: number;
  results: BatchJob[];
};

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
  framedPhotoUrl?: string | null;
};
