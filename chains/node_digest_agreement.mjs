// Holds UAI-2's Node implementation of the CNS subject digest (interop/node/uai.mjs, written without CNS code) to
// contracts/digest-vectors.json, through its own strict reader. Node implements the restricted_v1 profile
// (contracts/DIGEST.md section 4) with UAI-1's own limits: a vector flagged restricted_v1 must read, render and digest
// exactly as the file says, and every other vector must be refused (by strictParse, checkProfile or canonical) or, where
// UAI-1's limit is wider (depth 32 against restricted_v1's 31), digest the same. A different digest is never allowed.
//
// Run it through chains/node_digest_agreement.py, which hands each vector's content as the JSON text Python writes
// (so 1.0 stays a float token, which JSON.parse would turn into 1). Input: one JSON object per line with
// name, restricted_v1, rendering, digest and text. Exit 0 when the rule holds, 1 when it does not, 2 when the inputs
// cannot be read.
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

let uai, rows;
try {
  uai = await import(pathToFileURL(process.argv[2]).href);
  rows = readFileSync(process.argv[3], "utf8").split("\n").filter(Boolean).map((line) => JSON.parse(line));
} catch (e) {
  console.log(`node_digest_agreement: cannot read the inputs: ${e.message}`);
  process.exit(2);
}
let agree = 0, refusedOutside = 0, sameOutside = 0;
const problems = [];
for (const v of rows) {
  let rendering, digest, refused = null;
  try {
    const content = uai.strictParse(v.text);
    uai.checkProfile(content);
    rendering = uai.canonical(content);
    digest = uai.digest(content);
  } catch (e) {
    refused = e.message;
  }
  if (v.restricted_v1) {
    if (refused !== null) problems.push(`${v.name}: in the profile but refused (${refused})`);
    else if (rendering !== v.rendering || digest !== v.digest) problems.push(`${v.name}: rendered ${rendering}`);
    else agree++;
  } else if (refused === null && digest !== v.digest) {
    problems.push(`${v.name}: outside the profile and digested differently (${rendering})`);
  } else if (refused === null) {
    sameOutside++;  // outside restricted_v1 but inside UAI-1's own limits (depth 32): the same digest is no conflict
  } else {
    refusedOutside++;
  }
}
for (const p of problems) console.log(`node_digest_agreement: ${p}`);
console.log(`node_digest_agreement: ${agree} vectors agree, ${refusedOutside} outside the profile refused, ${sameOutside} outside it digested alike, ${problems.length} problems`);
process.exit(problems.length === 0 && agree > 0 ? 0 : 1);
