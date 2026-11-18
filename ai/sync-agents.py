"""Build and synchronize local Æmacs AI Agents.

Generates repository-local agent definitions from `ai/*.md`:
1. GitHub Copilot agents (`.github/agents/*.agent.md`)
2. Native Æmacs agent souls (`.aemacs/agents/*.yaml`)
3. Antigravity CLI agents (`.agents/agents/*.md`)
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from typing import Final, List, Mapping, Optional, Sequence, TypedDict


class SourceSpec(TypedDict, total=False):
    """Configuration describing a Markdown persona roster file."""

    file: str
    marker: str
    type: str
    footer_pattern: str
    split_regex: str


class ParsedAgent(TypedDict):
    """Normalized representation of a parsed agent persona."""

    name: str
    slug: str
    role: str
    body: str
    type: str


class ArtifactContract(TypedDict):
    """Canonical Org-Mode input/output contract for strategic pipeline agents."""

    upstream_inputs: Sequence[str]
    output_targets: Sequence[str]
    templates: Sequence[str]
    instructions: str


# ==========================================
#  PATHS & CONSTANTS (REPO-LOCAL ONLY)
# ==========================================

SCRIPT_DIR: Final[str] = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT: Final[str] = os.path.dirname(SCRIPT_DIR)

COPILOT_AGENTS_DIR: Final[str] = os.path.join(REPO_ROOT, ".github", "agents")
AEMACS_AGENT_DIR: Final[str] = os.path.join(REPO_ROOT, ".aemacs", "agents")
LOCAL_SKILLS_DIR: Final[str] = os.path.join(REPO_ROOT, ".agents", "skills")
LOCAL_ANTIGRAVITY_DIR: Final[str] = os.path.join(REPO_ROOT, ".agents", "agents")

ACTIVE_AGENT_TOOLS: Final[Sequence[str]] = (
    "read_file",
    "write_file",
    "edit_file",
    "run_command",
    "manage_task",
    "ask_question",
    "search_web",
    "generate_image",
    "invoke_subagent",
    "define_subagent",
    "manage_subagents",
    "send_message",
    "schedule",
)

SIMULATION_READONLY_TOOLS: Final[Sequence[str]] = (
    "read_file",
    "ask_question",
    "search_web",
)

SOURCES: Final[Sequence[SourceSpec]] = (
    {
        "file": "coding_ai.md",
        "marker": "### The Specialist Team Roster",
        "type": "specialist",
        "footer_pattern": r"(?m)^## How to Choose.*",
        "split_regex": r"(?m)^\s*-\s+\*\*Role:\*\*\s+",
    },
    {
        "file": "general_ai.md",
        "marker": "### Strategic & Authoring Roles (Your Team)",
        "type": "strategic",
        "footer_pattern": r"(?m)^## How to Choose.*",
        "split_regex": r"(?m)^\s*-\s+\*\*Role:\*\*\s+",
    },
    {
        "file": "stakeholder_ai.md",
        "marker": "## The Core User Base (The Community)",
        "type": "simulation",
        "footer_pattern": r"(?m)^## How to Choose.*",
        "split_regex": r"(?m)^\s*-\s+\*\*Name:\*\*\s+",
    },
)

NAME_MAPPING: Final[Mapping[str, str]] = {
    "professor": "professor",
    "mckarthy": "professor",
    "kael'thas": "kaelthas",
    "kael": "kaelthas",
    "bob": "bob",
    "lector": "lector",
    "freut": "freut",
    "freud": "freut",
    "griznak": "griznak",
    "orb": "orb",
    "magos": "magos",
    "scribe": "veridian",
    "veridian": "veridian",
    "reginald": "reginald",
    "kallista": "kallista",
    "einafetz": "mopfl",
    "mopfl": "mopfl",
    "spacky": "spacky",
    "bzzrts": "bzzrts",
    "vala": "vala",
    "nexus": "nexus",
    "marjin": "marjin",
    "dok": "dok",
    "g.o.l.e.m": "golem",
    "golem": "golem",
    "skeek": "skeek",
    "don testote": "don",
    "don": "don",
    "kairon": "kairon",
    "karl": "karl",
    "bwah": "bwah",
    "resonance": "resonance",
    "haskell": "resonance",
    "zolg": "zolg",
    "clojure": "zolg",
    "chen": "chen",
    "vlad": "vlad",
    "serge": "serge",
    "noobie": "noobie",
    "sarah": "sarah",
}

PROFILE_MAP: Final[Mapping[str, str]] = {
    "mopfl": "profiles/config_wizard.md",
    "spacky": "profiles/elisp.md",
    "bzzrts": "profiles/gfx.md",
    "nexus": "profiles/layers.md",
    "vala": "profiles/ci_github.md",
    "don": "profiles/rust_testing.md",
    "golem": "profiles/doc.md",
    "kairon": "profiles/rust.md",
    "karl": "profiles/python.md",
    "bwah": "profiles/go.md",
    "resonance": "profiles/haskell.md",
    "zolg": "profiles/clojure.md",
}

STRATEGIC_ARTIFACT_CONTRACTS: Final[Mapping[str, ArtifactContract]] = {
    "kaelthas": {
        "upstream_inputs": ("README.md / README.org (if present)", "Existing docs/ context"),
        "output_targets": ("docs/01_product_brief.org",),
        "templates": ("templates/product_brief.org",),
        "instructions": (
            "Clarify vision, scope, frozen product decisions, and risks with the user. "
            "Once aligned (or when asked to draft/update the brief), you MUST write the complete "
            "Org-Mode specification directly to `docs/01_product_brief.org` (or `docs/<epic>/01_product_brief.org` "
            "if scoped to a sub-epic) using `write_file` / `edit_file`, strictly following the template below."
        ),
    },
    "freut": {
        "upstream_inputs": ("docs/01_product_brief.org",),
        "output_targets": ("docs/02_requirements.org",),
        "templates": ("templates/requirements.org",),
        "instructions": (
            "First inspect `docs/01_product_brief.org` via `bat` / `read_file`. "
            "Interrogate ambiguities, surface hidden assumptions, and derive deterministic functional/non-functional "
            "requirements and GIVEN/WHEN/THEN acceptance criteria. Persist the resulting specification directly to "
            "`docs/02_requirements.org` using `write_file` / `edit_file`, strictly following the template below."
        ),
    },
    "bob": {
        "upstream_inputs": ("docs/01_product_brief.org", "docs/02_requirements.org"),
        "output_targets": ("docs/03_architecture.org", "docs/04_work_packages.org"),
        "templates": ("templates/architecture.org", "templates/work_packages.org"),
        "instructions": (
            "First inspect `docs/01_product_brief.org` and `docs/02_requirements.org` via `bat` / `read_file`. "
            "1. Design the concrete system topology, strict data/type schemas, functional purity boundaries, and "
            "security invariants, and write them directly to `docs/03_architecture.org` via `write_file` / `edit_file`.\n"
            "2. Once the architecture is solid/approved, decompose it into isolated, artisan-assigned Org-Mode work "
            "packages (including mandatory test packages for `/don`) and write them directly to `docs/04_work_packages.org`."
        ),
    },
    "veridian": {
        "upstream_inputs": ("docs/01_product_brief.org", "docs/02_requirements.org", "docs/03_architecture.org"),
        "output_targets": ("docs/*.org", "README.md"),
        "templates": (),
        "instructions": (
            "Author and maintain clear, structured Org-Mode or Markdown documentation on disk in `docs/` "
            "using `write_file` / `edit_file`. Never modify implementation source code."
        ),
    },
    "magos": {
        "upstream_inputs": ("docs/01_product_brief.org", "docs/02_requirements.org"),
        "output_targets": ("docs/ui_design_spec.org",),
        "templates": (),
        "instructions": (
            "Define grid-aligned UI layouts, shader/cel-shading visual rules, color tokens, and interaction states. "
            "When a UI design specification is finalized, persist it to `docs/ui_design_spec.org` via `write_file` / `edit_file`."
        ),
    },
}


def atomic_write_text(path: str, content: str, mode: int = 0o644) -> None:
    """Atomically write UTF-8 text to disk via tempfile + fsync + os.replace."""
    parent: str = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=parent, prefix=".tmp_sync_", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_path, mode)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def purge_and_ensure_dir(directory: str) -> None:
    """Idempotent directory management: cleans remnants and recreates directory."""
    if os.path.exists(directory):
        shutil.rmtree(directory)
    os.makedirs(directory, exist_ok=True)


def clean_slug(name: str) -> str:
    """Resolve an agent's display name to its canonical slash-command slug using word boundaries."""
    name_lower: str = name.lower()
    sorted_keys: List[str] = sorted(NAME_MAPPING.keys(), key=len, reverse=True)
    for key in sorted_keys:
        pattern: str = rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])"
        if re.search(pattern, name_lower):
            return NAME_MAPPING[key]
    return name_lower.split()[0].replace(".", "").replace("'", "").strip()


