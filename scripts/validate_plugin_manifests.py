#!/usr/bin/env python3
"""Codex plugin manifests and marketplace registration validator."""

import argparse
import json
import os
import pathlib
import re
import sys
import urllib.parse

REPOSITORY_URL = "https://github.com/pallgeuer/la-dev-codex-plugins"
LATEST_DOCUMENTATION_URL_PREFIX = REPOSITORY_URL + "/blob/main/"
AUTHOR_NAME = "pallgeuer"
AUTHOR_URL = "https://github.com/pallgeuer"
MARKETPLACE_NAME = "la-dev-codex-plugins"
LICENSE = "MIT"
HEX_COLOR_RE = re.compile(r"#[0-9A-Fa-f]{6}")
PLUGIN_NAME_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?")
STABLE_VERSION_RE = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
APP_ID_RE = re.compile(r"(?:asdk_app|connector|templated_apps)_[A-Za-z0-9][A-Za-z0-9_-]*")
MANIFEST_FIELDS = {"id", "name", "version", "description", "author", "homepage", "repository", "license", "keywords", "skills", "apps", "mcpServers", "interface"}
AUTHOR_FIELDS = {"name", "email", "url"}
INTERFACE_FIELDS = {
    "displayName",
    "shortDescription",
    "longDescription",
    "developerName",
    "category",
    "capabilities",
    "websiteURL",
    "privacyPolicyURL",
    "termsOfServiceURL",
    "brandColor",
    "composerIcon",
    "logo",
    "logoDark",
    "screenshots",
    "defaultPrompt",
    "default_prompt",
}
MARKETPLACE_FIELDS = {"name", "interface", "plugins"}
MARKETPLACE_INTERFACE_FIELDS = {"displayName"}
MARKETPLACE_PLUGIN_FIELDS = {"name", "source", "policy", "category"}
MARKETPLACE_SOURCE_FIELDS = {"source", "path"}
MARKETPLACE_POLICY_FIELDS = {"installation", "authentication", "products"}
INSTALLATION_POLICIES = {"NOT_AVAILABLE", "AVAILABLE", "INSTALLED_BY_DEFAULT"}
AUTHENTICATION_POLICIES = {"ON_INSTALL", "ON_USE"}
MARKETPLACE_PRODUCTS = {"ATLAS", "CHATGPT", "CODEX"}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(pathlib.Path(__file__).resolve().parents[1]), help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def add_error(errors, location, message):
    errors.append("{}: {}".format(location, message))


def load_json_object(path, location, errors):
    try:
        with path.open("r", encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, UnicodeError, ValueError) as error:
        add_error(errors, location, "must be readable UTF-8 JSON: {}".format(error))
        return None
    if not isinstance(value, dict):
        add_error(errors, location, "must contain a JSON object")
        return None
    return value


def reject_unknown_fields(value, allowed, location, errors):
    for field in sorted(set(value) - allowed):
        add_error(errors, location, "unsupported field {!r}".format(field))


def require_object(value, field, location, errors):
    child = value.get(field)
    if not isinstance(child, dict):
        add_error(errors, location, "field {!r} must be an object".format(field))
        return None
    return child


def require_string(value, field, location, errors):
    child = value.get(field)
    if not isinstance(child, str) or not child.strip():
        add_error(errors, location, "field {!r} must be a nonempty string".format(field))
        return None
    return child


def validate_https_url(value, field, location, errors):
    url = require_string(value, field, location, errors)
    if url is None:
        return None
    try:
        parsed = urllib.parse.urlsplit(url)
        hostname = parsed.hostname
        _parsed_port = parsed.port
    except ValueError:
        add_error(errors, location, "field {!r} must be an absolute HTTPS URL".format(field))
        return None
    has_unsupported_character = any(ord(character) <= 32 or ord(character) == 127 for character in url)
    if parsed.scheme != "https" or not parsed.netloc or hostname is None or parsed.username is not None or parsed.password is not None or has_unsupported_character:
        add_error(errors, location, "field {!r} must be an absolute HTTPS URL without credentials or unsupported characters".format(field))
        return None
    return url


