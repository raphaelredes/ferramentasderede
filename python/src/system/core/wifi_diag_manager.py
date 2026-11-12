# src/system/core/wifi_diag_manager.py
# Diagnóstico Corporativo Multi-Host de Conectividade (DNS, ICMP, WinRM Rápido, LAN, WLAN e Auditoria Estrita 802.1x)

import json
import os
import re
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, Any, Generator, List, Optional

from pypsrp.wsman import WSMan
from pypsrp.powershell import PowerShell, RunspacePool

from src.system.core.winrm_handler import WinRMHandler

CREATE_NO_WINDOW = 0x08000000

_SAFE_TARGET_RE = re.compile(r"^(?:(?:\d{1,3}\.){3}\d{1,3}|[A-Za-z0-9][A-Za-z0-9._\-]{0,252})$")
_IPV4_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")


def parse_targets(raw_targets: List[str] | str) -> List[str]:
    """Divide, higieniza e deduplica a lista de hosts/IPs preservando a ordem."""
    if isinstance(raw_targets, str):
        parts = re.split(r"[,;\r\n\s]+", raw_targets)
    else:
        parts = []
        for item in raw_targets:
            if isinstance(item, str):
                parts.extend(re.split(r"[,;\r\n\s]+", item))

    seen = set()
    cleaned: List[str] = []
    for p in parts:
        val = p.strip()
        if not val or not _SAFE_TARGET_RE.match(val):
            continue
        key = val.upper()
        if key not in seen:
            seen.add(key)
            cleaned.append(val if _IPV4_RE.match(val) else val.upper())
    return cleaned


def _get_candidate_domains() -> List[str]:
    """Coleta sufixos de domínio rapidamente a partir das redes configuradas e ambiente."""
    seen = set()
    domains: List[str] = []

    def add_dom(d: Optional[str]):
        if d and isinstance(d, str):
            c = d.strip().strip(".")
            if c and c.lower() not in seen and c.lower() not in ("n/a", "unknown", "local", "workgroup"):
                seen.add(c.lower())
                domains.append(c)

    add_dom(os.environ.get("USERDNSDOMAIN"))
    try:
        from api.routes.settings import load_settings
        settings = load_settings()
        for net in (settings.networks or []):
            if net.enabled and net.domain:
                add_dom(net.domain)
    except Exception:
        pass

    return domains


def _resolve_and_ping_host(target: str, candidate_domains: List[str]) -> Dict[str, Any]:
    """Fase 1: Resolução DNS direta/reversa rápida + sonda ICMP única (450ms)."""
    dns_ok = False
    ip_resolved = ""
    fqdn_resolved = target
    ping_ok = False
    ping_ms: Optional[int] = None
    ping_ttl: Optional[int] = None

    is_ip = bool(_IPV4_RE.match(target))
    if is_ip:
        ip_resolved = target
        dns_ok = True
        try:
            rev = socket.gethostbyaddr(target)[0]
            if rev:
                fqdn_resolved = rev
        except Exception:
            fqdn_resolved = target
    else:
        names_to_try = [target]
        if "." not in target:
            names_to_try = [f"{target}.{d}" for d in candidate_domains] + [target]

        for cand in names_to_try:
            try:
                infos = socket.getaddrinfo(cand, None, socket.AF_INET)
                if infos:
                    ip_resolved = infos[0][4][0]
                    fqdn_resolved = cand
                    dns_ok = True
                    break
            except Exception:
                continue

    ping_target = ip_resolved if ip_resolved else target
    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE

    try:
        proc = subprocess.run(
            ["ping", "-n", "1", "-w", "450", ping_target],
            capture_output=True,
            text=True,
            encoding="cp850",
            errors="replace",
            timeout=1.5,
            creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
            startupinfo=startupinfo,
        )
        out = proc.stdout or ""
        ttl_match = re.search(r"TTL\s*=\s*(\d+)", out, re.IGNORECASE)
        if ttl_match:
            ping_ok = True
            ping_ttl = int(ttl_match.group(1))
            ms_match = re.search(r"(?:tempo|time)\s*[=<]\s*(\d+)\s*ms", out, re.IGNORECASE)
            if ms_match:
                ping_ms = int(ms_match.group(1))
            elif re.search(r"[<]\s*1\s*ms", out, re.IGNORECASE):
                ping_ms = 0
            else:
                ping_ms = 1

            if not ip_resolved:
                ip_hdr = re.search(r"\[(\d{1,3}(?:\.\d{1,3}){3})\]", out)
                if ip_hdr:
                    ip_resolved = ip_hdr.group(1)
                    dns_ok = True
    except Exception:
        pass

    return {
        "dns_ok": dns_ok,
        "ip_resolved": ip_resolved,
        "fqdn_resolved": fqdn_resolved,
        "ping_ok": ping_ok,
        "ping_ms": ping_ms,
        "ping_ttl": ping_ttl,
    }


