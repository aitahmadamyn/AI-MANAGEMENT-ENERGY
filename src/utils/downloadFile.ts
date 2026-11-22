export interface DownloadProgressState {
  status: 'idle' | 'downloading' | 'error';
  activeFile: string | null;
  errorMessage: string | null;
}

function getMimeType(filename: string): string {
  const lower = filename.toLowerCase();
  if (lower.endsWith('.zip')) return 'application/zip';
  if (lower.endsWith('.xlsx')) {
    return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
  }
  if (lower.endsWith('.csv')) return 'text/csv;charset=utf-8';
  if (lower.endsWith('.ipynb')) return 'application/x-ipynb+json;charset=utf-8';
  if (lower.endsWith('.md')) return 'text/markdown;charset=utf-8';
  return 'application/octet-stream';
}

export async function downloadStagedAsset(href: string, filename: string): Promise<void> {
  if (!href) {
    throw new Error(`No staged download path available for ${filename}.`);
  }

  const response = await fetch(href, {
    method: 'GET',
    credentials: 'include',
    cache: 'no-store',
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status} while fetching ${filename}.`);
  }

  const buffer = await response.arrayBuffer();
  if (buffer.byteLength === 0) {
    throw new Error(`Downloaded empty file (0 bytes) for ${filename}.`);
  }

  const bytes = new Uint8Array(buffer);
  const headText = new TextDecoder('utf-8', { fatal: false }).decode(bytes.slice(0, 64)).trimStart().toLowerCase();
  if (headText.startsWith('<!doctype html') || headText.startsWith('<html')) {
    throw new Error(
      `Proxy returned an HTML page instead of ${filename}. Refresh the preview session and retry.`
    );
  }

  const lowerName = filename.toLowerCase();
  if (lowerName.endsWith('.zip') || lowerName.endsWith('.xlsx')) {
    const isPk = bytes.length >= 4 && bytes[0] === 0x50 && bytes[1] === 0x4b;
    if (!isPk) {
      throw new Error(`Invalid archive header in ${filename} (expected PKZIP magic bytes 0x50 0x4B).`);
    }
  }

  const blob = new Blob([buffer], { type: getMimeType(filename) });
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = objectUrl;
  link.download = filename;
  link.rel = 'noopener noreferrer';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1500);
}
