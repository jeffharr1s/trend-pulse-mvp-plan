#!/usr/bin/env node
// Bumps the version, commits it, and pushes to GitHub — the one step that
// counts as "uploading a revision". Run via `npm run release`.
//
// Version scheme: MAJOR.MINOR.0 (patch stays 0). Default bump is MINOR.
// Bumps MAJOR instead (and resets minor to 0) when either:
//   - a commit message since the last push contains a trigger word
//     (major, breaking, rewrite, replace), or
//   - the diff since the last push touches a "major surface" file
//     (vercel.json, package.json, requirements.txt)
import { execSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';

const sh = (cmd) => execSync(cmd, { encoding: 'utf8' }).trim();

const branch = sh('git rev-parse --abbrev-ref HEAD');
const upstream = `origin/${branch}`;

let hasUpstream = true;
try {
  sh(`git rev-parse ${upstream}`);
} catch {
  hasUpstream = false;
}

const range = hasUpstream ? `${upstream}..HEAD` : 'HEAD';

const pendingCommits = sh(`git log ${range} --format=%B`).trim();
const changedFiles = sh(`git diff --name-only ${hasUpstream ? upstream : ''} HEAD 2>/dev/null || true`)
  .split('\n')
  .filter(Boolean);

if (!pendingCommits && changedFiles.length === 0) {
  console.log('Nothing new to release — no commits ahead of ' + upstream + '.');
  process.exit(0);
}

const MAJOR_TRIGGER_WORDS = /\b(major|breaking|rewrite|replace)\b/i;
const MAJOR_SURFACE_FILES = new Set(['vercel.json', 'package.json', 'requirements.txt']);

const isMajor =
  MAJOR_TRIGGER_WORDS.test(pendingCommits) ||
  changedFiles.some((f) => MAJOR_SURFACE_FILES.has(f));

const pkgPath = new URL('../package.json', import.meta.url);
const pkg = JSON.parse(readFileSync(pkgPath, 'utf8'));
const [majorNum, minorNum] = pkg.version.split('.').map(Number);

const newVersion = isMajor ? `${majorNum + 1}.0.0` : `${majorNum}.${minorNum + 1}.0`;

pkg.version = newVersion;
writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + '\n');

sh(`git add package.json`);
sh(`git commit -m "chore: bump version to ${newVersion}"`);

console.log(
  `Version bumped: ${pkg.version === newVersion ? `${majorNum}.${minorNum}.0` : pkg.version} -> ${newVersion} (${isMajor ? 'MAJOR' : 'minor'})`
);

console.log(`Pushing ${branch} to origin...`);
console.log(execSync(`git push origin ${branch}`, { encoding: 'utf8' }));
