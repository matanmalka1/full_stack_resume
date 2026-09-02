export const formatBytes = (bytes: number): string =>
  bytes < 1024
    ? `${bytes} B`
    : bytes < 1024 * 1024
      ? `${(bytes / 1024).toLocaleString("en-US", { maximumFractionDigits: 1 })} KB`
      : `${(bytes / (1024 * 1024)).toLocaleString("en-US", { maximumFractionDigits: 2 })} MB`;
