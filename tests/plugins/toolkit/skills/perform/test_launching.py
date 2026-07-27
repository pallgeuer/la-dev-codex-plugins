"""Standalone launcher API and Codex argv tests."""

import importlib
import json

import pytest

diagnostics_module = importlib.import_module("toolkit_perform_runtime.diagnostics")
launching_module = importlib.import_module("toolkit_perform_runtime.launching")
rendering_module = importlib.import_module("toolkit_perform_runtime.rendering")
validation_module = importlib.import_module("toolkit_perform_runtime.validation")


def make_catalog(tmp_path, complete, file_data, write_file, load_catalog, **updates):
    """Create one explicit action catalog for launch tests."""
    source = tmp_path / "source"
    write_file(source, file_data(actions={"test": {"python": complete(**updates)}}))
    return load_catalog(source)


def test_launch_config_preserves_every_action_field_and_isolation(tmp_path, complete, file_data, write_file, load_catalog):
    fields = complete(
        gloss="Launch test",
        model="gpt-5",
        reasoning_effort="high",
        goal_mode=True,
        plan_reasoning_effort="high",
        no_edits=True,
        prompt_vars={"Target": "Target"},
        prompt="Inspect %Target%.",
        requires_interactive=False,
        custom_codex_args=["--search"],
        notes="Visible note.",
    )
    catalog = make_catalog(tmp_path, complete, file_data, write_file, load_catalog, **fields)
    config = catalog.launch_config("test[python]")
    fields["prompt_vars"]["Later"] = "Mutation"
    fields["custom_codex_args"].append("--later")
    payload = config.to_dict()
    assert config.custom_codex_args == ("--search",)
    assert not hasattr(config, "interactive")
    assert payload["selector"] == "test[python]"
    assert payload["name"] == "test"
    assert payload["language"] == "python"
    assert list(payload["action"]) == list(validation_module.ACTION_FIELDS)
    assert payload["action"] == {
        "gloss": "Launch test",
        "model": "gpt-5",
        "reasoning_effort": "high",
        "goal_mode": True,
        "plan_mode": False,
        "plan_reasoning_effort": "high",
        "no_edits": True,
        "prompt_vars": {"Target": "Target"},
        "prompt": "Inspect %Target%.",
        "requires_interactive": False,
        "custom_codex_args": ["--search"],
        "notes": "Visible note.",
    }
    assert launching_module.ActionLaunchConfig.__slots__ == ("_is_frozen", "language", "name", "selector", *validation_module.ACTION_FIELDS)


def test_prepare_launch_keeps_configured_and_rendered_prompts_separate(tmp_path, complete, file_data, write_file, load_catalog):
    catalog = make_catalog(
        tmp_path,
        complete,
        file_data,
        write_file,
        load_catalog,
        no_edits=True,
        prompt_vars={"Target": "Target"},
        prompt="Inspect %Target%.",
        notes="Separate.",
    )
    spec = catalog.prepare_launch("test[python]", {"Target": "src/"}, qualification="Report findings.")
    payload = spec.to_dict()
    assert payload["action"]["prompt"] == "Inspect %Target%."
    assert payload["rendered_prompt"] == "No edits. Inspect src/. BUT: Report findings."
    assert payload["qualification"] == "Report findings."
    assert payload["action"]["notes"] == "Separate."


def test_builtin_help_has_normal_launch_configuration_and_question_rendering(tmp_path, load_catalog):
    catalog = load_catalog(tmp_path)
    config = catalog.launch_config("help[agnostic]")
    assert config.selector == "help[agnostic]"
    assert config.model == "default"
    assert config.reasoning_effort == "medium"
    assert config.no_edits is True
    assert config.prompt_vars == {}
    assert config.requires_interactive is False

    question = "How do repository overrides work?"
    spec = catalog.prepare_launch("help[agnostic]", {}, qualification="  BUT: " + question + "  ")
    assert spec.config.selector == "help[agnostic]"
    assert spec.qualification == question
    assert spec.rendered_prompt.startswith("No edits. Read the following installed Perform guides")
    assert spec.rendered_prompt.endswith("\n\nUser question: " + question)
    assert "BUT: " not in spec.rendered_prompt

    with pytest.raises(diagnostics_module.PerformRequestError) as extra_variable:
        catalog.render("help[agnostic]", {"Question": question})
    assert extra_variable.value.status == "extra_variables"

    with pytest.raises(diagnostics_module.PerformRequestError) as invalid_question:
        catalog.render("help[agnostic]", {}, qualification="first\nsecond")
    assert invalid_question.value.status == "invalid_qualification"