def clean_trailing_rules(text: str) -> str:
    """Strip trailing horizontal rules from parsed markdown blocks."""
    return re.sub(r"(\n\s*[-*]{3,}\s*)+$", "", text.strip()).strip()


def parse_agents_from_text(roster_content: str, source_type: str, split_regex: str) -> List[ParsedAgent]:
    """Parse individual agent persona blocks from a Markdown roster section."""
    agents: List[ParsedAgent] = []
    raw_splits: List[str] = re.split(split_regex, roster_content)
    if len(raw_splits) < 2:
        return agents

    key: str = "Role" if "Role" in split_regex else "Name"
    for raw_chunk in raw_splits[1:]:
        chunk: str = re.split(r"(?m)^#{2,3} ", raw_chunk)[0]
        role: str = "Unknown"
        name: str = "Unknown"

        if key == "Role":
            role = chunk.split("\n")[0].strip()
            name_match = re.search(r"-\s+\*\*Name:\*\*\s+(.*?)$", chunk, re.MULTILINE)
            name = name_match.group(1).strip() if name_match else "Unknown"
        else:
            name = chunk.split("\n")[0].strip()
            role_match = re.search(r"-\s+\*\*Role:\*\*\s+(.*?)$", chunk, re.MULTILINE)
            role = role_match.group(1).strip() if role_match else "Simulation Persona"

        slug_name: str = clean_slug(name)
        full_body: str = f"- **{key}:** {chunk.strip()}"
        agents.append(
            {
                "name": name,
                "slug": slug_name,
                "role": role,
                "body": full_body,
                "type": source_type,
            }
        )
    return agents