def validate_optional_https_url(value, field, location, errors):
    if field in value:
        validate_https_url(value, field, location, errors)


def validate_string_list(value, field, location, errors, minimum=0, maximum=None):
    child = value.get(field)
    if not isinstance(child, list) or not all(isinstance(item, str) and item.strip() for item in child):
        add_error(errors, location, "field {!r} must be an array of nonempty strings".format(field))
        return None
    if len(child) < minimum:
        add_error(errors, location, "field {!r} must contain at least {} entries".format(field, minimum))
    if maximum is not None and len(child) > maximum:
        add_error(errors, location, "field {!r} must contain at most {} entries".format(field, maximum))
    return child


def path_uses_symlink(base, path):
    try:
        relative_path = path.relative_to(base)
    except ValueError:
        return False
    candidate = base
    if candidate.is_symlink():
        return True
    for part in relative_path.parts:
        candidate = candidate / part
        if candidate.is_symlink():
            return True
    return False


def validate_component_path(plugin_root, raw_path, location, errors, expected_kind=None):
    if not isinstance(raw_path, str) or not raw_path.startswith("./"):
        add_error(errors, location, "must be a relative plugin path beginning with './'")
        return None
    pure_path = pathlib.PurePosixPath(raw_path)
    if pure_path.is_absolute() or ".." in pure_path.parts or not pure_path.parts:
        add_error(errors, location, "must remain inside the plugin root")
        return None
    plugin_real = os.path.realpath(str(plugin_root))
    candidate = plugin_root.joinpath(*pure_path.parts)
    candidate_real = os.path.realpath(str(candidate))
    try:
        inside_plugin = os.path.commonpath((plugin_real, candidate_real)) == plugin_real
    except ValueError:
        inside_plugin = False
    if not inside_plugin:
        add_error(errors, location, "resolves outside the plugin root")
        return None
    if path_uses_symlink(plugin_root, candidate):
        add_error(errors, location, "must not use symbolic links")
        return None
    if expected_kind == "directory" and not candidate.is_dir():
        add_error(errors, location, "must reference an existing directory")
        return None
    if expected_kind == "file" and not candidate.is_file():
        add_error(errors, location, "must reference an existing file")
        return None
    return candidate


def validate_homepage(repo_root, manifest, location, errors):
    homepage = validate_https_url(manifest, "homepage", location, errors)
    if homepage is None:
        return None
    if not homepage.startswith(LATEST_DOCUMENTATION_URL_PREFIX):
        add_error(errors, location, "field 'homepage' must link directly to the latest product documentation on the canonical main branch")
        return homepage
    relative_path = homepage[len(LATEST_DOCUMENTATION_URL_PREFIX) :]
    pure_path = pathlib.PurePosixPath(relative_path)
    if pure_path.is_absolute() or ".." in pure_path.parts or not relative_path.startswith("docs/") or pure_path.suffix != ".md":
        add_error(errors, location, "field 'homepage' must identify a Markdown product guide below docs/")
        return homepage
    target = repo_root.joinpath(*pure_path.parts)
    if path_uses_symlink(repo_root, target):
        add_error(errors, location, "field 'homepage' must not target documentation through symbolic links")
        return homepage
    if not target.is_file():
        add_error(errors, location, "field 'homepage' targets missing local documentation {}".format(relative_path))
    return homepage


def validate_author(manifest, location, errors):
    author = require_object(manifest, "author", location, errors)
    if author is None:
        return
    reject_unknown_fields(author, AUTHOR_FIELDS, location + ".author", errors)
    name = require_string(author, "name", location + ".author", errors)
    url = validate_https_url(author, "url", location + ".author", errors)
    if "email" in author:
        require_string(author, "email", location + ".author", errors)
    if name is not None and name != AUTHOR_NAME:
        add_error(errors, location + ".author", "field 'name' must identify the canonical publisher {!r}".format(AUTHOR_NAME))
    if url is not None and url != AUTHOR_URL:
        add_error(errors, location + ".author", "field 'url' must identify the canonical publisher profile")


