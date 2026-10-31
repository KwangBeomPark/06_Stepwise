# SignTool / SimplySign troubleshooting

`The specified CSP could not be found` means the signing path could not resolve or use the requested cryptographic provider. It can involve a provider installation/load problem, a process architecture mismatch, or a stale certificate/key association. The wording alone does not establish which cause applies. A certificate in `CurrentUser\My` with `HasPrivateKey=True` only records a key association; it does not prove that the provider can access the remote key or perform a signature.

## Read-only diagnosis

Run in the same Windows account and interactive PowerShell session used for signing:

```powershell
Set-Location -LiteralPath 'C:\Dev\GitHub\06_Stepwise'
& .\scripts\sign.ps1 -Diagnose -CertificateThumbprint 'E9C72CF5090840A1805296525D56BE680622A7FD'
```

This prints the selected SignTool path, PE architecture and product version, then runs native and x86 `certutil -silent -user -v -store My <thumbprint>` and `certutil -silent -csplist`. It does not sign, repair the store, build, or publish. Inspect the full output: `-store` can report a private-key verification failure while returning zero; `-csplist` can fail because of an unrelated provider such as Microsoft Pluton. Neither exit code alone establishes SimplySign health. Silent mode may itself prevent a key operation that requires interactive authentication.

Check the certificate's `Provider`, `ProviderType`, `Key Container` and `KeySpec`. ProviderType zero denotes a CNG KSP. Do not infer a legacy CSP simply from SignTool's error text. A provider listed by `-csplist` is not proof of a working login, container association, or signing operation.

## Tool architecture and selection

Automatic discovery selects x64 by default and searches versioned Windows SDK installations first (newest version per installation root), then the repository copy, then PATH. It reads PE headers for automatic candidates. A DLL installed only for x86 cannot be loaded by an x64 process, or vice versa. The architecture of the EXE being signed does not determine the required SignTool architecture.

`-SignToolArchitecture x86` or `arm64` changes automatic discovery. `-SignToolPath` (or `SIGNTOOL_PATH`) is an explicit override and takes precedence; its actual architecture is printed. The host PowerShell architecture does not change the architecture of a separately launched SignTool. Keep the SDK tool with its installed dependencies; copying just an EXE may introduce a different loader/dependency failure. There are no automatic architecture retries that might repeat key access.

```powershell
& .\scripts\sign.ps1 -Diagnose -SignToolArchitecture x86 -CertificateThumbprint 'E9C72CF5090840A1805296525D56BE680622A7FD'
# Or specify the actual installed SDK path; substitute your installed version:
# -SignToolPath 'C:\Program Files (x86)\Windows Kits\10\bin\<version>\x64\signtool.exe'
```

## Recovery and verification

1. Open SimplySign Desktop under the same Windows user and connect using the user's mobile token/PIN. A running process alone does not establish an authenticated session. Retry diagnosis in that user's PowerShell; elevation is not a general fix and using another administrator account changes `CurrentUser`.
2. If the intended provider is absent, fails to load, or differs across architectures, repair/update the official SimplySign Desktop installation with the matching provider components. Reconnect and inspect the certificate association again. Do not copy/register arbitrary provider DLLs or disable Windows security policy.
3. If the association points to an unavailable provider/container, use the vendor's certificate registration workflow or support guidance. `certutil -user -repairstore My <thumbprint>` **changes** the store and may prompt/access the key; it is not a routine diagnostic command and is not run by this script. Do not delete/reimport certificates or guess container names to resolve this error.
4. `CurrentUser\My` is the intended store. SignTool uses `/s My /sha1 <thumbprint>` without `/sm`; adding `/sm` selects `LocalMachine` and will not repair the user certificate. `/csp` and `/kc` explicitly select a provider/container, typically with a public certificate file (`/f`). Do not hardcode `SimplySign CSP` when the association says `SimplySign KSP`. Only use explicit values established by the vendor/diagnostics; the normal script uses the certificate's stored association.
5. Once source changes are committed, run `scripts\build.ps1` to create a new tested clean build, then use its **new** BuildRoot with `scripts\sign.ps1 -BuildRoot ... -CertificateThumbprint ...`. An old build from the preceding commit is intentionally refused. Start without `-Publish` for local signing/verification. Actual signing can require user-controlled authentication.

Signing prints `/v /debug` details. On failure it stops before official promotion. App and installer signatures must be Valid, use the expected thumbprint, and include a timestamp. For an additional Authenticode check, run the selected tool's `verify /pa /all /v <signed-file>` and inspect `Get-AuthenticodeSignature`. Only a successful real signature and verification establish signability. Local verification does not establish installation success or GitHub publication; publication requires the separate `-Publish` option and existing matching remote tag.

## Observed on 2026-10-31

The repository SignTool was a Microsoft-signed x64 executable, product version `10.0.28000.2705`. The current user certificate pointed to `SimplySign KSP`, ProviderType `0`, KeySpec `1`. Both native and x86 provider lists included SimplySign CSP and KSP. Native `certutil -store` reported `Could not verify certificate public key against private key`. These findings do not establish a 32/64-bit mismatch or complete provider absence; key association, provider/session behavior remain candidates. No certificate repair or real signing was performed during this investigation.

References: [Microsoft SignTool options](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool), [Microsoft CRYPT_KEY_PROV_INFO](https://learn.microsoft.com/en-us/windows/win32/api/wincrypt/ns-wincrypt-crypt_key_prov_info), [Microsoft certutil](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/certutil), [Certum SimplySign installation](https://support.certum.eu/en/installation-of-the-simplysign-applications/).
