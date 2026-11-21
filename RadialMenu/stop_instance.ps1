# Only stop standalone RadialMenu processes launched from this checkout.
$ErrorActionPreference = 'Stop'
try {
    $scriptPath = Join-Path $PSScriptRoot 'radial_gui.py'
    $scriptPattern = [regex]::Escape($scriptPath).Replace('\\', '[\\/]')
    $commandPattern = '(?i)(?:^|\s)"?' + $scriptPattern + '"?(?=\s|$)'
    $instances = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" |
        Where-Object { $_.CommandLine -match $commandPattern })
    foreach ($instance in $instances) {
        # The venv launcher and its Python child can both match. Either may
        # already have exited when the other is stopped.
        $process = Get-Process -Id $instance.ProcessId -ErrorAction SilentlyContinue
        if ($null -ne $process) {
            Write-Host "Stopping RadialMenu (PID $($process.Id))..."
            try {
                $process.Kill()
            } catch {
                # Killing the venv parent can also finish its Python child.
                if (-not $process.HasExited) { throw }
            }
            if (-not $process.WaitForExit(10000)) {
                throw "RadialMenu process $($process.Id) did not exit."
            }
        }
    }
    exit 0
} catch {
    Write-Error "Could not stop RadialMenu: $_"
    exit 1
}