def test_launch_config_does_not_construct_a_base_prompt(monkeypatch, tmp_path, complete, file_data, write_file, load_catalog):
    catalog = make_catalog(tmp_path, complete, file_data, write_file, load_catalog)

    def unexpected_prompt(*_args, **_kwargs):
        raise AssertionError("launch_config must not construct a base prompt")

    monkeypatch.setattr(rendering_module, "build_base_prompt", unexpected_prompt)
    assert catalog.launch_config("test[python]").selector == "test[python]"


@pytest.mark.parametrize(
    ("requires_interactive", "non_interactive", "expected_non_interactive"),
    [
        (False, False, False),
        (False, True, True),
        (True, False, False),
    ],
)
def test_interactivity_requirement_and_override_select_frontend(tmp_path, complete, file_data, write_file, load_catalog, requires_interactive, non_interactive, expected_non_interactive):
    catalog = make_catalog(tmp_path, complete, file_data, write_file, load_catalog, requires_interactive=requires_interactive)
    invocation = launching_module.build_codex_invocation(catalog.prepare_launch("test[python]", {}), overrides=launching_module.LaunchOverrides(non_interactive=non_interactive))
    assert invocation.argv[0] == "codex"
    assert ("exec" in invocation.argv) is expected_non_interactive
    assert invocation.argv[-2:] == ("--", "Perform the test action.")
    assert invocation.non_interactive is expected_non_interactive
    assert not hasattr(invocation, "interactive")
    assert invocation.effective_settings["non_interactive"] is expected_non_interactive
    assert invocation.mode == "default"


def test_required_interactivity_rejects_noninteractive_override(tmp_path, complete, file_data, write_file, load_catalog):
    catalog = make_catalog(tmp_path, complete, file_data, write_file, load_catalog, requires_interactive=True)
    with pytest.raises(diagnostics_module.PerformRequestError) as error:
        launching_module.build_codex_invocation(catalog.prepare_launch("test[python]", {}), overrides=launching_module.LaunchOverrides(non_interactive=True))
    assert error.value.status == "interactive_required"
    assert "test[python]" in error.value.message


def test_invocation_builder_trusts_validated_value_objects(monkeypatch, tmp_path, complete, file_data, write_file, load_catalog):
    catalog = make_catalog(tmp_path, complete, file_data, write_file, load_catalog)
    spec = catalog.prepare_launch("test[python]", {})
    overrides = launching_module.LaunchOverrides(extra_codex_args=["--no-alt-screen"])

    def unexpected_validation(_value):
        raise AssertionError("generic argument validation must not be repeated")

    monkeypatch.setattr(validation_module, "validate_action_codex_args", unexpected_validation)
    monkeypatch.setattr(validation_module, "validate_extra_codex_args", unexpected_validation)
    invocation = launching_module.build_codex_invocation(spec, overrides=overrides)
    assert "--no-alt-screen" in invocation.argv


def test_invocation_places_global_action_args_before_structured_settings_and_exec_args(tmp_path, complete, file_data, write_file, load_catalog):
    catalog = make_catalog(
        tmp_path,
        complete,
        file_data,
        write_file,
        load_catalog,
        model="configured-model",
        reasoning_effort="medium",
        plan_reasoning_effort="medium",
        requires_interactive=False,
        custom_codex_args=["--search"],
    )
    overrides = launching_module.LaunchOverrides(
        model="override-model",
        reasoning_effort="high",
        plan_reasoning_effort="xhigh",
        non_interactive=True,
        extra_codex_args=["--color=never"],
        cwd="/work",
        json_output=True,
    )
    invocation = launching_module.build_codex_invocation(catalog.prepare_launch("test[python]", {}), codex_executable="/bin/codex", overrides=overrides)
    assert invocation.argv == (
        "/bin/codex",
        "--search",
        "--cd",
        "/work",
        "--model",
        "override-model",
        "-c",
        'model_reasoning_effort="high"',
        "-c",
        'plan_mode_reasoning_effort="xhigh"',
        "exec",
        "--color=never",
        "--json",
        "--",
        "Perform the test action.",
    )
    assert invocation.effective_settings == {
        "model": "override-model",
        "reasoning_effort": "high",
        "plan_reasoning_effort": "xhigh",
        "non_interactive": True,
        "custom_codex_args": ("--search",),
        "extra_codex_args": ("--color=never",),
        "cwd": "/work",
        "json_output": True,
    }


