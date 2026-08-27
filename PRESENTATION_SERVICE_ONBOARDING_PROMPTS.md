# Presentation Service — onboarding prompts

Starting prompts for the two people picking up the work described in
[`PRESENTATION_SERVICE_DESIGN.md`](./PRESENTATION_SERVICE_DESIGN.md).

Each prompt is self-contained: it assumes no prior familiarity with the design
document or with this part of the project. Copy the whole block into a fresh
Claude Code session opened in this repository.

The two tracks share only the bundle format, so they can proceed in parallel and
neither blocks the other.

---

## Track A — DevOps / infrastructure

```
Please start by reading PRESENTATION_SERVICE_DESIGN.md in this project's root.
It's a design document that was written before I joined this piece of work, so
treat it as my briefing material as much as yours.

Background, so you know where I'm coming in: this repo is an archiving system
with an internal browsing platform that holds everything we've captured. That
platform is deliberately kept quiet - we don't publicise it or hand out links,
because it would be a valuable target. But some of the material is of public
interest and needs to be shareable. The plan is to stand up a completely separate
server that hosts nothing but frozen, static HTML-and-media copies of individual
items. The internal platform pushes copies to it; the public server holds no
database, runs no application code, and is not supposed to know the internal
platform exists.

I own the infrastructure side. The document splits the work into two tracks -
mine is "Track A". Please leave Track B alone, someone else has it.

I want your help both deciding things and actually building them. Concretely:

1. There's one decision the document deliberately left open, about how a bundle
   of files should physically travel from the internal platform to the public
   server. It lays out four options and explains the concern driving them: server
   logs on the public box would record the internal platform's IP address, so
   anyone who breaks into the public server could work out where the real archive
   lives. Read that section, then pressure-test it with me. Is that scenario
   realistic enough to justify the cost and complexity of the more paranoid
   options? Are there leakage routes the document missed - certificate
   transparency logs, DNS history, both machines sitting in the same provider's
   address space, billing records, or timing correlation between publishes and
   activity on the internal platform? I want a recommendation with reasoning I
   can take to the team, not just a pick.

2. Hosting. The document sketches three shapes without choosing. The workload is
   under 100GB of static files, mostly video, low steady request volume, with
   occasional spikes if something circulates. Price them out properly with
   current numbers. Flag any place where a hosting choice would constrain the
   decision in point 1 - I'm told object storage in particular changes "you can
   only upload over SSH" into "you can upload with an API key", which is a
   meaningful difference for us.

3. Then actually set it up, don't just advise. I want the machine provisioned as
   infrastructure-as-code: pick a tool that fits how this repo already works,
   write the configuration, and get it to the point where I can run it. That
   includes the nginx configuration the document specifies, TLS, and the full
   hardening list it gives (minimised logging, no server version banners, no
   directory listings, no build metadata leaking into the published files).
   Write the provisioning runbook as you go.

4. There's also an optional performance item in the document - serving media
   files through nginx directly instead of through the Python application. It's
   independent of everything above. Tell me whether it's worth doing now.

Work through 1 and 2 with me first and get my agreement before writing any
configuration. Ask me anything that would change your recommendation - including
things about our situation that aren't in the document.
```

---

## Track B — UX / application

```
Please start by reading PRESENTATION_SERVICE_DESIGN.md in this project's root.
It's a design document written before I picked this up, so treat it as my
briefing as much as yours.

Background: this repo is an archiving system. It has an internal browsing
platform where we look at everything we've captured, and that platform is kept
deliberately low-profile because it would be a valuable target. Some of the
archived material is of public interest, though, and we want to be able to share
it. The plan is a separate public server that hosts nothing but frozen static
copies of individual items. An admin looking at something in the internal
platform clicks a button, we build a self-contained snapshot of it, push it to
the public server, and get back a link.

The hard constraint running through all of this: the people who captured this
material used real social media accounts, and exposing which accounts those were
would put them at risk. Nothing identifying them may end up in a published
snapshot. The document has an inventory of everywhere that information currently
hides - it's in more places than you'd guess, including inside the file paths of
the media itself.

I own the application side. The document splits the work into two tracks - mine
is "Track B". Please leave Track A alone, that's the infrastructure work and
someone else has it. Usefully, my half can be built and tested end to end without
the public server existing yet.

Please follow the build order below rather than starting with the visible parts:

1. The redaction layer first, with tests, before any UI exists. It decides what
   information is allowed to leave, so it's the security boundary for this whole
   feature. The document lists four specific test cases as the acceptance
   criteria. One detail it's firm about: there's a final check that scans the
   finished snapshot for anything identifying before it's allowed out, and that
   check must not be skippable.

2. Then the asset handling - copying media files, generating video poster images,
   and assembling the cryptographic proof block that lets a reader verify a
   published file is authentic. The document describes several tiers of proof
   depending on how old the archive is; only implement the ones it says to, and
   leave the older formats as explicitly unimplemented until we get real examples
   of them. It's also emphatic that published media must never be re-encoded -
   read why before you're tempted.

3. Then the database table, API routes and services, testing against a local
   directory as the publish destination.

4. Then the UI. Note that snapshots are permanent by design - once something is
   published it can't be withdrawn from the internal platform. That makes the
   preview step, where the publisher sees exactly what's about to go out, one of
   only two things standing between a mistake and a permanent public leak. Please
   design it so people genuinely read it rather than clicking past it. That's the
   part I most want your judgement on.

5. Finally, some video-loading fixes in the existing internal platform. Right now
   opening a page with ten videos starts ten downloads nobody asked for. The
   document lists the exact places to fix and flags one that needs different
   treatment from the rest.

Two cautions before you trust the document's specifics. It cites file paths and
line numbers from a survey of the code as it was - confirm they still point where
it claims before relying on them. And it warns about one function in particular
that must not be called from the publishing code, because it embeds the internal
platform's own address into its output.

Read it, then show me your plan for step 1 before you write it.
```

---

## Not covered by either track

The design document closes with a follow-up item that is **out of scope for both
tracks** and should be assigned separately: the existing share-link feature leaks
capture-machine details (hostname, LAN IP, MAC address, and several other
metadata fields) to share-link recipients today. That is a live exposure in
shipped code and should not wait on this project.
