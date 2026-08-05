param(
  [Parameter(Mandatory=$true)]
  [string]$ProjectSlug,

  [string]$Date = (Get-Date -Format "yyyy-MM-dd"),

  # Run root outside the repo. Defaults to $repoRoot\local_runs so behavior is
  # unchanged for legacy usage. Passing an external path keeps project artifacts
  # physically out of the framework git repo (recommended to avoid committing
  # client data back to the shared repo).
  [string]$RunRoot
)

$ErrorActionPreference = "Stop"

if ($ProjectSlug -notmatch '^[a-z0-9]+(-[a-z0-9]+)*$') {
  throw "ProjectSlug must use lowercase letters, numbers, and hyphens only. Example: lonely-robot-rainy-city"
}

$repoRoot = Split-Path -Parent $PSScriptRoot
if ($RunRoot) {
  $runsBase = $RunRoot
} else {
  $runsBase = Join-Path $repoRoot "local_runs"
}
$runRoot = Join-Path $runsBase "$Date\$ProjectSlug"
$createdAt = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$resolvedRunRoot = [System.IO.Path]::GetFullPath($runRoot)

$dirs = @(
  "inputs",
  "outputs",
  "outputs\assets",
  "outputs\assets\characters",
  "outputs\assets\characters\prompts",
  "outputs\assets\characters\images",
  "outputs\assets\scenes",
  "outputs\assets\scenes\prompts",
  "outputs\assets\scenes\images",
  "outputs\assets\props",
  "outputs\assets\props\prompts",
  "outputs\assets\props\images",
  "outputs\storyboard_boards",
  "outputs\storyboard_board_inputs",
  "outputs\video_prompts",
  "outputs\video_generation",
  "outputs\final_packages",
  "outputs\versions",
  "outputs\reviews",
  "outputs\imports",
  "references",
  "logs"
)

foreach ($dir in $dirs) {
  New-Item -ItemType Directory -Force -Path (Join-Path $runRoot $dir) | Out-Null
}

Copy-Item -LiteralPath (Join-Path $repoRoot "inputs\idea_brief.template.md") -Destination (Join-Path $runRoot "inputs\idea_brief.md") -Force

# Prefer `python` on PATH; fall back to the Windows `py` launcher so the script
# works on machines that only expose `py`.
if (Get-Command python -ErrorAction SilentlyContinue) {
  $Python = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
  $Python = "py"
} else {
  throw "Python is required. Install Python 3 and ensure 'python' or 'py' is on PATH."
}

$checkpointScript = Join-Path $repoRoot "scripts\init_checkpoint.py"
$checkpointTemplate = Join-Path $repoRoot "checkpoint.template.json"
$checkpointOutput = Join-Path $runRoot "checkpoint.json"
& $Python $checkpointScript --template $checkpointTemplate --output $checkpointOutput --slug $ProjectSlug --created-at $createdAt --run-dir ($resolvedRunRoot -replace '\\', '/')
if ($LASTEXITCODE -ne 0) { throw "Checkpoint initialization failed" }

Copy-Item -LiteralPath (Join-Path $repoRoot "docs\local_run_template.md") -Destination (Join-Path $runRoot "notes.md") -Force

$requiredFiles = @(
  "inputs\idea_brief.md",
  "checkpoint.json",
  "notes.md"
)

foreach ($file in $requiredFiles) {
  $path = Join-Path $runRoot $file
  if (-not (Test-Path -LiteralPath $path)) {
    throw "Initialization failed. Required file missing: $path"
  }
}

Write-Output "Created local run: $runRoot"
Write-Output ""
Write-Output "IMPORTANT: project artifacts under $runRoot are client data. They must"
Write-Output "never be committed to the framework repo. If this run lives inside the"
Write-Output "repo (local_runs/), it is ignored by .gitignore only while untracked;"
Write-Output "do NOT 'git add' any of it. For a clean separation, re-run with"
Write-Output "-RunRoot pointing outside the repo, e.g.:"
Write-Output "  powershell -File scripts/init_local_run.ps1 -ProjectSlug $ProjectSlug -RunRoot D:\client-projects"