def test_interactive_caller_args_precede_structured_settings(tmp_path, complete, file_data, write_file, load_catalog):
    catalog = make_catalog(tmp_path, complete, file_data, write_file, load_catalog, custom_codex_args=["--search"])
    invocation = launching_module.build_codex_invocation(
        catalog.prepare_launch("test[python]", {}),
        overrides=launching_module.LaunchOverrides(extra_codex_args=("--no-alt-screen",), cwd="/work"),
    )
    assert invocation.argv[:5] == ("codex", "--search", "--no-alt-screen", "--cd", "/work")
    assert "exec" not in invocation.argv


def test_default_model_is_omitted_and_structured_json_is_added_once(tmp_path, complete, file_data, write_file, load_catalog):
    catalog = make_catalog(tmp_path, complete, file_data, write_file, load_catalog, requires_interactive=False)
    invocation = launching_module.build_codex_invocation(
        catalog.prepare_launch("test[python]", {}),
        overrides=launching_module.LaunchOverrides(json_output=True),
    )
    assert "--model" not in invocation.argv
    assert invocation.argv.count("--json") == 1


def test_json_implicitly_selects_noninteractive(tmp_path, complete, file_data, write_file, load_catalog):
    catalog = make_catalog(tmp_path, complete, file_data, write_file, load_catalog, requires_interactive=False)
    invocation = launching_module.build_codex_invocation(catalog.prepare_launch("test[python]", {}), overrides=launching_module.LaunchOverrides(json_output=True))
    assert invocation.non_interactive is True
    assert invocation.effective_settings["non_interactive"] is True
    assert "exec" in invocation.argv
    assert "--json" in invocation.argv


def test_json_rejects_required_interactive_action(tmp_path, complete, file_data, write_file, load_catalog):
    required = make_catalog(tmp_path, complete, file_data, write_file, load_catalog, requires_interactive=True)
    with pytest.raises(diagnostics_module.PerformRequestError) as implicit:
        launching_module.build_codex_invocation(required.prepare_launch("test[python]", {}), overrides=launching_module.LaunchOverrides(json_output=True))
    assert implicit.value.status == "interactive_required"


@pytest.mark.parametrize("non_interactive", [False, True])
def test_plan_mode_reports_cli_activation_is_unavailable(tmp_path, complete, file_data, write_file, load_catalog, non_interactive):
    catalog = make_catalog(tmp_path, complete, file_data, write_file, load_catalog, plan_mode=True, reasoning_effort="medium", plan_reasoning_effort="high", no_edits=True, requires_interactive=True)
    spec = catalog.prepare_launch("test[python]", {})
    with pytest.raises(diagnostics_module.PerformRequestError) as error:
        launching_module.build_codex_invocation(spec, overrides=launching_module.LaunchOverrides(non_interactive=non_interactive))
    assert error.value.status == "plan_mode_unavailable"
    assert "$toolkit:perform" in error.value.message


@pytest.mark.parametrize("non_interactive", [False, True])
def test_goal_mode_always_uses_exact_objective_bootstrap(tmp_path, complete, file_data, write_file, load_catalog, non_interactive):
    objective = 'Use quotes " and Unicode \u03bb.\nSecond line.'
    catalog = make_catalog(tmp_path, complete, file_data, write_file, load_catalog, goal_mode=True, requires_interactive=False, prompt=objective)
    invocation = launching_module.build_codex_invocation(catalog.prepare_launch("test[python]", {}), overrides=launching_module.LaunchOverrides(non_interactive=non_interactive))
    envelope = json.loads(invocation.submitted_prompt.rsplit("\n\n", 1)[1])
    assert invocation.mode == "goal"
    assert invocation.non_interactive is non_interactive
    assert invocation.objective == objective
    assert envelope == {"objective": objective}
    assert not invocation.submitted_prompt.startswith("/goal")
    assert invocation.argv[-2:] == ("--", invocation.submitted_prompt)


