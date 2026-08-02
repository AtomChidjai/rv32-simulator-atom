let renderIndex = 0;
let wavedromPromise;

function currentWaveDrom() {
    return window.wavedrom || window.WaveDrom;
}

function loadWaveDrom() {
    const current = currentWaveDrom();
    if (current?.renderWaveElement) {
        return Promise.resolve(current);
    }
    wavedromPromise ??= import('./vendor/wavedrom.min.js').then(() => {
        const loaded = currentWaveDrom();
        if (!loaded?.renderWaveElement) {
            throw new Error('WaveDrom browser API did not initialize');
        }
        return loaded;
    });
    return wavedromPromise;
}

function showError(target, message) {
    target.replaceChildren();
    const fallback = document.createElement('div');
    fallback.className = 'decode-bitfield-error';
    fallback.textContent = message;
    target.append(fallback);
}

export function clearDecodeBitfield(targetId) {
    document.getElementById(targetId)?.replaceChildren();
}

export async function renderDecodeBitfield(targetId, source) {
    const target = document.getElementById(targetId);
    if (!target) return;

    const index = renderIndex++;
    target.dataset.decodeRender = String(index);

    try {
        const WaveDrom = await loadWaveDrom();
        if (!target.isConnected || target.dataset.decodeRender !== String(index)) return;

        const output = document.createElement('div');
        target.replaceChildren(output);
        WaveDrom.renderWaveElement(
            index,
            source,
            output,
            WaveDrom.waveSkin,
            false,
        );
        const svg = output.querySelector('svg');
        if (svg) {
            svg.setAttribute('role', 'img');
            svg.setAttribute('aria-label', source.ariaLabel || 'Instruction encoding');
        }
    } catch (error) {
        console.error('Decode bitfield rendering failed:', error);
        if (target.isConnected && target.dataset.decodeRender === String(index)) {
            showError(target, 'Could not render this instruction encoding.');
        }
    }
}

window.RV32IDecodeBitfield = {
    clear: clearDecodeBitfield,
    render: renderDecodeBitfield,
};