def validate_keywords(manifest, location, errors):
    keywords = validate_string_list(manifest, "keywords", location, errors, minimum=1)
    if keywords is None:
        return
    normalized = [keyword.strip() for keyword in keywords]
    if normalized != keywords or any(keyword.lower() != keyword for keyword in keywords):
        add_error(errors, location, "field 'keywords' entries must be trimmed lowercase strings")
    if len(set(keywords)) != len(keywords):
        add_error(errors, location, "field 'keywords' entries must be unique")


def validate_interface(plugin_root, manifest, homepage, location, errors):
    interface = require_object(manifest, "interface", location, errors)
    if interface is None:
        return None
    interface_location = location + ".interface"
    reject_unknown_fields(interface, INTERFACE_FIELDS, interface_location, errors)
    for field in ("displayName", "shortDescription", "longDescription", "category"):
        require_string(interface, field, interface_location, errors)
    developer_name = require_string(interface, "developerName", interface_location, errors)
    if developer_name is not None and developer_name != AUTHOR_NAME:
        add_error(errors, interface_location, "field 'developerName' must identify the canonical publisher {!r}".format(AUTHOR_NAME))
    capabilities = validate_string_list(interface, "capabilities", interface_location, errors, minimum=1)
    if capabilities is not None and len(set(capabilities)) != len(capabilities):
        add_error(errors, interface_location, "field 'capabilities' entries must be unique")
    website_url = validate_https_url(interface, "websiteURL", interface_location, errors)
    if homepage is not None and website_url is not None and website_url != homepage:
        add_error(errors, interface_location, "field 'websiteURL' must match the direct product homepage")
    for field in ("privacyPolicyURL", "termsOfServiceURL"):
        validate_optional_https_url(interface, field, interface_location, errors)
    if "brandColor" in interface:
        brand_color = require_string(interface, "brandColor", interface_location, errors)
        if brand_color is not None and HEX_COLOR_RE.fullmatch(brand_color) is None:
            add_error(errors, interface_location, "field 'brandColor' must use #RRGGBB notation")
    prompts_field = "defaultPrompt" if "defaultPrompt" in interface or "default_prompt" not in interface else "default_prompt"
    if "defaultPrompt" in interface and "default_prompt" in interface:
        add_error(errors, interface_location, "must not declare both 'defaultPrompt' and 'default_prompt'")
    prompts = validate_string_list(interface, prompts_field, interface_location, errors, minimum=1, maximum=3)
    if prompts is not None:
        for index, prompt in enumerate(prompts):
            if len(prompt) > 128:
                add_error(errors, "{}.{}[{}]".format(interface_location, prompts_field, index), "must not exceed 128 characters")
    for field in ("composerIcon", "logo", "logoDark"):
        if field in interface:
            path = validate_component_path(plugin_root, interface[field], "{}.{}".format(interface_location, field), errors, expected_kind="file")
            if path is not None and pathlib.PurePosixPath(interface[field]).parts[:1] != ("assets",):
                add_error(errors, "{}.{}".format(interface_location, field), "must remain below the plugin assets directory")
    screenshots = interface.get("screenshots", [])
    if not isinstance(screenshots, list):
        add_error(errors, interface_location, "field 'screenshots' must be an array")
    else:
        for index, screenshot in enumerate(screenshots):
            path = validate_component_path(plugin_root, screenshot, "{}.screenshots[{}]".format(interface_location, index), errors, expected_kind="file")
            if path is not None and (path.suffix.lower() != ".png" or pathlib.PurePosixPath(screenshot).parts[:1] != ("assets",)):
                add_error(errors, "{}.screenshots[{}]".format(interface_location, index), "must reference a PNG below the plugin assets directory")
    return interface