def test_goal_interactivity_can_be_overridden_without_changing_bootstrap(tmp_path, complete, file_data, write_file, load_catalog):
    catalog = make_catalog(tmp_path, complete, file_data, write_file, load_catalog, goal_mode=True, requires_interactive=False)
    spec = catalog.prepare_launch("test[python]", {})
    interactive = launching_module.build_codex_invocation(spec)
    noninteractive = launching_module.build_codex_invocation(spec, overrides=launching_module.LaunchOverrides(non_interactive=True))
    assert interactive.submitted_prompt == noninteractive.submitted_prompt
    assert interactive.objective == noninteractive.objective
    assert "exec" not in interactive.argv
    assert "exec" in noninteractive.argv


@pytest.mark.parametrize("argument", ["--ephemeral", "--disable=goals", "--config=features.goals=false", "--config=features={goals=false}"])
def test_goal_mode_rejects_caller_arguments_that_can_disable_goals(tmp_path, complete, file_data, write_file, load_catalog, argument):
    catalog = make_catalog(tmp_path, complete, file_data, write_file, load_catalog, goal_mode=True, requires_interactive=False)
    spec = catalog.prepare_launch("test[python]", {})
    with pytest.raises(diagnostics_module.PerformRequestError) as error:
        launching_module.build_codex_invocation(spec, overrides=launching_module.LaunchOverrides(extra_codex_args=[argument]))
    assert error.value.status == "conflicting_extra_codex_args"


def test_goal_mode_allows_goal_enablement_and_unrelated_arguments(tmp_path, complete, file_data, write_file, load_catalog):
    catalog = make_catalog(tmp_path, complete, file_data, write_file, load_catalog, goal_mode=True, requires_interactive=False)
    overrides = launching_module.LaunchOverrides(extra_codex_args=["--enable=goals", "--config=unrelated=true"])
    invocation = launching_module.build_codex_invocation(catalog.prepare_launch("test[python]", {}), overrides=overrides)
    assert "--enable=goals" in invocation.argv
    assert "--config=unrelated=true" in invocation.argv


def test_interactive_mode_rejects_caller_ephemeral(tmp_path, complete, file_data, write_file, load_catalog):
    catalog = make_catalog(tmp_path, complete, file_data, write_file, load_catalog, requires_interactive=False)
    spec = catalog.prepare_launch("test[python]", {})
    with pytest.raises(diagnostics_module.PerformRequestError) as error:
        launching_module.build_codex_invocation(spec, overrides=launching_module.LaunchOverrides(extra_codex_args=["--ephemeral"]))
    assert error.value.status == "invalid_extra_codex_args"


@pytest.mark.parametrize(
    ("kwargs", "status"),
    [
        ({"model": "bad model"}, "invalid_model"),
        ({"reasoning_effort": "High"}, "invalid_effort"),
        ({"plan_reasoning_effort": "High"}, "invalid_effort"),
        ({"non_interactive": "yes"}, "invalid_interactivity"),
        ({"extra_codex_args": ["--model", "bad"]}, "conflicting_extra_codex_args"),
        ({"extra_codex_args": ["--cd", "/tmp"]}, "conflicting_extra_codex_args"),
        ({"extra_codex_args": "--help"}, "invalid_extra_codex_args"),
        ({"extra_codex_args": {"--help": True}}, "invalid_extra_codex_args"),
        ({"extra_codex_args": 7}, "invalid_extra_codex_args"),
        ({"extra_codex_args": ["--"]}, "invalid_extra_codex_args"),
        ({"extra_codex_args": ["--help"]}, "invalid_extra_codex_args"),
        ({"extra_codex_args": ["--help=x"]}, "invalid_extra_codex_args"),
        ({"extra_codex_args": ["--version"]}, "invalid_extra_codex_args"),
        ({"extra_codex_args": ["--version=x"]}, "invalid_extra_codex_args"),
        ({"extra_codex_args": ["--json"]}, "conflicting_extra_codex_args"),
        ({"extra_codex_args": ["--json=true"]}, "conflicting_extra_codex_args"),
        ({"extra_codex_args": ["--verbose"]}, "conflicting_extra_codex_args"),
        ({"extra_codex_args": ["--verbose=true"]}, "conflicting_extra_codex_args"),
        ({"extra_codex_args": ["resume"]}, "invalid_extra_codex_args"),
        ({"extra_codex_args": ["--color", "never"]}, "invalid_extra_codex_args"),
        ({"extra_codex_args": ["-h"]}, "invalid_extra_codex_args"),
        ({"extra_codex_args": ["-V"]}, "invalid_extra_codex_args"),
        ({"extra_codex_args": ["-o=result.txt"]}, "invalid_extra_codex_args"),
        ({"extra_codex_args": ["--future=\ud800"]}, "invalid_extra_codex_args"),
    ],
)
def test_launch_overrides_validate_structured_policy(kwargs, status):
    with pytest.raises(diagnostics_module.PerformRequestError) as error:
        launching_module.LaunchOverrides(**kwargs)
    assert error.value.status == status


