/**
 * Active Campaign Persistence and Context Helper
 *
 * Manages the currently selected campaign identifier across workflow steps.
 * Synchronizes with URL query parameters and browser localStorage.
 */

const STORAGE_KEY = "campaignlift_active_campaign_id"

export function getActiveCampaignId(): string | null {
  if (typeof window === "undefined") return null

  // 1. Check URL hash query parameters (e.g. #/?campaign_id=... or #/?id=...)
  const hash = window.location.hash || ""
  const qIndex = hash.indexOf("?")
  if (qIndex !== -1) {
    const params = new URLSearchParams(hash.slice(qIndex + 1))
    const fromUrl = params.get("campaign_id") || params.get("id")
    if (fromUrl) {
      try {
        localStorage.setItem(STORAGE_KEY, fromUrl)
      } catch {
        // localStorage not available
      }
      return fromUrl
    }
  }

  // 2. Check localStorage
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

export function setActiveCampaignId(id: string): void {
  if (typeof window === "undefined") return
  try {
    localStorage.setItem(STORAGE_KEY, id)
  } catch {
    // localStorage not available
  }
  window.dispatchEvent(
    new CustomEvent("campaignlift:campaign_changed", { detail: { id } }),
  )
}

export function clearActiveCampaignId(): void {
  if (typeof window === "undefined") return
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // localStorage not available
  }
  window.dispatchEvent(
    new CustomEvent("campaignlift:campaign_changed", { detail: { id: null } }),
  )
}
