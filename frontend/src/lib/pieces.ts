import type { VersionInfo } from "./api";

const SCREENSHOT = "screenshot.png";

/**
 * The version whose build screenshot stands for a piece on the Pieces page: the approved
 * version when it has one, else the newest version that has one, else none. `infos` is the
 * piece's versions newest first (an entry is undefined until it has loaded).
 */
export function pictureVersion(infos: (VersionInfo | undefined)[]): { version: number; approved: boolean } | null {
  const hasScreenshot = (info: VersionInfo | undefined) => Boolean(info?.files?.includes(SCREENSHOT));
  const approved = infos.find((info) => info?.approved_at);
  if (approved && hasScreenshot(approved)) return { version: approved.version, approved: true };
  const newest = infos.find(hasScreenshot);
  return newest ? { version: newest.version, approved: false } : null;
}
