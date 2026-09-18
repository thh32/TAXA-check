'use strict';

const REPOSITORY_RAW = 'https://raw.githubusercontent.com/thh32/TAXA-check/main/';
const MANIFEST_URL = REPOSITORY_RAW + 'database/latest.json';
const ALLOWED_PREFIX = REPOSITORY_RAW;
const KEYS = {
  names: 'taxacheckRemoteNames',
  epithets: 'taxacheckRemoteEpithets',
  metadata: 'taxacheckRemoteMetadata',
  version: 'taxacheckRemoteDatabaseVersion',
  installedAt: 'taxacheckRemoteDatabaseInstalledAt',
  lastChecked: 'taxacheckDatabaseLastChecked'
};

function versionParts(value) {
  return String(value || '').split(/[^0-9]+/).filter(Boolean).map(Number);
}
function compareVersions(left, right) {
  const a = versionParts(left), b = versionParts(right);
  for (let i = 0; i < Math.max(a.length, b.length); i += 1) {
    const difference = (a[i] || 0) - (b[i] || 0);
    if (difference) return difference;
  }
  return 0;
}
async function fetchJson(url) {
  if (!url.startsWith(ALLOWED_PREFIX)) throw new Error('Update URL is outside the TAXA-check repository.');
  const response = await fetch(url, {cache: 'no-store', redirect: 'follow'});
  if (!response.ok) throw new Error(`Download failed: HTTP ${response.status}`);
  return response.json();
}
async function digestText(value) {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(digest)].map(byte => byte.toString(16).padStart(2, '0')).join('');
}
function validateManifest(value) {
  if (!value || value.schema_version !== 1 || !value.database_version) throw new Error('Invalid update manifest.');
  for (const item of ['names', 'epithets', 'metadata']) {
    const url = value[`${item}_url`];
    if (!url || !url.startsWith(ALLOWED_PREFIX)) throw new Error(`Invalid ${item} URL.`);
  }
}
function validateDatabase(names, epithets, metadata) {
  if (!names || typeof names !== 'object' || Array.isArray(names)) throw new Error('Invalid names database.');
  if (!epithets || typeof epithets !== 'object' || Array.isArray(epithets)) throw new Error('Invalid epithet database.');
  if (!metadata || typeof metadata !== 'object' || Array.isArray(metadata)) throw new Error('Invalid metadata database.');
  for (const required of ['escherichia coli', 'firmicutes', 'proteobacteria']) {
    if (!names[required]) throw new Error(`Validation name missing: ${required}`);
  }
}
async function bundledMetadata() {
  try {
    const response = await fetch(chrome.runtime.getURL('generated/metadata.json'));
    return response.ok ? response.json() : {};
  } catch (_) {
    return {};
  }
}
async function installedStatus() {
  const stored = await chrome.storage.local.get(Object.values(KEYS));
  const bundled = await bundledMetadata();
  return {
    installedVersion: stored[KEYS.version] || bundled.database_version || bundled.built_at || 'bundled',
    remoteInstalled: Boolean(stored[KEYS.version]),
    installedAt: stored[KEYS.installedAt] || null,
    lastChecked: stored[KEYS.lastChecked] || null
  };
}
async function checkUpdate() {
  const manifest = await fetchJson(MANIFEST_URL);
  validateManifest(manifest);
  const status = await installedStatus();
  const now = new Date().toISOString();
  await chrome.storage.local.set({[KEYS.lastChecked]: now});
  return {
    ...status,
    lastChecked: now,
    availableVersion: manifest.database_version,
    updateAvailable: status.installedVersion === 'bundled' || compareVersions(manifest.database_version, status.installedVersion) > 0,
    manifest
  };
}
async function installUpdate(manifest) {
  validateManifest(manifest);
  async function download(label, url) {
    if (!url.startsWith(ALLOWED_PREFIX)) throw new Error(`Invalid ${label} URL.`);
    const response = await fetch(url, {cache: 'no-store', redirect: 'follow'});
    if (!response.ok) throw new Error(`${label} download failed: HTTP ${response.status}`);
    const raw = await response.text();
    const expected = String(manifest[`${label}_sha256`] || '').toLowerCase();
    if (expected && await digestText(raw) !== expected) throw new Error(`${label} checksum mismatch.`);
    return JSON.parse(raw);
  }
  const [names, epithets, metadata] = await Promise.all([
    download('names', manifest.names_url),
    download('epithets', manifest.epithets_url),
    download('metadata', manifest.metadata_url)
  ]);
  validateDatabase(names, epithets, metadata);
  const installedAt = new Date().toISOString();
  await chrome.storage.local.set({
    [KEYS.names]: names,
    [KEYS.epithets]: epithets,
    [KEYS.metadata]: {...metadata, database_version: manifest.database_version},
    [KEYS.version]: manifest.database_version,
    [KEYS.installedAt]: installedAt,
    [KEYS.lastChecked]: installedAt
  });
  return {installedVersion: manifest.database_version, installedAt};
}
async function restoreBundled() {
  await chrome.storage.local.remove([KEYS.names, KEYS.epithets, KEYS.metadata, KEYS.version, KEYS.installedAt]);
  return installedStatus();
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || !message.type?.startsWith('taxacheck-db-')) return false;
  (async () => {
    if (message.type === 'taxacheck-db-status') return installedStatus();
    if (message.type === 'taxacheck-db-check') return checkUpdate();
    if (message.type === 'taxacheck-db-install') return installUpdate(message.manifest);
    if (message.type === 'taxacheck-db-restore') return restoreBundled();
    throw new Error('Unknown database update operation.');
  })().then(result => sendResponse({ok: true, result})).catch(error => sendResponse({ok: false, error: error.message}));
  return true;
});
