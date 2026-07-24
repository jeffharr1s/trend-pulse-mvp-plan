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

// Deliberately narrower than "file X changed" — bumping npm scripts or
// reformatting vercel.json shouldn't count as a major/breaking change.
// Only the parts of these files that represent real architecture shifts do.
function dependenciesChanged() {
  if (!changedFiles.includes('requirements.txt')) return false;
  // requirements.txt is pure dependency list — any change is a dependency change.
  return true;
}

function packageDependenciesChanged() {
  if (!changedFiles.includes('package.json') || !hasUpstream) return false;
  const oldPkg = JSON.parse(sh(`git show ${upstream}:package.json`));
  const newPkg = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'));
  return (
    JSON.stringify(oldPkg.dependencies || {}) !== JSON.stringify(newPkg.dependencies || {}) ||
    JSON.stringify(oldPkg.devDependencies || {}) !== JSON.stringify(newPkg.devDependencies || {})
  );
}

function deployConfigChanged() {
  if (!changedFiles.includes('vercel.json') || !hasUpstream) return false;
  const oldCfg = JSON.parse(sh(`git show ${upstream}:vercel.json`));
  const newCfg = JSON.parse(readFileSync(new URL('../vercel.json', import.meta.url), 'utf8'));
  return JSON.stringify(oldCfg) !== JSON.stringify(newCfg);
}

const isMajor =
  MAJOR_TRIGGER_WORDS.test(pendingCommits) ||
  dependenciesChanged() ||
  packageDependenciesChanged() ||
  deployConfigChanged();

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
