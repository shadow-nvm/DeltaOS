param(
    [Alias('Profile')]
    [ValidateSet('core', 'full')]
    [string]$DeltaProfile = 'core',
    [switch]$RefreshPackages,
    [switch]$Clean
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$workDir = Join-Path $repo 'build\work'
New-Item -ItemType Directory -Force -Path $workDir | Out-Null
$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerCommand) {
    throw 'Docker CLI was not found. Install Docker Desktop, switch it to Linux containers, and start it.'
}

$engineOs = & docker info --format '{{.OSType}}'
if ($LASTEXITCODE -ne 0) {
    throw 'Docker Desktop is not running. Start it, then run this script again.'
}
if ($engineOs.Trim() -ne 'linux') {
    throw 'DeltaOS requires Docker Desktop in Linux container mode.'
}

Write-Host 'Building the DeltaOS ISO builder image...'
& docker build --tag deltaos-builder (Join-Path $repo 'build')
if ($LASTEXITCODE -ne 0) { throw 'Could not build the DeltaOS builder image.' }

$dockerArgs = @(
    'run', '--rm', '--privileged',
    '--volume', "${repo}:/work",
    '--volume', 'deltaos-deltaos-build-work:/work/build/work',
    '--workdir', '/work',
    'deltaos-builder',
    'bash', './build/build-iso.sh', $DeltaProfile
)
if ($RefreshPackages) { $dockerArgs += '--refresh-packages' }
if ($Clean) { $dockerArgs += '--clean' }

Write-Host "Building DeltaOS ($DeltaProfile profile); this may take a while..."
& docker @dockerArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Recent build log output:'
    $logArgs = @(
        'run', '--rm',
        '--volume', 'deltaos-deltaos-build-work:/work/build/work',
        '--entrypoint', 'sh', 'deltaos-builder', '-lc',
        'if [ -f /work/build/work/build.log ]; then tail -n 80 /work/build/work/build.log; else echo "No build log was created."; fi'
    )
    & docker @logArgs
    throw 'DeltaOS build failed. Review the error above and the build output.'
}

Write-Host "Finished. ISO files are in $(Join-Path $repo 'build\output')."