def load_ai_asset(rel_path: str) -> str:
    """Read a profile or template file relative to SCRIPT_DIR (`ai/`)."""
    abs_path: str = os.path.join(SCRIPT_DIR, rel_path)
    if not os.path.exists(abs_path):
        print(f"⚠️ Warning: Asset file '{abs_path}' not found.")
        return f"<!-- Warning: Asset {rel_path} not found at build time -->"
    with open(abs_path, "r", encoding="utf-8") as asset_file:
        return asset_file.read().strip()


def build_execution_and_handoff_section(slug: str, agent_type: str, runtime_prefix: str) -> str:
    """Build the execution mode and deterministic Org-Mode file-handoff contract."""
    if agent_type == "strategic":
        contract: Optional[ArtifactContract] = STRATEGIC_ARTIFACT_CONTRACTS.get(slug)
        base_mode: str = (
            "MODE: STRATEGIC PLANNING, REQUIREMENTS & ARCHITECTURE\n"
            "(Focus on high-level design, user stories, formal data contracts, and work-package decomposition. "
            "Never write `.rs`/`.clj`/`.py`/`.hs`/`.go` implementation code, MUST persist `.org` specs in `docs/`.)\n"
        )
        if not contract:
            return (
                f"{base_mode}\n"
                "## Artifact Persistence Rule (`docs/*.org`)\n"
                "- When asked to produce or update a plan, audit, release checklist, or configuration blueprint, "
                "persist it cleanly inside `docs/` as an `.org` file using `write_file` / `edit_file`.\n"
            )

        inputs_str: str = ", ".join(f"`{p}`" for p in contract["upstream_inputs"])
        outputs_str: str = ", ".join(f"`{p}`" for p in contract["output_targets"])
        section_lines: List[str] = [
            base_mode,
            "## Mandatory Org-Mode File-Handoff Contract",
            f"- **Upstream Inputs to Read First:** {inputs_str}",
            f"- **Canonical Output File(s) to Write/Update on Disk:** {outputs_str}",
            f"- **Execution Rule:** {contract['instructions']}",
        ]
        for tpl_rel in contract["templates"]:
            tpl_name: str = os.path.basename(tpl_rel)
            tpl_runtime_path: str = f"{runtime_prefix}/{tpl_rel}"
            tpl_body: str = load_ai_asset(tpl_rel)
            section_lines.append(
                f"\n### Loaded Org-Mode Template: `{tpl_runtime_path}` (`{tpl_name}`)\n"
                f"```org\n{tpl_body}\n```"
            )
        return "\n".join(section_lines) + "\n"

    if agent_type == "specialist":
        return (
            "MODE: IMPLEMENTATION, TESTING & CRAFTSMANSHIP\n"
            "(Focus on concrete, strictly typed, functionally pure code and deterministic tests adhering to your loaded profile.)\n\n"
            "## Mandatory Work-Package & File Persistence Contract\n"
            "1. **Read Specs First:** If `docs/04_work_packages.org` and `docs/03_architecture.org` exist, inspect your assigned "
            "`WP-XXX` block and data contracts via `bat` before writing code.\n"
            "2. **Persist Code & Verify:** Write implementation and test files directly to the repository using `write_file`, "
            "`edit_file`, `sd`, or `ast-grep`, and verify compilation/linters/tests via `run_command`.\n"
            "3. **Update Work-Package Status:** After all acceptance criteria pass, update ONLY your owned `WP-XXX` heading state "
            "(`OPEN` -> `IN_PROGRESS` -> `FINISHED`) in `docs/04_work_packages.org`.\n"
        )

    if agent_type == "simulation":
        return (
            "MODE: VIRTUAL STAKEHOLDER SIMULATION (STRICTLY READ-ONLY)\n"
            "(Provide authentic, persona-consistent usability feedback, friction reports, and user scenarios in chat only. "
            "NEVER write code or modify files.)\n"
        )

    return ""


