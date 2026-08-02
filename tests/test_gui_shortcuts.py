"""Browser-independent checks for focus-safe simulator shortcuts."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest


_SHORTCUTS = Path(__file__).parents[1] / "gui" / "assets" / "shortcuts.js"


def run_shortcut_probe() -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the shortcut module probe")

    script = f"""
        import {{
            installSimulatorShortcuts,
            isEditingTarget,
            shortcutAction,
        }} from {json.dumps(_SHORTCUTS.as_uri())};

        const event = (changes = {{}}) => ({{
            key: 'Enter',
            ctrlKey: true,
            metaKey: false,
            shiftKey: false,
            altKey: false,
            defaultPrevented: false,
            repeat: false,
            isComposing: false,
            keyCode: 13,
            ...changes,
        }});

        let handler;
        let clicks = 0;
        let prevented = 0;
        const control = {{
            disabled: false,
            getAttribute: () => null,
            click: () => clicks++,
        }};
        const root = {{
            addEventListener: (_name, callback) => handler = callback,
            removeEventListener: () => {{}},
            getElementById: () => control,
        }};
        installSimulatorShortcuts(root);
        handler(event({{
            target: {{closest: () => null}},
            preventDefault: () => prevented++,
        }}));
        handler(event({{
            target: {{closest: () => true}},
            preventDefault: () => prevented++,
        }}));

        const result = {{
            step: shortcutAction(event()),
            run: shortcutAction(event({{shiftKey: true}})),
            reset: shortcutAction(event({{key: 'r', altKey: true}})),
            repeat: shortcutAction(event({{repeat: true}})),
            composing: shortcutAction(event({{isComposing: true}})),
            editor: isEditingTarget({{closest: () => true}}),
            canvas: isEditingTarget({{closest: () => null}}),
            clicks,
            prevented,
        }};
        process.stdout.write(JSON.stringify(result));
    """
    completed = subprocess.run(
        [
            node,
            "--experimental-default-type=module",
            "--input-type=module",
            "-e",
            script,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_shortcut_mapping_and_editor_guard() -> None:
    result = run_shortcut_probe()

    assert result == {
        "step": "sim-step",
        "run": "sim-run-toggle",
        "reset": "sim-reset",
        "repeat": None,
        "composing": None,
        "editor": True,
        "canvas": False,
        "clicks": 1,
        "prevented": 1,
    }
