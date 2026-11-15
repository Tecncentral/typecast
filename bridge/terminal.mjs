#!/usr/bin/env node
// Terminal chat with the same logic as the phone line. Start the API first, then: node bridge/terminal.mjs
import readline from "node:readline";
import { handle } from "./core.mjs";

const show = (p) => console.log(p.image ? `   [image] ${p.image}` : `\n${p.text}`);
const rl = readline.createInterface({ input: process.stdin });
console.log("Typecast (terminal). Type a scene. Ctrl+C to quit.");
process.stdout.write("\nyou> ");
for await (const line of rl) {
  const parts = await handle("terminal", line, { say: async (t) => console.log(`\n${t}`) });
  parts.forEach(show);
  process.stdout.write("\nyou> ");
}
