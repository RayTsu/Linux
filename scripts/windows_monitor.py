#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import winrm
import argparse
from datetime import datetime
import json
import re

class WindowsMonitor:
    def __init__(self, host, username='zabbix_monitor', password='Aa_123456', port=5985):
        """
        初始化Windows监控器

        Args:
            host: Windows机器IP或主机名
            username: 用户名 (默认: zabbix_monitor)
            password: 密码 (默认: Aa_123456)
            port: WinRM端口 (默认5985 HTTP, 5986 HTTPS)
        """
        self.host = host
        self.username = username
        self.password = password
        self.port = port

        print(f"正在连接 {host} ...")
        print(f"认证方式: basic")

        # 创建WinRM会话
        self.session = winrm.Session(
            f'http://{host}:{port}/wsman',
            auth=(username, password),
            transport='basic',
            server_cert_validation='ignore',
            operation_timeout_sec=60,
            read_timeout_sec=70
        )
        print("✓ 连接成功")

    def get_cpu_usage(self):
        """获取CPU使用率"""
        try:
            # 使用兼容PowerShell 2.0的方式
            ps_script = """
            $cpu = Get-WmiObject Win32_Processor
            $cpu.LoadPercentage
            """

            result = self.session.run_ps(ps_script)
            if result.status_code == 0:
                output = result.std_out.decode('gbk', errors='ignore').strip()
                if output:
                    cpu_usage = float(output.split()[0])
                    return round(cpu_usage, 2)
            return None
        except Exception as e:
            print(f"CPU获取异常: {str(e)}")
            return None

    def get_memory_usage(self):
        """获取内存使用率"""
        try:
            # 使用兼容PowerShell 2.0的方式
            ps_script = """
            $os = Get-WmiObject Win32_OperatingSystem
            $total = [float]$os.TotalVisibleMemorySize
            $free = [float]$os.FreePhysicalMemory
            $used = (($total - $free) / $total) * 100
            $used
            """

            result = self.session.run_ps(ps_script)
            if result.status_code == 0:
                output = result.std_out.decode('gbk', errors='ignore').strip()
                if output:
                    mem_usage = float(output.split()[0])
                    return round(mem_usage, 2)
            return None
        except Exception as e:
            print(f"内存获取异常: {str(e)}")
            return None

    def get_disk_usage(self, drive_letter=None):
        """
        获取磁盘使用率 - 兼容PowerShell 2.0版本
        """
        try:
            if drive_letter:
                # 获取指定磁盘
                ps_script = f"""
                $drive = Get-WmiObject Win32_LogicalDisk -Filter "DeviceID='{drive_letter}:'"
                if ($drive) {{
                    $used = [math]::Round((($drive.Size - $drive.FreeSpace) / $drive.Size) * 100, 2)
                    $totalGB = [math]::Round($drive.Size / 1GB, 2)
                    $freeGB = [math]::Round($drive.FreeSpace / 1GB, 2)
                    $usedGB = [math]::Round(($drive.Size - $drive.FreeSpace) / 1GB, 2)

                    Write-Host "Drive: $($drive.DeviceID)"
                    Write-Host "TotalGB: $totalGB"
                    Write-Host "UsedGB: $usedGB"
                    Write-Host "FreeGB: $freeGB"
                    Write-Host "UsedPercent: $used"
                }}
                """
            else:
                # 获取所有本地磁盘
                ps_script = """
                $drives = Get-WmiObject Win32_LogicalDisk -Filter "DriveType=3"
                foreach ($drive in $drives) {
                    $used = [math]::Round((($drive.Size - $drive.FreeSpace) / $drive.Size) * 100, 2)
                    $totalGB = [math]::Round($drive.Size / 1GB, 2)
                    $freeGB = [math]::Round($drive.FreeSpace / 1GB, 2)
                    $usedGB = [math]::Round(($drive.Size - $drive.FreeSpace) / 1GB, 2)

                    Write-Host "Drive: $($drive.DeviceID)"
                    Write-Host "TotalGB: $totalGB"
                    Write-Host "UsedGB: $usedGB"
                    Write-Host "FreeGB: $freeGB"
                    Write-Host "UsedPercent: $used"
                    Write-Host "---"
                }
                """

            result = self.session.run_ps(ps_script)
            if result.status_code == 0:
                output = result.std_out.decode('gbk', errors='ignore').strip()
                return self._parse_disk_output(output)
            else:
                print(f"磁盘获取失败: {result.std_err}")
                return None

        except Exception as e:
            print(f"磁盘获取异常: {str(e)}")
            return None

    def _parse_disk_output(self, output):
        """解析磁盘输出格式"""
        disks = []
        current_disk = {}

        for line in output.split('\n'):
            line = line.strip()
            if not line:
                continue

            if line.startswith('Drive:'):
                if current_disk and 'Drive' in current_disk:
                    disks.append(current_disk)
                current_disk = {'Drive': line.replace('Drive:', '').strip()}
            elif line.startswith('TotalGB:'):
                current_disk['TotalGB'] = float(line.replace('TotalGB:', '').strip())
            elif line.startswith('UsedGB:'):
                current_disk['UsedGB'] = float(line.replace('UsedGB:', '').strip())
            elif line.startswith('FreeGB:'):
                current_disk['FreeGB'] = float(line.replace('FreeGB:', '').strip())
            elif line.startswith('UsedPercent:'):
                current_disk['UsedPercent'] = float(line.replace('UsedPercent:', '').strip())
            elif line == '---':
                if current_disk and 'Drive' in current_disk:
                    disks.append(current_disk)
                    current_disk = {}

        # 添加最后一个磁盘
        if current_disk and 'Drive' in current_disk:
            disks.append(current_disk)

        return disks if disks else None

    def get_system_info(self):
        """获取系统基本信息 - 兼容PowerShell 2.0"""
        try:
            ps_script = """
            $os = Get-WmiObject Win32_OperatingSystem
            $cs = Get-WmiObject Win32_ComputerSystem
            $cpu = Get-WmiObject Win32_Processor | Select-Object -First 1

            Write-Host "ComputerName: $env:COMPUTERNAME"
            Write-Host "OSName: $($os.Caption)"
            Write-Host "OSVersion: $($os.Version)"
            Write-Host "LastBootTime: $($os.LastBootUpTime)"
            Write-Host "TotalMemoryGB: $([math]::Round($cs.TotalPhysicalMemory / 1GB, 2))"
            Write-Host "CPUName: $($cpu.Name)"
            Write-Host "CPUCores: $($cpu.NumberOfCores)"
            Write-Host "CPULogical: $($cpu.NumberOfLogicalProcessors)"
            """

            result = self.session.run_ps(ps_script)
            if result.status_code == 0:
                output = result.std_out.decode('gbk', errors='ignore').strip()
                return self._parse_system_info(output)
            else:
                print(f"系统信息获取失败: {result.std_err}")
                return None
        except Exception as e:
            print(f"系统信息获取异常: {str(e)}")
            return None

    def _parse_system_info(self, output):
        """解析系统信息输出"""
        info = {}
        for line in output.split('\n'):
            line = line.strip()
            if not line:
                continue
            if ':' in line:
                key, value = line.split(':', 1)
                info[key.strip()] = value.strip()
        return info

    def monitor_all(self):
        """获取所有监控数据"""
        print(f"\n正在监控 Windows 主机: {self.host}")
        print("=" * 60)

        # 获取系统信息
        system_info = self.get_system_info()
        if system_info:
            print("\n📋 系统信息:")
            print(f"  计算机名: {system_info.get('ComputerName', 'N/A')}")
            print(f"  操作系统: {system_info.get('OSName', 'N/A')}")
            print(f"  最后启动: {system_info.get('LastBootTime', 'N/A')}")
            print(f"  总内存: {system_info.get('TotalMemoryGB', 'N/A')} GB")
            cpu_name = system_info.get('CPUName', 'N/A')
            print(f"  CPU: {cpu_name[:50]}..." if len(cpu_name) > 50 else f"  CPU: {cpu_name}")
            print(f"  CPU核心: {system_info.get('CPUCores', 'N/A')} 物理, {system_info.get('CPULogical', 'N/A')} 逻辑")

        # 获取CPU使用率
        cpu = self.get_cpu_usage()
        if cpu is not None:
            print(f"\n💻 CPU使用率: {cpu}%")
            if cpu > 80:
                print("  ⚠️ 警告: CPU使用率过高!")
            elif cpu > 60:
                print("  ⚠️ 注意: CPU使用率偏高")

        # 获取内存使用率
        memory = self.get_memory_usage()
        if memory is not None:
            print(f"\n📊 内存使用率: {memory}%")
            if memory > 80:
                print("  ⚠️ 警告: 内存使用率过高!")
            elif memory > 60:
                print("  ⚠️ 注意: 内存使用率偏高")

        # 获取所有磁盘信息
        disks = self.get_disk_usage()
        if disks:
            print("\n💾 磁盘使用情况:")
            for disk in disks:
                self._print_disk_info(disk)

        return {
            'timestamp': datetime.now().isoformat(),
            'host': self.host,
            'cpu': cpu,
            'memory': memory,
            'disks': disks,
            'system_info': system_info
        }

    def _print_disk_info(self, disk):
        """打印磁盘信息"""
        drive = disk.get('Drive', 'N/A')
        used_percent = disk.get('UsedPercent', 0)
        total = disk.get('TotalGB', 0)
        used = disk.get('UsedGB', 0)
        free = disk.get('FreeGB', 0)

        # 创建进度条
        bar_length = 30
        filled = int(bar_length * used_percent / 100)
        bar = '█' * filled + '░' * (bar_length - filled)

        print(f"  {drive} [{bar}] {used_percent:.1f}%")
        print(f"    总大小: {total:.1f} GB, 已用: {used:.1f} GB, 可用: {free:.1f} GB")

        if used_percent > 80:
            print("    ⚠️ 警告: 磁盘空间不足!")
        elif used_percent > 60:
            print("    ⚠️ 注意: 磁盘使用率偏高")


