// agent.mjs: a standalone UAI-1 agent in Node, speaking JSON Lines on stdin and stdout.
//
//   node agent.mjs decider     prints its manifest, then answers each envelope it reads with one line
//   node agent.mjs requester   reads a decider's manifest, then runs one request to a verified decision
//
// Configuration comes from the environment, so keys do not appear in a process listing:
//   UAI_SEED   this agent's 32-byte Ed25519 seed, hex (a real deployment would read it from a keystore)
//   UAI_TRUST  comma-separated identities this agent pins; it deals with no one else
//   UAI_DOC    requester only: {"identity": ..., "values": {...}, "offer": [...], "evidence": [...]}
//
// Every stdout line is one JSON object: an envelope, {"uai_error": {code, reason}}, {"uai_ok": ...} or
// {"uai_result": ...}. One line in, one line out, so a peer can drive it over a plain pipe.
//
// Its policy is its own and is not the Python reference's: it screens income against 450000 cents a month and only
// for a paystub or a tax return, and it will not take any field it does not need.

import { createInterface } from "node:readline";
import * as U from "./uai.mjs";

const role = process.argv[2];
const me = U.signerFromSeed(Buffer.from(process.env.UAI_SEED || "", "hex"));
const trust = new U.PinnedTrust((process.env.UAI_TRUST || "").split(",").filter(Boolean));
const ledger = new U.Ledger();
const TTL = 60000;
const out = (obj) => process.stdout.write(JSON.stringify(obj) + "\n");
const fail = (e) => out({ uai_error: { code: e.code || "internal", reason: e.reason || String(e.message || e) } });

const CAP = {
  name: "income-screen", version: 1, summary: "monthly income at or above 450000 cents, from a paystub or tax return",
  accepts: ["doc_type", "monthly_income_cents"], requires: ["doc_type", "monthly_income_cents"],
  evidence: ["threshold-check"], max_ttl_ms: 120000,
};

function judge(seen) {
  const okDoc = ["paystub", "tax-return"].includes(seen.doc_type);
  const ok = okDoc && Number.isSafeInteger(seen.monthly_income_cents) && seen.monthly_income_cents >= 450000;
  if (ok) return { verdict: "pass", reasons: ["income meets 450000 from an accepted document"], evidence: { "threshold-check": { threshold_cents: 450000, observed_cents: seen.monthly_income_cents, doc_type: seen.doc_type } } };
  return { verdict: "retry", reasons: [okDoc ? `income ${seen.monthly_income_cents} is below 450000` : `a ${seen.doc_type} is not an accepted document`], evidence: {} };
}

