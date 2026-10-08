$ErrorActionPreference = 'Stop'
try {
    $identidade = [Security.Principal.WindowsIdentity]::GetCurrent()
    $usuario = New-Object Security.Principal.WindowsPrincipal($identidade)
    if (-not $usuario.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Clique com o botao direito em Liberar Acesso Rede.bat e escolha Executar como administrador.'
    }
    $arquivo = Join-Path $PSScriptRoot '..\data\rede_local\config.json'
    $config = Get-Content -LiteralPath $arquivo -Raw | ConvertFrom-Json
    $ip = $null
    if (-not [Net.IPAddress]::TryParse($config.ip, [ref]$ip) -or
        $ip.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork -or
        $config.porta -lt 1 -or $config.porta -gt 65535 -or
        -not (Test-Path -LiteralPath $config.python)) { throw 'Configuracao da rede invalida; repita o instalador do servidor.' }
    if ($config.ip -notmatch '^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)') {
        throw 'A regra exige um IPv4 da rede local.'
    }
    if (-not (Get-NetIPAddress -IPAddress $config.ip -AddressFamily IPv4 -ErrorAction SilentlyContinue)) {
        throw 'Este IPv4 nao pertence ao PC atual. Repita Configurar Acesso Rede.bat.'
    }
    $nome = 'DominioAutomationEngineRedeLocal'
    $regra = Get-NetFirewallRule -Name $nome -ErrorAction SilentlyContinue
    if ($regra) { Remove-NetFirewallRule -Name $nome }
    New-NetFirewallRule -Name $nome -DisplayName 'Dominio Automation Engine - Rede local' -Direction Inbound -Action Allow -Protocol TCP -LocalPort $config.porta -LocalAddress $config.ip -RemoteAddress LocalSubnet -Profile Private,Domain -Program $config.python | Out-Null
    Write-Host 'Acesso liberado para esta porta/IP/Python, somente na sub-rede local e em redes privadas ou de dominio.'
    Write-Host 'Confira que seu Wi-Fi esta configurado como rede privada no Windows.'
    exit 0
} catch {
    Write-Host ('Acesso nao configurado: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