def validate_skill_manifests(repo_root, skills_path, location, errors):
    skill_manifest_count = 0
    for skill_path in sorted(skills_path.iterdir()):
        if skill_path.is_symlink():
            add_error(errors, str(skill_path.relative_to(repo_root)), "skill directories must not use symbolic links")
            continue
        if not skill_path.is_dir():
            continue
        skill_manifest = skill_path / "SKILL.md"
        if skill_manifest.is_symlink():
            add_error(errors, str(skill_manifest.relative_to(repo_root)), "skill manifests must not use symbolic links")
        elif skill_manifest.is_file():
            skill_manifest_count += 1
    if skill_manifest_count == 0:
        add_error(errors, location, "must contain at least one regular skill manifest")


def validate_app_manifest(repo_root, app_path, errors):
    location = str(app_path.relative_to(repo_root))
    app_manifest = load_json_object(app_path, location, errors)
    if app_manifest is None:
        return
    apps = require_object(app_manifest, "apps", location, errors)
    if apps is None:
        return
    for app_name in sorted(apps):
        app_location = "{}.apps[{!r}]".format(location, app_name)
        app = apps[app_name]
        if not isinstance(app, dict):
            add_error(errors, app_location, "must be an object")
            continue
        app_id = require_string(app, "id", app_location, errors)
        if app_id is not None and APP_ID_RE.fullmatch(app_id) is None:
            add_error(errors, app_location, "field 'id' must use a supported registered app identifier")
        for field in ("optional", "required"):
            if field in app and not isinstance(app[field], bool):
                add_error(errors, app_location, "field {!r} must be a boolean".format(field))


def validate_mcp_manifest(repo_root, mcp_path, errors):
    location = str(mcp_path.relative_to(repo_root))
    mcp_manifest = load_json_object(mcp_path, location, errors)
    if mcp_manifest is None:
        return
    mcp_servers = require_object(mcp_manifest, "mcpServers", location, errors)
    if mcp_servers is None:
        return
    for server_name in sorted(mcp_servers):
        server_location = "{}.mcpServers[{!r}]".format(location, server_name)
        if not isinstance(server_name, str) or not server_name.strip():
            add_error(errors, server_location, "server names must be nonempty strings")
        if not isinstance(mcp_servers[server_name], dict):
            add_error(errors, server_location, "must be an object")


