"""
一键安装脚本 — 将金价推送工具安装到 Hermes Agent

功能：
  1. 复制 jin10_client.py 到 Hermes scripts 目录
  2. 安装 jin10-mcp skill 到 Hermes skills 目录
  3. 创建 config.yaml 模板（如不存在）

运行：python install.py
"""
import sys
import os
import shutil
from pathlib import Path


def get_hermes_dir():
    """获取 Hermes 数据目录"""
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA', '')) / 'hermes'
    else:
        return Path.home() / '.local' / 'share' / 'hermes'


def main():
    hermes_dir = get_hermes_dir()
    project_dir = Path(__file__).parent
    scripts_dir = hermes_dir / 'scripts'
    skills_dir = hermes_dir / 'skills' / 'finance' / 'jin10-mcp'

    print("=" * 50)
    print("金价推送工具 — 安装到 Hermes Agent")
    print("=" * 50)
    print()
    print(f"Hermes 目录: {hermes_dir}")
    print()

    # 1. 复制 jin10_client.py
    src_client = project_dir / 'scripts' / 'jin10_client.py'
    dst_client = scripts_dir / 'jin10_client.py'

    if not src_client.exists():
        print(f"[✗] 源文件不存在: {src_client}")
        return 1

    scripts_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_client, dst_client)
    print(f"[✓] 已复制 jin10_client.py → {dst_client}")

    # 2. 复制 gold_monitor.py
    src_monitor = project_dir / 'scripts' / 'gold_monitor.py'
    dst_monitor = scripts_dir / 'gold_monitor.py'

    if src_monitor.exists():
        shutil.copy2(src_monitor, dst_monitor)
        print(f"[✓] 已复制 gold_monitor.py → {dst_monitor}")

    # 3. 安装 skill
    src_skill = project_dir / 'skill' / 'SKILL.md'
    if src_skill.exists():
        skills_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_skill, skills_dir / 'SKILL.md')
        print(f"[✓] 已安装 skill: jin10-mcp → {skills_dir}")
    else:
        print(f"[!] 跳过 skill 安装（未找到 {src_skill}）")

    # 4. 提示配置
    print()
    print("=" * 50)
    print("安装完成！接下来需要配置 Token：")
    print("=" * 50)
    print()
    print("1. 复制配置模板：")
    print(f"   copy {project_dir}\\config_template.yaml {project_dir}\\config.yaml")
    print()
    print("2. 编辑 config.yaml，填入：")
    print("   - jin10.token: 你的金十数据 MCP Token")
    print("   - bark.key: 你的 Bark 推送 Key")
    print()
    print("3. 运行环境检查：")
    print(f"   python {project_dir}\\scripts\\check_env.py")
    print()
    print("4. 在 Hermes 中创建定时任务：")
    print('   创建定时任务 name=金价监控 schedule="*/5 * * * *" script=gold_monitor.py no_agent=true deliver=local')
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
