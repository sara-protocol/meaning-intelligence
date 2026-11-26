param(
  [Parameter(Mandatory = $true)][string]$JobPath,
  [Parameter(Mandatory = $true)][string]$OutputDirectory,
  [switch]$Force
)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Speech
$job = Get-Content -LiteralPath $JobPath -Raw -Encoding UTF8 | ConvertFrom-Json
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$installed = @(Get-ChildItem -LiteralPath $OutputDirectory -Filter "*.wav" -ErrorAction SilentlyContinue)
$synthesizer = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voiceMap = @{}
try {
  foreach ($language in @("zh", "en")) {
    $culture = if ($language -eq "zh") { "zh-CN" } else { "en-US" }
    $preferred = if ($language -eq "zh") { "Microsoft Huihui Desktop" } else { "Microsoft Zira Desktop" }
    $voice = @($synthesizer.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -eq $culture } | ForEach-Object { $_.VoiceInfo } | Where-Object { $_.Name -eq $preferred })
    if ($voice.Count -eq 0) {
      $voice = @($synthesizer.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -eq $culture } | ForEach-Object { $_.VoiceInfo })
    }
    if ($voice.Count -eq 0) { throw "No installed $culture SAPI voice was found." }
    $voiceMap[$language] = $voice[0]
  }
  $index = 0
  foreach ($cue in $job.cues) {
    $index++
    $filename = [string]$cue.filename
    if ($filename -notmatch '^(zh|en)__[a-z0-9-]+__[0-9]{3}\.wav$') { throw "Unsafe cue filename: $filename" }
    $path = Join-Path $OutputDirectory $filename
    if (-not $Force -and (Test-Path -LiteralPath $path)) {
      Write-Output ("SKIP {0}/{1} {2}" -f $index, $job.cues.Count, $filename)
      continue
    }
    $language = [string]$cue.language
    if (-not $voiceMap.ContainsKey($language)) { throw "Unsupported narration language: $language" }
    $culture = $voiceMap[$language].Culture.Name
    $safeText = [System.Security.SecurityElement]::Escape([string]$cue.text)
    $ssml = "<speak version='1.0' xml:lang='$culture'><p>$safeText</p></speak>"
    $synthesizer.SelectVoice($voiceMap[$language].Name)
    $synthesizer.Rate = 1
    $synthesizer.Volume = 100
    $synthesizer.SetOutputToWaveFile($path)
    try {
      $synthesizer.Speak($ssml)
    } finally {
      $synthesizer.SetOutputToNull()
    }
    Write-Output ("OK {0}/{1} {2}" -f $index, $job.cues.Count, $filename)
  }
  Write-Output "VOICES zh=$($voiceMap['zh'].Name) en=$($voiceMap['en'].Name)"
} finally {
  $synthesizer.Dispose()
}