def main():
    parser = argparse.ArgumentParser(description='监控Windows机器资源使用情况')
    parser.add_argument('--host', default='10.10.1.109', help='Windows主机IP (默认: 10.10.1.109)')
    parser.add_argument('--username', default='zabbix_monitor', help='用户名 (默认: zabbix_monitor)')
    parser.add_argument('--password', default='Aa_123456', help='密码 (默认: Aa_123456)')
    parser.add_argument('--port', type=int, default=5985, help='WinRM端口 (默认5985)')
    parser.add_argument('--drive', help='指定监控的磁盘 (如 C)，不指定则监控所有磁盘')
    parser.add_argument('--json', action='store_true', help='以JSON格式输出')

    args = parser.parse_args()

    # 创建监控器
    monitor = WindowsMonitor(
        host=args.host,
        username=args.username,
        password=args.password,
        port=args.port
    )

    try:
        if args.drive:
            # 只获取指定磁盘信息
            disk_info = monitor.get_disk_usage(args.drive.upper())
            if args.json:
                print(json.dumps(disk_info, indent=2, ensure_ascii=False))
            else:
                print(f"\n磁盘 {args.drive.upper()}: 信息")
                if disk_info:
                    if isinstance(disk_info, list):
                        for disk in disk_info:
                            monitor._print_disk_info(disk)
                    else:
                        monitor._print_disk_info(disk_info)
        else:
            # 获取所有信息
            data = monitor.monitor_all()
            if args.json:
                print(json.dumps(data, indent=2, ensure_ascii=False, default=str))

    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        print("\n可能的原因:")
        print("1. 目标机器IP或端口不正确")
        print("2. WinRM服务未启动或配置不正确")
        print("3. 防火墙阻止了5985端口")
        print("4. 用户名密码错误")
        print("5. 用户没有足够的权限")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