@pytest.mark.parametrize("keyword", ["interactive", "prefer_interactive"])
def test_launch_overrides_reject_removed_interactivity_keywords(keyword):
    with pytest.raises(TypeError):
        launching_module.LaunchOverrides(**{keyword: True})


def test_launch_overrides_preserve_posix_surrogateescape_arguments():
    with pytest.raises(diagnostics_module.PerformRequestError) as error:
        launching_module.LaunchOverrides(extra_codex_args=["--future=\udc00"])
    assert error.value.status == "invalid_extra_codex_args"
    overrides = launching_module.LaunchOverrides(extra_codex_args=["--future=path\udc80"])
    assert overrides.extra_codex_args == ("--future=path\udc80",)


def test_option_and_subcommand_shaped_prompts_remain_literal(tmp_path, complete, file_data, write_file, load_catalog):
    for index, prompt in enumerate(("--help", "resume", "-leading")):
        catalog = make_catalog(tmp_path / str(index), complete, file_data, write_file, load_catalog, requires_interactive=False, prompt=prompt)
        invocation = launching_module.build_codex_invocation(catalog.prepare_launch("test[python]", {}))
        assert invocation.argv[-2:] == ("--", prompt)


def test_launcher_value_objects_and_argument_collections_are_immutable(tmp_path, complete, file_data, write_file, load_catalog):
    catalog = make_catalog(tmp_path, complete, file_data, write_file, load_catalog, requires_interactive=False, custom_codex_args=["--search"])
    spec = catalog.prepare_launch("test[python]", {})
    overrides = launching_module.LaunchOverrides(extra_codex_args=["--color=never"])
    invocation = launching_module.build_codex_invocation(spec, overrides=overrides)
    assert spec.config.custom_codex_args == ("--search",)
    assert overrides.extra_codex_args == ("--color=never",)
    assert isinstance(invocation.argv, tuple)
    with pytest.raises(TypeError):
        spec.config.prompt_vars["Changed"] = "changed"
    with pytest.raises(TypeError):
        invocation.effective_settings["model"] = "changed"
    with pytest.raises(AttributeError):
        spec.config.custom_codex_args = ("--changed",)
    with pytest.raises(AttributeError):
        overrides.extra_codex_args = ("--changed",)
    with pytest.raises(AttributeError):
        invocation.argv = ("codex",)
    for value, attribute in ((spec.config, "model"), (spec, "rendered_prompt"), (overrides, "model"), (invocation, "argv")):
        with pytest.raises(AttributeError):
            delattr(value, attribute)
    for value in (spec.config, spec, overrides, invocation):
        with pytest.raises(AttributeError):
            delattr(value, "_is_frozen")


def test_launch_overrides_to_dict_is_complete_and_isolated():
    overrides = launching_module.LaunchOverrides(model="gpt-5", non_interactive=True, extra_codex_args=["--color=never"], cwd="/work", json_output=True)
    payload = overrides.to_dict()
    assert payload == {
        "model": "gpt-5",
        "reasoning_effort": None,
        "plan_reasoning_effort": None,
        "non_interactive": True,
        "extra_codex_args": ["--color=never"],
        "cwd": "/work",
        "json_output": True,
    }
    payload["extra_codex_args"].append("--changed")
    assert overrides.extra_codex_args == ("--color=never",)


def test_invocation_to_dict_is_complete_and_isolated(tmp_path, complete, file_data, write_file, load_catalog):
    catalog = make_catalog(tmp_path, complete, file_data, write_file, load_catalog, requires_interactive=False)
    invocation = launching_module.build_codex_invocation(catalog.prepare_launch("test[python]", {}))
    payload = invocation.to_dict()
    payload["argv"].append("--mutated")
    payload["effective_settings"]["extra_codex_args"].append("--mutated")
    assert "--mutated" not in invocation.argv
    assert "--mutated" not in invocation.effective_settings["extra_codex_args"]
    assert set(payload) == {"launch_spec", "effective_settings", "mode", "non_interactive", "objective", "submitted_prompt", "argv"}
    assert list(payload["launch_spec"]["action"]) == list(validation_module.ACTION_FIELDS)
