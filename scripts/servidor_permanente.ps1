param([ValidateSet('instalar','remover','status','reiniciar')][string]$Acao = 'instalar', [switch]$Forcar)
$ErrorActionPreference = 'Stop'
$nome = 'AutomacaoDominioServidor'
try {
    $raiz = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
    $vbs = Join-Path $raiz 'atalhos\servidor\Servidor Oculto.vbs'
    $usuario = "$env:USERDOMAIN\$env:USERNAME"
    if ($Acao -eq 'status') {
        $t = Get-ScheduledTask -TaskName $nome -ErrorAction SilentlyContinue
        if ($t) { Write-Host ("Tarefa '$nome': " + $t.State) } else { Write-Host "Servidor permanente NAO instalado." }
        exit 0
    }
    if ($Acao -eq 'reiniciar') {
        # Nao reinicia no meio de uma rotina (o lote seria interrompido), salvo com -Forcar.
        $banco = Join-Path $raiz 'data\servidor.sqlite3'
        if ((Test-Path -LiteralPath $banco) -and -not $Forcar) {
            $ocupado = python (Join-Path $raiz 'scripts\servidor_ocupado.py')
            if ([int]$ocupado -gt 0) {
                throw "Ha $ocupado tarefa(s) pendente(s) ou rodando. Espere terminar (ou use Reiniciar Servidor (forcar).bat, que interrompe o lote)."
            }
        }
        $t = Get-ScheduledTask -TaskName $nome -ErrorAction SilentlyContinue
        if ($t) { Stop-ScheduledTask -TaskName $nome -ErrorAction SilentlyContinue }
        Get-CimInstance Win32_Process | Where-Object {
            ($_.Name -match '^(cmd|python)(w)?\.exe$' -and $_.CommandLine -match 'Servidor Permanente \(loop\)|scripts[\/]servidor\.py')
        } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        Start-Sleep -Seconds 3
        if ($t) { Start-ScheduledTask -TaskName $nome } else { Start-Process -FilePath 'wscript.exe' -ArgumentList ('"' + $vbs + '"') -WorkingDirectory $raiz }
        for ($i = 0; $i -lt 30; $i++) {
            Start-Sleep -Seconds 2
            if (Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python(w)?\.exe$' -and $_.CommandLine -match 'scripts[\/]servidor\.py' }) {
                Write-Host 'Servidor reiniciado e no ar (sem desligar o PC). Se o painel estava aberto, atualize a pagina (Ctrl+F5).'
                exit 0
            }
        }
        throw 'O servidor nao subiu em 60 s. Veja o fim de data\servidor_permanente.log.'
    }
    if ($Acao -eq 'remover') {
        if (Get-ScheduledTask -TaskName $nome -ErrorAction SilentlyContinue) {
            Stop-ScheduledTask -TaskName $nome -ErrorAction SilentlyContinue
            Unregister-ScheduledTask -TaskName $nome -Confirm:$false
        }
        # Encerra o loop e o servidor que ficaram abertos.
        Get-CimInstance Win32_Process | Where-Object {
            ($_.Name -match '^(cmd|python)(w)?\.exe$' -and $_.CommandLine -match 'Servidor Permanente \(loop\)|scripts[\/]servidor\.py')
        } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        Write-Host 'Servidor permanente removido. Para abrir manualmente use Executar Dominio na Rede.bat.'
        exit 0
    }
    if (-not (Test-Path -LiteralPath (Join-Path $raiz 'data\rede_local\config.json'))) {
        throw 'Rode antes atalhos\servidor\Configurar Acesso Rede.bat (e Liberar Acesso Rede.bat como administrador).'
    }
    $acaoTarefa = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument ('"' + $vbs + '"') -WorkingDirectory $raiz
    $gatilho = New-ScheduledTaskTrigger -AtLogOn -User $usuario
    $cfg = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) `
        -MultipleInstances IgnoreNew -StartWhenAvailable
    $principal = New-ScheduledTaskPrincipal -UserId $usuario -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $nome -Action $acaoTarefa -Trigger $gatilho -Settings $cfg -Principal $principal `
        -Description 'Servidor da automacao do Dominio (sobe no logon, sem janela, reinicia se cair).' -Force | Out-Null
    # O Dominio e controlado pela tela: o PC nao pode dormir nem apagar a tela enquanto o servidor roda.
    powercfg /change standby-timeout-ac 0 | Out-Null
    powercfg /change monitor-timeout-ac 0 | Out-Null
    powercfg /change hibernate-timeout-ac 0 | Out-Null
    Start-ScheduledTask -TaskName $nome
    Write-Host "Servidor permanente instalado: sobe sozinho quando '$usuario' entra no Windows, sem janela."
    Write-Host 'Deixe este usuario logado, a tela desbloqueada e o Dominio aberto na tela azul.'
    Write-Host 'Log: data\servidor_permanente.log'
    exit 0
} catch {
    Write-Host ('Nao concluido: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