def _check_tcp_port(host: str, port: int = 5985, timeout: float = 1.5) -> bool:
    """Pré-checagem rápida TCP antes de negociar WinRM (evita timeout de 15-30s em portas bloqueadas)."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def _is_cross_domain(username: str, target_domain: Optional[str]) -> bool:
    """Detecta se a autenticação cruza fronteira de domínio ou ocorre sem FQDN."""
    local_dom = (os.environ.get("USERDNSDOMAIN") or os.environ.get("USERDOMAIN") or "").strip().lower()
    if not local_dom:
        return True

    local_short = local_dom.split(".")[0]
    if target_domain:
        td = target_domain.strip().lower()
        if td and td != local_dom and td.split(".")[0] != local_short:
            return True

    user_dom = ""
    if "\\" in username:
        user_dom = username.split("\\", 1)[0].strip().lower()
    elif "@" in username:
        user_dom = username.split("@", 1)[1].strip().lower()

    if user_dom and user_dom not in (".", local_dom, local_short) and user_dom.split(".")[0] != local_short:
        return True

    return False


# Script otimizado em .NET nativo (NetworkInterface + X509Store + Registry)
# Executa em ~150-350ms dentro de um RunspacePool, evitando o lag de WMI SetupAPI e do Cert: provider.
REMOTE_AUDIT_PS1 = r'''
$ErrorActionPreference = 'SilentlyContinue'
$res = [ordered]@{
    Hostname          = $env:COMPUTERNAME
    Domain            = ''
    OSCaption         = ''
    LanConnected      = $false
    LanAdapters       = @()
    WifiPresent       = $false
    WifiConnected     = $false
    WifiState         = 'Ausente'
    WifiSSID          = ''
    WifiBSSID         = ''
    WifiSignal        = ''
    WifiSignalNum     = 0
    WifiRadio         = ''
    WifiChannel       = ''
    WifiAuth          = ''
    WifiCipher        = ''
    WifiIP            = ''
    WifiDesc          = ''
    WifiProfiles8021x = @()
    WifiProfiles8021xDetail = @()
    WifiAllProfiles   = @()
    Certs8021x        = @()
    CertStatus        = 'Missing'
    CertSummary       = ''
}

try {
    $dom = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().DomainName
    if (-not $dom) { $dom = $env:USERDNSDOMAIN }
    $res.Domain = [string]$dom

    $cv = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion' -ErrorAction SilentlyContinue
    if ($cv -and $cv.ProductName) {
        $cap = [string]$cv.ProductName
        $bld = 0
        [void][int]::TryParse([string]$cv.CurrentBuild, [ref]$bld)
        if ($bld -ge 22000 -and $cap -match 'Windows 10') {
            $cap = $cap -replace 'Windows 10', 'Windows 11'
        }
        $res.OSCaption = $cap
    }
} catch {}

$noiseNic = 'Hyper-V|Virtual|VMware|VirtualBox|Loopback|TAP|VPN|Miniport|ZeroTier|Tailscale|Bluetooth|Wi-Fi Direct|WAN |Kernel Debug|Npcap'
$hasWirelessNic = $false
$wifiIpMap = @{}

try {
    $allNics = [System.Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces()
    $pingObj = New-Object System.Net.NetworkInformation.Ping

    foreach ($ni in $allNics) {
        $desc = [string]$ni.Description
        $name = [string]$ni.Name
        $ntype = [string]$ni.NetworkInterfaceType
        if ($ntype -eq 'Loopback' -or $ntype -eq 'Tunnel') { continue }
        if ($desc -match $noiseNic -or $name -match $noiseNic) { continue }

        $ipProps = $ni.GetIPProperties()
        $v4List = @($ipProps.UnicastAddresses | Where-Object { $_.Address.AddressFamily -eq 'InterNetwork' } | ForEach-Object { $_.Address.IPAddressToString })
        $ipv4 = $v4List -join ', '

        if ($ntype -eq 'Wireless80211' -or $desc -match 'Wireless|Wi-Fi|802\.11|WLAN') {
            $hasWirelessNic = $true
            if ($ni.OperationalStatus -eq 'Up' -and $ipv4) {
                $wifiIpMap[$desc] = $ipv4
                if (-not $res.WifiIP) { $res.WifiIP = $ipv4 }
            }
            if (-not $res.WifiDesc) { $res.WifiDesc = $desc }
            continue
        }

        if ($ntype -in @('Ethernet','GigabitEthernet','FastEthernetT','FastEthernetFx')) {
            $isConn = ($ni.OperationalStatus -eq 'Up')
            if ($isConn) { $res.LanConnected = $true }

            $macRaw = $ni.GetPhysicalAddress().ToString()
            $macFmt = if ($macRaw.Length -eq 12) { ($macRaw -replace '(.{2})(?=.)', '$1:') } else { $macRaw }

            $speedMbps = 0
            $speedTxt = 'N/D'
            if ($isConn -and $ni.Speed -gt 0 -and $ni.Speed -lt 1000000000000) {
                $speedMbps = [math]::Round($ni.Speed / 1000000, 0)
                if ($speedMbps -ge 1000) {
                    $speedTxt = "$([math]::Round($speedMbps / 1000, 1)) Gbps"
                } else {
                    $speedTxt = "$speedMbps Mbps"
                }
            }

            $gwList = @($ipProps.GatewayAddresses | Where-Object { $_.Address.AddressFamily -eq 'InterNetwork' } | ForEach-Object { $_.Address.IPAddressToString })
            $gw = if ($gwList.Count -gt 0) { [string]$gwList[0] } else { '' }
            $gwStatus = 'Sem Gateway'
            if ($gw) {
                if ($isConn) {
                    try {
                        $reply = $pingObj.Send($gw, 250)
                        if ($reply -and $reply.Status -eq 'Success') { $gwStatus = "GW $gw OK" }
                        else { $gwStatus = "GW $gw s/ Ping" }
                    } catch { $gwStatus = "GW $gw" }
                } else {
                    $gwStatus = "GW $gw"
                }
            }

            $dnsList = @($ipProps.DnsAddresses | Where-Object { $_.AddressFamily -eq 'InterNetwork' } | ForEach-Object { $_.IPAddressToString })
            $dnsIps = $dnsList -join ', '

            $res.LanAdapters += [ordered]@{
                Name        = $name
                Description = $desc
                Status      = if ($isConn) { 'Conectado' } else { 'Desconectado' }
                MAC         = $macFmt
                SpeedMbps   = $speedMbps
                SpeedText   = $speedTxt
                IPv4        = $ipv4
                Gateway     = $gw
                GwStatus    = $gwStatus
                DNS         = $dnsIps
            }
        }
    }
    $pingObj.Dispose()
} catch {}

# 2. Enlace Wi-Fi (executa netsh apenas se WlanSvc ativo ou interface WLAN presente)
$wlanSvc = Get-Service -Name 'WlanSvc' -ErrorAction SilentlyContinue
if ($hasWirelessNic -or ($wlanSvc -and $wlanSvc.Status -eq 'Running')) {
    try {
        $wlanRaw = @(netsh wlan show interfaces 2>&1)
        $wlanText = $wlanRaw -join "`n"
        if ($wlanText -match 'SSID' -or $wlanText -match 'Estado|State') {
            $res.WifiPresent = $true
            $res.WifiState = 'Desconectado'
            foreach ($line in $wlanRaw) {
                $s = [string]$line
                if ($s -match '^\s*(?:Descri[cç][aã]o|Description)\s*:\s*(.+)$') { $res.WifiDesc = $matches[1].Trim() }
                elseif ($s -match '^\s*(?:Estado|State)\s*:\s*(.+)$') {
                    $st = $matches[1].Trim()
                    if ($st -match '^(?:conectado|connected)$') {
                        $res.WifiConnected = $true
                        $res.WifiState = 'Conectado'
                    } else {
                        $res.WifiState = $st
                    }
                }
                elseif ($s -match '^\s*SSID\s*:\s*(.+)$') { $res.WifiSSID = $matches[1].Trim() }
                elseif ($s -match '^\s*(?:BSSID|AP BSSID)\s*:\s*(.+)$') { $res.WifiBSSID = $matches[1].Trim() }
                elseif ($s -match '^\s*(?:Sinal|Signal)\s*:\s*(\d+)%') {
                    $res.WifiSignalNum = [int]$matches[1]
                    $res.WifiSignal = "$($matches[1])%"
                }
                elseif ($s -match '^\s*(?:Tipo de r[aá]dio|Radio type)\s*:\s*(.+)$') { $res.WifiRadio = $matches[1].Trim() }
                elseif ($s -match '^\s*(?:Canal|Channel)\s*:\s*(.+)$') { $res.WifiChannel = $matches[1].Trim() }
                elseif ($s -match '^\s*(?:Autentica[cç][aã]o|Authentication)\s*:\s*(.+)$') { $res.WifiAuth = $matches[1].Trim() }
                elseif ($s -match '^\s*(?:Cifra|Cipher)\s*:\s*(.+)$') { $res.WifiCipher = $matches[1].Trim() }
            }
            if ($res.WifiConnected -and $res.WifiDesc -and $wifiIpMap.ContainsKey($res.WifiDesc)) {
                $res.WifiIP = $wifiIpMap[$res.WifiDesc]
            }
        }

        if ($res.WifiPresent) {
            $domPrefix = ''
            if ($res.Domain -and $res.Domain -notmatch '^(?:WORKGROUP|N/A)$') {
                $domPrefix = [regex]::Escape(($res.Domain -split '\.')[0])
            }
            $profOut = @(netsh wlan show profiles 2>&1)
            foreach ($line in $profOut) {
                $s = [string]$line
                if ($s -match ':\s*(.+)$') {
                    $pName = $matches[1].Trim()
                    if ($pName -and $pName -notmatch '^(?:Perfis|Profiles|Nenhum|None|<)') {
                        $res.WifiAllProfiles += $pName
                        $is8021xProf = ($pName -match '802\.1x|BT-|CORP|WIFI|WLAN|ENTERPRISE|GOV|EDU')
                        if (-not $is8021xProf -and $domPrefix -and $pName -match $domPrefix) { $is8021xProf = $true }
                        if ($is8021xProf) { $res.WifiProfiles8021x += $pName }
                    }
                }
            }
            if ($res.WifiConnected -and $res.WifiSSID -and $res.WifiAuth -match 'Enterprise|802\.1[xX]') {
                if ($res.WifiProfiles8021x -notcontains $res.WifiSSID) { $res.WifiProfiles8021x += $res.WifiSSID }
            }
        }
    } catch {}
}

# 3. Políticas WLAN 802.1X (RSOP / EAP) e Certificados de Rede via .NET X509Store
try {
    $now = Get-Date
    $foundCerts = @()
    $seenThumbs = @{}
    $trustedRootMap = @{}

    # 3.1 Exporta e analisa os perfis WLAN 802.1X para identificar configurações EAP e CAs de Raiz marcadas
    $tempDir = [System.IO.Path]::GetTempPath()
    $randSub = [System.IO.Path]::GetRandomFileName()
    $workDir = Join-Path $tempDir "wf_$randSub"
    [void][System.IO.Directory]::CreateDirectory($workDir)

    try {
        [void](netsh wlan export profile folder="$workDir" 2>&1)
        $xmlFiles = Get-ChildItem -Path $workDir -Filter "*.xml" -ErrorAction SilentlyContinue

        foreach ($f in $xmlFiles) {
            try {
                [xml]$x = Get-Content -Path $f.FullName -Raw -Encoding UTF8
                $pName = [string]$x.WLANProfile.name
                $onexNode = $x.WLANProfile.MSM.security.OneX
                if (-not $onexNode) { continue }

                if ($res.WifiProfiles8021x -notcontains $pName) {
                    $res.WifiProfiles8021x += $pName
                }

                $authMode = [string]$onexNode.authMode
                $eapConfigNode = $onexNode.EAPConfig.EapHostConfig
                $eapTypeVal = [string]$eapConfigNode.Config.Eap.Type
                if (-not $eapTypeVal) { $eapTypeVal = [string]$eapConfigNode.EapMethod.Type }

                $typeName = switch ($eapTypeVal) {
                    '25' { 'PEAP (EAP Protegido)' }
                    '13' { 'EAP-TLS (Certificado / Smart Card)' }
                    '21' { 'TTLS (EAP Tunneled TLS)' }
                    default { if ($eapTypeVal) { "EAP Tipo $eapTypeVal" } else { '802.1X Padrão' } }
                }

                $serverValNode = $eapConfigNode.Config.Eap.EapType.ServerValidation
                $disablePrompt = if ($serverValNode.DisableUserPromptForServerValidation -eq 'true') { $true } else { $false }
                $serverNames = [string]$serverValNode.ServerNames
                $fastReconn = if ($eapConfigNode.Config.Eap.EapType.FastReconnect -eq 'true') { $true } else { $false }

                $innerType = [string]$eapConfigNode.Config.Eap.EapType.Eap.Type
                $innerName = switch ($innerType) {
                    '26' { 'EAP-MSCHAP v2' }
                    '13' { 'EAP-TLS' }
                    default { if ($innerType) { "Inner Tipo $innerType" } else { '' } }
                }
                $useWinLogon = if ($eapConfigNode.Config.Eap.EapType.Eap.EapType.UseWinLogonCredentials -eq 'true') { $true } else { $false }

                $roots = @()
                if ($serverValNode.TrustedRootCA) {
                    foreach ($rca in $serverValNode.TrustedRootCA) {
                        $cleaned = ([string]$rca -replace '[\s:]', '').ToUpper()
                        if ($cleaned) {
                            $roots += $cleaned
                            if (-not $trustedRootMap.ContainsKey($cleaned)) {
                                $trustedRootMap[$cleaned] = @()
                            }
                            $trustedRootMap[$cleaned] += [ordered]@{
                                ProfileName       = $pName
                                EapTypeName       = $typeName
                                InnerEapTypeName  = $innerName
                                AuthMode          = $authMode
                                ServerNames       = $serverNames
                                DisableUserPrompt = $disablePrompt
                                FastReconnect     = $fastReconn
                                UseWinLogon       = $useWinLogon
                            }
                        }
                    }
                }

                $res.WifiProfiles8021xDetail += [ordered]@{
                    ProfileName       = $pName
                    AuthMode          = $authMode
                    EapType           = $eapTypeVal
                    EapTypeName       = $typeName
                    InnerEapType      = $innerType
                    InnerEapTypeName  = $innerName
                    ValidateServer    = ($roots.Count -gt 0 -or $serverNames -or $disablePrompt)
                    ServerNames       = $serverNames
                    DisableUserPrompt = $disablePrompt
                    FastReconnect     = $fastReconn
                    UseWinLogon       = $useWinLogon
                    TrustedRootCount  = $roots.Count
                    TrustedRootThumbs = $roots
                }
            } catch {}
        }
    } finally {
        if (Test-Path $workDir) {
            Remove-Item -Path $workDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    # 3.2 Busca e valida as CAs de Raiz marcadas na política 802.1X (PEAP / EAP-TLS)
    foreach ($tp in $trustedRootMap.Keys) {
        $pList = $trustedRootMap[$tp]
        $pNames = ($pList | ForEach-Object { $_.ProfileName } | Select-Object -Unique) -join ', '
        $eapSummary = ($pList | ForEach-Object { "$($_.ProfileName) [$($_.EapTypeName)$(if ($_.InnerEapTypeName) { ' / ' + $_.InnerEapTypeName })]" } | Select-Object -Unique) -join '; '
        $firstP = $pList[0]

        $foundCertObj = $null
        $foundStoreName = ''
        foreach ($stName in @('Root', 'CA', 'AuthRoot', 'My')) {
            $st = [System.Security.Cryptography.X509Certificates.X509Store]::new($stName, 'LocalMachine')
            try {
                $st.Open('ReadOnly')
                foreach ($c in $st.Certificates) {
                    if ($c.Thumbprint.ToUpper() -eq $tp) {
                        $foundCertObj = $c
                        $foundStoreName = "LocalMachine\$stName"
                        break
                    }
                }
            } finally {
                $st.Close()
            }
            if ($foundCertObj) { break }
        }

        $seenThumbs[$tp] = $true

        if ($foundCertObj) {
            $daysLeft = [math]::Floor(($foundCertObj.NotAfter - $now).TotalDays)
            $foundCerts += [ordered]@{
                Subject            = ($foundCertObj.Subject -replace '^CN=', '')
                Issuer             = ($foundCertObj.Issuer -replace '^CN=', '')
                Thumbprint         = $tp
                NotBefore          = $foundCertObj.NotBefore.ToString('dd/MM/yyyy')
                NotAfter           = $foundCertObj.NotAfter.ToString('dd/MM/yyyy')
                DaysLeft           = [int]$daysLeft
                HasPrivateKey      = [bool]$foundCertObj.HasPrivateKey
                Template           = "Autoridade Raiz 802.1X ($pNames)"
                FriendlyName       = [string]$foundCertObj.FriendlyName
                Store              = $foundStoreName
                SerialNumber       = [string]$foundCertObj.SerialNumber
                IsEapTrustedRoot   = $true
                EapProfileName     = $pNames
                EapConfigSummary   = $eapSummary
                EapAuthMode        = [string]$firstP.AuthMode
                EapFastReconnect   = [bool]$firstP.FastReconnect
                EapDisablePrompt   = [bool]$firstP.DisableUserPrompt
                EapServerNames     = [string]$firstP.ServerNames
                IsMissingFromStore = $false
            }
        } else {
            $foundCerts += [ordered]@{
                Subject            = "Autoridade Raiz NÃO Instalada no Host!"
                Issuer             = "Exigida pelo perfil 802.1X ($pNames)"
                Thumbprint         = $tp
                NotBefore          = 'N/D'
                NotAfter           = 'Ausente'
                DaysLeft           = -9999
                HasPrivateKey      = $false
                Template           = "Política 802.1X ($pNames)"
                FriendlyName       = ''
                Store              = 'LocalMachine\Root (Ausente!)'
                SerialNumber       = ''
                IsEapTrustedRoot   = $true
                EapProfileName     = $pNames
                EapConfigSummary   = $eapSummary
                EapAuthMode        = [string]$firstP.AuthMode
                EapFastReconnect   = [bool]$firstP.FastReconnect
                EapDisablePrompt   = [bool]$firstP.DisableUserPrompt
                EapServerNames     = [string]$firstP.ServerNames
                IsMissingFromStore = $true
            }
        }
    }

    # 3.3 Busca certificados de cliente (My) e CAs corporativas (CA/Root) adicionais
    $domTokens = @()
    if ($res.Domain -and $res.Domain -notmatch '^(?:WORKGROUP|N/A)$') {
        $domTokens = @($res.Domain -split '\.' | Where-Object { $_.Length -ge 3 -and $_ -notmatch '^(?:com|local|lan|corp|net|org|gov|br)$' })
    }
    $compToken = [regex]::Escape($env:COMPUTERNAME)

    $noiseSubjectRegex = 'Kaspersky|TeamViewer|AnyDesk|Splashtop|RustDesk|Docker|VMware|Hyper-V|IIS Express|localhost|WMSvc|SQL|Desktop|Remote Desktop|Intel|NVIDIA|Adobe|Citrix'
    $noiseIssuerRegex  = 'Kaspersky|TeamViewer|AnyDesk|Splashtop|RustDesk|DigiCert|GlobalSign|Sectigo|Comodo|Let''s Encrypt|Entrust|VeriSign|GoDaddy|Google|Amazon|Cloudflare|Balt|USERTrust|AAA Certificate|Microsoft Root|Microsoft Time-Stamp|Microsoft Code|Microsoft Windows|Microsoft Corporation|Autoridade Certificadora Raiz Brasileira|ICP-Brasil'

    foreach ($stName in @('My', 'CA')) {
        $store = [System.Security.Cryptography.X509Certificates.X509Store]::new($stName, 'LocalMachine')
        try {
            $store.Open('ReadOnly')
            foreach ($cert in $store.Certificates) {
                $tp = [string]$cert.Thumbprint.ToUpper()
                if ($seenThumbs.ContainsKey($tp)) { continue }
                $subj = [string]$cert.Subject
                $iss  = [string]$cert.Issuer
                $frnd = [string]$cert.FriendlyName
                if ($subj -match $noiseSubjectRegex -or $iss -match $noiseIssuerRegex) { continue }

                $isMatch = $false
                if ($stName -eq 'My') {
                    $isClientAuth = $false
                    foreach ($ext in $cert.Extensions) {
                        if ($ext.Oid.Value -eq '2.5.29.37') {
                            $ekuExt = [System.Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension]$ext
                            foreach ($oid in $ekuExt.EnhancedKeyUsages) {
                                if ($oid.Value -eq '1.3.6.1.5.5.7.3.2') { $isClientAuth = $true; break }
                            }
                            break
                        }
                    }
                    $isCorpMatch = ($subj -match '802\.1x|BT-|WIFI|WLAN|RADIUS|NPS|\bNAC\b' -or $iss -match '802\.1x|BT-|WIFI|WLAN|RADIUS|NPS|\bNAC\b|-CA|CA-' -or $frnd -match '802\.1x|BT-|WIFI|WLAN')
                    foreach ($dt in $domTokens) {
                        if ($subj -match [regex]::Escape($dt) -or $iss -match [regex]::Escape($dt)) { $isCorpMatch = $true; break }
                    }
                    if ($compToken -and $subj -match $compToken) { $isCorpMatch = $true }
                    $isMatch = ($isClientAuth -or $isCorpMatch)
                } else {
                    $isMatch = ($subj -match '802\.1x|BT-|WIFI|WLAN|RADIUS|NPS|\bNAC\b' -or $iss -match '802\.1x|BT-|WIFI|WLAN|RADIUS|NPS|\bNAC\b' -or $frnd -match '802\.1x|BT-|WIFI|WLAN|RADIUS')
                    if (-not $isMatch) {
                        foreach ($dt in $domTokens) {
                            if ($subj -match [regex]::Escape($dt) -or $iss -match [regex]::Escape($dt)) { $isMatch = $true; break }
                        }
                    }
                }

                if ($isMatch) {
                    $seenThumbs[$tp] = $true
                    $tmpl = if ($stName -eq 'My') { '' } else { "Autoridade Intermediária ($stName)" }
                    if ($stName -eq 'My') {
                        foreach ($ext in $cert.Extensions) {
                            if ($ext.Oid.Value -in @('1.3.6.1.4.1.311.20.2', '1.3.6.1.4.1.311.21.7')) {
                                $tmpl = $ext.Format($false); break
                            }
                        }
                    }
                    $daysLeft = [math]::Floor(($cert.NotAfter - $now).TotalDays)
                    $foundCerts += [ordered]@{
                        Subject            = ($subj -replace '^CN=', '')
                        Issuer             = ($iss -replace '^CN=', '')
                        Thumbprint         = $tp
                        NotBefore          = $cert.NotBefore.ToString('dd/MM/yyyy')
                        NotAfter           = $cert.NotAfter.ToString('dd/MM/yyyy')
                        DaysLeft           = [int]$daysLeft
                        HasPrivateKey      = [bool]$cert.HasPrivateKey
                        Template           = [string]$tmpl
                        FriendlyName       = $frnd
                        Store              = "LocalMachine\$stName"
                        SerialNumber       = [string]$cert.SerialNumber
                        IsEapTrustedRoot   = $false
                        EapProfileName     = ''
                        EapConfigSummary   = ''
                        EapAuthMode        = ''
                        EapFastReconnect   = $false
                        EapDisablePrompt   = $false
                        EapServerNames     = ''
                        IsMissingFromStore = $false
                    }
                }
            }
        } finally {
            $store.Close()
        }
    }

    $res.Certs8021x = $foundCerts
    if ($foundCerts.Count -eq 0) {
        $res.CertStatus  = 'Missing'
        $res.CertSummary = 'Nenhum cert. 802.1x localizado'
    } else {
        $eapRoots = @($foundCerts | Where-Object { $_.IsEapTrustedRoot })
        $missingEapRoot = @($eapRoots | Where-Object { $_.IsMissingFromStore })
        $expiredEapRoot = @($eapRoots | Where-Object { -not $_.IsMissingFromStore -and $_.DaysLeft -le 0 })
        $expiringEapRoot = @($eapRoots | Where-Object { -not $_.IsMissingFromStore -and $_.DaysLeft -gt 0 -and $_.DaysLeft -le 30 })

        if ($missingEapRoot.Count -gt 0) {
            $res.CertStatus  = 'Problem'
            $res.CertSummary = "CA Raiz 802.1X NÃO INSTALADA no host!"
        } elseif ($expiredEapRoot.Count -gt 0) {
            $res.CertStatus  = 'Problem'
            $res.CertSummary = "CA Raiz 802.1X EXPIRADA ($($expiredEapRoot[0].NotAfter))!"
        } elseif ($expiringEapRoot.Count -gt 0) {
            $res.CertStatus  = 'Expiring'
            $res.CertSummary = "CA Raiz 802.1X expira em $($expiringEapRoot[0].DaysLeft)d ($($expiringEapRoot[0].NotAfter))"
        } elseif ($eapRoots.Count -gt 0) {
            $res.CertStatus  = 'OK'
            $firstSubj = ($eapRoots[0].Subject -split ',')[0]
            $res.CertSummary = "CA Raiz 802.1X OK ($firstSubj)"
        } else {
            $validCerts = @($foundCerts | Where-Object { $_.DaysLeft -gt 0 -and ($_.Store -ne 'LocalMachine\My' -or $_.HasPrivateKey) })
            if ($validCerts.Count -gt 0) {
                $best = $validCerts | Sort-Object DaysLeft -Descending | Select-Object -First 1
                if ($best.DaysLeft -le 30) {
                    $res.CertStatus  = 'Expiring'
                    $res.CertSummary = "Expira em $($best.DaysLeft)d ($($best.NotAfter))"
                } else {
                    $res.CertStatus  = 'OK'
                    $res.CertSummary = "Válido até $($best.NotAfter) ($($best.DaysLeft)d)"
                }
            } else {
                $res.CertStatus  = 'Problem'
                $res.CertSummary = 'Certificado expirado ou sem chave privada'
            }
        }
    }
} catch {
    $res.CertStatus  = 'Unknown'
    $res.CertSummary = 'Erro ao ler repositório X509Store'
}

$res | ConvertTo-Json -Depth 5 -Compress
'''


def _build_tiles_and_report(data: Dict[str, Any]) -> Dict[str, Any]:
    """Constrói os tiles visuais, badge global, síntese e o relatório técnico formatado."""
    stage = data["stage"]
    dns_ok = data["dns_ok"]
    ip_res = data["ip_resolved"]
    fqdn_res = data["fqdn_resolved"]
    ping_ok = data["ping_ok"]
    ping_ms = data["ping_ms"]
    ping_ttl = data["ping_ttl"]
    winrm_ok = data.get("winrm_ok", False)
    winrm_err = data.get("winrm_error", "")

    t1_state = "Green" if dns_ok else "Red"
    t1_main = ip_res if dns_ok and ip_res else "Não Resolvido"
    t1_sub = fqdn_res if dns_ok else "Host inexistente no DNS"

    t2_state = "Green" if ping_ok else "Red"
    t2_main = f"Online ({ping_ms if ping_ms is not None else '<1'} ms)" if ping_ok else "Sem Resposta"
    t2_sub = f"TTL {ping_ttl} • ICMP Echo OK" if ping_ok else "Timeout ICMP (450ms)"

    if stage == "PingStage":
        tiles = {
            "tile1": {"title": "RESOLUÇÃO DNS & IP", "main": t1_main, "sub": t1_sub, "state": t1_state},
            "tile2": {"title": "ALCANCE (PING ICMP)", "main": t2_main, "sub": t2_sub, "state": t2_state},
            "tile3": {"title": "GERÊNCIA (WINRM)", "main": "Autenticando...", "sub": "Testando sessão remota", "state": "Neutral"},
            "tile4": {"title": "ENLACE CABEADO (LAN)", "main": "Coletando...", "sub": "Inspecionando interfaces", "state": "Neutral"},
            "tile5": {"title": "ENLACE WI-FI (WLAN)", "main": "Coletando...", "sub": "Consultando netsh wlan", "state": "Neutral"},
            "tile6": {"title": "CONTROLE 802.1X", "main": "Coletando...", "sub": "Auditando X509Store", "state": "Neutral"},
        }
        data["tiles"] = tiles
        data["overall_badge"] = f"PING {ping_ms}ms • AUDITANDO WINRM..." if ping_ok else "SEM PING • TENTANDO WINRM..."
        data["overall_state"] = "Blue" if ping_ok else "Amber"
        data["synthesis"] = (
            f"Alcance ICMP confirmado ({ping_ms} ms). Coletando interfaces, Wi-Fi e certificados 802.1x..."
            if ping_ok
            else "Sem resposta ICMP. Testando conexão administrativa direta na porta 5985..."
        )
        return data

    # Stage == Final
    if winrm_ok:
        t3_state = "Green"
        t3_main = "Conectado (WSMan)"
        os_cap = data.get("os_caption") or ""
        os_short = re.sub(r"Microsoft\s+|Windows\s+", "Win ", os_cap).strip()
        dom = data.get("domain") or "Local"
        t3_sub = f"{dom} • {os_short}" if os_short else f"Domínio: {dom}"
        winrm_detail = ""
    else:
        t3_state = "Amber" if ping_ok else "Red"
        err_low = (winrm_err or "").lower()
        if any(k in err_low for k in ("acesso negado", "access is denied", "0x80070005", "unauthorized", "401", "credenciais recusadas")):
            t3_main = "Acesso Negado"
            t3_sub = "Conta sem Admin Local ou credencial recusada"
            winrm_detail = "O host respondeu na porta 5985, mas recusou a credencial informada ou o usuário não pertence ao grupo Administradores local."
        elif any(k in err_low for k in ("kerberos", "logon", "credentials", "rejected", "0x80090308")):
            t3_main = "Falha de Autenticação"
            t3_sub = "Erro de logon no domínio ou senha incorreta"
            winrm_detail = "Falha na autenticação. Verifique usuário (DOMINIO\\usuario), senha e permissões administrativas."
        elif ping_ok:
            t3_main = "Bloqueado / Parado"
            t3_sub = "Serviço WinRM parado ou Firewall (5985)"
            winrm_detail = "O computador responde ao Ping, mas a porta TCP 5985 (WinRM) não aceitou conexão."
        else:
            t3_main = "Sem Conexão"
            t3_sub = "Equipamento desligado ou fora da rede"
            winrm_detail = "Não houve resposta ICMP nem conexão TCP na porta 5985."
    data["winrm_detail"] = winrm_detail

    t4_state, t4_main, t4_sub = "Neutral", "Não Auditado", "Requer sessão WinRM ativa"
    lan_adapters = data.get("lan_adapters") or []
    lan_conn = data.get("lan_connected", False)
    if winrm_ok:
        if lan_conn:
            t4_state = "Green"
            active_lan = next((a for a in lan_adapters if a.get("Status") == "Conectado"), lan_adapters[0] if lan_adapters else {})
            t4_main = f"Ativo • {active_lan.get('SpeedText') or 'N/D'}"
            t4_sub = f"IP: {active_lan.get('IPv4') or 'Sem IP'} • {active_lan.get('GwStatus') or 'Sem GW'}"
        elif len(lan_adapters) > 0:
            t4_main = "Cabo Desconectado"
            t4_sub = f"{len(lan_adapters)} placa(s) Ethernet sem link físico"
        else:
            t4_main = "Sem Placa Ethernet"
            t4_sub = "Nenhum adaptador cabeado físico detectado"

    t5_state, t5_main, t5_sub = "Neutral", "Não Auditado", "Requer sessão WinRM ativa"
    wifi_present = data.get("wifi_present", False)
    wifi_conn = data.get("wifi_connected", False)
    if winrm_ok:
        if wifi_conn:
            t5_state = "Blue"
            t5_main = f"{data.get('wifi_ssid') or 'SSID Oculto'} ({data.get('wifi_signal') or '?%'})"
            t5_sub = f"IP: {data.get('wifi_ip') or 'Sem IPv4'} • Canal {data.get('wifi_channel') or '?'}"
        elif wifi_present:
            t5_main = "Desconectado"
            w_desc = data.get("wifi_desc") or "Adaptador WLAN presente"
            t5_sub = w_desc[:44] + "..." if len(w_desc) > 44 else w_desc
        else:
            t5_main = "Sem Placa Wi-Fi"
            t5_sub = "Interface WLAN inexistente ou desativada"

    t6_state, t6_main, t6_sub = "Neutral", "Não Auditado", "Requer sessão WinRM ativa"
    if winrm_ok:
        profs = data.get("wifi_profiles_8021x") or []
        prof_txt = f"Perfil: {', '.join(profs)}" if profs else "Sem perfil WLAN 802.1x"
        c_status = data.get("cert_status", "Missing")
        c_sum = data.get("cert_summary", "Nenhum cert. 802.1x localizado")

        if c_status == "OK":
            t6_state, t6_main, t6_sub = "Green", "Certificado 802.1x OK", f"{c_sum} • {prof_txt}"
        elif c_status == "Expiring":
            t6_state, t6_main, t6_sub = "Amber", "Cert. Expirando", f"{c_sum} • {prof_txt}"
        elif c_status == "Problem":
            t6_state, t6_main, t6_sub = "Red", "Certificado Inválido", f"{c_sum} • {prof_txt}"
        elif c_status == "Missing":
            if wifi_conn or wifi_present:
                t6_state, t6_main, t6_sub = "Amber", "Sem Cert. 802.1x", f"Ausente em LocalMachine • {prof_txt}"
            else:
                t6_state, t6_main, t6_sub = "Neutral", "Não Aplicável (Desktop)", "Sem Wi-Fi e sem certificado 802.1x"
        else:
            t6_state, t6_main, t6_sub = "Amber", "Não Verificado", c_sum

    if not dns_ok and not ping_ok and not winrm_ok:
        overall_badge = "OFFLINE • FALHA DE DNS"
        overall_state = "Red"
        synthesis = "O nome informado não pôde ser traduzido para um endereço IP válido pelos servidores DNS."
    elif not ping_ok and not winrm_ok:
        overall_badge = "OFFLINE • SEM RESPOSTA"
        overall_state = "Red"
        synthesis = f"DNS resolveu para {ip_res}, mas o host não responde a Ping ICMP nem aceita conexão WinRM."
    elif ping_ok and not winrm_ok:
        overall_badge = "PING OK • WINRM FALHOU"
        overall_state = "Amber"
        synthesis = f"Equipamento ativo na rede ({ping_ms} ms), porém sem gerência remota: {winrm_detail}"
    else:
        if lan_conn and wifi_conn:
            overall_badge = "MODO HÍBRIDO • CABO + WI-FI"
            overall_state = "Amber"
            synthesis = (
                f"Dupla conexão ativa simultaneamente: Cabeado e Wi-Fi ({data.get('wifi_ssid')} - {data.get('wifi_signal')}). "
                f"Status 802.1x: {data.get('cert_summary')}."
            )
        elif lan_conn and not wifi_conn:
            overall_badge = "ONLINE • EXCLUSIVO CABO"
            overall_state = "Green"
            synthesis = "Operando exclusivamente via rede cabeada (Ethernet). Interface Wi-Fi desconectada ou ausente."
        elif not lan_conn and wifi_conn:
            overall_badge = "ONLINE • EXCLUSIVO WI-FI"
            overall_state = "Green"
            synthesis = (
                f"Operando exclusivamente via Wi-Fi no SSID '{data.get('wifi_ssid')}' "
                f"(Sinal {data.get('wifi_signal')}, IP {data.get('wifi_ip')}). Status 802.1x: {data.get('cert_summary')}."
            )
        else:
            overall_badge = "ONLINE • SEM ENLACE PADRÃO"
            overall_state = "Amber"
            synthesis = "Sessão WinRM estabelecida, mas nenhuma interface física padrão reportou status Conectado."

    data["tiles"] = {
        "tile1": {"title": "RESOLUÇÃO DNS & IP", "main": t1_main, "sub": t1_sub, "state": t1_state},
        "tile2": {"title": "ALCANCE (PING ICMP)", "main": t2_main, "sub": t2_sub, "state": t2_state},
        "tile3": {"title": "GERÊNCIA (WINRM)", "main": t3_main, "sub": t3_sub, "state": t3_state},
        "tile4": {"title": "ENLACE CABEADO (LAN)", "main": t4_main, "sub": t4_sub, "state": t4_state},
        "tile5": {"title": "ENLACE WI-FI (WLAN)", "main": t5_main, "sub": t5_sub, "state": t5_state},
        "tile6": {"title": "CONTROLE 802.1X", "main": t6_main, "sub": t6_sub, "state": t6_state},
    }
    data["overall_badge"] = overall_badge
    data["overall_state"] = overall_state
    data["synthesis"] = synthesis
    data["raw_report"] = _format_host_report(data)
    return data


def _format_host_report(d: Dict[str, Any]) -> str:
    """Gera o relatório textual completo para inspeção técnica e cópia para área de transferência."""
    lines = [
        "==========================================================================",
        f" HOST ALVO: {d.get('host_input')}   [Status: {d.get('overall_badge')}]",
        "==========================================================================",
        f" • Horário da Coleta : {d.get('timestamp')}",
        f" • Resolução DNS     : {'OK (' + d.get('ip_resolved', '') + ' / ' + d.get('fqdn_resolved', '') + ')' if d.get('dns_ok') else 'FALHOU'}",
        f" • Alcance ICMP      : {'Respondendo (' + str(d.get('ping_ms')) + ' ms | TTL ' + str(d.get('ping_ttl')) + ')' if d.get('ping_ok') else 'Sem resposta (Timeout 450ms)'}",
        f" • Gerência WinRM    : {'Conectado (' + d.get('hostname', '') + ' | Domínio: ' + d.get('domain', '') + ')' if d.get('winrm_ok') else 'Falhou (' + (d.get('winrm_detail') or d.get('winrm_error') or 'Sem conexão') + ')'}",
    ]
    if d.get("os_caption"):
        lines.append(f" • Sistema Operac.   : {d.get('os_caption')}")
    lines.append(f" • Síntese Executiva : {d.get('synthesis')}")
    lines.append("")

    if d.get("winrm_ok"):
        lines.append(" --- [1] INTERFACES CABEADAS (ETHERNET FÍSICA) ---")
        lan_list = d.get("lan_adapters") or []
        if not lan_list:
            lines.append("   Nenhuma interface física Ethernet localizada.")
        else:
            for a in lan_list:
                lines.append(f"   • [{a.get('Status')}] {a.get('Name')} - {a.get('Description')}")
                lines.append(
                    f"     MAC: {a.get('MAC')} | Velocidade: {a.get('SpeedText')} | "
                    f"IPv4: {a.get('IPv4')} | {a.get('GwStatus')} | DNS: {a.get('DNS')}"
                )
        lines.append("")

        lines.append(" --- [2] INTERFACE SEM FIO (WI-FI / WLAN) ---")
        if not d.get("wifi_present"):
            lines.append("   Hardware Wi-Fi ausente ou serviço WLAN AutoConfig parado.")
        else:
            lines.append(f"   • Estado       : {d.get('wifi_state')}")
            lines.append(f"   • Adaptador    : {d.get('wifi_desc')}")
            if d.get("wifi_connected"):
                lines.append(f"   • SSID / BSSID : {d.get('wifi_ssid')}  ({d.get('wifi_bssid')})")
                lines.append(
                    f"   • Sinal / Rádio: {d.get('wifi_signal')} | {d.get('wifi_radio')} | Canal {d.get('wifi_channel')}"
                )
                lines.append(
                    f"   • Segurança    : {d.get('wifi_auth')} ({d.get('wifi_cipher')}) | IPv4: {d.get('wifi_ip')}"
                )
            all_profs = d.get("wifi_all_profiles") or []
            if all_profs:
                lines.append(f"   • Perfis Salvos: {', '.join(all_profs)}")
        lines.append("")

        lines.append(" --- [3] AUDITORIA DE CONTROLE 802.1X & POLÍTICAS WLAN (RSOP) ---")
        lines.append(f"   • Resumo 802.1x: {d.get('cert_summary')} (Status: {d.get('cert_status')})")
        profs_detail = d.get("wifi_profiles_8021x_detail") or []
        if profs_detail:
            lines.append("   • Políticas WLAN 802.1X e EAP (RSOP / GPO):")
            for p in profs_detail:
                lines.append(f"     - Perfil: {p.get('ProfileName')} [{p.get('EapTypeName')}]")
                lines.append(f"       Modo: {p.get('AuthMode')} | Autenticação Interna: {p.get('InnerEapTypeName') or 'N/A'}")
                lines.append(f"       Validação Servidor: {p.get('ValidateServer')} | Reconexão Rápida: {p.get('FastReconnect')}")
                lines.append(f"       CAs Raiz Confiáveis Marcadas no Perfil: {p.get('TrustedRootCount')} autoridade(s)")
        
        certs = d.get("certs_8021x") or []
        if certs:
            lines.append("   • Certificados Auditados / Autoridades de Rede:")
            for c in certs:
                tag_eap = f" ★ [MARCADA NO PERFIL: {c.get('EapProfileName')}]" if c.get("IsEapTrustedRoot") else ""
                lines.append(f"     - [{c.get('Store')}] {c.get('Subject')}{tag_eap}")
                lines.append(f"       Emissor: {c.get('Issuer')}")
                valid_str = f"{c.get('NotAfter')} ({c.get('DaysLeft')} dias)"
                if c.get("NotBefore"):
                    valid_str = f"De {c.get('NotBefore')} até {c.get('NotAfter')} ({c.get('DaysLeft')} dias)"
                lines.append(
                    f"       Validade: {valid_str} | "
                    f"Chave Privada: {c.get('HasPrivateKey')} | Template: {c.get('Template') or 'Padrão'}"
                )
                if c.get("IsEapTrustedRoot"):
                    lines.append(f"       Config EAP: {c.get('EapConfigSummary')}")
                if c.get("SerialNumber"):
                    lines.append(f"       Serial: {c.get('SerialNumber')}")
                lines.append(f"       Thumbprint: {c.get('Thumbprint')}")
    return "\n".join(lines)


def _execute_fast_winrm(
    target_conn: str,
    target_fqdn: Optional[str],
    username: str,
    password: str,
) -> str:
    """Conexão WinRM de baixa latência: pré-checagem TCP 5985 + NTLM direto em cross-domain."""
    target_domain = target_fqdn.split(".", 1)[1] if (target_fqdn and "." in target_fqdn) else None
    cross_domain = _is_cross_domain(username, target_domain) or not target_fqdn

    # Em cross-domain ou conexão via IP, NTLM direto evita 15-30s de timeout SPNEGO/Kerberos
    auth_sequence = ["ntlm"] if cross_domain else ["negotiate", "ntlm"]

    last_exc: Optional[Exception] = None
    for auth_method in auth_sequence:
        wsman = None
        pool = None
        try:
            ws_kwargs: Dict[str, Any] = {
                "server": target_conn,
                "username": username,
                "password": password,
                "ssl": False,
                "auth": auth_method,
                "connection_timeout": 5,
                "read_timeout": 12,
                "operation_timeout": 8,
            }
            if auth_method == "negotiate" and target_fqdn:
                ws_kwargs["negotiate_hostname_override"] = target_fqdn

            wsman = WSMan(**ws_kwargs)
            pool = RunspacePool(wsman, configuration_name="Microsoft.PowerShell")
            pool.open()
            ps = PowerShell(pool)
            ps.add_script(REMOTE_AUDIT_PS1)
            output_list = ps.invoke()
            if ps.had_errors and ps.streams.error and not output_list:
                raise RuntimeError("; ".join(str(e) for e in ps.streams.error))
            return "".join(str(x) for x in output_list).strip()
        except Exception as exc:
            last_exc = exc
            msg_low = str(exc).lower()
            # Só faz fallback negotiate -> ntlm se falhou por Kerberos/SPN; falha explícita de credencial não repete
            if auth_method == "negotiate" and any(k in msg_low for k in ("kerberos", "spn", "kdc", "timed out", "timeout")):
                continue
            break
        finally:
            if pool:
                try:
                    pool.close()
                except Exception:
                    pass
            if wsman:
                try:
                    wsman.close()
                except Exception:
                    pass

    raise last_exc if last_exc else RuntimeError("Falha ao executar auditoria via WinRM.")


def _extract_and_apply_winrm(data: Dict[str, Any], raw_out: str) -> Dict[str, Any]:
    """Extrai o JSON retornado pelo script remoto e preenche o dicionário de diagnóstico."""
    json_start = raw_out.find("{")
    json_end = raw_out.rfind("}")
    raw_json = raw_out[json_start : json_end + 1] if (json_start != -1 and json_end > json_start) else raw_out
    parsed = json.loads(raw_json)

    data["winrm_ok"] = True
    data["winrm_error"] = ""
    data["hostname"] = parsed.get("Hostname") or data["host_input"]
    data["domain"] = parsed.get("Domain") or ""
    data["os_caption"] = parsed.get("OSCaption") or ""
    data["lan_connected"] = bool(parsed.get("LanConnected"))
    data["lan_adapters"] = parsed.get("LanAdapters") or []
    data["wifi_present"] = bool(parsed.get("WifiPresent"))
    data["wifi_connected"] = bool(parsed.get("WifiConnected"))
    data["wifi_state"] = parsed.get("WifiState") or "Ausente"
    data["wifi_ssid"] = parsed.get("WifiSSID") or ""
    data["wifi_bssid"] = parsed.get("WifiBSSID") or ""
    data["wifi_signal"] = parsed.get("WifiSignal") or ""
    data["wifi_signal_num"] = int(parsed.get("WifiSignalNum") or 0)
    data["wifi_radio"] = parsed.get("WifiRadio") or ""
    data["wifi_channel"] = parsed.get("WifiChannel") or ""
    data["wifi_auth"] = parsed.get("WifiAuth") or ""
    data["wifi_cipher"] = parsed.get("WifiCipher") or ""
    data["wifi_ip"] = parsed.get("WifiIP") or ""
    data["wifi_desc"] = parsed.get("WifiDesc") or ""
    data["wifi_profiles_8021x"] = parsed.get("WifiProfiles8021x") or []
    data["wifi_all_profiles"] = parsed.get("WifiAllProfiles") or []
    data["certs_8021x"] = parsed.get("Certs8021x") or []
    data["cert_status"] = parsed.get("CertStatus") or "Missing"
    data["cert_summary"] = parsed.get("CertSummary") or ""
    return _build_tiles_and_report(data)


def _audit_winrm_host(base_data: Dict[str, Any], username: str, password: str) -> Dict[str, Any]:
    """Fase 2: Pré-checagem TCP 5985 + execução rápida WinRM em .NET nativo."""
    data = dict(base_data)
    data["stage"] = "Final"
    data["timestamp"] = datetime.now().strftime("%H:%M:%S")

    target_conn = data["ip_resolved"] if data["ip_resolved"] else data["host_input"]
    target_fqdn = data["fqdn_resolved"] if data["fqdn_resolved"] and "." in data["fqdn_resolved"] else None

    if not _check_tcp_port(target_conn, 5985, timeout=1.5):
        data["winrm_ok"] = False
        data["winrm_error"] = f"Porta 5985 (WinRM) inacessível em {target_conn}."
        return _build_tiles_and_report(data)

    try:
        raw_out = _execute_fast_winrm(target_conn, target_fqdn, username, password)
        if not raw_out:
            data["winrm_ok"] = False
            data["winrm_error"] = "Sessão WinRM retornou resposta vazia."
            return _build_tiles_and_report(data)
        return _extract_and_apply_winrm(data, raw_out)
    except Exception as e:
        err_str = str(e)
        # Fallback único com prefixo de domínio do alvo caso o operador tenha informado usuário sem domínio
        if (
            any(k in err_str.lower() for k in ("cred", "unauthorized", "401", "logon", "0x80090308"))
            and "\\" not in username
            and "@" not in username
            and target_fqdn
            and "." in target_fqdn
        ):
            try:
                dom_u = f"{target_fqdn.split('.', 1)[1].split('.')[0]}\\{username}"
                raw_retry = _execute_fast_winrm(target_conn, target_fqdn, dom_u, password)
                if raw_retry:
                    return _extract_and_apply_winrm(data, raw_retry)
            except Exception as e2:
                err_str = str(e2)

        data["winrm_ok"] = False
        data["winrm_error"] = err_str
        return _build_tiles_and_report(data)


def stream_connectivity_diagnostic(
    targets: List[str],
    username: str = "",
    password: str = "",
) -> Generator[bytes, None, None]:
    """Gera eventos NDJSON (UTF-8 bytes) em tempo real sem buffering."""
    # Emite cabeçalho imediato para destravar ReadableStream do WebView2/Chromium instantaneamente
    yield (json.dumps({"type": "started", "count": len(targets)}, ensure_ascii=False) + "\n").encode("utf-8")

    candidate_domains = _get_candidate_domains()
    pending_winrm: List[Dict[str, Any]] = []

    # Fase 1: DNS + ICMP paralelo
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(targets)))) as ping_pool:
        future_to_target = {
            ping_pool.submit(_resolve_and_ping_host, t, candidate_domains): t
            for t in targets
        }
        for fut in as_completed(future_to_target):
            t = future_to_target[fut]
            try:
                p_info = fut.result()
            except Exception:
                p_info = {
                    "dns_ok": False,
                    "ip_resolved": "",
                    "fqdn_resolved": t,
                    "ping_ok": False,
                    "ping_ms": None,
                    "ping_ttl": None,
                }

            base_item: Dict[str, Any] = {
                "host_input": t,
                "stage": "PingStage",
                "mode": "Full",
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "dns_ok": p_info["dns_ok"],
                "ip_resolved": p_info["ip_resolved"],
                "fqdn_resolved": p_info["fqdn_resolved"],
                "ping_ok": p_info["ping_ok"],
                "ping_ms": p_info["ping_ms"],
                "ping_ttl": p_info["ping_ttl"],
                "winrm_ok": False,
                "winrm_error": "",
                "winrm_detail": "",
                "hostname": t,
                "domain": "",
                "os_caption": "",
                "lan_connected": False,
                "lan_adapters": [],
                "wifi_present": False,
                "wifi_connected": False,
                "wifi_state": "Ausente",
                "wifi_ssid": "",
                "wifi_bssid": "",
                "wifi_signal": "",
                "wifi_signal_num": 0,
                "wifi_radio": "",
                "wifi_channel": "",
                "wifi_auth": "",
                "wifi_cipher": "",
                "wifi_ip": "",
                "wifi_desc": "",
                "wifi_profiles_8021x": [],
                "wifi_all_profiles": [],
                "certs_8021x": [],
                "cert_status": "Unknown",
                "cert_summary": "",
            }

            if not p_info["ping_ok"] and not p_info["ip_resolved"]:
                base_item["stage"] = "Final"
                base_item["winrm_error"] = "Host inexistente no DNS e sem resposta ICMP."
                final_dead_item = _build_tiles_and_report(base_item)
                yield (json.dumps({"type": "host_update", "data": final_dead_item}, ensure_ascii=False) + "\n").encode("utf-8")
            else:
                stage1_item = _build_tiles_and_report(base_item)
                yield (json.dumps({"type": "host_update", "data": stage1_item}, ensure_ascii=False) + "\n").encode("utf-8")
                pending_winrm.append(base_item)

    # Fase 2: Execução concorrente de WinRM para hosts alcançáveis
    if pending_winrm:
        with ThreadPoolExecutor(max_workers=min(8, max(1, len(pending_winrm)))) as winrm_pool:
            future_to_item = {
                winrm_pool.submit(_audit_winrm_host, item, username, password): item["host_input"]
                for item in pending_winrm
            }
            for fut in as_completed(future_to_item):
                h_name = future_to_item[fut]
                try:
                    final_item = fut.result()
                except Exception as e:
                    fallback = next((x for x in pending_winrm if x["host_input"] == h_name), {"host_input": h_name})
                    fallback["stage"] = "Final"
                    fallback["winrm_ok"] = False
                    fallback["winrm_error"] = str(e)
                    final_item = _build_tiles_and_report(fallback)
                yield (json.dumps({"type": "host_update", "data": final_item}, ensure_ascii=False) + "\n").encode("utf-8")

    yield (json.dumps({"type": "done", "timestamp": datetime.now().isoformat()}, ensure_ascii=False) + "\n").encode("utf-8")
