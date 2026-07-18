# UniJos Journal System — Design Brief

A design-focused description of the product for use in **Claude Design**. This document explains *what* the system is, *who* uses it, and *what screens* need to exist — so the visual/interaction design can be redone well.

---

## 1. What is being built

**UniJos Journal System** is a web platform for the **University of Jos** to manage academic journals end-to-end: from an author submitting a manuscript, through **blind (anonymous) peer review**, editorial decisions, revisions, to final **publication** in an online journal and a **searchable archive** of past issues.

Think of it as a lightweight, self-hosted version of platforms like **OJS (Open Journal Systems)**, **ScholarOne**, or **Editorial Manager** — but tailored to a single university with multiple departments, each running its own journals.

It is a **Django** web application (server-rendered HTML templates). Today it uses Bootstrap 5 + a Material-flavored CSS layer, Poppins font, and Font Awesome / Material icons. The redesign should modernize the visual system while keeping it template-friendly (server-rendered pages, no heavy SPA framework required).

---

## 2. Who uses it (roles)

The product serves **five distinct audiences**, and the design must make each person's "next action" obvious:

| Role | Who they are | What they do |
|------|--------------|--------------|
| **Public / Reader** | Anyone on the internet | Browse published journals, read articles, search, download PDFs, view archives |
| **Author** | Faculty, researchers, students | Submit manuscripts (Word docs), track review status, respond to revision requests, re-upload revised documents |
| **Reviewer** | Registered peer reviewers | See assigned manuscripts (author identity hidden), read, give feedback + recommendation, upload annotated documents |
| **Editor** | Department editors | Oversee submissions, coordinate reviewers, make editorial decisions |
| **Admin** | Journal managers / staff | Assign reviewers, manage the whole workflow, invite external guest reviewers, publish articles, configure the site, manage archives |

There are also **Guest Reviewers** — external experts *without accounts*. They receive an email invitation with a secure token link and review a manuscript **without logging in**. Their experience must feel trustworthy and self-explanatory since they have no dashboard or onboarding.

**Blind peer review is central:** reviewers must never see the author's name. Manuscripts are identified by an anonymized ID like `MS-2026-0007`. The design must consistently hide author identity in every reviewer-facing surface.

---

## 3. Core concepts / domain model

- **Department** → owns → **Journals** (e.g., "Faculty of Science" → "Journal of Natural Sciences").
- **Journal** → contains → **Articles** (published) and **Categories** and **Rubrics** (author guidelines/content).
- **Submission** → the manuscript in the review pipeline. Has a status lifecycle:
  `Pending → In Review → With Editor → Revision Requested → Revised → Approved → Published` (or `Rejected`).
- **Assignment** → links a Submission to a Reviewer or Editor (regular user *or* guest reviewer). Carries their feedback, recommendation, and an optional amended document. Can be `blinded`.
- **Document Version** → each re-upload during review is versioned; one can be marked *final*.
- **Submission Message** → in-app chat between admin/editors/reviewers about a submission (supports attachments, read/unread state).
- **Submission Log** → activity timeline of everything that happened to a submission.
- **Archived Journal** → a full past issue (PDF + cover image + volume/issue/date), browsable publicly.
- **Article** → the published output: title, abstract, content, keywords, DOI, volume/issue/pages, extracted citations & sections from the final Word document.
- **Site Settings** → admin-configurable branding: site title, logo, favicon, **primary & secondary color**, footer, contact info, social links. *(The design should respect these theming variables.)*
- **Hero Slides** → admin-managed homepage carousel (image, title, subtitle, CTA button).

---

## 4. Key screens & flows to design

### A. Public-facing
- **Homepage** — hero carousel, featured/archived journals, list of journals by department, recent published articles. This is the "front door" and should feel like a credible academic publisher.
- **Journal list & Department journal page** — browse journals grouped by department.
- **Article list / detail** — read a published article: abstract, keywords, citations, metadata (volume, issue, pages, DOI), PDF download.
- **Article search / filter** — search across published articles.
- **Public archives** — browse past issues (cover thumbnails, volume/issue), archive detail with document download.
- **Auth** — register, login, password reset flow (4 screens).

### B. Author experience
- **Author dashboard** — my submissions and their live status.
- **Submission create** — upload a `.docx` manuscript + optional cover letter.
- **Submission detail** — status timeline, messages, revision requests, document versions.
- **Submission revise** — re-upload a revised document in response to feedback.

### C. Reviewer / Editor experience
- **Reviewer & Editor dashboards** — assigned manuscripts (author identity hidden, shown as `MS-YYYY-####`).
- **My assignments** — list of things awaiting my review.
- **Work on submission** — the core review workspace: read the manuscript, download document, write feedback, pick a recommendation (Approve / Minor revision / Major revision / Reject), upload an amended document, chat with the editor.

### D. Admin / staff
- **Admin dashboard** — pipeline overview, counts by status, things needing attention.
- **Admin submission detail** — full control: assign reviewers/editors, request revisions, upload final document, preview extracted content, approve/publish/reject, share with author.
- **Assign reviewer** — pick internal reviewers or guest reviewers, toggle blinding.
- **Guest reviewer management** — add one / bulk add via CSV, edit, resend invitation.
- **Archived journals CRUD** — upload/manage past issues.
- **Site settings & Hero slides** — branding and homepage management.

### E. Guest reviewer (no login)
- **Guest access landing** (token link), **guest work-on-submission** (review without account), **feedback submitted** confirmation, and a **guest access error** page. Must be extremely clear and self-contained since these users have zero context.

### F. Transactional emails (HTML)
Invitations, assignment notifications, feedback confirmations, approval notices, "share with author," welcome, revision notifications. These should share the platform's visual identity.

---

## 5. Design goals & priorities

1. **Credible & academic** — this represents a university's scholarly output. It should feel authoritative, clean, and trustworthy, not flashy.
2. **Role-clarity** — five audiences share the same app. Each landing/dashboard must instantly answer "what do I do next?" Status and pending-action states are the most important UI elements.
3. **Status is the hero** — submissions move through many states. Use a clear, consistent status system (badges, timelines, progress) across author, reviewer, editor, and admin views.
4. **Protect anonymity** — never leak author identity into reviewer surfaces. Design the `MS-YYYY-####` identity treatment as a first-class element.
5. **Guest-friendly** — the no-login guest review flow must be legible and reassuring on its own.
6. **Themeable** — respect admin-set primary/secondary colors, logo, and favicon from Site Settings.
7. **Document-centric** — uploading, versioning, and downloading Word/PDF documents is the main mechanic; make file states and versions obvious.
8. **Responsive & accessible** — works on desktop (staff workflows) and mobile (authors/readers checking status). Meet contrast/accessibility norms expected of a public institution.

---

## 6. Technical constraints for design

- **Server-rendered Django templates** (Bootstrap 5 currently). Prefer a system implementable with CSS + light JS; avoid designs that assume a full SPA.
- Rich text comes from a WYSIWYG editor (CKEditor) — abstracts, bios, and article content are HTML.
- Brand seed: **University of Jos**. Default colors today are a blue primary / pink-magenta secondary, but these are admin-configurable — design a palette system, not a single hardcoded look.
- Icons: currently Font Awesome + Material Icons. Typeface: Poppins.

---

## 7. One-line summary

> A University of Jos platform where authors submit manuscripts, experts peer-review them anonymously, editors manage the pipeline, and accepted work is published into searchable online journals with a public archive.