def build_toolbox_section(slug: str, agent_type: str, profile_rel: Optional[str], runtime_prefix: str) -> str:
    """Build the Toolbox Markdown section with inlined profile content."""
    if profile_rel:
        profile_filename: str = os.path.basename(profile_rel)
        profile_alias: str = f"profile_{profile_filename}"
        runtime_path: str = f"{runtime_prefix}/{profile_rel}"
        embedded_profile: str = load_ai_asset(profile_rel)
        extra_note: str = ""
        if slug == "don":
            extra_note = (
                f"\n> **Multi-Language Testing Note:** `rust_testing.md` is pre-loaded below by default. "
                f"When testing Clojure, Python, Haskell, Go, or Elisp, also read `{runtime_prefix}/profiles/<lang>_testing.md` "
                f"via `bat` before writing tests!\n"
            )
        return (
            f"\n# Toolbox (Auto-Loaded)\n"
            f"## Loaded Profile: `{runtime_path}` (`{profile_alias}` — STATUS: LOADED)\n"
            f"{extra_note}\n"
            f"{embedded_profile}\n"
        )
    if agent_type == "specialist":
        return (
            f"\n# Toolbox (Dynamic Runtime Profile)\n"
            f"⚠️ No fixed default profile is pre-bound to `{slug}`. Before modifying code, inspect the target language "
            f"and read the matching profile from `{runtime_prefix}/profiles/` (e.g., `rust.md`, `clojure.md`, "
            f"`python.md`, `haskell.md`, `go.md`, `gfx.md`, `ci_github.md`, `doc.md`) via `bat`, or ask the user if ambiguous.\n"
        )
    return ""


