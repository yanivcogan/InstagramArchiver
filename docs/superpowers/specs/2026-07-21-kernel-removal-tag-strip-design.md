# Kernel removal & community-tag stripping — design

**Date:** 2026-07-21
**Scope:** `browsing_platform/client/src/pages/CommunityDetectionPage.tsx` only. No backend changes.

## Problem

On the Community Detection page in tag-bound mode, kernel (seed) membership is derived
from the community tag (and its subtags). Removing an account from the kernel without
also stripping its justifying tag(s) means the account silently returns to the kernel
the next time the page is loaded for that tag. The two removal paths currently diverge:

- **Compact pill view:** the X button calls `removeFromKernel()` directly — no warning,
  account returns on next load.
- **Expanded view:** "Remove from seeds" goes through `takeOutOfKernel()`, which opens a
  confirmation dialog that **forces** tag removal — there is no "remove for this session
  only" option.

## Design

### Shared helper

Extract `stripTagsAndRemove(entry: KernelEntry)`: awaits `removeAccountTag(accountId, tagId)`
for each tag in `entry.tagSources`, then calls `removeFromKernel(entry.account.id)`.
Used by the pill modal's confirm action and by the expanded view's strip button.

### Compact view (KernelAccountPill X button)

- If tag mode is active (`communityDropdown` non-null) **and** `entry.tagSources.length > 0`:
  open the removal modal (reuses the existing `pendingKernelTagRemoval` state/dialog).
- Otherwise: `removeFromKernel()` directly, as today.

Modal (upgraded from the existing forced-removal dialog):

- **Title:** "Also remove the community tag(s)?"
- **Body:** names the account, lists its community tag source(s), and explains that
  removing it from the seeds **without** removing the tag(s) means it will automatically
  return to the seeds the next time the community page is loaded for this tag.
- **Actions:**
  1. Cancel
  2. "Remove from seeds only" — session-only removal (`removeFromKernel`)
  3. "Remove tag(s) & remove from seeds" — error-styled; `stripTagsAndRemove(entry)`

### Expanded view (KernelAccountCard)

No confirmation modal on this path anymore — the branching is expressed as explicit
buttons instead (more space; saves a click):

- When tag mode is active **and** `entry.tagSources.length > 0`, show **two** buttons:
  1. "Remove & strip tag(s)" — calls `stripTagsAndRemove(entry)` directly; keeps the
     existing tooltip explaining the tag(s) are removed from the account in the database.
     **Visible only when `tagSources.length > 0`.**
  2. "Remove from seeds" — calls `removeFromKernel()` directly; tooltip explains the
     account will return to the seeds on the next load of this tag's community page.
- Otherwise (no tag mode, or no tag sources): single "Remove from seeds" button that
  removes directly — unchanged behavior.

### Out of scope

- Manually added accounts whose tag state exists only in the DB (never toggled in this
  session) have empty `tagSources` and are removed without a modal — consistent with the
  page's existing source-of-truth (`tagSources` reflects what the session knows).
- No snackbar/undo changes; dismissal persistence (`saveTagDismissals`) untouched.