function decider() {
  const offers = new Map(); // offer digest -> { terms, expiresAt }
  out(U.publish(me, "node-screener", "node/uai.mjs (OpenSSL Ed25519)", [CAP]));
  const refuse = (env, e) => U.seal(me, "refuse", { code: e.code, reasons: [e.reason] }, { to: env.from, replyTo: env, ttlMs: TTL });
  return (line) => {
    const wire = U.strictParse(line);
    if (wire.kind === "manifest") { U.readManifest(wire, { trust }); return out({ uai_ok: "manifest read" }); }
    const env = U.openEnvelope(wire, { audience: me.agent, kinds: new Set(["request", "accept"]) });
    if (env.expires_at === null) throw new U.Refused("malformed", "session messages must expire");
    if (env.expires_at - env.issued_at > 86400000) throw new U.Refused("malformed", "a session message may live at most 24 hours");
    try { trust.admit(env.from); } catch (e) { ledger.spend(env.from, env.id); return out(refuse(env, e)); }
    if (env.kind === "request") {
      if (env.in_reply_to) throw new U.Refused("malformed", "a request answers nothing");
      ledger.spend(env.from, env.id);
      let terms;
      try { terms = U.proposeTerms(CAP, env.body, { decider: me.agent, requester: env.from }); } catch (e) { return out(refuse(env, e)); }
      const offer = U.seal(me, "offer", { terms }, { to: env.from, replyTo: env, ttlMs: TTL });
      const now = Date.now();
      for (const [k, v] of offers) if (now >= v.expiresAt) offers.delete(k); // forget lapsed offers
      offers.set(U.envelopeDigest(offer), { terms, expiresAt: offer.expires_at });
      return out(offer);
    }
    const open = offers.get(env.in_reply_to);
    if (!open) throw new U.Refused("terms", "the accept answers no offer this decider has open");
    if (Date.now() >= open.expiresAt) { offers.delete(env.in_reply_to); throw new U.Refused("expired", "the offer this accept answers has lapsed"); }
    const terms = open.terms;
    if (env.from !== terms.requester) throw new U.Refused("terms", "the accept comes from someone the offer was not made to");
    ledger.spend(env.from, env.id);
    offers.delete(env.in_reply_to);
    let seen;
    try {
      if (Object.keys(env.body).sort().join() !== "disclosure,terms_digest") throw new U.Refused("terms", "an accept is exactly terms_digest and disclosure");
      if (env.body.terms_digest !== U.termsDigest(terms)) throw new U.Refused("terms", "the accept does not agree to the terms offered");
      if (terms.disclose.length) seen = U.openDisclosure(terms.subject.digest, env.body.disclosure, terms.disclose);
      else if (env.body.disclosure !== null) throw new U.Refused("disclosure", "the terms disclose nothing, so the accept's disclosure must be null");
      else seen = {};
    } catch (e) { return out(refuse(env, e)); }
    const j = judge(seen);
    return out(U.issueDecision(me, env, terms, j.verdict, { reasons: j.reasons, evidence: j.verdict === "pass" ? j.evidence : {} }));
  };
}

function requester() {
  const doc = JSON.parse(process.env.UAI_DOC || "{}");
  const document = U.commit(doc.identity, doc.values);
  let decider = null, request = null, req = null, accept = null, terms = null;
  return (line) => {
    const wire = U.strictParse(line);
    if (!decider) {
      decider = U.readManifest(wire, { trust }).from;
      req = U.requestBody("income-screen", 1, { identity: document.identity, digest: document.digest, offerFields: doc.offer, requireEvidence: doc.evidence, maxTtlMs: 600000 });
      request = U.seal(me, "request", req, { to: decider, ttlMs: TTL });
      return out(request);
    }
    if (!accept) {
      const env = U.openEnvelope(wire, { audience: me.agent, kinds: new Set(["offer", "refuse"]) });
      if (env.from !== decider || env.in_reply_to !== U.envelopeDigest(request)) throw new U.Refused("terms", "a reply to something this requester did not send");
      ledger.spend(env.from, env.id);
      if (env.kind === "refuse") return out({ uai_result: { declined: env.body.reasons } });
      terms = U.checkTerms(env.body.terms, req, { decider, requester: me.agent });
      accept = U.seal(me, "accept", { terms_digest: U.termsDigest(terms), disclosure: terms.disclose.length ? document.reveal(terms.disclose) : null }, { to: decider, replyTo: env, ttlMs: TTL });
      return out(accept);
    }
    const got = U.verifyDecision(wire, { terms, acceptDigest: U.envelopeDigest(accept), ledger });
    return out({ uai_result: { verified_by: "node/uai.mjs", verdict: got.verdict, allowed: got.allowed, reasons: got.reasons, evidence: got.evidence, cns_root: got.cnsRoot, signer: got.envelope.from, disclosed: terms.disclose } });
  };
}

if (role !== "decider" && role !== "requester") { console.error("usage: node agent.mjs decider|requester"); process.exit(2); }
const handle = role === "decider" ? decider() : requester();
const rl = createInterface({ input: process.stdin, crlfDelay: Infinity });
rl.on("line", (line) => { if (!line.trim()) return; try { handle(line); } catch (e) { fail(e); } });