def generate_copilot_files(global_headers: Mapping[str, str], agents: Sequence[ParsedAgent]) -> None:
    """Generate GitHub Copilot agent definitions in `.github/agents/`."""
    print(f"📝 Generating GitHub Copilot Agents in {COPILOT_AGENTS_DIR}...")
    purge_and_ensure_dir(COPILOT_AGENTS_DIR)

    for agent in agents:
        slug: str = agent["slug"]
        path: str = os.path.join(COPILOT_AGENTS_DIR, f"{slug}.agent.md")
        yaml_front: str = f"---\nname: {slug}\ndescription: {agent['role']}\nmodel: gpt-5.4\n---"
        context: str = global_headers.get(agent["type"], "")
        exec_section: str = build_execution_and_handoff_section(slug, agent["type"], "ai")
        body_clean: str = clean_trailing_rules(agent["body"])
        toolbox_text: str = build_toolbox_section(slug, agent["type"], PROFILE_MAP.get(slug), "ai")

        content: str = (
            f"{yaml_front}\n\n{context}\n\n---\n\n"
            f"# Identity: {agent['name']}\n{body_clean}\n{toolbox_text}\n---\n\n"
            f"# Execution Mode\n{exec_section}"
        )
        atomic_write_text(path, content)

    print(f"   Generated {len(agents)} Copilot agent files.")


def generate_aemacs_native_files(global_headers: Mapping[str, str], agents: Sequence[ParsedAgent]) -> None:
    """Generate Native Æmacs YAML agent definitions in `.aemacs/agents/`."""
    print(f"🐍 Generating Native Æmacs Agents in {AEMACS_AGENT_DIR}...")
    purge_and_ensure_dir(AEMACS_AGENT_DIR)

    for agent in agents:
        slug: str = agent["slug"]
        system_header: str = global_headers.get(agent["type"], "")
        body_clean: str = clean_trailing_rules(agent["body"])
        exec_section: str = build_execution_and_handoff_section(slug, agent["type"], "ai")
        toolbox_section: str = build_toolbox_section(slug, agent["type"], PROFILE_MAP.get(slug), "ai")

        full_prompt: str = (
            f"SYSTEM INSTRUCTIONS:\n{system_header}\n\n"
            f"---\nAGENT PERSONA:\n{body_clean}\n\n"
            f"---\n{exec_section.strip()}\n"
            f"{toolbox_section}"
        )
        indented_prompt: str = "\n".join(f"    {line}" for line in full_prompt.strip().split("\n"))
        clean_desc: str = agent["role"].replace('"', "'")
        yaml_content: str = (
            f'name: "{slug}"\n'
            f'description: "{clean_desc}"\n'
            f"system_prompt: |\n{indented_prompt}\n"
        )
        atomic_write_text(os.path.join(AEMACS_AGENT_DIR, f"{slug}.yaml"), yaml_content)

    print(f"   Generated {len(agents)} native Æmacs agent souls.")


