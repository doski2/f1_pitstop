param(
  [string]$Target = 'master',
  [string[]]$Exclude = @(),
  [switch]$Offline
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Asegurar exclusiones
if ($Exclude -notcontains $Target) { $Exclude += $Target }

function Assert-GitRepo {
  try {
    git rev-parse --is-inside-work-tree | Out-Null
  } catch {
    throw 'No parece un repositorio Git. Ejecuta dentro de la carpeta del repo.'
  }
}

function Set-Branch([string]$branch) {
  if (-not (git show-ref --verify --quiet ("refs/heads/" + $branch))) {
    if (git show-ref --verify --quiet ("refs/remotes/origin/" + $branch)) {
      git checkout -b $branch "origin/$branch" | Out-Null
    } else {
      throw "La rama '$branch' no existe ni local ni en origin."
    }
  } else {
    git checkout $branch | Out-Null
    if (-not $Offline) { git pull --ff-only | Out-Null } else { Write-Host 'Modo offline: omitiendo pull.' }
  }
}

function Update-RemoteBranches([string]$target) {
  $remotes = git branch -r --format "%(refname:short)" | Where-Object { $_ -notmatch 'origin/HEAD' -and $_ -ne "origin/$target" }
  foreach ($r in $remotes) {
    $local = $r -replace '^origin/',''
    if (-not (git show-ref --verify --quiet ("refs/heads/" + $local))) {
      git branch --track $local $r | Out-Null
    }
  }
}

function Merge-All([string]$target, [string[]]$exclude) {
  git checkout $target | Out-Null
  $branches = git branch --format "%(refname:short)" | Where-Object { $exclude -notcontains $_ }
  foreach ($b in $branches) {
    Write-Host "Integrando $b -> $target"
    git checkout $target | Out-Null
    git merge --ff-only $b | Out-Host
    if ($LASTEXITCODE -ne 0) {
      Write-Host 'No FF posible; intentando merge --no-ff'
      git merge --no-ff $b -m "Merge $b into $target" | Out-Host
      if ($LASTEXITCODE -ne 0) {
        Write-Host "Conflictos al integrar $b. Resuelve, luego: git add -A; git commit"
        throw "Conflictos pendientes con $b"
      }
    }
  }
}

function Show-DeletionPreview([string]$target, [string[]]$exclude) {
  Write-Host "`nRamas locales MERGED en $target (previa):"
  $script:mergedLocal = git branch --merged $target --format "%(refname:short)" | Where-Object { $exclude -notcontains $_ }
  $script:mergedLocal | ForEach-Object { Write-Host "  $_" }

  Write-Host "`nRamas remotas MERGED en origin/$target (previa):"
  $script:mergedRemote = git branch -r --merged origin/$target --format "%(refname:short)" | Where-Object { $_ -notmatch 'origin/HEAD' -and $_ -ne "origin/$target" }
  $script:mergedRemote | ForEach-Object { Write-Host "  $_" }
}



try {
  Assert-GitRepo
  if (-not $Offline) {
    Write-Host 'Fetching remotos...'
    try { git fetch --all --prune | Out-Null } catch { Write-Warning "No se pudo hacer fetch (modo offline). Continuando..." }
  } else {
    Write-Host 'Modo offline: omitiendo fetch de remotos.'
  }

  Set-Branch -branch $Target

  $tag = "backup/pre-merge-{0:yyyyMMdd-HHmm}" -f (Get-Date)
  git tag $tag

  if (-not $Offline) { Update-RemoteBranches -target $Target } else { Write-Host 'Modo offline: no se crean ramas de seguimiento remoto.' }
  Merge-All -target $Target -exclude $Exclude

  if (-not $Offline) {
    try { git push origin $Target --follow-tags } catch { Write-Warning 'No se pudo hacer push (modo offline). Continúa localmente.' }
  } else {
    Write-Host 'Modo offline: omitiendo push a remoto.'
  }

  Show-DeletionPreview -target $Target -exclude $Exclude
  $ans = Read-Host '¿Eliminar ramas anteriores integradas? (y/N)'
  if ($ans -match '^[Yy]') {
    foreach ($b in $script:mergedLocal) { git branch -d $b }
    if (-not $Offline) {
      foreach ($r in $script:mergedRemote) { $bn = $r -replace '^origin/',''; git push origin --delete $bn }
    } else {
      Write-Host 'Modo offline: no se borran ramas remotas.'
    }
  }

  Write-Host 'Listo ✅'
} catch {
  Write-Error $_
  exit 1
}
