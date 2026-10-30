export function filenameFromContentDisposition(contentDisposition: string | null, fallback: string): string {
  if (!contentDisposition) return fallback;
  const match = contentDisposition.match(/filename\*?=(?:UTF-8''|utf-8'')?(?:"([^"]+)"|([^;\s]+))/);
  const rawFilename = match?.[1] ?? match?.[2];
  if (!rawFilename) return fallback;
  try {
    return decodeURIComponent(rawFilename);
  } catch {
    return rawFilename;
  }
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