def render_antigravity_markdown(
    agent: ParsedAgent,
    system_header: str,
    runtime_prefix: str,
) -> str:
    """Render a single Antigravity v1.5.2 Markdown agent file with role-scoped tools."""
    slug: str = agent["slug"]
    agent_type: str = agent["type"]
    is_simulation: bool = agent_type == "simulation"
    tool_list: Sequence[str] = SIMULATION_READONLY_TOOLS if is_simulation else ACTIVE_AGENT_TOOLS
    inherit_mcp: str = "false" if is_simulation else "true"
    tools_yaml: str = "\n".join(f"  - {tool}" for tool in tool_list)

    body_clean: str = clean_trailing_rules(agent["body"])
    exec_section: str = build_execution_and_handoff_section(slug, agent_type, runtime_prefix)
    toolbox_section: str = build_toolbox_section(slug, agent_type, PROFILE_MAP.get(slug), runtime_prefix)
    clean_desc: str = agent["role"].replace('"', "'")

    return (
        f"---\n"
        f"name: {slug}\n"
        f'description: "{clean_desc}"\n'
        f"mainAgent: true\n"
        f"subagent: true\n"
        f"hidden: false\n"
        f"model: inherit\n"
        f"commandExecutionPolicy: sandbox\n"
        f"inheritMcp: {inherit_mcp}\n"
        f"tools:\n"
        f"{tools_yaml}\n"
        f"---\n\n"
        f"# System Instructions\n"
        f"{system_header}\n\n"
        f"---\n\n"
        f"# Identity: {agent['name']}\n"
        f"{body_clean}\n\n"
        f"---\n\n"
        f"# Execution Mode\n"
        f"{exec_section}"
        f"{toolbox_section}\n"
    )


def generate_local_antigravity_files(global_headers: Mapping[str, str], agents: Sequence[ParsedAgent]) -> None:
    """Generate repo-local Antigravity v1.5.2 agents inside `.agents/agents/`."""
    if os.path.exists(LOCAL_SKILLS_DIR):
        print(f"🧹 Removing legacy Antigravity Skills directory {LOCAL_SKILLS_DIR}...")
        shutil.rmtree(LOCAL_SKILLS_DIR)

    print(f"🌌 Generating repo-local Antigravity Agents in {LOCAL_ANTIGRAVITY_DIR}...")
    purge_and_ensure_dir(LOCAL_ANTIGRAVITY_DIR)
    for agent in agents:
        header_local: str = global_headers.get(agent["type"], "")
        md_local: str = render_antigravity_markdown(agent, header_local, "ai")
        atomic_write_text(os.path.join(LOCAL_ANTIGRAVITY_DIR, f"{agent['slug']}.md"), md_local)
    print(f"   Generated {len(agents)} repo-local Antigravity agents.")


def main() -> None:
    """Parse all local Æmacs persona rosters and generate Copilot, Native Æmacs, and Antigravity targets."""
    all_agents: List[ParsedAgent] = []
    global_headers: dict[str, str] = {}

    for source in SOURCES:
        file_path: str = os.path.join(SCRIPT_DIR, source["file"])
        if not os.path.exists(file_path):
            print(f"❌ Error: {file_path} not found.")
            continue

        print(f"🚀 Reading {source['file']}...")
        with open(file_path, "r", encoding="utf-8") as source_file:
            full_content: str = source_file.read()

        marker: str = source["marker"]
        if marker not in full_content:
            print(f"⚠️ Warning: Marker '{marker}' not found in {source['file']}.")
            continue

        parts: List[str] = full_content.split(marker, maxsplit=1)
        header_raw: str = parts[0]
        roster_raw: str = parts[1]
        header: str = clean_trailing_rules(header_raw)

        footer_pattern: Optional[str] = source.get("footer_pattern")
        if footer_pattern:
            footer_match = re.search(footer_pattern, roster_raw, re.DOTALL)
            if footer_match:
                split_index: int = footer_match.start()
                footer_content: str = roster_raw[split_index:]
                roster_raw = roster_raw[:split_index]
                header = f"{header}\n\n---\n{footer_content.strip()}"

        global_headers[source["type"]] = header
        parsed: List[ParsedAgent] = parse_agents_from_text(roster_raw, source["type"], source["split_regex"])
        all_agents.extend(parsed)
        print(f"   Found {len(parsed)} agents: {[a['slug'] for a in parsed]}")

    generate_copilot_files(global_headers, all_agents)
    generate_local_antigravity_files(global_headers, all_agents)
    generate_aemacs_native_files(global_headers, all_agents)

    print("\n✅ Done! Synced all local Æmacs agent targets.")


if __name__ == "__main__":
    main()
