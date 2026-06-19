# Multi-Modal Evidence Review

The domain language for a system that verifies damage claims (car / laptop / package) from a
claim transcript, submitted images, user history, and a minimum-evidence rulebook. This file is a
glossary only — no implementation details.

## Language

**Claim**:
A single damage report about one object (`car`, `laptop`, or `package`), consisting of a chat
transcript plus one or more submitted images. One row of `claims.csv` is one Claim.
_Avoid_: case, ticket, request

**Asserted Damage**:
The specific damage the customer is claiming, as extracted from the transcript (object part +
issue type). Distinct from what the images actually show.
_Avoid_: reported issue, complaint

**Issue Type**:
The damage type *observed in the image* (`dent`, `scratch`, `crack`, `broken_part`, …) — not the
type asserted in the transcript. `none` when the relevant part is visible and no issue is present;
`unknown` when the issue cannot be determined. Output field `issue_type`.
_Avoid_: claimed issue, reported damage type

**Object Part**:
The part of the object the decision is about, named from the *observed image* using that object's
allowed part vocabulary; `unknown` when the part cannot be determined. Distinct from the part named
in the Asserted Damage. Output field `object_part`.
_Avoid_: claimed part, affected part

**Evidence Standard Met**:
Whether the submitted image set is *sufficient to evaluate* the Claim. A gate on evidence
sufficiency — not a verdict on the Claim. Output field `evidence_standard_met`.
_Avoid_: evidence passed, evidence valid, sufficient

**Claim Status**:
The verdict on the Claim: `supported`, `contradicted`, or `not_enough_information`. The outcome of
evaluation, distinct from Evidence Standard Met which is its precondition.
_Avoid_: decision, result, outcome

**Not Enough Information**:
The Claim Status value meaning no verdict could be reached. Required whenever Evidence Standard
Met is false; may also occur when evidence is sufficient but the images remain visually
inconclusive. The relationship is one-way: `evidence_standard_met = false` ⟹ this status, but this
status does **not** imply `evidence_standard_met = false`.
_Avoid_: inconclusive, unknown, NEI

**Valid Image**:
Whether the image set can be **trusted for an automated decision without a human reviewer**. A
trust/authenticity axis, orthogonal to Evidence Standard Met (a visibility/sufficiency axis): an
image can be visually sufficient to reach a verdict yet still be `valid_image = false` if it looks
non-original, manipulated, or carries embedded text instructions — anything that routes it to
manual review. Output field `valid_image`.
_Avoid_: good image, clear image, readable image, usable image

**Supporting Image**:
The image ID(s) that support the *decision reached* — not the claim. For a `supported` verdict,
the image(s) showing the claimed damage; for `contradicted`, the image(s) showing the
contradicting reality; `none` when no image is sufficient (e.g. Not Enough Information). Report the
**minimal sufficient set**, not every relevant image. Output field `supporting_image_ids`.
_Avoid_: proof image, claim image, all relevant images

**Severity**:
The extent of the damage *observed in the image* — `none` (nothing wrong), `low` / `medium` /
`high` (by visible seriousness), or `unknown` (cannot determine). Part of the observed-reality
cluster with Issue Type and Object Part; independent of Claim Status — a `contradicted` claim can
still be `high` if the image shows severe but unclaimed damage. Output field `severity`.
_Avoid_: claimed damage level, impact, priority

**Risk Flag**:
A quality, trust, or history concern attached to a Claim (e.g. blurry image, claim mismatch, user
history risk). Adds context and may route to manual review, but never changes Claim Status by
itself. Output field `risk_flags`.
_Avoid_: warning, error, alert

**User History Risk**:
A Risk Flag derived from the claimant's past-claim record. Can flag a Claim for scrutiny but, per
the problem statement, must not override clear visual evidence in deciding Claim Status.
_Avoid_: fraud score, trust score

**Manual Review Required**:
A Risk Flag meaning a human agent must look at the Claim before it is finalized. Fires on a hybrid
trigger: any `contradicted` verdict, OR any trust/history concern (User History Risk,
`non_original_image`, `possible_manipulation`, `text_instruction_present`, `wrong_object`) — even on
a `supported` Claim. A plain image-quality Not Enough Information (e.g. `wrong_angle`, "reshoot it")
does not trigger it. Output flag `manual_review_required`.
_Avoid_: needs review, escalate, human-in-the-loop

**Claim Mismatch**:
A Risk Flag meaning the image shows evidence that *conflicts* with the claim — wrong part, wrong
damage type, wrong object, or wrong severity. A contradiction-only signal (`wrong_object` /
`wrong_object_part` are specific kinds that co-occur). Distinct from Damage Not Visible. Output
flag `claim_mismatch`.
_Avoid_: false claim, wrong claim

**Damage Not Visible**:
A Risk Flag meaning the claimed part is visible but shows no damage — the claimed issue simply is
not there. Drives a `contradicted` verdict *by absence*, as opposed to Claim Mismatch's *conflict*.
Output flag `damage_not_visible`.
_Avoid_: no damage, undamaged
