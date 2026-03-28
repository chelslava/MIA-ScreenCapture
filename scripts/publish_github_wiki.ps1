param(
    [string]$Repo = "chelslava/MIA-ScreenCapture"
)

$wikiUrl = "https://github.com/$Repo.wiki.git"
$src = Join-Path $PSScriptRoot "..\docs\wiki"
$dst = Join-Path $PSScriptRoot "..\wiki_repo"

if (Test-Path $dst) {
    Remove-Item -LiteralPath $dst -Recurse -Force
}

try {
    git clone $wikiUrl $dst
} catch {
    Write-Error "Не удалось клонировать wiki. Сначала откройте вкладку Wiki в GitHub и создайте первую страницу (Home)."
    throw
}

Copy-Item "$src\*.md" $dst -Force

Push-Location $dst
try {
    git add .
    git diff --cached --quiet
    if ($LASTEXITCODE -ne 0) {
        git commit -m "Обновить wiki документацию"
        git push origin master
    } else {
        Write-Host "Изменений нет"
    }
} finally {
    Pop-Location
}
