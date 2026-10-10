# Release Audit: 06 Stepwise

- Audit date: 2026-10-10
- Source HEAD inspected: `49c7eca1fa6a6e580141029448b6573a84faa778`
- Review: Codex independent source review and isolated mock verification of the existing changes.
- Scope: release scripts and fixtures. No real signing, compilation, installation, GitHub mutation, commit, or push was performed.

## Findings and corrections

1. `Publish-GitHubRelease` now accepts exactly three distinct canonical asset names derived from the semantic-version tag:
   - `App06_Stepwise_Setup_v<version>.exe`
   - `build-manifest.v<version>.json`
   - `SHA256SUMS.v<version>.txt`
   Local files must exist before any remote operation. Historical files in the local `release/` directory remain preserved and are not selected for upload.
2. All GitHub operations explicitly target `KwangBeomPark/06_Stepwise`. A different origin and a remote tag pointing to a different source commit are rejected before upload.
3. New releases are created as drafts. Matching existing draft assets are downloaded and compared by SHA-256 before missing assets are uploaded. A public release, unexpected asset, missing upload state, or incomplete upload is rejected.
4. A discovered gap was corrected: an existing prerelease draft could previously become public before the final state check rejected it. Tag, actual Boolean draft state, and `prerelease=false` are now required before upload and again before publication.
5. Exact asset count, expected names, upload state, and downloaded hashes are checked before publication and after publication. An absent published release is checked before indexing the result under Strict Mode.

## Changed files

- `scripts/release_helpers.ps1`
- `tests/Test-ReleasePipeline.ps1`
- `RELEASE_AUDIT.md`

## Executed verification

Run from the project root with Windows PowerShell:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tests\Test-ReleasePipeline.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tests\Test-ReleaseOrchestration.ps1
```

- `Test-ReleasePipeline.ps1`: **67 assertions passed**, exit 0. Git and GitHub are mocked; fixture signatures are mocked.
- `Test-ReleaseOrchestration.ps1`: **16 assertions passed**, exit 0. The real local signing entry point runs only in a disposable fixture with fake certificate, signer, and compiler providers; publication is not requested.

The publication fixtures now use the actual three-file naming contract rather than two arbitrary historical filenames. They exercise matching-asset draft recovery, fresh draft creation, remote hash mismatch, additional assets, pending/missing upload state, missing or non-Boolean draft state, an existing public release, prerelease drafts, wrong origin, wrong tag commit, duplicate/two-file/wrong-version/wrong-name input, creation/upload failures, corrupted uploads, pending post-upload assets, and missing post-publication state. Failures before publication are checked to leave the draft unpublished.

These tests do not prove KSP private-key access, real Authenticode validity, a real network publication, or application/installer behavior.

## Remaining gates

- Source changes are uncommitted. Existing published releases and signed local artifacts were preserved; this audit does not request replacing them.
- For a future release: commit the reviewed source, choose a new version, rebuild with passing application tests, and sign through the user's interactive SimplySign session.
- Verify the actual expected-signer timestamped app and installer signatures and perform installation/upgrade acceptance. Existing processes must close correctly and user settings must remain intact.
- Publish only after those gates pass and the intended remote tag already points to the verified source commit. The actual `scripts/sign.ps1 -Publish` path remains unexecuted in this review.
- A failure after publication is reported for inspection; the script does not delete or replace public assets automatically.