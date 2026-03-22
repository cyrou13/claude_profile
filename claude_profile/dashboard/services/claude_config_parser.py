"""Parse Claude Code configuration: skills, agents, commands, CLAUDE.md, settings."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SkillInfo:
    """Parsed skill metadata."""

    name: str
    description: str = ""
    has_scripts: bool = False


@dataclass
class AgentInfo:
    """Parsed agent metadata."""

    name: str
    description: str = ""
    model: str = ""
    tools: list[str] = field(default_factory=list)


@dataclass
class CommandInfo:
    """Parsed command metadata."""

    name: str
    description: str = ""


@dataclass
class ProjectClaudeMd:
    """A project-level CLAUDE.md."""

    project_name: str
    path: str
    line_count: int
    preview: str = ""


@dataclass
class ClaudeConfig:
    """Full parsed Claude Code configuration."""

    global_claude_md: str = ""
    global_claude_md_lines: int = 0
    skills: list[SkillInfo] = field(default_factory=list)
    agents: list[AgentInfo] = field(default_factory=list)
    commands: list[CommandInfo] = field(default_factory=list)
    project_claude_mds: list[ProjectClaudeMd] = field(default_factory=list)
    settings: dict[str, object] = field(default_factory=dict)
    mcp_servers: list[str] = field(default_factory=list)


def parse_claude_config(claude_home: Path, scan_dirs: list[str] | None = None) -> ClaudeConfig:
    """Parse all Claude Code configuration from ~/.claude/."""
    config = ClaudeConfig()

    # Global CLAUDE.md
    claude_md_path = claude_home / "CLAUDE.md"
    if claude_md_path.exists():
        content = claude_md_path.read_text()
        config.global_claude_md = content
        config.global_claude_md_lines = len(content.splitlines())

    # Skills
    skills_dir = claude_home / "skills"
    if skills_dir.exists():
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill = SkillInfo(name=skill_dir.name)
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                text = skill_md.read_text()
                # First non-empty non-heading line as description
                for line in text.splitlines():
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
                        skill.description = stripped[:120]
                        break
            skill.has_scripts = (skill_dir / "scripts").exists()
            config.skills.append(skill)

    # Agents
    agents_dir = claude_home / "agents"
    if agents_dir.exists():
        for agent_file in sorted(agents_dir.iterdir()):
            if agent_file.suffix != ".md":
                continue
            agent = AgentInfo(name=agent_file.stem)
            text = agent_file.read_text()
            # Parse YAML frontmatter
            fm_match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
            if fm_match:
                fm = fm_match.group(1)
                for line in fm.splitlines():
                    if line.startswith("model:"):
                        agent.model = line.split(":", 1)[1].strip().strip('"')
                    elif line.startswith("tools:"):
                        agent.tools = [t.strip() for t in line.split(":", 1)[1].split(",")]
                # Description: first line of name field or first content line after frontmatter
                name_match = re.search(r'^name:\s*(.+)', fm, re.MULTILINE)
                if name_match:
                    agent.name = name_match.group(1).strip().strip('"')
                desc_match = re.search(r'^description:\s*["\']?(.+?)(?:["\']?\s*$)', fm, re.MULTILINE)
                if desc_match:
                    raw_desc = desc_match.group(1)
                    # Truncate long descriptions (remove example blocks)
                    if "\\n" in raw_desc:
                        raw_desc = raw_desc.split("\\n")[0]
                    agent.description = raw_desc[:150]
            config.agents.append(agent)

    # Commands
    commands_dir = claude_home / "commands"
    if commands_dir.exists():
        for cmd_file in sorted(commands_dir.iterdir()):
            if cmd_file.suffix != ".md":
                continue
            cmd = CommandInfo(name=cmd_file.stem)
            text = cmd_file.read_text()
            fm_match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
            if fm_match:
                fm = fm_match.group(1)
                desc_match = re.search(r'^description:\s*(.+)', fm, re.MULTILINE)
                if desc_match:
                    cmd.description = desc_match.group(1).strip().strip('"')
            if not cmd.description:
                # First non-empty line as description
                for line in text.splitlines():
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
                        cmd.description = stripped[:120]
                        break
            config.commands.append(cmd)

    # Project-level CLAUDE.md files
    if scan_dirs:
        for scan_dir in scan_dirs:
            base = Path(scan_dir).expanduser()
            if not base.exists():
                continue
            for project_dir in sorted(base.iterdir()):
                if not project_dir.is_dir():
                    continue
                claude_md = project_dir / "CLAUDE.md"
                if claude_md.exists():
                    content = claude_md.read_text()
                    lines = content.splitlines()
                    preview = "\n".join(lines[:5])
                    config.project_claude_mds.append(
                        ProjectClaudeMd(
                            project_name=project_dir.name,
                            path=str(claude_md),
                            line_count=len(lines),
                            preview=preview,
                        )
                    )

    # Settings
    settings_file = claude_home / "settings.json"
    if settings_file.exists():
        try:
            config.settings = json.loads(settings_file.read_text())
        except json.JSONDecodeError:
            pass

    # MCP servers from settings
    mcp = config.settings.get("mcpServers", {})
    if isinstance(mcp, dict):
        config.mcp_servers = sorted(mcp.keys())

    # Also check plugins for MCP servers
    plugins_file = claude_home / "plugins" / "installed_plugins.json"
    if plugins_file.exists():
        try:
            plugins_data = json.loads(plugins_file.read_text())
            for plugin_name in plugins_data.get("plugins", {}):
                # Plugin names like "context7@claude-plugins-official"
                short_name = plugin_name.split("@")[0]
                if short_name not in config.mcp_servers:
                    config.mcp_servers.append(short_name)
            config.mcp_servers.sort()
        except json.JSONDecodeError:
            pass

    return config
