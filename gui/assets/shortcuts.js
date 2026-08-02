const EDITING_SELECTOR = [
    '.nicegui-codemirror',
    '.cm-editor',
    '.cm-content',
    '.xterm',
    'input',
    'textarea',
    'select',
    '[contenteditable="true"]',
    '[role="textbox"]',
].join(',');

export function isEditingTarget(target) {
    return Boolean(target && typeof target.closest === 'function' && target.closest(EDITING_SELECTOR));
}

export function shortcutAction(event) {
    if (
        event.defaultPrevented
        || event.repeat
        || event.isComposing
        || event.keyCode === 229
        || (!event.ctrlKey && !event.metaKey)
    ) {
        return null;
    }

    const key = String(event.key || '').toLowerCase();
    if (key === 'enter' && !event.altKey) {
        return event.shiftKey ? 'sim-run-toggle' : 'sim-step';
    }
    if (key === 'r' && event.altKey && !event.shiftKey) {
        return 'sim-reset';
    }
    return null;
}

export function installSimulatorShortcuts(root = document) {
    const handler = (event) => {
        if (isEditingTarget(event.target)) {
            return;
        }
        const action = shortcutAction(event);
        if (!action) {
            return;
        }
        const control = root.getElementById(action);
        if (!control || control.disabled || control.getAttribute('aria-disabled') === 'true') {
            return;
        }
        event.preventDefault();
        control.click();
    };

    root.addEventListener('keydown', handler, true);
    return () => root.removeEventListener('keydown', handler, true);
}
