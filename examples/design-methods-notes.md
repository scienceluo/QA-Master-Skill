# Illustrative design model and oracles

This is fictional training input, not a production requirement or an approved
baseline. No software is executed by generating the associated cases.

The example intentionally links all reference IDs to this local document.
The engine preserves the IDs and locators but does not read this document or
infer its meaning. A reviewer must verify that the structured model agrees with
the referenced specification before approving a baseline.

| Reference | Explicit example meaning |
| --- | --- |
| SRC-REQ | REQ-EXAMPLE covers the three independent models below. |
| SRC-RULE | Membership determines discount; region does not change this rule. |
| SRC-STATE | An order starts in draft and can be submitted once; submitted is terminal. |
| SRC-EFFECT | A valid submit changes the order from draft to submitted once. |
| OR-VALID | Amount on the 0.01 grid and in [0.01, 100) is accepted. |
| OR-INVALID | Amount outside that interval is rejected without creating an order. |
| OR-DISCOUNT | A member receives the discount outcome, with no rate inferred. |
| OR-NORMAL | A nonmember receives the normal outcome. |
| OR-SUBMITTED | A draft order becomes submitted and the submission effect occurs once. |
| OR-DENY | An undeclared state/event pair is denied without changing state or applying a submission effect. |

`closed_world: true` is an explicit example assumption: every unlisted pair of
the declared states and triggers is denied. It is not inferred for other models.
The example does not define HTTP response codes, discount percentages, timing
targets, authentication, or remote-system behavior.
