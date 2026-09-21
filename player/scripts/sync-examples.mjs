// Mirrors the repo's .twk examples into player/public/data so the preset
// dropdown in index.html (/data/geography.twk, /data/shards/...) resolves.
//
// Cross-platform replacement for the old `mkdir -p && cp -f` postinstall,
// which is POSIX-only and fails under npm's default cmd.exe shell on Windows.

import { cp, mkdir, readdir } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const playerRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const examplesRoot = resolve(playerRoot, '..', 'examples');
const dataRoot = join(playerRoot, 'public', 'data');

/**
 * Copy every *.twk file from one directory into another (non-recursive).
 * @param {string} fromDir
 * @param {string} toDir
 * @returns {Promise<number>} number of files copied
 */
async function copyTwk(fromDir, toDir) {
  await mkdir(toDir, { recursive: true });
  const entries = await readdir(fromDir, { withFileTypes: true });
  let copied = 0;
  for (const entry of entries) {
    if (!entry.isFile() || !entry.name.endsWith('.twk')) continue;
    await cp(join(fromDir, entry.name), join(toDir, entry.name));
    copied += 1;
  }
  return copied;
}

const documents = await copyTwk(examplesRoot, dataRoot);
const shards = await copyTwk(join(examplesRoot, 'shards'), join(dataRoot, 'shards'));

console.log(`sync-examples: ${documents} document(s), ${shards} shard(s) -> ${dataRoot}`);
