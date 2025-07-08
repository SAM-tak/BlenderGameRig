Add-Type -AssemblyName System.IO.Compression.FileSystem

$sourceFolder = ".\gamerig"
$zipPath = "gamerig.zip"

# 除外パターン（ワイルドカード）
$excludePatterns = @("*__pycache__*", "*.vscode*", "desktop.ini")

# 古い zip を削除
if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}

# 一時フォルダに除外済みファイル群をコピー
$tempFolder = "$env:TEMP\gamerig_temp"
Remove-Item $tempFolder -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item $sourceFolder $tempFolder -Recurse

# 除外対象を削除
Get-ChildItem -Path $tempFolder -Recurse | Where-Object {
    foreach ($pattern in $excludePatterns) {
        if ($_ -like $pattern) { return $true }
    }
    return $false
} | Remove-Item -Force -Recurse

# zip を作成
[System.IO.Compression.ZipFile]::CreateFromDirectory($tempFolder, $zipPath)

# 後始末
Remove-Item $tempFolder -Recurse -Force