def validate_manifest(repo_root, plugin_root, errors):
    manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    location = str(manifest_path.relative_to(repo_root))
    manifest_parent = manifest_path.parent
    if manifest_parent.is_symlink():
        add_error(errors, str(manifest_parent.relative_to(repo_root)), "manifest directory must not use symbolic links")
        return None
    if not manifest_parent.is_dir():
        if manifest_parent.exists():
            add_error(errors, str(manifest_parent.relative_to(repo_root)), "manifest parent must be a directory")
        else:
            add_error(errors, location, "plugin manifest is missing")
        return None
    if manifest_path.is_symlink():
        add_error(errors, location, "plugin manifest must not use symbolic links")
        return None
    if not manifest_path.is_file():
        add_error(errors, location, "plugin manifest must be a regular file")
        return None
    manifest = load_json_object(manifest_path, location, errors)
    if manifest is None:
        return None
    reject_unknown_fields(manifest, MANIFEST_FIELDS, location, errors)
    if "id" in manifest:
        require_string(manifest, "id", location, errors)
    name = require_string(manifest, "name", location, errors)
    version = require_string(manifest, "version", location, errors)
    require_string(manifest, "description", location, errors)
    if name is not None:
        if PLUGIN_NAME_RE.fullmatch(name) is None:
            add_error(errors, location, "field 'name' must use lowercase hyphen-case and contain at most 64 characters")
        if name != plugin_root.name:
            add_error(errors, location, "field 'name' must match plugin directory {!r}".format(plugin_root.name))
    if version is not None and STABLE_VERSION_RE.fullmatch(version) is None:
        add_error(errors, location, "field 'version' must use stable X.Y.Z Semantic Versioning")
    validate_author(manifest, location, errors)
    homepage = validate_homepage(repo_root, manifest, location, errors)
    repository = validate_https_url(manifest, "repository", location, errors)
    if repository is not None and repository != REPOSITORY_URL:
        add_error(errors, location, "field 'repository' must identify the canonical repository")
    license_name = require_string(manifest, "license", location, errors)
    if license_name is not None and license_name != LICENSE:
        add_error(errors, location, "field 'license' must match the repository license {!r}".format(LICENSE))
    validate_keywords(manifest, location, errors)
    skills = require_string(manifest, "skills", location, errors)
    skills_path = validate_component_path(plugin_root, skills, location + ".skills", errors, expected_kind="directory") if skills is not None else None
    if skills is not None and pathlib.PurePosixPath(skills) != pathlib.PurePosixPath("skills"):
        add_error(errors, location + ".skills", "must identify the conventional ./skills/ directory")
    if skills_path is not None:
        validate_skill_manifests(repo_root, skills_path, location + ".skills", errors)
    if "apps" in manifest:
        apps_path = validate_component_path(plugin_root, manifest["apps"], location + ".apps", errors, expected_kind="file")
        if apps_path is not None and pathlib.PurePosixPath(manifest["apps"]) != pathlib.PurePosixPath(".app.json"):
            add_error(errors, location + ".apps", "must identify ./.app.json")
        elif apps_path is not None:
            validate_app_manifest(repo_root, apps_path, errors)
    if "mcpServers" in manifest:
        mcp_servers = manifest["mcpServers"]
        mcp_path = validate_component_path(plugin_root, mcp_servers, location + ".mcpServers", errors, expected_kind="file")
        if mcp_path is not None and pathlib.PurePosixPath(mcp_servers) != pathlib.PurePosixPath(".mcp.json"):
            add_error(errors, location + ".mcpServers", "must identify ./.mcp.json")
        elif mcp_path is not None:
            validate_mcp_manifest(repo_root, mcp_path, errors)
    interface = validate_interface(plugin_root, manifest, homepage, location, errors)
    return {"name": name, "interface": interface, "manifest": manifest}


