// A stand-in for UAI-2's uai.mjs that reads like it and digests wrongly. The chains workflow runs
// chains/node_digest_agreement.py against it and requires exit 1, so a checker that passes everything is caught.
export function strictParse(text) { return JSON.parse(text); }
export function checkProfile() {}
export function canonical() { return "x"; }
export const digest = () => "0".repeat(64);
