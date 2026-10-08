param([string]$Endereco)
$ErrorActionPreference = 'Stop'
try {
    $configPacote = Join-Path $PSScriptRoot 'endereco.json'
    $pacote = $null
    if (Test-Path -LiteralPath $configPacote) {
        $pacote = Get-Content -LiteralPath $configPacote -Raw | ConvertFrom-Json
        if (-not $Endereco) { $Endereco = $pacote.endereco }
    }
    if (-not $Endereco) { $Endereco = Read-Host 'Endereco HTTPS do servidor (ex.: https://192.168.1.50:8765)' }
    $uri = $null
    if (-not [Uri]::TryCreate($Endereco, [UriKind]::Absolute, [ref]$uri) -or
        $uri.Scheme -ne 'https' -or $uri.UserInfo -or $uri.Query -or $uri.Fragment -or
        $uri.AbsolutePath -ne '/') {
        throw 'Informe o endereco HTTPS do servidor, sem chave ou senha no endereco.'
    }
    $Endereco = $uri.GetLeftPart([UriPartial]::Authority) + '/'
    $navegador = $null
    foreach ($nome in @('msedge.exe', 'chrome.exe')) {
        foreach ($registro in @('HKCU:', 'HKLM:')) {
            $item = Get-ItemProperty -LiteralPath "$registro\Software\Microsoft\Windows\CurrentVersion\App Paths\$nome" -ErrorAction SilentlyContinue
            if ($item -and (Test-Path -LiteralPath $item.'(default)')) { $navegador = $item.'(default)'; break }
        }
        if ($navegador) { break }
    }
    if (-not $navegador) {
        foreach ($base in @(${env:ProgramFiles(x86)}, $env:ProgramFiles, $env:LOCALAPPDATA)) {
            if (-not $base) { continue }
            foreach ($relativo in @('Microsoft\Edge\Application\msedge.exe', 'Google\Chrome\Application\chrome.exe')) {
                $candidato = Join-Path $base $relativo
                if (Test-Path -LiteralPath $candidato) { $navegador = $candidato; break }
            }
            if ($navegador) { break }
        }
    }
    if (-not $navegador) { throw 'Instale Chrome ou Edge neste PC e repita o instalador da interface.' }
    $certificado = Join-Path $PSScriptRoot 'dominio-rede.cer'
    if ($pacote -and $pacote.certificado_sha256) {
        if (-not (Test-Path -LiteralPath $certificado)) { throw 'Certificado publico ausente; copie a pasta completa do servidor.' }
        if ((Get-FileHash -LiteralPath $certificado -Algorithm SHA256).Hash -ne $pacote.certificado_sha256) {
            throw 'Certificado difere do pacote do servidor; instalacao interrompida.'
        }
        $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($certificado)
        if ($cert.HasPrivateKey -or $cert.NotAfter -lt (Get-Date) -or $cert.NotBefore -gt (Get-Date)) {
            throw 'Certificado publico invalido ou vencido.'
        }
        Write-Host 'Instalando confianca na autoridade HTTPS local do servidor, para seu usuario Windows.'
        Write-Host ('Certificado SHA256: ' + $pacote.certificado_sha256)
        Import-Certificate -FilePath $certificado -CertStoreLocation 'Cert:\CurrentUser\Root' | Out-Null
    }
    $destino = Join-Path $env:LOCALAPPDATA 'Dominio Automation Engine\Interface'
    New-Item -ItemType Directory -Path $destino -Force | Out-Null
    @{endereco = $Endereco} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $destino 'servidor.json') -Encoding UTF8
    $areaTrabalho = [Environment]::GetFolderPath('Desktop')
    $shell = New-Object -ComObject WScript.Shell
    $atalho = $shell.CreateShortcut((Join-Path $areaTrabalho 'Dominio - Interface.lnk'))
    $atalho.TargetPath = $navegador
    $atalho.Arguments = '--app="' + $Endereco + '"'
    $atalho.Description = 'Interface conectada ao servidor de automacao fiscal'
    $atalho.Save()
    Write-Host 'Interface instalada. Abra Dominio - Interface na area de trabalho.'
    Write-Host ('Servidor configurado: ' + $Endereco)
    Write-Host 'Ao abrir a interface, informe a chave de acesso fornecida pelo servidor.'
    Write-Host 'Python, OCR e Dominio ficam no PC servidor.'
    exit 0
} catch {
    Write-Host ('Instalacao nao concluida: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