def validate_marketplace(repo_root, manifests, errors):
    marketplace_path = repo_root / ".agents" / "plugins" / "marketplace.json"
    location = str(marketplace_path.relative_to(repo_root))
    marketplace = load_json_object(marketplace_path, location, errors)
    if marketplace is None:
        return
    reject_unknown_fields(marketplace, MARKETPLACE_FIELDS, location, errors)
    name = require_string(marketplace, "name", location, errors)
    if name is not None and name != MARKETPLACE_NAME:
        add_error(errors, location, "field 'name' must be {!r}".format(MARKETPLACE_NAME))
    interface = require_object(marketplace, "interface", location, errors)
    if interface is not None:
        reject_unknown_fields(interface, MARKETPLACE_INTERFACE_FIELDS, location + ".interface", errors)
        require_string(interface, "displayName", location + ".interface", errors)
    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list):
        add_error(errors, location, "field 'plugins' must be an array")
        return
    marketplace_names = []
    seen_marketplace_names = set()
    duplicate_names = set()
    for index, entry in enumerate(plugins):
        entry_location = "{}.plugins[{}]".format(location, index)
        if not isinstance(entry, dict):
            add_error(errors, entry_location, "must be an object")
            continue
        reject_unknown_fields(entry, MARKETPLACE_PLUGIN_FIELDS, entry_location, errors)
        plugin_name = require_string(entry, "name", entry_location, errors)
        if plugin_name is not None:
            marketplace_names.append(plugin_name)
            if plugin_name in seen_marketplace_names:
                duplicate_names.add(plugin_name)
            seen_marketplace_names.add(plugin_name)
        source = require_object(entry, "source", entry_location, errors)
        if source is not None:
            reject_unknown_fields(source, MARKETPLACE_SOURCE_FIELDS, entry_location + ".source", errors)
            source_type = require_string(source, "source", entry_location + ".source", errors)
            source_path = require_string(source, "path", entry_location + ".source", errors)
            if source_type is not None and source_type != "local":
                add_error(errors, entry_location + ".source", "field 'source' must be 'local'")
            if plugin_name is not None and source_path is not None and source_path != "./plugins/{}".format(plugin_name):
                add_error(errors, entry_location + ".source", "field 'path' must match the plugin identity")
        policy = require_object(entry, "policy", entry_location, errors)
        if policy is not None:
            reject_unknown_fields(policy, MARKETPLACE_POLICY_FIELDS, entry_location + ".policy", errors)
            installation = require_string(policy, "installation", entry_location + ".policy", errors)
            authentication = require_string(policy, "authentication", entry_location + ".policy", errors)
            if installation is not None and installation not in INSTALLATION_POLICIES:
                add_error(errors, entry_location + ".policy", "field 'installation' uses an unsupported policy")
            if authentication is not None and authentication not in AUTHENTICATION_POLICIES:
                add_error(errors, entry_location + ".policy", "field 'authentication' uses an unsupported policy")
            if "products" in policy:
                products = validate_string_list(policy, "products", entry_location + ".policy", errors, minimum=1)
                if products is not None:
                    if len(set(products)) != len(products):
                        add_error(errors, entry_location + ".policy", "field 'products' entries must be unique")
                    for product in products:
                        if product not in MARKETPLACE_PRODUCTS:
                            add_error(errors, entry_location + ".policy", "field 'products' entry {!r} is unsupported".format(product))
        category = require_string(entry, "category", entry_location, errors)
        manifest = manifests.get(plugin_name)
        if manifest is not None and manifest["interface"] is not None and category is not None and category != manifest["interface"].get("category"):
            add_error(errors, entry_location, "field 'category' must match the plugin interface category")
    for duplicate_name in sorted(duplicate_names):
        add_error(errors, location, "plugin {!r} is registered more than once".format(duplicate_name))
    manifest_names = set(manifests)
    marketplace_name_set = set(marketplace_names)
    for missing_name in sorted(manifest_names - marketplace_name_set):
        add_error(errors, location, "plugin {!r} has no marketplace registration".format(missing_name))
    for unknown_name in sorted(marketplace_name_set - manifest_names):
        add_error(errors, location, "marketplace plugin {!r} has no local manifest".format(unknown_name))


def validate_repository(repo_root):
    repo_root = pathlib.Path(repo_root).resolve()
    errors = []
    plugins_root = repo_root / "plugins"
    if plugins_root.is_symlink():
        add_error(errors, "plugins", "plugin root directory must not use symbolic links")
        return errors, 0
    if not plugins_root.is_dir():
        add_error(errors, "plugins", "plugin root directory is missing")
        return errors, 0
    plugin_roots = []
    for path in sorted(plugins_root.iterdir()):
        if path.is_symlink():
            add_error(errors, str(path.relative_to(repo_root)), "plugin directories must not use symbolic links")
        elif path.is_dir():
            plugin_roots.append(path)
    manifests = {}
    for plugin_root in plugin_roots:
        result = validate_manifest(repo_root, plugin_root, errors)
        if result is not None and result["name"] is not None:
            if result["name"] in manifests:
                add_error(errors, "plugins", "plugin identity {!r} is declared by more than one manifest".format(result["name"]))
            manifests[result["name"]] = result
    validate_marketplace(repo_root, manifests, errors)
    return errors, len(plugin_roots)


def main(argv=None):
    args = parse_args(argv)
    errors, plugin_count = validate_repository(args.repo_root)
    if errors:
        for error in errors:
            print("error: {}".format(error), file=sys.stderr)
        return 1
    print("Validated {} plugin manifests and marketplace registrations.".format(plugin_count))
    return 0


if __name__ == "__main__":
    sys.exit(main())
